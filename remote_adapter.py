# Copyright 2024-2025.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This code is derived from code written by Yanndroid (https://github.com/Yanndroid)

import tools

log = tools.logger(__name__)

import gestures, remote
from remote import HwRevisions
from hdmi import Key


class Adapter(remote.RemoteListener):
    def __init__(self, pipe):
        self.pipe = pipe
        self.button_state = 0
        self.swipe_recognizer = gestures.SwipeRecognizer(self.swipe_callback)
        self.dpad_emulator = gestures.DPadEmulator()
        self.multitap_recognizer = gestures.MultiTapRecognizer(1, 3, self.multitap_callback)
        self.battery_level = 100
        self.is_charging = False

    def event_button(self, remote, buttons: int):
        btns = remote.profile.buttons

        keymap = {
            btns.HOME : Key.ROOT_MENU,
            btns.VOLUME_UP : Key.VOLUME_UP,
            btns.VOLUME_DOWN : Key.VOLUME_DOWN,
            btns.MUTE : Key.TOGGLE_MUTE,
            btns.SELECT : Key.SELECT,
            btns.BACK : Key.BACK,
            btns.PLAY_PAUSE : Key.PAUSE_PLAY,
            btns.UP : Key.UP,
            btns.RIGHT : Key.RIGHT,
            btns.DOWN : Key.DOWN,
            btns.LEFT : Key.LEFT,
            btns.POWER : Key.POWER,
            btns.SIRI : Key.DISPLAY_INFO,
        }

        log.info(f'Buttons {buttons:04X}')
        dpad_buttons = self.dpad_emulator.buttons(remote, buttons)
        if buttons != dpad_buttons:
            buttons = dpad_buttons
            log.info(f'Buttons dpad {buttons:04X}')

        pressed_buttons = buttons & ~self.button_state
        released_buttons = self.button_state & ~buttons
        self.button_state = buttons

        for button in keymap.keys():
            if pressed_buttons & button:
                hkey = keymap[button]
                log.info(f'Key press {hkey.name}')
                if self.pipe:
                    self.pipe.key_press(hkey)
            if released_buttons & button:
                hkey = keymap[button]
                log.info(f'Key release {hkey.name}')
                if self.pipe:
                    self.pipe.key_release(hkey)

    def swipe_callback(self, recognizer, event):
        if not (event.type & gestures.EventType.Detected):
            return
        if self.button_state != 0:
            log.info(f'Swipe with active buttons {self.button_state:04X}. Ignoring!')
            return
        if event.x < 0:
            counter = -event.x
            hkey = Key.LEFT
        elif event.x > 0:
            counter = event.x
            hkey = Key.RIGHT
        elif event.y < 0:
            counter = -event.y
            hkey = Key.DOWN
        else: # event.y > 0
            counter = event.y
            hkey = Key.UP
        log.info(f'Swiping {hkey.name} {counter} times')
        if self.pipe:
            self.pipe.key_press(hkey, counter)

    def multitap_callback(self, recognizer, event):
        if not (event.type & gestures.EventType.Detected):
            return
        buttons = self.button_state | event.remote.profile.buttons.POWER
        self.event_button(event.remote, buttons)
        buttons = self.button_state & ~event.remote.profile.buttons.POWER
        self.event_button(event.remote, buttons)

    def event_touches(self, remote, touches):
        self.swipe_recognizer.touches(remote, touches)
        self.dpad_emulator.touches(remote, touches)
        if remote.profile.hw_revision in (HwRevisions.GEN_1, HwRevisions.GEN_1_5):
            self.multitap_recognizer.touches(remote, touches)

    def event_battery(self, remote, percent: int):
        log.info(f'Battery charge at {percent}%')
        self.battery_level = percent
        if self.pipe:
            self.pipe.battery_state(self.battery_level, self.is_charging)

    def event_power(self, remote, charging: bool):
        if charging:
            log.info('Charging')
        else:
            log.info('Not charging')
        self.is_charging = charging
        if self.pipe:
            self.pipe.battery_state(self.battery_level, self.is_charging)
