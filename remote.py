# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This code is derived from code written by Yanndroid (https://github.com/Yanndroid)

import tools

log = tools.logger(__name__)

import subprocess, time
from bluepy3.btle import AssignedNumbers, BTLEConnectError, BTLEException, DefaultDelegate, Peripheral

class PnpInfo(object):
    @classmethod
    def WithData(self, data):
        vendor_id_type = data[0]
        vendor_id = int.from_bytes(data[1:3], byteorder='little')
        product_id = int.from_bytes(data[3:5], byteorder='little')
        product_version = int.from_bytes(data[5:7], byteorder='little')
        return PnpInfo(vendor_id_type, vendor_id, product_id, product_version)

    def __init__(self, vendor_id_type, vendor_id, product_id, product_version):
        self.vendor_id_type = vendor_id_type
        self.vendor_id = vendor_id
        self.product_id = product_id
        self.product_version = product_version
    def __eq__(self, other):
        return (self.vendor_id_type == other.vendor_id_type and
                self.vendor_id == other.vendor_id and
                self.product_id == other.product_id and
                self.product_version == other.product_version)
    def __hash__(self):
        return self.vendor_id_type + self.vendor_id + (self.product_id + self.product_version) * 65536
    def __str__(self):
        return f'Type {self.vendor_id_type:02X} Vendor {self.vendor_id:04X} Product ID {self.product_id:04X} Product version {self.product_version:04X}'


class UnknownRemoteException(Exception):
    def __init__(self, hw, fw, pnp_info):
        self.hw = hw
        self.fw = fw
        self.pnp_info = pnp_info
    def __str__(self):
        return f'Unknown hw "{self.hw}" fw "{self.fw}" PNP {self.pnp_info}'

class Vector(object):
    def __init__(self, xyz):
        self.x, self.y, self.z = xyz
    def __str__(self):
        return f'({self.x}, {self.y}, {self.z})'
    def __repr__(self):
        return f'({self.x}, {self.y}, {self.z})'

class MotionEvent(object):
    def __init__(self, gyro):
        self.gyro = gyro
    def __str__(self):
        return f'gyro {self.gyro}'

class Touch(object):
    def __init__(self, remote, idtxyp):
        self.remote = remote
        self.id, self.timestamp, self.x, self.y, self.p = idtxyp
    def axis_distances_from_touch(self, t): # in mm
        rtp = self.remote.profile.touchpad
        dx_mm = (self.x - t.x) / rtp.RESOLUTION[rtp.X_AXIS] * rtp.SIZE_MM
        dy_mm = (self.y - t.y) / rtp.RESOLUTION[rtp.Y_AXIS] * rtp.SIZE_MM
        return dx_mm, dy_mm
    def distance_from_touch(self, t): # in mm
        dx_mm, dy_mm = self.axis_distances_from_touch(t)
        return (dx_mm**2 + dy_mm**2)**.5
    def velocity_from_touch(self, t): # in mm/s
        dt = self.time_from_touch(t)
        if dt == 0: return self.remote.profile.touchpad.size_MM
        return self.distance_from_touch(t) / dt
    def axis_velocities_from_touch(self, t): # in mm/s
        dt = self.time_from_touch(t)
        if dt == 0:
            rtp = self.remote.profile.touchpad
            return rtp.SIZE_MM, rtp.SIZE_MM
        dx_mm, dy_mm = self.axis_distances_from_touch(t)
        return dx_mm/dt, dy_mm/dt
    def time_from_touch(self, t):
        dt = self.timestamp - t.timestamp
        if dt < 0:
            dt += 65536
        return dt / self.remote.profile.touchpad.TIMESTAMP_HZ

    def __str__(self):
        return f'({self.id}, {self.timestamp}, {self.x}, {self.y}, {self.p})'
    def __repr__(self):
        return f'({self.id}, {self.timestamp}, {self.x}, {self.y}, {self.p})'

class RemoteListener(object):
    def event_battery(self, remote, percent: int):
        pass

    def event_power(self, remote, charging: bool):
        pass

    def event_button(self, remote, button: int):
        pass

    def event_touches(self, remote, touches):
        pass

    def event_motion(self, remote, motion: MotionEvent):
        pass

    def event_audio(self, remote, data: bytes):
        pass

class RemoteListenerAsyncWrapper(RemoteListener):
    def __init__(self, loop, listener):
        self.loop = loop
        self.listener = listener

    def event_battery(self, remote, percent: int):
        self.loop.call_soon_threadsafe(self.listener.event_battery, remote, percent)

    def event_power(self, remote, charging: bool):
        self.loop.call_soon_threadsafe(self.listener.event_power, remote, charging)

    def event_button(self, remote, button: int):
        self.loop.call_soon_threadsafe(self.listener.event_button, remote, button)

    def event_touches(self, remote, touches):
        self.loop.call_soon_threadsafe(self.listener.event_touches, remote, touches)

    def event_motion(self, remote, motion: MotionEvent):
        self.loop.call_soon_threadsafe(self.listener.event_motion, remote, motion)

    def event_audio(self, remote, data: bytes):
        self.loop.call_soon_threadsafe(self.listener.event_audio, remote, data)

class HwRevisions(object):
    GEN_1   = 0x0266
    GEN_1_5 = 0x026D
    GEN_2   = 0x0314
    GEN_3   = 0x0315

class FwRevisions(object):
    GEN_2_0x0083 = 0x0083
    GEN_1_0x257 = 0x257

class ButtonCodes(object):
    def __init__(self, hw_revision, fw_revision):
        self.INVALID = 0x80000000
        self.RELEASED = 0x0000
        # These don't exist in gen 1. However, it's useful to always define them
        # so they can be emulated for gen 1.
        self.UP = 0x0200
        self.RIGHT = 0x0400
        self.DOWN = 0x0800
        self.LEFT = 0x1000
        if hw_revision in (HwRevisions.GEN_1, HwRevisions.GEN_1_5):
            self.HOME = 0x01
            self.VOLUME_UP = 0x02
            self.VOLUME_DOWN = 0x04
            self.PLAY_PAUSE = 0x08
            self.SIRI = 0x10
            self.BACK = 0x20
            self.SELECT = 0x80
            self.POWER = self.INVALID
            self.MUTE = self.INVALID
        else: # gen 2 or later
            self.HOME = 0x0001
            self.VOLUME_UP = 0x0002
            self.VOLUME_DOWN = 0x0004
            self.SELECT = 0x0008
            self.POWER = 0x0010
            self.SIRI = 0x0020
            self.BACK = 0x0040
            self.MUTE = 0x0080
            self.PLAY_PAUSE = 0x0100

class TouchpadProfile(object):
    INVALID_AXIS = -1
    X_AXIS = 0
    Y_AXIS = 1
    def __init__(self, hw_revision, fw_revision):
        if hw_revision in (HwRevisions.GEN_1, HwRevisions.GEN_1_5):
            self.RESOLUTION = (26180, 106)
            self.SIZE_MM = 37 # Side of the square pad
            self.TIMESTAMP_HZ = 2461
        else: # gen 2 or later
            self.RESOLUTION = (21400, 80)
            self.SIZE_MM = 31 # Diameter of the circular pad
            self.TIMESTAMP_HZ = 2000

class Handles(object):
    def __init__(self, hw_revision, fw_revision):
        self.INVALID = 0xffff
        self.BATTERY = self.INVALID
        self.BATTERY_CONFIG = self.INVALID
        self.POWER = self.INVALID
        self.POWER_CONFIG = self.INVALID
        if hw_revision >= HwRevisions.GEN_2:
            if fw_revision >= FwRevisions.GEN_2_0x0083:
                self.AUDIO = 0x0036
                self.INPUT = 0x003a
                self.TOUCH = 0x003e
            else:
                self.AUDIO = 0x0035
                self.INPUT = 0x0039
                self.TOUCH = 0x003d
        else: # Gen 1
            self.INPUT = 0x0023
            self.TOUCH = 0x0032
            self.AUDIO = self.INVALID

class PowerStates(object):
    def __init__(self, hw_revision, fw_revision):
        if hw_revision >= HwRevisions.GEN_2:
            if fw_revision >= FwRevisions.GEN_2_0x0083:
                self.CHARGING = 0x3b
                self.DISCHARGING = 0x2f
                self.PLUGGED_IN = 0x2b
            else:
                self.CHARGING = 0xab
                self.DISCHARGING = 0xaf
                self.PLUGGED_IN = 0xbb
        else:
            self.CHARGING = 0xab
            self.DISCHARGING = 0xaf
            self.PLUGGED_IN = 0xbb

class RemoteProfile(object):
    def __init__(self, hw_revision, fw_revision):
        self.hw_revision = hw_revision
        self.buttons = ButtonCodes(hw_revision, fw_revision)
        self.touchpad = TouchpadProfile(hw_revision, fw_revision)

class SiriRemote(DefaultDelegate):
    def __init__(self, mac, listener: RemoteListener):
        self.mac = mac
        self.__ready = False
        self.__listener = listener
        self.__device_name = None
        self.__serial_number = None
        self.__pnp_info = None
        self.__hwr = None
        self.__hw_revision = None
        self.__fw_revision = None
        self.__last_keepalive = None
        self.profile = RemoteProfile(HwRevisions.GEN_2, FwRevisions.GEN_2_0x0083)
        self.__setup()

    def __setup(self):
        while True:
            try:
                self.__ready = False
                self.__device = Peripheral()
                self.__device.withDelegate(self)
                # The system will often connect on its own to the remote, and stop us from
                # connecting. So disconnect the remote from the system.
                log.info(f'Calling bluetoothctl to disconnect MAC {self.mac}')
                subprocess.run(['/usr/bin/bluetoothctl', 'disconnect', self.mac], capture_output=True)
                self.__device.connect(self.mac)
                self.__device.getServices()

                # Need to know HW/FW revisions to work with the different remotes
                device_info_svc = self.__device.getServiceByUUID(AssignedNumbers.device_information)
                for ch in device_info_svc.getCharacteristics():
                    if ch.uuid == AssignedNumbers.device_name:
                        self.__device_name = self.read_characteristic(ch.getHandle()).decode()
                    elif ch.uuid == AssignedNumbers.serial_number_string:
                        self.__serial_number = self.read_characteristic(ch.getHandle()).decode()
                    elif ch.uuid == AssignedNumbers.hardware_revision_string:
                        hwr = self.read_characteristic(ch.getHandle()).decode()
                    elif ch.uuid == AssignedNumbers.firmware_revision_string:
                        fwr = self.read_characteristic(ch.getHandle()).decode()
                    elif ch.uuid == AssignedNumbers.pnp_id:
                        pnp_data = self.read_characteristic(ch.getHandle())

                pnp_info = PnpInfo.WithData(pnp_data)
                self.__pnp_info = pnp_info
                product_id = pnp_info.product_id

                #print(f'hw {hwr} fw {fwr} PNP {pnp_info}')

                # Try to parse HW/FW versions strings into meaningful versions
                # If it fails, raise an exception
                try:
                    # Some(?) gen 1/1.5 remotes have crazy long, meaningless looking, FW strings.
                    # ATV denotes those as version 0x257
                    if product_id in (HwRevisions.GEN_1, HwRevisions.GEN_1_5) and len(fwr) > 5:
                        fwr = FwRevisions.GEN_1_0x257
                    else:
                        fwr = int(fwr, 16)
                except ValueError:
                    raise UnknownRemoteException(hwr, fwr, pnp_info)

                # hwr seems to be inconsistent compared to the PNP product id,
                # so use the product id instead. We store hwr strictly for debug.
                self.__hw_revision = product_id
                self.__fw_revision = fwr
                self.__hwr = hwr

                # Negotiate MTU
                if self.__hw_revision >= HwRevisions.GEN_2:
                    mtu = 527
                else:
                    mtu = 185
                self.__device.setMTU(mtu)

                self.profile = RemoteProfile(self.__hw_revision, self.__fw_revision)
                self.__last_button = self.profile.buttons.RELEASED
                self.__handles = Handles(self.__hw_revision, self.__fw_revision)
                self.__power_states = PowerStates(self.__hw_revision, self.__fw_revision)

                # Find handles for battery, and power state
                battery_service = self.__device.getServiceByUUID(AssignedNumbers.battery_service)
                for ch in battery_service.getCharacteristics():
                    config_handle = self.__handles.INVALID
                    for desc in ch.getDescriptors():
                        if desc.uuid == AssignedNumbers.client_characteristic_configuration:
                            config_handle = desc.handle
                    log.info(f'Battery service characteristic {ch.uuid} {ch.uuid.getCommonName()} {ch.getHandle():02X} config {config_handle:02X}')
                    if ch.uuid == AssignedNumbers.battery_level:
                        self.__handles.BATTERY = ch.getHandle()
                        self.__handles.BATTERY_CONFIG = config_handle
                    elif ch.uuid == AssignedNumbers.battery_level_status:
                        self.__handles.POWER = ch.getHandle()
                        self.__handles.POWER_CONFIG = config_handle

                # Start remote notifications
                self.enable_notifications(self.__handles.BATTERY_CONFIG)
                self.enable_notifications(self.__handles.POWER_CONFIG)

                if self.__hw_revision >= HwRevisions.GEN_2:
                    if self.__fw_revision >= FwRevisions.GEN_2_0x0083:
                        self.enable_notifications(0x0037)
                        self.enable_notifications(0x003b)
                        self.enable_notifications(0x003f)
                        self.enable_notifications(0x0043)
                        self.enable_notifications(0x0047)
                        self.enable_notifications(0x004b)
                        self.enable_notifications(0x003a)
                        self.write_characteristic(0x004e, b'\xF0\xBC')  # magic 1
                        self.write_characteristic(0x004e, b'\xF0\xBB')  # magic 2
                    else: # Known to work for firmware version 0x0021
                        self.enable_notifications(0x003a)  # hid service | buttons
                        self.enable_notifications(0x003e)  # hid service | touch
                        self.enable_notifications(0x0036)  # hid service | audio
                        self.write_characteristic(0x004d, b'\xF0\x00')  # magic
                elif self.__hw_revision in (HwRevisions.GEN_1, HwRevisions.GEN_1_5):
                    self.enable_notifications(0x0024) # HID
                    self.write_characteristic(0x001d, b'\xAF') # magic 1
                else:
                    raise UnknownRemoteException(self.__hwr, self.__fw_revision, self.__pnp_info)

                self.__handle_battery(self.read_characteristic(self.__handles.BATTERY))
                self.__handle_power(self.read_characteristic(self.__handles.POWER))

                self.__ready = True
                while True:
                    self.__device.waitForNotifications(5)

            except (BTLEConnectError, BTLEException, BrokenPipeError) as e:
                log.info(f'Ignoring remote exception {e}. Will restart.')
                self.__listener.event_button(self, 0)  # release all keys
                time.sleep(0.5)

    def zero_touch(self):
        return Touch(self, (0, 0, 0, 0, 0))

    def has_motion(self):
        return self.__hw_revision in (HwRevisions.GEN_1, HwRevisions.GEN_1_5)

    def enable_motion(self, enable):
        if not self.has_motion():
            return False
        self.__last_keepalive = time.time()
        return self.write_characteristic(0x001d, b'\xA0\x01' if enable else b'\xA0\x00') is not None

    def read_characteristic(self, handle):
        return self.__device.readCharacteristic(handle)

    def write_characteristic(self, handle, data):
        return self.__device.writeCharacteristic(handle, data, withResponse=True)

    def enable_notifications(self, handle):
        self.write_characteristic(handle, b'\x01\x00')

    def handleNotification(self, handle, data):
        if not self.__ready: return
        if handle == self.__handles.BATTERY:
            self.__handle_battery(data)
        elif handle == self.__handles.POWER:
            self.__handle_power(data)
        elif handle == self.__handles.INPUT:
            if self.__hw_revision in (HwRevisions.GEN_1, HwRevisions.GEN_1_5):
                # Gen 1 multiplexes together all events - button, touch, and motion
                # byte 0 flags are:
                #    - 0x00 for a button only event (i.e. every event is a button event)
                #    - 0x01 for a touch event
                #    - 0x02 for a two touch event
                #    - 0x04 for a motion event
                flags = data[0]
                # byte 1 is button state
                self.__handle_button(data[1]) # Button event
                data = data[2:] # Skip the unknown status byte
                if not data: return
                if flags & 0x02: # two touch event
                    self.__handle_touchpad(data[:18])
                    data = data[18:]
                elif flags & 0x01: # one touch event
                    self.__handle_touchpad(data[:11])
                    data = data[11:]
                if not data: return
                if flags & 0x04: # Motion event
                    self.__handle_motion(data)
            else: # Gen 2, or later
                button = int.from_bytes(data, byteorder='little')
                self.__handle_button(button)
        elif handle == self.__handles.TOUCH:
            self.__handle_touchpad(data)
        elif handle == self.__handles.AUDIO:
            self.__handle_audio(data)

    def __handle_battery(self, data):
        self.__listener.event_battery(self, data[0])

    def __handle_power(self, data):
        #print(f'power {data[0]:02X}')
        if data[0] in (self.__power_states.CHARGING, self.__power_states.PLUGGED_IN):
            self.__listener.event_power(self, True)
        elif data[0] == self.__power_states.DISCHARGING:
            self.__listener.event_power(self, False)

    def __handle_button(self, button):
        if button != self.__last_button:
            self.__last_button = button
            self.__listener.event_button(self, button)

    def __handle_motion(self, data):
        now = time.time()
        if now - self.__last_keepalive > 50:
            self.write_characteristic(0x001d, b'\xf0\x7f')
            self.__last_keepalive = now
        # The gen 1 remote uses a Bosch BMA280 accelerometer.
        # It is speculated that the remote is exporting the values as is from the chip. But it
        # is not clear which values/how or where. So most of it remains unknown at the moment.
        # X axis - left to right across the narrow of the remote
        # Y axis - bottom to top across the length of the remote
        # Z axis - below to above the plain of the remote buttons
        # 0  - 2 bytes  - ???
        # 1  -          - ???
        # 2  - 2 bytes - accelerometer?
        # 3  -         - ^^^
        # 4  - 2 bytes - ???
        # 5  -         - ???
        # 6  - 2 bytes - accelerometer?
        # 7  -         - ^^^
        # 8  - 2 bytes - ???
        # 9  -         - ???
        # 10 - 2 bytes - accelerometer?
        # 11 -         - ???
        # 12 -
        # 13 -
        # 14 -  ??? Gyro?
        # 15 -
        # 16 -
        # 17 -
        # 18 - 2 bytes - gyro X, signed.
        # 19 -         - ^^^
        # 20 - 2 bytes - gyro Y, signed.
        # 21 -         - ^^^
        # 22 - 2 bytes - gyro Z, signed.
        # 23 -         - ^^^

        # Acceleromter reading interpretation according to the Bosch BMA280 accelerometer
        # datasheet. Not sure that it is relevant.
        def acc_value(x):
            a = (x[1] << 6) | (x[0] >> 2)
            if a & 0x2000:
                a -= 0x4000
            return a

        x = int.from_bytes(data[18:20], byteorder='little', signed=True)
        y = int.from_bytes(data[20:22], byteorder='little', signed=True)
        z = int.from_bytes(data[22:24], byteorder='little', signed=True)
        gyro = Vector((x, y, z))
        motion = MotionEvent(gyro)

        self.__listener.event_motion(self, motion)

    def __handle_touchpad(self, data):
        # Gen 1/2
        # 0  - 1 byte  - Always 0x32
        # 1  - 2 bytes - timestamp
        # 2  -         - gen 1 - 2461 ticks/sec
        #                gen 2 - 2000 ticks/sec
        # 3  - 1 byte  - ??? Sometimes, 0x01 for one touch, 0x10 for 'other' touch, 0x11 for two
        #                touches. Sometimes 0x00 after a while...
        # 4  - 2 bytes - X coordinate, signed.
        # 5  -           Increases right.
        #                Structured as so [byte 1 low nibble] | [byte 0] | [byte 1 high nibble]
        #                gen 1 - x = 0 at 16000 units right of center. Resolution is roughly 26180 units.
        #                gen 2 - x = 0 at 5760 units right of center. Resolution is roughly 21400 units.
        # 6  - 1 byte  - Y coordinate, signed.
        #                Increases up.
        #                gen 1 - y = 0 at 15 units above of center. Resolution is 106 units.
        #                gen 2 - y = 0 at 25 units above of center. Resolution is 80 units.
        # 7  - 1 byte  - touch point size 1
        # 8  - 1 byte  - touch point size 2 (Not clear how/why this is different from touch point size 1)
        # 9  - 1 byte  - pressure
        # 10 - 1 byte  - flags
        #              - bit 4 - (0x08) is touch ID. Usually, 1 for first touch, 0 for second touch.
        #                         Though with alternating touches the touch IDs can flip relative
        #                         to the earlier touch.
        # If second touch, bytes 11-17, inclusive, are added, and are as bytes 4-10 for the
        # second touch
        timestamp = int.from_bytes(data[1:3], byteorder='little', signed=False)
        touches = [self.__decode_finger(timestamp, data[4:11])]
        if len(data) > 11:
            touches.append(self.__decode_finger(timestamp, data[11:]))
        self.__listener.event_touches(self, touches)

    def __handle_audio(self, data):
        self.__listener.event_audio(self, data)

    def __decode_finger(self, timestamp, data):
        x = ((data[1] & 0x0f) << 12) | (data[0] << 4) | ((data[1] & 0xf0) >> 4)
        if x & 0x8000:
            x -= 0x10000
        if self.__hw_revision in (HwRevisions.GEN_1, HwRevisions.GEN_1_5):
            x += 16000
        else: # Gen 2 or greater
            x += 5760
        y = data[2]
        if y & 0x80:
            y -= 0x100
        if self.__hw_revision in (HwRevisions.GEN_1, HwRevisions.GEN_1_5):
            y += 15
        else: # Gen 2 or greater
            y += 25
        p = data[5]
        # Make it so first touch is usually 0, and second touch is usually 1.
        # Though, the order is not guaranteed for all touch sequences.
        id = 1 - ((data[6] & 0x08) >> 3)
        return Touch(self, (id, timestamp, x, y, p))
