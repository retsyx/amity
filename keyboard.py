# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio
import evdev.ecodes as e
from evdev import KeyEvent

from aconfig import config
from hdmi import Key

config.default('keyboard.required_keys', ((e.KEY_ENTER, e.KEY_SELECT), e.KEY_UP,
                                          e.KEY_RIGHT, e.KEY_DOWN,
                                          e.KEY_LEFT, e.KEY_BACK,
                                          e.KEY_VOLUMEUP, e.KEY_VOLUMEDOWN,
                                          e.KEY_MUTE, (e.KEY_POWER, e.KEY_SLEEP)))

config.default('keyboard.keymap', {
        e.KEY_SELECT : Key.SELECT.value,
        e.KEY_ENTER : Key.SELECT.value,
        e.KEY_KPENTER : Key.SELECT.value,
        e.KEY_UP : Key.UP.value,
        e.KEY_RIGHT : Key.RIGHT.value,
        e.KEY_DOWN : Key.DOWN.value,
        e.KEY_LEFT : Key.LEFT.value,
        e.KEY_BACK : Key.BACK.value,
        e.KEY_ESC : Key.BACK.value,
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
        e.KEY_PLAYPAUSE : Key.PAUSE_PLAY.value,
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
        e.KEY_F8 : Key.SETUP_MENU.value, # Vizio XRT270
        e.KEY_WWW : Key.DISPLAY_INFO.value, # Vizio XRT270 Microphone key
        e.KEY_LEFTBRACE : Key.SET_INPUT.value, # Vizio XRT270 Input key
        e.KEY_UNKNOWN : Key.F1.value, # Vizio XRT270 Star and Sling keys
        e.KEY_NEXTSONG : Key.F2.value, # Vizio XRT270 Netflix key
        e.KEY_PREVIOUSSONG : Key.F3.value, # Vizio XRT270 Prime Video key
        e.KEY_F1 : Key.F1.value,
        e.KEY_F2 : Key.F2.value,
        e.KEY_F3 : Key.F3.value,
        e.KEY_F4 : Key.F4.value,
        e.KEY_F14 : Key.F4.value, # Vizio XRT270 Disney+ key
        e.KEY_F19 : Key.F5.value, # Vizio XRT270 iHeart Radio key
        e.KEY_F20 : Key.F6.value, # Vizio XRT270 Xumo Play key
        e.KEY_EDIT : Key.F7.value, # Vizio XRT270 Watch Free key
        e.KEY_CAMERA_ACCESS_DISABLE : Key.F1.value, # Google TV Remote YouTube key
        e.KEY_CAMERA_ACCESS_TOGGLE : Key.F2.value, # Google TV Remote Netflix key
        e.KEY_SPREADSHEET : Key.F3.value, # Google TV Remote star key
    })

config.default('keyboard.battery.monitor.enable', True)
config.default('keyboard.battery.monitor.period_sec', 3600)

def isiterable(o):
    try:
        iter(o)
        return True
    except:
        return False

class Handler(object):
    def __init__(self, pipe):
        self.name = 'Keyboard'
        self.pipe = pipe
        self.taskit = tools.Tasker('Keyboard')
        self.taskit(self.battery_monitor_task())

    def wait_on(self):
        return self.taskit.tasks

    required_keys = config['keyboard.required_keys']

    def probe(self, dev):
        caps = dev.capabilities()
        supported_keys = caps.get(e.EV_KEY)
        if not supported_keys:
            return False
        for keys in self.required_keys:
            if isiterable(keys):
                # This is a list of alternative keys, of which at least one needs to be supported
                if not any(key in supported_keys for key in keys):
                    return False
            else:
                # This is a single required key
                if keys not in supported_keys:
                    return False
        return True

    keymap = config['keyboard.keymap']

    async def dispatch_input_event(self, event):
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

    async def battery_monitor_task(self):
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
                        log.info(f'Unable to parse batter level line {line}')
                        battery_level = None
                    if battery_level:
                        if self.pipe:
                            self.pipe.battery_state(battery_level, False)
                    break
            await asyncio.sleep(period_sec)

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
