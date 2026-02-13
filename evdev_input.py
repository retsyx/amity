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

class EvdevInput(object):
    def __init__(self, handlers, loop):
        self.devices = []
        self.handlers = handlers
        self.loop = loop
        self.taskit = tools.Tasker('EvdevInput')
        self.listen_to_all_devices()
        self.start_input_monitor()

    def wait_on(self):
        tasks = set(self.taskit.tasks)
        for handler in self.handlers:
            tasks.update(handler.wait_on())
        return tasks

    def start_input_monitor(self):
        path = '/dev/input/'
        log.info(f'Monitoring {path} for new input devices')
        self.observer = Observer()
        self.observer.schedule(self, path, recursive=False)
        self.observer.start()

    # Watchdog handler must be called dispatch()
    def dispatch(self, event):
        if event.event_type == 'created' and not event.is_directory:
            log.info(f'New input event source {event.src_path}')

            # This sleep is obviously a hack...
            # The issue is that the device is initially created with permissions
            # that don't allow us to access it. It's chmoded after creation. In theory, we need
            # to monitor the create, and then the modification messages to hit at the right time.
            # That's an ugly can of worms that is best avoided with this very generous sleep on the
            # observer's thread.
            time.sleep(.75)
            self.loop.call_soon_threadsafe(self.listen_device_at_path, event.src_path)
        elif event.event_type == 'deleted' and not event.is_directory:
            log.info(f'Input event source delete {event.src_path}')

    async def listen_device_task(self, device, handler):
        path = device.path
        log.info(f'{handler.name}: Listening to device {path}')
        try:
            async for event in device.async_read_loop():
                await handler.dispatch_input_event(event)
        except OSError as exc:
            log.info(f'{handler.name}: Stopped listening to device {path}')

    def listen_to_all_devices(self):
        for path in evdev.list_devices():
            self.listen_device_at_path(path)

    def listen_device_at_path(self, path):
        device = evdev.InputDevice(path)
        for handler in self.handlers:
            if handler.probe(device):
                self.taskit(self.listen_device_task(device, handler))

async def main():
    loop = asyncio.get_event_loop()
    inp = EvdevInput([], loop)
    while True:
        await asyncio.gather(*list(inp.wait_on()))
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())
