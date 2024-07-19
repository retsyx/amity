# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio, evdev, sys, time
import evdev.ecodes as e
from evdev import KeyEvent
from watchdog.observers import Observer

from hdmi import Key

class Keyboard(object):
    required_keys = (e.KEY_ENTER, e.KEY_UP, e.KEY_RIGHT, e.KEY_DOWN, e.KEY_LEFT, e.KEY_BACK,
                     e.KEY_VOLUMEUP, e.KEY_VOLUMEDOWN, e.KEY_MUTE, e.KEY_POWER)
    @classmethod
    def is_keyboard(self, dev):
        caps = dev.capabilities()
        supported_keys = caps.get(e.EV_KEY)
        if not supported_keys:
            return False
        for key in Keyboard.required_keys:
            if key not in supported_keys:
                return False
        return True

    def __init__(self, loop, pipe):
        self.devices = []
        self.loop = loop
        self.pipe = pipe
        self.tasks = set()
        self.listen_to_all_devices()
        self.start_input_monitor()

    def wait_on(self):
        return self.tasks

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

    keymap = {
        e.KEY_ENTER : Key.SELECT,
        e.KEY_KPENTER : Key.SELECT,
        e.KEY_UP : Key.UP,
        e.KEY_RIGHT : Key.RIGHT,
        e.KEY_DOWN : Key.DOWN,
        e.KEY_LEFT : Key.LEFT,
        e.KEY_BACK : Key.BACK,
        e.KEY_VOLUMEUP : Key.VOLUME_UP,
        e.KEY_VOLUMEDOWN : Key.VOLUME_DOWN,
        e.KEY_MUTE : Key.TOGGLE_MUTE,
        e.KEY_POWER : Key.POWER,
        e.KEY_MENU : Key.BACK,
        e.KEY_SEARCH : Key.DISPLAY_INFO,
        e.KEY_HOMEPAGE : Key.ROOT_MENU,
        e.KEY_REWIND : Key.REWIND,
        e.KEY_PLAYPAUSE : Key.PAUSE_PLAY,
        e.KEY_FASTFORWARD : Key.FAST_FORWARD,
        e.KEY_PROGRAM : Key.GUIDE
    }

    def taskit(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.check_task)

    def check_task(self, task):
        self.tasks.discard(task)
        exc = task.exception()
        if exc is not None:
            log.info(f'Task exception {exc}')
            sys.exit(1)

    async def listen_device_task(self, device):
        path = device.path
        try:
            async for event in device.async_read_loop():
                if event.type != e.EV_KEY:
                    continue
                hkey = self.keymap.get(event.code)
                if hkey is None:
                    continue
                if event.value == KeyEvent.key_down:
                    log.info(f'Key press {hkey.name}')
                    if self.pipe:
                        self.pipe.key_press(hkey)
                elif event.value == KeyEvent.key_up:
                    log.info(f'Key release {hkey.name}')
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
        await asyncio.gather(*list(kb.tasks))
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())
