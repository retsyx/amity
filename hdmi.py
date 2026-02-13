# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

from aconfig import config
import pprint, time
import cec
from cec import Device, DeviceType, Key, Message, PowerStatus

config.default('hdmi.quirks', {})
# This address is a guess. We don't want to read EDID data from the TV, or provide EDID downstream.
config.default('hdmi.front.physical_address', 0x1000)

def pretty_physical_address(address):
    return '.'.join(list(f'{address:04X}'))

no_activity_descriptor = { 'name': 'No Activity',
                'display': None,
                'source': None,
                'audio': None,
                }

class Switch(object):
    def __init__(self, d):
        self.device = d['device']
        self.input = d['input']

    def __repr__(self):
        d = { 'device': self.device,
              'input': self.input
            }
        return pprint.pformat(d)

class Activity(object):
    def __init__(self, d=no_activity_descriptor):
        self.name = d['name']
        self.display = d['display']
        self.source = d['source']
        self.audio = d['audio']
        switch_d = d.get('switch')
        if switch_d is not None:
            self.switch = Switch(switch_d)
        else:
            self.switch = None

    def devices(self):
        ds = [self.display, self.source, self.audio]
        if self.switch is not None:
            ds.append(self.switch.device)
        return ds

    def __repr__(self):
        d = {
            'name': self.name,
            'display': self.display,
            'source': self.source,
            'audio': self.audio,
        }
        return pprint.pformat(d)

no_activity = Activity()

class Quirk(object):
    def __init__(self, d):
        self.data = [int(c, 16) for c in d['data'].split(':')]

    def __repr__(self):
        return ':'.join(f'{c:02X}' for c in self.data)

class Device(object):
    quirks = None
    def __init__(self, dev):
        if Device.quirks is None:
            Device.quirks = config['hdmi.quirks']
        self.dev = dev

    @property
    def osd_name(self):
        return self.dev.osd_name

    async def get_osd_name(self):
        await self.dev.get_osd_name()

    @property
    def address(self):
        return self.dev.address

    @property
    def physical_address(self):
        return self.dev.physical_address

    def lookup_quirk(self, op):
        v = Device.quirks.get(f'{self.dev.vendor_id:06X}')
        if v is None: return None
        q = v.get(op)
        if q is None: return None
        return Quirk(q)

    async def be_quirky(self, op):
        quirk = self.lookup_quirk(op)
        if not quirk:
            return False
        log.info(f'Using quirk {quirk} for {op}')
        await self.dev.transmit(quirk.data)
        if quirk.data[0] == Message.KEY_PRESS:
            await self.dev.key_release()
        return True

    async def power_on(self):
        if await self.be_quirky('power_on'):
            return
        await self.dev.power_on()

    async def power_off(self):
        if await self.be_quirky('power_off'):
            return
        await self.standby()

    async def standby(self):
        await self.dev.standby()

    async def press_key(self, key, repeat=None):
        if repeat is None: repeat = False
        await self.dev.key_press(key)
        if not repeat:
            await self.release_key()

    async def release_key(self):
        await self.dev.key_release()

    async def set_stream_path(self):
        await self.dev.set_stream_path()

    def handle_report_physical_address(self, msg):
        self.dev.parse_report_physical_address_message(msg)

    async def set_input(self, index):
        # Press the SET INPUT key with the input index
        await self.dev.transmit(bytes([Message.KEY_PRESS, Key.SET_INPUT, index]))
        # And then release the key
        await self.dev.key_release()

class ControllerImpl(object):
    def __init__(self, front_dev, back_dev, osd_name, loop, activities):
        self.inited = False
        self.devices = {}
        self.loop = loop
        self.last_device_rescan_time = 0
        self.rescan_wait_time_sec = 2 * 60
        self.activities = activities
        self.current_activity = no_activity
        self.front_adapter = cec.Adapter(devname=front_dev,
                                         loop=loop,
                                         listen_callback_coro=self.front_listen,
                                         device_types=DeviceType.PLAYBACK,
                                         osd_name = osd_name,
                                         physical_address_override=config['hdmi.front.physical_address'])
        self.back_adapter = cec.Adapter(devname=back_dev,
                                        loop=loop,
                                        listen_callback_coro=self.back_listen,
                                        device_types=DeviceType.TV,
                                        osd_name = osd_name)

    def set_inited(self):
        self.inited = True

    async def handle_front_give_device_power_status(self, adapter, msg):
        log.info('Power status requested')
        msg = Message(adapter.address, msg.src)
        if self.current_activity == no_activity:
            status = PowerStatus.STANDBY
        else:
            status = PowerStatus.ON
        log.info(f'Responding with power status {status.name}')
        msg.set_data((Message.REPORT_POWER_STATUS, status))
        await adapter.transmit(msg)

    async def handle_back_give_device_power_status(self, adapter, msg):
        log.info('Power status requested')
        device_address = msg.src
        msg = Message(adapter.address, msg.src)
        if self.current_activity == no_activity:
            status = PowerStatus.STANDBY
        else:
            ca = self.current_activity
            source_device = await self.get_device(ca.source)
            status = PowerStatus.STANDBY
            if source_device is not None:
                if source_device.address == device_address:
                    status = PowerStatus.ON
        log.info(f'Responding with power status {status.name}')
        msg.set_data((Message.REPORT_POWER_STATUS, status))
        await adapter.transmit(msg)

    async def front_listen(self, msg):
        # LG TVs love spamming this message every 10 seconds.
        if msg.op == Message.VENDOR_ID and msg.dst == cec.BROADCAST_ADDRESS:
            return
        log.info(f'Front RX {msg}')
        if not self.inited:
            return
        match msg.op:
            case Message.GIVE_DEVICE_POWER_STATUS:
                await self.handle_front_give_device_power_status(self.front_adapter, msg)

    async def handle_device_report_physical_address(self, adapter, msg):
        new_device = True

        # Update an existing device if any...
        for device in self.devices.values():
            if msg.src == device.address:
                device.handle_report_physical_address(msg)
                new_device = False
                break

        if new_device:
            # This is a new device!
            dev = await cec.Device(adapter, msg.src)
            device = Device(dev)
            self.devices[dev.osd_name] = device
            log.info(f'Adding new found device {dev.osd_name}')

        pa = pretty_physical_address(device.physical_address)
        log.info(f'{device.osd_name} updated physical address to {pa}')
        if not device.osd_name:
            await device.get_osd_name()
        if device.osd_name == self.current_activity.source:
            log.info(f'Setting stream path to updated address {pa}')
            await device.set_stream_path()

        # The protocol is flaky, and there may be an old device that once claimed this physical
        # address, and is now likely dormant. If there is, remove it from our list of devices.
        for other_osd_name, other_device in list(self.devices.items()):
            if other_device is device:
                continue
            if other_device.physical_address == device.physical_address:
                log.info(f'Removing {other_osd_name} that previously had address {pa}')
                self.devices.pop(other_osd_name)

    async def back_listen(self, msg):
        log.info(f'Back RX {msg}')
        if not self.inited:
            return
        match msg.op:
            case Message.REPORT_PHYSICAL_ADDR:
                await self.handle_device_report_physical_address(self.back_adapter, msg)
            case Message.IMAGE_VIEW_ON:
                await self.stop_source_thief(msg)
            case Message.ACTIVE_SOURCE:
                await self.stop_source_thief(msg)
            case Message.GIVE_DEVICE_POWER_STATUS:
                await self.handle_back_give_device_power_status(self.back_adapter, msg)

    async def stop_source_thief(self, msg):
        log.info(f'Device address {msg.src} wants source')
        if self.current_activity == no_activity:
            log.info('No current activity, so forcing standby')
            await self.force_standby()
            return

        fix = False
        ca = self.current_activity
        if ca.source is None:
            log.info('Activity has no defined source so device must be a thief')
            fix = True
        else:
            source_device = await self.get_device(ca.source)
            if source_device is not None:
                if source_device.address != msg.src:
                    fix = True
                else:
                    log.info(f'Device is not a thief')
            else:
                log.info(f"Can't find source device for current activity so will let source thief win")

        if fix:
            log.info('Putting thief in standby')
            msg = Message(self.back_adapter.address, msg.src)
            msg.set_data([Message.STANDBY])
            await self.back_adapter.transmit(msg)
            log.info('Taking back source')
            await self.set_activity_input(ca)

    async def scan_devices(self):
        log.info('Scanning devices...')
        devices = {}
        for adapter in (self.back_adapter, self.front_adapter):
            cec_devices = await adapter.list_devices()
            for dev in cec_devices:
                devices[dev.osd_name] = Device(dev)
        log.info('Scanned devices:')
        log.info(f'{"Name":15s} Address Physical Address')
        for name, device in devices.items():
            log.info(f'{name:15s} {device.address:6X}   {pretty_physical_address(device.physical_address):10}')
        return devices

    async def rescan_devices(self):
        now = time.time()
        delta = now - self.last_device_rescan_time
        if delta < self.rescan_wait_time_sec:
            time_left = self.rescan_wait_time_sec - delta
            log.info(f'Device rescan is too frequent, {time_left:0.2f}s until allowed')
            return
        self.last_device_rescan_time = now
        self.devices = await self.scan_devices()

    async def get_device(self, name, op=None):
        if name is None:
            return None
        device = self.devices.get(name)
        if device is None:
            log.info(f'Failed to find device {name}')
            await self.rescan_devices()
            device = self.devices.get(name)
            if device is None:
                if op is not None:
                    log.info(f'Device {name} not found for {op}')
                else:
                    log.info(f'Device {name} not found')
        return device

    async def set_activity(self, index):
        if index < -1 or index >= len(self.activities):
            log.info(f'Activity index {index} is out of bounds')
            return False
        ca = self.current_activity
        if index >= 0:
            na = self.activities[index]
            is_power_off = False
        else:
            na = no_activity
            is_power_off = True
        log.info(f'Setting activity {na.name} from activity {ca.name}')
        if na is ca:
            await self.fix_current_activity()
            return True
        current_devices = ca.devices()
        new_devices = na.devices()
        for current_device in current_devices:
            if current_device not in new_devices:
                device = await self.get_device(current_device, 'STANDBY')
                if device is None:
                    continue
                log.info(f'Device {current_device} STANDBY')
                if is_power_off:
                    await device.power_off()
                else:
                    await device.standby()
        for new_device in new_devices:
            if new_device not in current_devices:
                device = await self.get_device(new_device, 'POWER ON')
                if device is None:
                    continue
                log.info(f'Device {new_device} POWER ON')
                await device.power_on()
        await self.set_activity_input(na)
        self.current_activity = na
        return True

    async def fix_current_activity(self):
        ca = self.current_activity
        log.info(f'Fixing activity {ca.name}')
        current_devices = ca.devices()
        for current_device in current_devices:
            device = await self.get_device(current_device, 'POWER ON')
            if device is None:
                continue
            log.info(f'Device {current_device} POWER ON')
            await device.power_on()
        await self.set_activity_input(ca)

    async def set_activity_input(self, activity):
        # Setting the stream path is the better way...
        device = await self.get_device(activity.source, 'SET STREAM PATH')
        if device is not None:
            log.info(f'Setting stream path to {pretty_physical_address(device.physical_address)}')
            await device.set_stream_path()
            return
        # However, some devices aren't particularly HDMI-CEC compliant, so, as a fallback, the user
        # can optionally configure the switch device (receiver) on which we should set the input
        # instead (assuming the receiver supports it...)
        if activity.switch:
            device = await self.get_device(activity.switch.device, 'SET INPUT')
            if device is None:
                return
            await device.set_input(activity.switch.input)
        # Also, remind the TV that we are the source
        await self.front_adapter.active_source()

    async def standby(self):
        await self.set_activity(-1)

    async def force_standby(self):
        await self.front_adapter.broadcast().standby()
        await self.back_adapter.broadcast().standby()

    async def press_key(self, key, repeat=None):
        if key in (Key.VOLUME_UP, Key.VOLUME_DOWN, Key.TOGGLE_MUTE):
            device_name = self.current_activity.audio
        else:
            device_name = self.current_activity.source
        device = await self.get_device(device_name, 'PRESS KEY')
        if device is None:
            return False
        log.info(f'Device {device_name} PRESS KEY 0x{key:02X}')
        await device.press_key(key, repeat)
        return True

    async def release_key(self):
        cs = self.current_activity.source
        device = await self.get_device(cs, 'RELEASE KEY')
        if device is None:
            return
        log.info(f'Device {cs} RELEASE KEY')
        await device.release_key()

async def Controller(front_dev, back_dev, osd_name, loop, activities):
    ctrl = ControllerImpl(front_dev, back_dev, osd_name, loop, activities)
    await ctrl.rescan_devices() # sets self.devices dict()
    ctrl.set_inited()
    return ctrl
