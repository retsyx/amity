# Copyright 2024-2025.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio
from typing import Any

import evdev
import evdev.ecodes as e
from evdev import InputDevice, KeyEvent

from aconfig import config
from hdmi import Key
from messaging import Pipe

config.default('keyboard.required_keys', ((e.KEY_ENTER, e.KEY_SELECT), e.KEY_UP,
                                          e.KEY_RIGHT, e.KEY_DOWN,
                                          e.KEY_LEFT, (e.KEY_BACK, e.KEY_ESC),
                                          e.KEY_VOLUMEUP, e.KEY_VOLUMEDOWN,
                                          e.KEY_MUTE, (e.KEY_POWER, e.KEY_SLEEP)))

config.default('keyboard.keymap', {
        e.KEY_SELECT : Key.SELECT,
        e.KEY_ENTER : Key.SELECT,
        e.KEY_KPENTER : Key.SELECT,
        e.KEY_UP : Key.UP,
        e.KEY_RIGHT : Key.RIGHT,
        e.KEY_DOWN : Key.DOWN,
        e.KEY_LEFT : Key.LEFT,
        e.KEY_BACK : Key.BACK,
        e.KEY_ESC : Key.BACK,
        e.KEY_VOLUMEUP : Key.VOLUME_UP,
        e.KEY_VOLUMEDOWN : Key.VOLUME_DOWN,
        e.KEY_CHANNELUP : Key.CHANNEL_UP,
        e.KEY_CHANNELDOWN : Key.CHANNEL_DOWN,
        e.KEY_MUTE : Key.TOGGLE_MUTE,
        e.KEY_POWER : Key.POWER,
        e.KEY_SLEEP : Key.POWER,
        e.KEY_MENU : Key.BACK,
        e.KEY_SEARCH : Key.DISPLAY_INFO,
        e.KEY_HOME : Key.ROOT_MENU,
        e.KEY_HOMEPAGE : Key.ROOT_MENU,
        e.KEY_REWIND : Key.REWIND,
        e.KEY_PLAYPAUSE : Key.PAUSE_PLAY,
        e.KEY_PLAY : Key.PLAY,
        e.KEY_PAUSE : Key.PAUSE,
        e.KEY_FASTFORWARD : Key.FAST_FORWARD,
        e.KEY_PROGRAM : Key.GUIDE,
        e.KEY_SETUP : Key.SETUP_MENU,
        e.KEY_VIDEO : Key.VOD,
        e.KEY_LIST : Key.CONTENTS_MENU,
        e.KEY_0 : Key.NUMBER_0,
        e.KEY_1 : Key.NUMBER_1,
        e.KEY_2 : Key.NUMBER_2,
        e.KEY_3 : Key.NUMBER_3,
        e.KEY_4 : Key.NUMBER_4,
        e.KEY_5 : Key.NUMBER_5,
        e.KEY_6 : Key.NUMBER_6,
        e.KEY_7 : Key.NUMBER_7,
        e.KEY_8 : Key.NUMBER_8,
        e.KEY_9 : Key.NUMBER_9,
        e.KEY_BLUE : Key.F1,
        e.KEY_RED : Key.F2,
        e.KEY_GREEN: Key.F3,
        e.KEY_YELLOW : Key.F4,
        e.KEY_F8 : Key.SETUP_MENU, # Vizio XRT270
        e.KEY_WWW : Key.DISPLAY_INFO, # Vizio XRT270 Microphone key
        e.KEY_LEFTBRACE : Key.SET_INPUT, # Vizio XRT270 Input key
        e.KEY_UNKNOWN : Key.F1, # Vizio XRT270 Star and Sling keys
        e.KEY_NEXTSONG : Key.F2, # Vizio XRT270 Netflix key
        e.KEY_PREVIOUSSONG : Key.F3, # Vizio XRT270 Prime Video key
        e.KEY_F1 : Key.F1,
        e.KEY_F2 : Key.F2,
        e.KEY_F3 : Key.F3,
        e.KEY_F4 : Key.F4,
        e.KEY_F14 : Key.F4, # Vizio XRT270 Disney+ key
        e.KEY_F19 : Key.F5, # Vizio XRT270 iHeart Radio key
        e.KEY_F20 : Key.F6, # Vizio XRT270 Xumo Play key
        e.KEY_EDIT : Key.F7, # Vizio XRT270 Watch Free key
        e.KEY_CAMERA_ACCESS_DISABLE : Key.F1, # Google TV Remote YouTube key
        e.KEY_CAMERA_ACCESS_TOGGLE : Key.F2, # Google TV Remote Netflix key
        e.KEY_SPREADSHEET : Key.F3, # Google TV Remote star key
    })

config.default('keyboard.battery.monitor.enable', True)
config.default('keyboard.battery.monitor.period_sec', 3600)

class Handler:
    def __init__(self, pipe: Pipe | None) -> None:
        self.name = 'Keyboard'
        self.pipe = pipe
        self.taskit = tools.Tasker('Keyboard')
        self.taskit(self.battery_monitor_task())

    def wait_on(self) -> set[asyncio.Task[Any]]:
        return self.taskit.tasks

    required_keys = config['keyboard.required_keys']

    def probe(self, dev: InputDevice) -> bool:
        caps = dev.capabilities()
        supported_keys = caps.get(e.EV_KEY)
        if not supported_keys:
            return False
        for keys in self.required_keys:
            if tools.isiterable(keys):
                # This is a list of alternative keys, of which at least one needs to be supported
                if not any(key in supported_keys for key in keys):
                    return False
            else:
                # This is a single required key
                if keys not in supported_keys:
                    return False
        return True

    keymap = config['keyboard.keymap']

    async def dispatch_input_event(self, event: evdev.InputEvent) -> None:
        if event.type != e.EV_KEY:
            return
        hkey = self.keymap.get(event.code, None)
        if hkey is None:
            log.debug(f'Unhandled key {event.code:02X}')
            return
        if event.value == KeyEvent.key_down:
            log.info(f'Key press {hkey:02X}')
            if self.pipe:
                self.pipe.key_press(hkey)
        elif event.value == KeyEvent.key_up:
            log.info(f'Key release {hkey:02X}')
            if self.pipe:
                self.pipe.key_release(hkey)

    async def battery_monitor_task(self) -> None:
        if not config['keyboard.battery.monitor.enable']:
            log.info('Keyboard battery monitoring disabled')
            return
        mac = config['keyboard.mac']
        if mac is None:
            log.info('No keyboard mac. Not monitoring battery')
            return
        period_sec = config['keyboard.battery.monitor.period_sec']
        log.info(f'Keyboard battery monitoring period {period_sec}s')
        while True:
            proc = await asyncio.create_subprocess_shell(f'/usr/bin/bluetoothctl info {mac}',
                                                        stdout=asyncio.subprocess.PIPE,
                                                        stderr=asyncio.subprocess.PIPE)
            stdout, stderr = await proc.communicate()
            log.info(f'bluetoothctl info status {proc.returncode}')
            log.debug(f'stdout:\n{stdout.decode()}\nstderr:\n{stderr.decode()}')
            if stdout:
                for line in stdout.decode().splitlines():
                    if 'Battery Percentage' not in line:
                        continue
                    try:
                        battery_level = int(line.split(':')[1].strip().split(' ')[0][2:], 16)
                        log.info(f'Battery level {battery_level}')
                    except ValueError as e:
                        log.info(f'Unable to parse battery level line {line}')
                        battery_level = None
                    if battery_level:
                        if self.pipe:
                            self.pipe.battery_state(battery_level, False)
                    break
            await asyncio.sleep(period_sec)

async def main() -> None:
    import evdev_input
    h = Handler(None)
    loop = asyncio.get_event_loop()
    inp = evdev_input.EvdevInput([h], loop)
    while True:
        await asyncio.gather(*list(inp.wait_on()))
        await asyncio.sleep(1)

if __name__ == '__main__':
    asyncio.run(main())
