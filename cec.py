# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

from ctypes import Structure, Union, c_char, c_uint8, c_uint16, c_uint32, c_uint64, sizeof
from enum import IntEnum
import asyncio
import errno
import fcntl
import os

_IOC_NRBITS   =  8
_IOC_TYPEBITS =  8
_IOC_SIZEBITS = 14
_IOC_DIRBITS  =  2

_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = (_IOC_NRSHIFT+_IOC_NRBITS)
_IOC_SIZESHIFT = (_IOC_TYPESHIFT+_IOC_TYPEBITS)
_IOC_DIRSHIFT  = (_IOC_SIZESHIFT+_IOC_SIZEBITS)

_IOC_NONE = 0
_IOC_WRITE = 1
_IOC_READ = 2

def _IOC(direction, tp, nr, size):
    if type(tp) == str:
        tp = ord(tp) # XXX doesn't work for multi byte integers...
    if type(size) != int:
        size = sizeof(size)

    return (((direction)  << _IOC_DIRSHIFT) |
        ((tp) << _IOC_TYPESHIFT) |
        ((nr)   << _IOC_NRSHIFT) |
        ((size) << _IOC_SIZESHIFT))

def _IO(type, nr):
    return _IOC(0, type, nr, 0)

def _IOR(type, nr, size):
    return _IOC(_IOC_READ, type, nr, size)

def _IOW(type, nr, size):
    return _IOC(_IOC_WRITE, type, nr, size)

def _IOWR(type, nr, size):
    return _IOC(_IOC_READ|_IOC_WRITE, type, nr, size)

INVALID_PHYSICAL_ADDRESS = 0xffff
BROADCAST_ADDRESS = 0x0f
INVALID_ADDRESS = 0xff

class Capabilities(Structure):
    PHYS_ADDR = (1 << 0) # Userspace has to configure the physical address
    LOG_ADDRS = (1 << 1) # Userspace has to configure the logical addresses
    TRANSMIT = (1 << 2) # Userspace can transmit messages (and thus become follower as well)
    PASSTHROUGH = (1 << 3) # Passthrough all messages instead of processing them
    RC = (1 << 4) # Supports remote control
    MONITOR_ALL = (1 << 5) # Hardware can monitor all messages, not just directed and broadcast
    NEEDS_HPD = (1 << 6) # Hardware can use CEC only if the HDMI HPD pin is high.
    MONITOR_PIN = (1 << 7) # Hardware can monitor CEC pin transitions

    _fields_ = [
        ('driver', c_char * 32),
        ('name', c_char * 32),
        ('available_log_addrs', c_uint32),
        ('capabilities', c_uint32),
        ('version', c_uint32)]

class LogAddrs(Structure):
    MAX_LOG_ADDRS = 4
    MAX_OSD_NAME = 15
    CEC_VERSION_1_3A = 4
    CEC_VERSION_1_4 = 5
    CEC_VERSION_2_0 = 6

    LOG_ADDR_INVALID = 0xff

    _fields_ = [
        ('log_addr', c_uint8 * MAX_LOG_ADDRS),
        ('log_addr_mask', c_uint16),
        ('cec_version', c_uint8),
        ('num_log_addrs', c_uint8),
        ('vendor_id', c_uint32),
        ('flags', c_uint32),
        ('osd_name', c_char * MAX_OSD_NAME),
        ('primary_device_type', c_uint8 * MAX_LOG_ADDRS),
        ('log_addr_type', c_uint8 * MAX_LOG_ADDRS),
        ('all_device_types', c_uint8 * MAX_LOG_ADDRS),
        ('features', c_uint8 * MAX_LOG_ADDRS * 12)]

class Key(IntEnum):
    NO_KEY = -1
    SELECT = 0x00
    UP = 0x01
    DOWN = 0x02
    LEFT = 0x03
    RIGHT = 0x04
    ROOT_MENU = 0x09
    SETUP_MENU = 0x0A
    CONTENTS_MENU = 0x0B
    FAVORITE_MENU = 0x0C
    BACK = 0x0D
    NUMBER_0 = 0x20
    NUMBER_1 = 0x21
    NUMBER_2 = 0x22
    NUMBER_3 = 0x23
    NUMBER_4 = 0x24
    NUMBER_5 = 0x25
    NUMBER_6 = 0x26
    NUMBER_7 = 0x27
    NUMBER_8 = 0x28
    NUMBER_9 = 0x29
    CHANNEL_UP = 0x30
    CHANNEL_DOWN = 0x31
    DISPLAY_INFO = 0x35
    POWER = 0x40
    VOLUME_UP = 0x41
    VOLUME_DOWN = 0x42
    TOGGLE_MUTE = 0x43
    PLAY = 0x44
    PAUSE = 0x46
    REWIND = 0x48
    FAST_FORWARD = 0x49
    FORWARD = 0x4B
    BACKWARD = 0x4C
    SUB_PICTURE = 0x51
    VOD = 0x52
    GUIDE = 0x53
    PLAY_FUNCTION = 0x60
    PAUSE_PLAY = 0x61
    SET_INPUT = 0x69
    POWER_OFF = 0x6C
    POWER_ON = 0x6D
    F1 = 0x71 # Blue
    F2 = 0x72 # Red
    F3 = 0x73 # Green
    F4 = 0x74 # Yellow
    F5 = 0x75
    # Below are all invalid HDMI-CEC key codes that are more than 1 byte.
    # They are a hack to allow extending the number of F keys that can be represented internally
    # for activity selection.
    F6 = 0x100
    F7 = 0x101

class PowerStatus(IntEnum):
    ON = 0
    STANDBY = 1
    IN_TRANSITION_STANDBY_TO_ON = 2
    IN_TRANSITION_ON_TO_STANDBY = 3

class Message(Structure):
    IMAGE_VIEW_ON = 0x04
    STANDBY = 0x36
    KEY_PRESS = 0x44
    KEY_RELEASE = 0x45
    GIVE_OSD_NAME = 0x46
    SET_OSD_NAME = 0x47
    ACTIVE_SOURCE = 0x82
    GIVE_PHYSICAL_ADDR = 0x83
    REPORT_PHYSICAL_ADDR = 0x84
    REQUEST_ACTIVE_SOURCE = 0x85
    SET_STREAM_PATH = 0x86
    VENDOR_ID = 0x87
    GIVE_DEVICE_POWER_STATUS = 0x8f
    REPORT_POWER_STATUS = 0x90
    GIVE_VENDOR_ID = 0x8c

    TX_STATUS_OK = (1 << 0)
    TX_STATUS_ARB_LOST = (1 << 1)
    TX_STATUS_NACK = (1 << 2)
    TX_STATUS_LOW_DRIVE = (1 << 3)
    TX_STATUS_ERROR = (1 << 4)
    TX_STATUS_MAX_RETRIES = (1 << 5)
    TX_STATUS_ABORTED = (1 << 6)
    TX_STATUS_TIMEOUT = (1 << 7)
    RX_STATUS_OK = (1 << 0)
    RX_STATUS_TIMEOUT = (1 << 1)
    RX_STATUS_FEATURE_ABORT = (1 << 2)
    RX_STATUS_ABORTED = (1 << 3)

    MAX_MSG_SIZE = 16
    _fields_ = [
        ('tx_ts', c_uint64),
        ('rx_ts', c_uint64),
        ('len', c_uint32),
        ('timeout', c_uint32),
        ('sequence', c_uint32),
        ('flags', c_uint32),
        ('msg', c_uint8 * MAX_MSG_SIZE),
        ('reply', c_uint8),
        ('rx_status', c_uint8),
        ('tx_status', c_uint8),
        ('tx_arb_lost_cnt', c_uint8),
        ('tx_nack_cnt', c_uint8),
        ('tx_low_drive_cnt', c_uint8),
        ('tx_error_cnt', c_uint8)]

    def __init__(self, src: int, dst: int):
        self.len = 1
        self.msg[0] = (src << 4) | dst

    @property
    def op(self):
        return self.msg[1]

    @op.setter
    def op(self, cmd):
        self.msg[1] = cmd

    @property
    def src(self):
        return self.msg[0] >> 4

    @property
    def dst(self):
        return self.msg[0] & 0x0f

    def set_data(self, data):
        self.len = len(data) + 1
        for i, d in enumerate(data):
            self.msg[1 + i] = d

    def ok(self):
        if self.tx_status and not (self.tx_status & self.TX_STATUS_OK):
            return False
        if self.rx_status and not (self.rx_status & self.RX_STATUS_OK):
            return False
        if not self.rx_status and not self.tx_status:
            return False
        return not (self.rx_status & self.RX_STATUS_FEATURE_ABORT)

    def did_rx(self):
        return (self.rx_status & self.RX_STATUS_OK) != 0

    def tx_status_text(self):
        s = self.tx_status
        a = ['Tx']
        if s & self.TX_STATUS_OK:
            a.append('OK')
        if s & self.TX_STATUS_ARB_LOST:
            a.append(f'Arbitration Lost {self.tx_arb_lost_cnt}')
        if s & self.TX_STATUS_NACK:
            a.append(f'NACK ({self.tx_nack_cnt})')
        if s & self.TX_STATUS_LOW_DRIVE:
            a.append(f'Low Drive ({self.tx_low_drive_cnt})')
        if s & self.TX_STATUS_ERROR:
            a.append(f'Error ({self.tx_error_cnt})')
        if s & self.TX_STATUS_ABORTED:
            a.append(f'Aborted')
        if s & self.TX_STATUS_TIMEOUT:
            a.append(f'Timeout')
        if s & self.TX_STATUS_MAX_RETRIES:
            a.append('Max Retries')
        return ', '.join(a)

    def rx_status_text(self):
        s = self.rx_status
        a = ['Rx']
        if s & self.RX_STATUS_OK:
            a.append('OK')
        if s & self.RX_STATUS_TIMEOUT:
            a.append('Timeout')
        if s & self.RX_STATUS_FEATURE_ABORT:
            a.append('Feature Abort')
        if s & self.RX_STATUS_ABORTED:
            a.append('Aborted')
        return ', '.join(a)

    def status_text(self):
        s = []
        if self.tx_status:
            s.append(self.tx_status_text())
        if self.rx_status:
            s.append(self.rx_status_text())
        return ', '.join(s)

    def __str__(self):
        return ':'.join(f'{c:02X}' for c in self.msg[:self.len])

class EventStateChange(Structure):
    _fields_ = [
        ('phys_addr', c_uint16),
        ('log_addr_mask', c_uint16),
        ('have_conn_info', c_uint16)]

class EventLogMsgs(Structure):
    _fields_ = [
        ('lost_msgs', c_uint32)]

class EventUnion(Union):
    _fields_ = [
        ('state_change', EventStateChange),
        ('lost_msgs', EventLogMsgs),
        ('raw', c_uint32 * 16)]

class Event(Structure):
    STATE_CHANGE = 1
    LOST_MSGS = 2
    PIN_CEC_LOW = 3
    PIN_CEC_HIGH = 4
    PIN_HPD_LOW = 5
    PIN_HPD_HIGH = 6
    PIN_5V_LOW = 7
    PIN_5V_HIGH =  8

    _fields_ = [
        ('ts', c_uint64),
        ('event', c_uint32),
        ('flags', c_uint32),
        ('union', EventUnion)]

class DRMConnectorInfo(Structure):
    _fields_ = [
        ('card_no', c_uint32),
        ('connector_id', c_uint32)]

class ConnectorInfoUnion(Union):
    _fields_ = [
        ('drm', DRMConnectorInfo),
        ('raw', c_uint32 * 16)]

class ConnectorInfo(Structure):
    _fields_ = [
        ('type', c_uint32),
        ('union', ConnectorInfoUnion)]

class Ioctl(IntEnum):
    ADAP_G_CAPS = _IOWR('a', 0, Capabilities)
    ADAP_G_PHYS_ADDR = _IOR('a', 1, c_uint16)
    ADAP_S_PHYS_ADDR = _IOW('a', 2, c_uint16)
    ADAP_G_LOG_ADDRS = _IOR('a', 3, LogAddrs)
    ADAP_S_LOG_ADDRS = _IOWR('a', 4, LogAddrs)
    TRANSMIT = _IOWR('a', 5, Message)
    RECEIVE = _IOWR('a', 6, Message)
    DQEVENT = _IOWR('a', 7, Event)
    G_MODE = _IOR('a', 8, c_uint32)
    S_MODE = _IOW('a', 9, c_uint32)
    ADAP_G_CONNECTOR_INFO = _IOR('a', 10, ConnectorInfo)

class Capability(IntEnum):
    PHYS_ADDR = (1 << 0) # Userspace has to configure the physical address
    LOG_ADDRS = (1 << 1) # Userspace has to configure the logical addresses
    TRANSMIT = (1 << 2) # Userspace can transmit messages (and thus become follower as well)
    PASSTHROUGH = (1 << 3) # Passthrough all messages instead of processing them
    RC = (1 << 4) # Supports remote control
    MONITOR_ALL	= (1 << 5) # Hardware can monitor all messages, not just directed and broadcast
    NEEDS_HPD =	(1 << 6) # Hardware can use CEC only if the HDMI HPD pin is high
    MONITOR_PIN = (1 << 7) # Hardware can monitor CEC pin transitions
    CONNECTOR_INFO = (1 << 8) # CEC_ADAP_G_CONNECTOR_INFO is available

class DeviceType(object):
    TV = 0
    RECORDING = 1
    TUNER = 3
    PLAYBACK = 4
    AUDIO_SYSTEM = 5
    SWITCH = 6
    PROCESSOR = 7
    INVALID = -1

    FLAG = {
        TV : 0x80,
        RECORDING : 0x40,
        TUNER : 0x20,
        PLAYBACK : 0x10,
        AUDIO_SYSTEM : 0x08,
        SWITCH : 0x04
        }

    ADDR_TYPE = {
        TV : 0,
        RECORDING : 1,
        TUNER : 2,
        PLAYBACK : 3,
        AUDIO_SYSTEM: 4,
        PROCESSOR: 5,
        SWITCH: 6
    }

    name = {
        TV : 'TV',
        RECORDING : 'Recording',
        TUNER : 'Tuner',
        PLAYBACK : 'Playback',
        AUDIO_SYSTEM : 'Audio System',
        SWITCH : 'Switch',
        PROCESSOR : 'Processor',
        INVALID : 'Invalid'}

class DeviceImpl(object):
    def __init__(self, adapter, address):
        self.adapter = adapter
        self.address = address
        self.physical_address = INVALID_PHYSICAL_ADDRESS
        self.primary_device_type = DeviceType.INVALID
        self.osd_name = ''
        self.vendor_id = 0
        if self.address == BROADCAST_ADDRESS:
            self.osd_name = '<BROADCAST>'
            return

    def is_broadcast(self):
        return self.address == BROADCAST_ADDRESS

    def new_msg(self):
        return Message(self.adapter.address, self.address)

    def parse_report_physical_address_message(self, msg):
        if msg.ok():
            self.physical_address = (msg.msg[2] << 8) | msg.msg[3]
            self.primary_device_type = msg.msg[4]
        else:
            if self.address == 0:
                # Some (LG) TVs are uncooperative?
                self.physical_address = 0
                self.primary_device_type = DeviceType.TV
            else:
                self.physical_address = INVALID_PHYSICAL_ADDRESS
                self.primary_device_type = DeviceType.INVALID

    async def get_physical_address_and_primary_device_type(self):
        msg = self.new_msg()
        msg.set_data([Message.GIVE_PHYSICAL_ADDR])
        msg.reply = Message.REPORT_PHYSICAL_ADDR
        msg = await self.adapter.transmit(msg)
        self.parse_report_physical_address_message(msg)

    async def get_osd_name(self):
        msg = self.new_msg()
        msg.set_data([Message.GIVE_OSD_NAME])
        msg.reply = Message.SET_OSD_NAME
        msg = await self.adapter.transmit(msg)
        if msg.ok():
            self.osd_name = ''.join([chr(c) for c in msg.msg[2:msg.len] if c != 0])
        else:
            if self.address == 0:
                # Some (LG) TVs are uncooperative?
                self.osd_name = 'TV'
            else:
                self.osd_name = ''

    async def send_osd_name(self, osd_name):
        data = [Message.SET_OSD_NAME]
        data.extend([ord(x) for x in osd_name[:Message.MAX_MSG_SIZE - 2]])
        await self.transmit(data)

    async def get_vendor_id(self):
        msg = self.new_msg()
        msg.set_data([Message.GIVE_VENDOR_ID])
        msg.reply = Message.VENDOR_ID
        msg = await self.adapter.transmit(msg)
        if msg.ok():
            vendor_id = 0
            for i in range(2, msg.len):
                vendor_id = (vendor_id << 8) | msg.msg[i]
            self.vendor_id = vendor_id
        else:
            self.vendor_id = 0

    async def standby(self):
        await self.transmit([Message.STANDBY])

    async def key_press(self, key: Key):
        await self.transmit([Message.KEY_PRESS, key])

    async def key_release(self):
        await self.transmit([Message.KEY_RELEASE])

    async def image_view_on(self):
        await self.transmit([Message.IMAGE_VIEW_ON])

    async def power_on(self):
        if self.primary_device_type == DeviceType.TV:
            await self.image_view_on()
        else:
            #await self.key_press(Key.POWER)
            await self.key_press(Key.POWER_ON)
            await self.key_release()

    async def set_stream_path(self):
        msg = Message(self.adapter.address, BROADCAST_ADDRESS)
        msg.set_data([Message.SET_STREAM_PATH,
                    self.physical_address >> 8,
                    self.physical_address & 0xff])
        await self.adapter.transmit(msg)

    async def active_source(self):
        msg = Message(self.adapter.address, BROADCAST_ADDRESS)
        msg.set_data([Message.ACTIVE_SOURCE,
                self.physical_address >> 8,
                self.physical_address & 0xff])
        await self.adapter.transmit(msg)

    async def transmit(self, data):
        msg = self.new_msg()
        msg.set_data(data)
        await self.adapter.transmit(msg)

    def __str__(self):
        return f'Device({self.address}) "{self.osd_name}"'

async def Device(adapter, address):
    device = DeviceImpl(adapter, address)
    if address != BROADCAST_ADDRESS:
        await device.get_physical_address_and_primary_device_type()
        await device.get_osd_name()
        await device.get_vendor_id()
    return device

def isiterable(o):
    try:
        iter(o)
        return True
    except:
        return False

class AdapterInitException(Exception):
    pass

class AsyncState(object):
    def __init__(self, msg, event):
        self.msg = msg
        self.event = event

class Adapter(object):
    MODE_INITIATOR = (1 << 0)
    MODE_FOLLOWER = (1 << 4)

    def __init__(self, devname, loop=None, listen_callback_coro=None,
                 device_types=(), osd_name='default', vendor_id=0, physical_address_override=None):
        self.taskit = tools.Tasker('Adapter')
        self.states = {}
        self.devname = devname
        if loop is None:
            loop = asyncio.get_running_loop()
        self.loop = loop
        self.listen_callback_coro = listen_callback_coro
        if not isiterable(device_types):
            device_types = (device_types, )
        self.device_types = device_types
        self.osd_name = osd_name
        self.vendor_id = vendor_id
        self.dev = open(devname, 'wb', buffering=0)
        self.caps = self.capabilities()
        self.laddrs = LogAddrs()
        mode = c_uint32(self.MODE_INITIATOR | self.MODE_FOLLOWER)
        self.ioctl(Ioctl.S_MODE, mode)
        self.setup(physical_address_override)
        # Setup (called above) is simpler to perform on a blocking device. After setup, set the
        # device to non-blocking for efficiency - CEC is very very slow (~400 bits/sec), so we
        # don't want to block on TX.
        os.set_blocking(self.dev.fileno(), False)
        self.loop.add_reader(self.dev.fileno(), self.reader)

    def close(self):
        self.loop.remove_reader(self.dev.fileno())
        self.dev.close()
        self.dev = None

    def ioctl(self, op, data):
        return fcntl.ioctl(self.dev, op, data)

    def capabilities(self, caps=None):
        if caps is None:
            caps = Capabilities()
        b = self.ioctl(Ioctl.ADAP_G_CAPS, bytes(bytearray(caps)))
        return Capabilities.from_buffer(bytearray(b))

    @property
    def address(self):
        return self.laddrs.log_addr[0]

    @property
    def physical_address(self):
        address = bytes(2)
        address = self.ioctl(Ioctl.ADAP_G_PHYS_ADDR, address)
        return int.from_bytes(address, byteorder='little')

    @physical_address.setter
    def physical_address(self, address):
        self.ioctl(Ioctl.ADAP_S_PHYS_ADDR, address.to_bytes(2, byteorder='little'))

    def setup(self, physical_address_override):
        # Clear the current logical address configuration
        laddrs = LogAddrs()
        self.ioctl(Ioctl.ADAP_S_LOG_ADDRS, laddrs)

        if not self.device_types:
            device_types = (DeviceType.PLAYBACK, )
        else:
            device_types = self.device_types
        self.device_types = device_types
        if len(device_types) > self.caps.available_log_addrs:
            raise AdapterInitException('Too many logical addresses')

        # cec-gpio devices must have their physical addresses configured at least once.
        # As a TV, we claim 0.0.0.0 by fiat.
        # As any other device we need to read the address from the EDID of the device we are
        # connected to. For Amity's limited aims, reading the EDID introduces a mountain of
        # unnecessary complexity that is best avoided. It would require routing HDMI's DDC pins
        # (SDA & SCL). We would then be able to read EDID info from the TV but would also need to
        # supply it to downstream devices! So it's best to let the TV continue to handle EDID
        # functionality.
        if (self.caps.capabilities & Capabilities.PHYS_ADDR and
            (self.physical_address == INVALID_PHYSICAL_ADDRESS)):
            if self.device_types[0] == DeviceType.TV:
                self.physical_address = 0x0000
            else:
                if physical_address_override is not None:
                    self.physical_address = physical_address_override
                else:
                    # Hopefully, this guessed address works universally.
                    self.physical_address = 0x1000

        # And configure...
        laddrs = LogAddrs()
        laddrs.cec_version = LogAddrs.CEC_VERSION_2_0
        laddrs.osd_name = self.osd_name.encode()[:laddrs.MAX_OSD_NAME - 1]
        laddrs.vendor_id = self.vendor_id

        primary_type = 0xff
        all_device_types = 0
        for device_type in device_types:
            la_type = DeviceType.ADDR_TYPE[device_type]
            all_device_types |= DeviceType.FLAG[device_type]
            if primary_type == 0xff:
                primary_type = device_type
            if device_type == DeviceType.TV:
                primary_type = device_type
            elif primary_type != DeviceType.TV and device_type == DeviceType.AUDIO_SYSTEM:
                primary_type = device_type
            laddrs.log_addr_type[laddrs.num_log_addrs] = la_type
            laddrs.num_log_addrs += 1

        for i in range(laddrs.num_log_addrs):
            laddrs.primary_device_type[i] = primary_type
            laddrs.all_device_types[i] = all_device_types

        self.ioctl(Ioctl.ADAP_S_LOG_ADDRS, laddrs)
        self.ioctl(Ioctl.ADAP_G_LOG_ADDRS, self.laddrs)

        if self.laddrs.log_addr[0] >= INVALID_ADDRESS:
            s = f'Logical address allocation failed. Is HDMI-CEC {self.devname} pin attached?'
            log.info(s)
            raise AdapterInitException(s)

        return self.laddrs

    async def transmit(self, msg: Message):
        state = AsyncState(msg, asyncio.Event())
        ret = self.ioctl(Ioctl.TRANSMIT, msg)
        if ret != 0:
            log.info(f'TX {msg} failed')
            return None
        log.info(f'TX {msg.sequence} {msg}')
        self.states[msg.sequence] = state
        await state.event.wait()
        msg = state.msg
        return msg

    async def active_source(self):
        msg = Message(self.address, BROADCAST_ADDRESS)
        msg.set_data([Message.ACTIVE_SOURCE,
                      self.physical_address >> 8,
                      self.physical_address & 0xff])
        await self.transmit(msg)

    async def poll_device(self, i):
        msg = Message(self.address, i)
        msg = await self.transmit(msg)
        if msg.ok():
            return await Device(self, i)
        if msg.tx_status & Message.TX_STATUS_MAX_RETRIES:
            log.info(f'{msg.status_text()} for addr {i}')
        return None

    async def list_devices(self):
        devices = []
        for i in range(0xf):
            if i == self.address:
                continue
            device = await self.poll_device(i)
            if device is None:
                continue
            devices.append(device)
        return devices

    def broadcast(self):
        return DeviceImpl(self, BROADCAST_ADDRESS)

    def reader(self):
        msg = Message(0, 0)

        # Events should be dequed in response to file handle exceptions. Not clear how to do that
        # in asyncio so using file handle read events, unreliably.
        try:
            event = Event()
            self.ioctl(Ioctl.DQEVENT, event)
            if event.event & event.LOST_MSGS:
                log.error(f'Lost {event.union.lost_msgs} messages, slow down')
        except OSError as e:
            pass

        while True:
            try:
                self.ioctl(Ioctl.RECEIVE, msg)
            except OSError as e:
                if e.errno == errno.EAGAIN:
                    break
                if e.errno == errno.ENODEV:
                    log.info('Disconnected')
                else:
                    log.info(f'Unexpected IOCTL error {e}')
                tools.die(f'CEC IOCTL error {e}')
            state = self.states.pop(msg.sequence, None)
            if state is not None:
                state.msg = msg
                if msg.did_rx():
                    log.info(f'RX {msg.sequence} {msg}')
                log.info(f'TX status {msg.sequence} {msg.status_text()}')
                state.event.set()
            else:
                # LG TVs love spamming this message every 10 seconds.
                if msg.op != Message.VENDOR_ID or msg.dst != BROADCAST_ADDRESS:
                    log.info(f'RX {msg.sequence} {msg}')
                # This is a new message RXd from a device
                if self.listen_callback_coro is not None:
                    self.taskit(self.listen_callback_coro(msg))
