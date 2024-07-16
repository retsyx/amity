# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio, pprint, yaml, time
import cec
from cec import Device, DeviceType, Key, Message, PowerStatus

def isiterable(o):
    try:
        iter(o)
        return True
    except:
        return False

def pretty_physical_address(address):
    return '.'.join(list(f'{address:04X}'))

no_activity_descriptor = { 'name': 'No Activity',
                'display': None,
                'source': None,
                'audio': None,
                }

class Activity(object):
    def __init__(self, d=no_activity_descriptor):
        self.name = d['name']
        self.display = d['display']
        self.source = d['source']
        self.audio = d['audio']

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
            with open('quirks.yaml', 'r') as file:
                Device.quirks = yaml.safe_load(file)
        self.dev = dev

    @property
    def osd_name(self):
        return self.dev.osd_name

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

    def be_quirky(self, op):
        return False
        quirk = self.lookup_quirk(op)
        if not quirk:
            return False
        log.info(f'Using quirk {quirk} for {op}')
        self.dev.transmit(quirk.data)
        if quirk.data[0] == Message.KEY_PRESS:
            self.dev.key_release()
        return True

    def power_on(self):
        if self.be_quirky('power_on'):
            return
        self.dev.power_on()

    def power_off(self):
        if self.be_quirky('power_off'):
            return
        self.standby()

    def standby(self):
        self.dev.standby()

    def press_key(self, key, repeat=None):
        if repeat is None: repeat = False
        self.dev.key_press(key)
        if not repeat:
            self.release_key()

    def release_key(self):
        self.dev.key_release()

    def set_stream_path(self):
        # Some devices will change their physical address after being powered on?
        #self.dev.get_physical_address_and_primary_device_type()
        self.dev.set_stream_path()

    def handle_report_physical_address(self, msg):
        self.dev.parse_report_physical_address_message(msg)

class Controller(object):
    def __init__(self, front_dev, back_dev, osd_name, loop, activities):
        self.front_adapter = cec.Adapter(devname=front_dev,
                                         device_types=DeviceType.PLAYBACK,
                                         osd_name = osd_name)
        self.back_adapter = cec.Adapter(devname=back_dev,
                                         device_types=DeviceType.TV,
                                         osd_name = osd_name)
        self.loop = loop
        self.last_device_rescan_time = 0
        self.rescan_wait_time_sec = 2 * 60
        self.rescan_devices() # sets self.devices dict()
        self.activities = activities
        self.current_activity = no_activity
        self.front_listener = asyncio.to_thread(self.front_listen)
        self.back_listener = asyncio.to_thread(self.back_listen)

    def handle_give_device_power_status(self, adapter, msg):
        log.info('Power status requested')
        msg = Message(adapter.address, msg.src)
        if self.current_activity == no_activity:
            status = PowerStatus.STANDBY
        else:
            status = PowerStatus.ON
        log.info(f'Responding with power status {status.name}')
        msg.set_data((Message.REPORT_POWER_STATUS, status))
        adapter.transmit(msg)

    def front_listen(self):
        while True:
            msg = self.front_adapter.listen()
            # LG TVs love spamming this message every 10 seconds.
            if msg.op == Message.VENDOR_ID and msg.dst == cec.BROADCAST_ADDRESS:
                continue
            log.info(f'Front RX {msg}')
            match msg.op:
                case Message.GIVE_DEVICE_POWER_STATUS:
                    self.loop.call_soon_threadsafe(self.handle_give_device_power_status,
                                                   self.front_adapter, msg)

    def handle_device_report_physical_address(self, adapter, msg):
        new_device = True

        # Update an existing device if any...
        for device in self.devices.values():
            if msg.src == device.address:
                device.handle_report_physical_address(msg)
                new_device = False
                break

        if new_device:
            # This is a new device!
            dev = cec.Device(adapter, msg.src)
            device = Device(dev)
            self.devices[dev.osd_name] = device
            log.info(f'Adding new found device {dev.osd_name}')

        pa = pretty_physical_address(device.physical_address)
        log.info(f'{device.osd_name} updated physical address to {pa}')
        if device.osd_name == self.current_activity.source:
            log.info(f'Setting stream path to updated address {pa}')
            device.set_stream_path()

    def back_listen(self):
        while True:
            msg = self.back_adapter.listen()
            log.info(f'Back RX {msg}')
            match msg.op:
                case Message.REPORT_PHYSICAL_ADDR:
                    self.loop.call_soon_threadsafe(self.handle_device_report_physical_address, self.back_adapter, msg)
                case Message.ACTIVE_SOURCE:
                    self.loop.call_soon_threadsafe(self.stop_source_thief, msg.src)
                case Message.GIVE_DEVICE_POWER_STATUS:
                    self.loop.call_soon_threadsafe(self.handle_give_device_power_status, self.back_adapter, msg)


    def wait_on(self):
        return self.front_listener, self.back_listener

    def stop_source_thief(self, device_address):
        log.info(f'Device address {device_address} wants source')
        if self.current_activity == no_activity:
            log.info('No current activity, so forcing standby')
            self.force_standby()
            return

        ca = self.current_activity
        source_device = self.get_device(ca.source)
        if source_device is not None:
            if source_device.address != device_address:
                log.info(f'Taking back source!')
                self.set_activity_input(ca)
            else:
                log.info(f'Device is not a thief')
        else:
            log.info(f"Can't find source device for current activity so will let source thief win")

    def scan_devices(self):
        log.info('Scanning devices...')
        devices = {}
        for adapter in (self.back_adapter, self.front_adapter):
            cec_devices = adapter.list_devices()
            for dev in cec_devices:
                devices[dev.osd_name] = Device(dev)
        log.info('Scanned devices:')
        log.info(f'{"Name":15s} Address Physical Address')
        for name, device in devices.items():
            log.info(f'{name:15s} {device.address:6X}   {pretty_physical_address(device.physical_address):10}')
        return devices

    def rescan_devices(self):
        now = time.time()
        delta = now - self.last_device_rescan_time
        if delta < self.rescan_wait_time_sec:
            time_left = self.rescan_wait_time_sec - delta
            log.info(f'Device rescan is too frequent, {time_left:0.2f}s until allowed')
            return
        self.last_device_rescan_time = now
        self.devices = self.scan_devices()

    def get_device(self, name, op=None):
        if name is None:
            return None
        device = self.devices.get(name)
        if device is None:
            log.info(f'Failed to find device {name}')
            self.rescan_devices()
            device = self.devices.get(name)
            if device is None:
                if op is not None:
                    log.info(f'Device {name} not found for {op}')
                else:
                    log.info(f'Device {name} not found')
        return device

    def set_activity(self, index):
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
            self.fix_current_activity()
            return True
        # Order probably matters so don't use a set().
        current_devices = [ca.audio, ca.source, ca.display]
        new_devices = [na.audio, na.source, na.display]
        for current_device in current_devices:
            if current_device not in new_devices:
                device = self.get_device(current_device, 'STANDBY')
                if device is None:
                    continue
                log.info(f'Device {current_device} STANDBY')
                if is_power_off:
                    device.power_off()
                else:
                    device.standby()
        for new_device in new_devices:
            if new_device not in current_devices:
                device = self.get_device(new_device, 'POWER ON')
                if device is None:
                    continue
                log.info(f'Device {new_device} POWER ON')
                device.power_on()
        self.set_activity_input(na)
        self.current_activity = na
        return True

    def fix_current_activity(self):
        ca = self.current_activity
        log.info(f'Fixing activity {ca.name}')
        current_devices = [ca.audio, ca.source, ca.display]
        for current_device in current_devices:
            device = self.get_device(current_device, 'POWER ON')
            if device is None:
                continue
            log.info(f'Device {current_device} POWER ON')
            device.power_on()
        self.set_activity_input(ca)

    def set_activity_input(self, activity):
        device = self.get_device(activity.source, 'SET STREAM PATH')
        if device is None:
            return
        log.info(f'Setting stream path to {pretty_physical_address(device.physical_address)}')
        device.set_stream_path()

    def standby(self):
        self.set_activity(-1)

    def force_standby(self):
        self.front_adapter.broadcast().standby()
        self.back_adapter.broadcast().standby()

    def press_key(self, key, repeat=None):
        if key in (Key.VOLUME_UP, Key.VOLUME_DOWN, Key.TOGGLE_MUTE):
            device_name = self.current_activity.audio
        else:
            device_name = self.current_activity.source
        device = self.get_device(device_name, 'PRESS KEY')
        if device is None:
            return
        log.info(f'Device {device_name} PRESS KEY 0x{key:02X}')
        device.press_key(key, repeat)

    def release_key(self):
        cs = self.current_activity.source
        device = self.get_device(cs, 'RELEASE KEY')
        if device is None:
            return
        log.info(f'Device {cs} RELEASE KEY')
        device.release_key()
