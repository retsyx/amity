# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio, evdev, time
import evdev.ecodes as e
from evdev import KeyEvent
from watchdog.observers import Observer

from aconfig import config
from hdmi import Key

config.default('keyboard.required_keys', (e.KEY_ENTER, e.KEY_UP,
                                          e.KEY_RIGHT, e.KEY_DOWN,
                                          e.KEY_LEFT, e.KEY_BACK,
                                          e.KEY_VOLUMEUP, e.KEY_VOLUMEDOWN,
                                          e.KEY_MUTE, (e.KEY_POWER, e.KEY_SLEEP)))

config.default('keyboard.keymap', {
        e.KEY_ENTER : Key.SELECT.value,
        e.KEY_KPENTER : Key.SELECT.value,
        e.KEY_UP : Key.UP.value,
        e.KEY_RIGHT : Key.RIGHT.value,
        e.KEY_DOWN : Key.DOWN.value,
        e.KEY_LEFT : Key.LEFT.value,
        e.KEY_BACK : Key.BACK.value,
        e.KEY_VOLUMEUP : Key.VOLUME_UP.value,
        e.KEY_VOLUMEDOWN : Key.VOLUME_DOWN.value,
        e.KEY_CHANNELUP : Key.CHANNEL_UP.value,
        e.KEY_CHANNELDOWN : Key.CHANNEL_DOWN.value,
        e.KEY_MUTE : Key.TOGGLE_MUTE.value,
        e.KEY_POWER : Key.POWER.value,
        e.KEY_SLEEP : Key.POWER.value,
        e.KEY_MENU : Key.BACK.value,
        e.KEY_SEARCH : Key.DISPLAY_INFO.value,
        e.KEY_HOME : Key.ROOT_MENU.value,
        e.KEY_HOMEPAGE : Key.ROOT_MENU.value,
        e.KEY_REWIND : Key.REWIND.value,
        e.KEY_PLAYPAUSE : Key.SELECT.value,
        e.KEY_PLAY : Key.PLAY.value,
        e.KEY_PAUSE : Key.PAUSE.value,
        e.KEY_FASTFORWARD : Key.FAST_FORWARD.value,
        e.KEY_PROGRAM : Key.GUIDE.value,
        e.KEY_SETUP : Key.SETUP_MENU.value,
        e.KEY_VIDEO : Key.VOD.value,
        e.KEY_LIST : Key.CONTENTS_MENU.value,
        e.KEY_0 : Key.NUMBER_0.value,
        e.KEY_1 : Key.NUMBER_1.value,
        e.KEY_2 : Key.NUMBER_2.value,
        e.KEY_3 : Key.NUMBER_3.value,
        e.KEY_4 : Key.NUMBER_4.value,
        e.KEY_5 : Key.NUMBER_5.value,
        e.KEY_6 : Key.NUMBER_6.value,
        e.KEY_7 : Key.NUMBER_7.value,
        e.KEY_8 : Key.NUMBER_8.value,
        e.KEY_9 : Key.NUMBER_9.value,
        e.KEY_BLUE : Key.F1.value,
        e.KEY_RED : Key.F2.value,
        e.KEY_GREEN: Key.F3.value,
        e.KEY_YELLOW : Key.F4.value,
    })

def isiterable(o):
    try:
        iter(o)
        return True
    except:
        return False

class Keyboard(object):
    required_keys = config['keyboard.required_keys']
    @classmethod
    def is_keyboard(self, dev):
        caps = dev.capabilities()
        supported_keys = caps.get(e.EV_KEY)
        if not supported_keys:
            return False
        for keys in Keyboard.required_keys:
            if isiterable(keys):
                # This is a list of alternative keys, of which at least one needs to be supported
                if not any(key in supported_keys for key in keys):
                    return False
            else:
                # This is a single required key
                if keys not in supported_keys:
                    return False
        return True

    def __init__(self, loop, pipe):
        self.devices = []
        self.loop = loop
        self.pipe = pipe
        self.taskit = tools.Tasker('Keyboard')
        self.listen_to_all_devices()
        self.start_input_monitor()

    def wait_on(self):
        return self.taskit.tasks

    def start_input_monitor(self):
        path = '/dev/input/'
        log.info(f'Monitoring {path} for new input devices')
        self.observer = Observer()
        self.observer.schedule(self, path, recursive=False)
        self.observer.start()

    def dispatch(self, event):
        if event.event_type == 'created' and not event.is_directory:
            log.info(f'New input event source {event.src_path}')

            # This sleep is obviously a hack...
            # The issue is that the device is initially created with permissions
            # that don't allow us to access it. It's chmoded after creation. In theory, we need
            # to monitor the create, and then the modification messages to hit at the right time.
            # That's an ugly can of worms that is best avoided with this very generous sleep on the
            # observer's thread.
            time.sleep(.5)
            self.loop.call_soon_threadsafe(self.listen_device_at_path, event.src_path)
        elif event.event_type == 'deleted' and not event.is_directory:
            log.info(f'Input event source delete {event.src_path}')

    def list_keyboards(self):
        devices = [evdev.InputDevice(path) for path in evdev.list_devices()]
        devices = [device for device in devices if Keyboard.is_keyboard(device)]
        return devices

    keymap = config['keyboard.keymap']

    async def listen_device_task(self, device):
        path = device.path
        try:
            async for event in device.async_read_loop():
                if event.type != e.EV_KEY:
                    continue
                hkey = self.keymap.get(event.code, None)
                if hkey is None:
                    continue
                if event.value == KeyEvent.key_down:
                    log.info(f'Key press {hkey}')
                    if self.pipe:
                        self.pipe.key_press(hkey)
                elif event.value == KeyEvent.key_up:
                    log.info(f'Key release {hkey}')
                    if self.pipe:
                        self.pipe.key_release(hkey)
        except OSError as exc:
            log.info(f'Stopped listening to device {path}')

    def listen_to_all_devices(self):
        devices = self.list_keyboards()
        for device in devices:
            self.listen_device(device)

    def listen_device_at_path(self, path):
        self.listen_device(evdev.InputDevice(path))

    def listen_device(self, device):
        if not Keyboard.is_keyboard(device):
            log.info(f'Not listening to non-Keyboard device {device}')
            return
        log.info(f'Listening to device {device}')
        self.taskit(self.listen_device_task(device))

async def main():
    loop = asyncio.get_event_loop()
    kb = Keyboard(loop, None)
    while True:
        await asyncio.gather(*list(kb.wait_on()))
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())
