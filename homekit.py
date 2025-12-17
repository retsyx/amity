# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio, io, qrcode, signal

from PIL import Image
from pyhap.accessory import Accessory
from pyhap.accessory_driver import AccessoryDriver
from pyhap.const import CATEGORY_TELEVISION

from hdmi import Key

from aconfig import config

config.default('homekit.keymap',
                {
                    0 : Key.REWIND.value,
                    1 : Key.FAST_FORWARD.value,
                    2 : Key.FORWARD.value,
                    3 : Key.BACKWARD.value,
                    4 : Key.UP.value,
                    5 : Key.DOWN.value,
                    6 : Key.LEFT.value,
                    7 : Key.RIGHT.value,
                    8 : Key.SELECT.value,
                    9 : Key.BACK.value,
                    10 : Key.ROOT_MENU.value,
                    11 : Key.PAUSE_PLAY.value,
                    # 15 is officially display info. However, info doesn't seem to be as useful as
                    # the root menu button which Apple uses for ATV instead of info.
                    15 : Key.ROOT_MENU.value, # Key.DISPLAY_INFO.value,
                })


class TV(Accessory):
    category = CATEGORY_TELEVISION

    NAME = 'Amity'

    def __init__(self, *args, **kwargs):
        self.activity_names = kwargs.pop('activity_names', None)
        self.pipe = kwargs.pop('pipe', None)
        super(TV, self).__init__(*args, **kwargs)

        self.keymap = config['homekit.keymap']

        self.set_info_service(
            manufacturer='Amity',
            model='Amity',
            firmware_revision='1.0',
            serial_number='1'
        )

        tv_service = self.add_preload_service(
            'Television', ['Name',
                           'ConfiguredName',
                           'Active',
                           'ActiveIdentifier',
                           'RemoteKey',
                           'SleepDiscoveryMode']
        )
        self._active = tv_service.configure_char(
            'Active', value=0,
            setter_callback=self._on_active_changed,
        )
        self._active_identifier = tv_service.configure_char(
            'ActiveIdentifier', value=0,
            setter_callback=self._on_active_identifier_changed,
        )
        tv_service.configure_char(
            'RemoteKey', setter_callback=self._on_remote_key,
        )
        tv_service.configure_char('Name', value=self.NAME)
        # TODO: implement persistence for ConfiguredName
        tv_service.configure_char('ConfiguredName', value=self.NAME)
        tv_service.configure_char('SleepDiscoveryMode', value=1)

        source_type = 3
        for idx, source_name in enumerate(self.activity_names):
            input_source = self.add_preload_service('InputSource', ['Name', 'Identifier'])
            input_source.configure_char('Name', value=source_name)
            input_source.configure_char('Identifier', value=idx)
            # TODO: implement persistence for ConfiguredName
            input_source.configure_char('ConfiguredName', value=source_name)
            input_source.configure_char('InputSourceType', value=source_type)
            input_source.configure_char('IsConfigured', value=1)
            input_source.configure_char('CurrentVisibilityState', value=0)

            tv_service.add_linked_service(input_source)

        tv_speaker_service = self.add_preload_service(
            'TelevisionSpeaker', ['Active',
                                  'Mute',
                                  'VolumeControlType',
                                  'VolumeSelector']
        )
        tv_speaker_service.configure_char('Active', value=1)
        # Set relative volume control
        tv_speaker_service.configure_char('VolumeControlType', value=1)
        tv_speaker_service.configure_char(
            'Mute', setter_callback=self._on_mute)
        tv_speaker_service.configure_char(
            'VolumeSelector', setter_callback=self._on_volume_selector)

        tv_service.add_linked_service(tv_speaker_service)

        battery_service = self.add_preload_service(
            'BatteryService',
            [
                'BatteryLevel',
                'ChargingState',
                'StatusLowBattery',
            ])
        self._battery_level = battery_service.configure_char(
            'BatteryLevel', value=100)
        self._charging_state = battery_service.configure_char(
            'ChargingState', value=0)
        self._status_low_battery = battery_service.configure_char(
            'StatusLowBattery', value=0)

        if self.pipe is not None:
            self.pipe.start_client_task(self)

    async def server_notify_set_activity(self, index):
        if index == -1: # Off
            log.info('Notified of standby')
            self._active.set_value(0)
        else:
            log.info(f'Notified of activity {self.activity_names[index]}')
            self._active.set_value(1)
            self._active_identifier.set_value(index)

    async def server_notify_battery_state(self, level, is_charging, is_low):
        log.info(f'Notified of battery state {level} {is_charging} {is_low}')
        self._battery_level.set_value(level)
        self._charging_state.set_value(1 if is_charging else 0)
        self._status_low_battery.set_value(1 if is_low else 0)

    def _on_active_changed(self, value):
        log.info(f'Active {value}')
        if value:
            i = self._active_identifier.get_value()
            log.info(f'Setting activity {self.activity_names[i]}')
        else:
            log.info('Standby')
            i = -1
        if self.pipe is None:
            log.info('No pipe')
            return
        self.pipe.set_activity(i)

    def _on_active_identifier_changed(self, value):
        log.info(f'Active identifier {value}')
        i = value
        log.info(f'Setting activity {self.activity_names[i]}')
        if self.pipe is None:
            log.info('No pipe')
            return
        self.pipe.set_activity(i)

    def _on_remote_key(self, value):
        key = self.keymap.get(value, None)
        if key is None:
            log.info(f'Unknown remote key {value}')
            return
        log.info(f'Remote key {value} {key}')
        self.key_press(key)

    def _on_mute(self, value):
        log.info(f'Mute {value}')
        self.key_press(Key.TOGGLE_MUTE)

    def _on_volume_selector(self, value):
        log.info(f'Volume {value}')
        if value == 0:
            self.key_press(Key.VOLUME_UP)
        else:
            self.key_press(Key.VOLUME_DOWN)

    def key_press(self, key):
        log.info(f'Press key {key}')
        if self.pipe is None:
            log.info('No pipe')
            return
        self.pipe.key_press(key, 1)


class HomeKit(object):
    def __init__(self, activity_names, loop, pipe):
        self.driver = AccessoryDriver(port=51826,
                    persist_file='var/homekit/state',
                    loop=loop)
        self.accessory = TV(self.driver, 'Amity', activity_names=activity_names, pipe=pipe)
        self.driver.add_accessory(accessory=self.accessory)

    async def start(self):
        log.info('Starting')
        await self.driver.async_start()
        if self.driver.state.paired:
            s = 'Paired'
            img = Image.new('RGB', (100, 100), color='black')
        else:
            s, img = self.setup_info()
        # var/homekit/code is used as a latch to monitor changes to homekit status in
        # homekit_tool.py which, in turn, is used by management.py. So ensure that var/homekit/code
        # is always the last thing to be modified as a signal that all changes have been made.
        img.save('var/homekit/code.png')
        log.info(s)
        with open('var/homekit/code', 'wb') as file:
            file.write(s.encode('utf-8'))

    def setup_info(self):
        """Generate setup message string
        """
        pincode = self.driver.state.pincode.decode()
        xhm_uri = self.accessory.xhm_uri()
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_Q)
        qr.add_data(xhm_uri)
        qr.make(fit=True)
        message = 'Scan this code with the Home app on your iOS device:\n\n'
        with io.StringIO() as f:
            qr.print_ascii(out=f, invert=True)
            f.seek(0)
            message += f.read() + '\n'
        message += f'Or enter this code in the Home app on your iOS device: {pincode}'
        img = qr.make_image()
        return message, img

async def main():
    activity_names = ('Watch TV', 'Play PS5', 'Play Switch', 'Play Music')
    hk = HomeKit(activity_names, asyncio.get_running_loop(), None)
    signal.signal(signal.SIGTERM, hk.driver.signal_handler)
    await hk.start()
    while True:
        await asyncio.sleep(10)

if __name__ == '__main__':
    asyncio.run(main())
