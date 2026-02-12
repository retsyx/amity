# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import evdev.ecodes as e

import asyncio, time
from aconfig import config
from hdmi import Key

# SolarCell is very odd. It is exposed as 3 devices in Linux, named:
# 'bluez-hog-device Keyboard'
# 'bluez-hog-device Mouse'
# 'bluez-hog-device'
# The keyboard and mouse seem to be inert while the anonymous device sends key press data as
# type=EV_REL, code=REL_MISC events with arbitrary key codes corresponding to the pressed keys.
# In addition, repeat is performed by continually spamming the key code until it is released.
# There is no indication of a button release. As a result, the only way to declare a button
# release is with a timeout.

config.default('solarcell.keymap', {
    0x02 : Key.POWER,
    0x07 : Key.VOLUME_UP,
    0x0B : Key.VOLUME_DOWN,
    0x0F : Key.TOGGLE_MUTE,
    0x10 : Key.CHANNEL_DOWN,
    0x12 : Key.CHANNEL_UP,
    0x4F : Key.GUIDE,
    0x58 : Key.BACK,
    0x60 : Key.UP,
    0x61 : Key.DOWN,
    0x62 : Key.RIGHT,
    0x65 : Key.LEFT,
    0x68 : Key.SELECT,
    #0x6A : Key.???                 # Magic Button (recommendations)
    0x79 : Key.ROOT_MENU,           # Home
    0xA0 : Key.DISPLAY_INFO,        # Microphone
    0xB4 : Key.F2,                  # Activity Samsung TV Plus
    0xB9 : Key.PAUSE_PLAY,          # Pause
    0xD2 : Key.SETUP_MENU,          # Settings
    0xDF : Key.F4,                  # Activity Disney+
    0xEF : Key.SUB_PICTURE,         # Picture-in-Picture
    0xF3 : Key.F5,                  # Activity Netflix
    0xF4 : Key.F3,                  # Activity Prime Video
    0xFA : Key.F4,                  # Activity YouTube
})

config.default('solarcell.repeat.timeout_sec', 0.15)
config.default('solarcell.repeat.sleep_sec', 0.075)

class Handler(object):
    def __init__(self, pipe):
        self.name = 'SolarCell'
        self.devices = []
        self.pipe = pipe
        self.taskit = tools.Tasker('Keyboard')
        self.taskit(self.repeat_monitor_task())
        self.last_key = Key.NO_KEY
        self.last_timestamp = 0
        self.key_event = asyncio.Event()

    def wait_on(self):
        return set()

    def probe(self, dev):
        # It's not clear how to definitively identify the SolarCell device of interest.
        # For now the conditions are:
        # 1. The vendor ID is 0x5D
        # 2. The product ID is 1...
        # 3. Device capabilities are strictly:
        #    {0: [0, 2], 2: [9]}
        #    which translates to evedev.ecodes
        #    EV_SYN : [SYN_REPORT, SYN_MT_REPORT],
        #    EV_REL : [REL_MISC]

        # Samsung vendor ID
        if dev.info.vendor != 0x5d:
            return False
        # Product ID
        if dev.info.product != 1:
            return False
        # Capabilities
        caps = dev.capabilities()
        if len(caps.keys()) > 2:
            return False
        if caps.get(e.EV_SYN) != [e.SYN_REPORT, e.SYN_MT_REPORT]:
            return False
        if caps.get(e.EV_REL) != [e.REL_MISC]:
            return False
        return True

    keymap = config['solarcell.keymap']

    async def dispatch_input_event(self, event):
        if event.type != e.EV_REL:
            return
        if event.code != e.REL_MISC:
            return
        hkey = self.keymap.get(event.value, None)
        if hkey is None:
            log.info(f'Unhandled key value {event.value:02X}')
            return

        # Note the time of the last key event
        self.last_timestamp = time.time()
        if self.last_key != hkey:
            if self.last_key == Key.NO_KEY:
                # Transitioning from quiet to key presses, start the key release monitor
                self.key_event.set()
            else:
                # Transitioning from one key to another, release the previous key
                if self.pipe:
                    self.pipe.key_release(self.last_key)
            self.last_key = hkey
            log.info(f'Key press {hkey:02X}')
            # Press the key
            if self.pipe:
                self.pipe.key_press(hkey)

    async def repeat_monitor_task(self):
        timeout_sec = config['solarcell.repeat.timeout_sec']
        sleep_sec = config['solarcell.repeat.sleep_sec']
        while True:
            # Wait for signal that key presses have begun
            await self.key_event.wait()
            self.key_event.clear()
            # Busy wait for key events to stop
            while time.time() - self.last_timestamp < timeout_sec:
                await asyncio.sleep(sleep_sec)
            # Events are done for now. Release the key, and start from the top...
            self.pipe.key_release(self.last_key)
            self.last_key = Key.NO_KEY


async def main():
    import evdev_input
    h = Handler(None)
    loop = asyncio.get_event_loop()
    inp = evdev_input.EvdevInput([h], loop)
    while True:
        await asyncio.gather(*list(inp.wait_on()))
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())
