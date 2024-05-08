#!/usr/bin/env python

# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import cec
from enum import IntEnum
import pprint, sched, time, yaml

import remote

class Key(IntEnum):
    SELECT = 0x00
    UP = 0x01
    DOWN = 0x02
    LEFT = 0x03
    RIGHT = 0x04
    ROOT_MENU = 0x09
    BACK = 0x0D
    TOGGLE_MUTE = 0x43
    PAUSE_PLAY = 0x61
    SET_INPUT = 0x69
    POWER_OFF = 0x6C
    POWER_ON = 0x6D

def isiterable(o):
    try:
        iter(o)
        return True
    except:
        return False

# Calling cec.init() twice locks up the process. Guard it so I can be lazy during development...
cec_initialized = False
def cec_init():
    global cec_initialized
    if not cec_initialized:
        cec.init()
        cec_initialized = True

no_activity_descriptor = { 'name': 'No Activity',
                'display': None,
                'source': None,
                'audio': None,
                'switch': { 'device': None, 'input': 0 }
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
        self.switch = Switch(d['switch'])

    def __repr__(self):
        d = {
            'name': self.name,
            'display': self.display,
            'source': self.source,
            'audio': self.audio,
            'switch': self.switch
        }
        return pprint.pformat(d)

no_activity = Activity()

class Quirk(object):
    def __init__(self, d):
        self.op = d['op']
        data = d['data']
        if not isiterable(data):
            data = [data]
        self.data = bytes(data)
    def __repr__(self):
        return pprint.pformat({
            'op': self.op,
            'data': self.data
        })

class Device(object):
    quirks = None
    def __init__(self, dev):
        if Device.quirks is None:
            with open('quirks.yaml', 'r') as file:
                Device.quirks = yaml.safe_load(file)
        self.dev = dev

    def name(self):
        return self.dev.osd_string

    def vendor(self):
        return self.dev.vendor

    def address(self):
        return self.dev.address

    def physical_address(self):
        return self.dev.physical_address

    def lookup_quirk(self, op):
        v = Device.quirks.get(self.dev.vendor)
        if v is None: return None
        q = v.get(op)
        if q is None: return None
        return Quirk(q)

    def power_on(self):
        quirk = self.lookup_quirk('power_on')
        if quirk:
            log.info(f'Using POWER ON quirk {quirk}')
            self.dev.transmit(quirk.op, quirk.data)
            if quirk.op == cec.CEC_OPCODE_USER_CONTROL_PRESSED:
                self.dev.transmit(cec.CEC_OPCODE_USER_CONTROL_RELEASE)
            return
        self.dev.power_on()

    def power_off(self):
        quirk = self.lookup_quirk('power_off')
        if quirk:
            log.info(f'Using POWER OFF quirk {quirk}')
            self.dev.transmit(quirk.op, quirk.data)
            if quirk.op == cec.CEC_OPCODE_USER_CONTROL_PRESSED:
                self.dev.transmit(cec.CEC_OPCODE_USER_CONTROL_RELEASE)
            return
        self.standby()

    def standby(self):
        self.dev.standby()
    #def toggle_mute(self):
    #    data = bytes([Key.ToggleMute])
    #    self.dev.transmit(cec.CEC_OPCODE_USER_CONTROL_PRESSED, data)
    #    self.dev.transmit(cec.CEC_OPCODE_USER_CONTROL_RELEASE)
    def set_input(self, index):
        self.dev.set_av_input(index)
        #data = bytes([Key.SET_INPUT, index])
        #self.dev.transmit(cec.CEC_OPCODE_USER_CONTROL_PRESSED, data)
        #self.dev.transmit(cec.CEC_OPCODE_USER_CONTROL_RELEASE)
    def press_key(self, key, repeat=None):
        if repeat is None: repeat = False
        data = bytes([key])
        self.dev.transmit(cec.CEC_OPCODE_USER_CONTROL_PRESSED, data)
        if not repeat:
            self.release_key()
    def release_key(self):
        self.dev.transmit(cec.CEC_OPCODE_USER_CONTROL_RELEASE)

class Controller(object):
    def __init__(self, loop, activities):
        self.loop = loop
        self.rescan_devices()
        self.activities = activities
        self.current_activity = no_activity
        cec.add_callback(self.cec_callback, cec.EVENT_ALL)

    def cec_callback(self, event_type, event):
        #log.info(f'EVENT {event_type} {event}')
        if len(self.activities) == 0:
            # We are running as a tool, not a controller, don't do anything
            return
        if event_type & cec.EVENT_COMMAND:
            if event['opcode'] == cec.CEC_OPCODE_REQUEST_ACTIVE_SOURCE:
                if self.loop is None:
                    self.stop_source_thief(event['initiator'])
                else:
                    self.loop.call_soon_threadsafe(self.stop_source_thief, event['initiator'])

    def stop_source_thief(self, device_address):
        log.info(f'Device address {device_address} wants source')
        if self.current_activity == no_activity:
            log.info('No current activity, so forcing standby')
            self.force_standby()
            return

        ca = self.current_activity
        no_devices = True
        for name in [ca.display,
                     ca.source,
                     ca.audio,
                     ca.switch.device]:
            device = self.get_device(name)
            if device is not None:
                no_devices = False
                if device.address() == device_address:
                    log.info(f'Device {name} is not a thief')
                    return
        if no_devices:
            log.info(f"Can't find source device for current activity so will let source thief win")
            return

        log.info(f'Taking back source!')
        self.set_activity_input(ca)

    def scan_devices(self):
        log.info('Scanning devices...')
        cec_devices = cec.list_devices()
        devices = {}
        for addr, cec_device in cec_devices.items():
            devices[cec_device.osd_string] = Device(cec_device)
        log.info('Scanned devices:')
        log.info(pprint.pformat(list(devices.keys())))
        return devices

    def rescan_devices(self):
        self.devices = self.scan_devices()

    def get_device(self, name):
        if name == None:
            return None
        device = self.devices.get(name)
        if device is None:
            log.info(f'Failed to find device {name}')
            self.rescan_devices()
            device = self.devices.get(name)
            if device is None:
                log.info(f'Failed to find device {name} after rescan')
        return device

    def set_activity(self, index):
        if index < -1 or index >= len(self.activities):
            log.info(f'Activity index {index} is out of bounds')
            return
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
            return
        # Order probably matters so don't use a set().
        current_devices = [ca.audio, ca.switch.device, ca.source, ca.display]
        new_devices = [na.audio, na.switch.device, na.source, na.display]
        for current_device in current_devices:
            if current_device not in new_devices:
                device = self.get_device(current_device)
                if device is None:
                    log.info(f'Device {current_device} not found for STANDBY')
                    continue
                log.info(f'Device {current_device} STANDBY')
                if is_power_off:
                    device.power_off()
                else:
                    device.standby()
        for new_device in new_devices:
            if new_device not in current_devices:
                device = self.get_device(new_device)
                if device is None:
                    log.info(f'Device {new_device} not found for POWER ON')
                    continue
                log.info(f'Device {new_device} POWER ON')
                device.power_on()
        # XXX May need to add a delay before SET INPUT
        self.set_activity_input(na)
        self.current_activity = na

    def fix_current_activity(self):
        ca = self.current_activity
        log.info(f'Fixing activity {ca.name}')
        current_devices = [ca.audio, ca.switch.device, ca.source, ca.display]
        for current_device in current_devices:
            device = self.get_device(current_device)
            if device is None:
                log.info(f'Device {current_device} not found for POWER ON')
                continue
            log.info(f'Device {current_device} POWER ON')
            device.power_on()
        # XXX May need to add a delay before SET INPUT
        self.set_activity_input(ca)

    def set_activity_input(self, activity):
        device = self.get_device(activity.switch.device)
        if device is None:
            log.info(f'Device {activity.switch.device} not found for SET INPUT')
        else:
            log.info(f'Device {activity.switch.device} SET INPUT to index {activity.switch.input}')
            device.set_input(activity.switch.input)

    def volume_up(self):
        cec.volume_up()

    def volume_down(self):
        cec.volume_down()

    def toggle_mute(self):
        cec.toggle_mute()

    def standby(self):
        self.set_activity(-1)

    def force_standby(self):
        cec.transmit(cec.CECDEVICE_BROADCAST, cec.CEC_OPCODE_STANDBY)

    def press_key(self, key, repeat=None):
        cs = self.current_activity.source
        device = self.get_device(cs)
        if device is None:
            log.info(f'Device {cs} not found for PRESS KEY')
            return
        log.info(f'Device {cs} PRESS KEY 0x{key:02X}')
        device.press_key(key, repeat)

    def release_key(self):
        cs = self.current_activity.source
        device = self.get_device(cs)
        if device is None:
            log.info(f'Device {cs} not found for RELEASE KEY')
            return
        log.info(f'Device {cs} RELEASE KEY')
        device.release_key()
