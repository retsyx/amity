#!/usr/bin/env python

# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import argparse
import tools

if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('--log', default='log/amity.log', help='log file path')
    args = arg_parser.parse_args()
    log_name = args.log
else:
    log_name = 'amity'

log = tools.logger(log_name)

import asyncio, pprint, subprocess, time, yaml

import remote
import gestures
import hdmi
import messaging
import ui

class Hub(remote.RemoteListener):
    def __init__(self, controller):
        self.controller = controller
        self.wait_for_release = False
        self.button_state = 0
        self.active_button = 0
        self.active_key = hdmi.Key.NO_KEY
        self.repeat_timer = None
        self.repeat_delay_sec = 0.2
        self.repeat_period_sec = 0.1
        self.swipe_recognizer = gestures.SwipeRecognizer((5, 5), self.swipe_callback)
        self.dpad_emulator = gestures.DPadEmulator()
        self.multitap_recognizer = gestures.MultiTapRecognizer(1, 3, self.multitap_callback)
        self.swipe_key = None
        self.swipe_counter = 0
        self.pipe = None
        self.set_wait_for_release()

    def set_wait_for_release(self):
        self.wait_for_release = True
        loop = asyncio.get_running_loop()
        loop.call_later(1, self.auto_clear_wait_for_release)

    def auto_clear_wait_for_release(self):
        self.wait_for_release = False

    def set_pipe(self, pipe):
        self.pipe = pipe
        self.pipe.start_server_task(self)

    # Duck typed methods for messaging
    def client_set_activity(self, index):
        if index == -1:
            self.standby()
        else:
            self.set_activity(index)

    def client_press_key(self, key):
        log.info(f'Client press key {key:02X}')
        self.press_key(key, self.repeat_delay_sec)

    def client_release_key(self, key):
        log.info(f'Client release key {key:02X}')
        self.release_key()

    def standby(self):
        if self.controller.current_activity is hdmi.no_activity:
            log.info('Forcing standby')
            self.controller.force_standby()
        else:
            self.controller.standby()
        self.set_wait_for_release()

    def set_activity(self, index):
        if not self.controller.set_activity(index):
            return False
        self.set_wait_for_release()
        self.pipe.notify_set_activity(index)
        return True

    def press_key(self, key, repeat_in_sec=None):
        self.controller.press_key(key)
        if repeat_in_sec:
            self.active_key = key
            loop = asyncio.get_running_loop()
            self.repeat_timer = loop.call_later(repeat_in_sec, self.event_timer)
        else:
            self.active_key = hdmi.Key.NO_KEY
            self.controller.release_key()

    def release_key(self):
        if self.active_key != hdmi.Key.NO_KEY:
            self.controller.release_key()
            self.active_key = hdmi.Key.NO_KEY

    def swipe(self):
        if self.swipe_counter == 0: return False
        log.info(f'Swiping key {self.swipe_key}')
        self.controller.press_key(self.swipe_key)
        self.swipe_counter -= 1
        if self.swipe_counter > 0:
            loop = asyncio.get_running_loop()
            self.repeat_timer = loop.call_later(self.repeat_period_sec, self.event_timer)
        else:
            log.info(f'Swipe is complete')
            self.controller.release_key()
            self.swipe_key = None
        return True

    def event_timer(self):
        if self.swipe():
            return
        if self.active_key == hdmi.Key.NO_KEY:
            return
        self.press_key(self.active_key, self.repeat_period_sec)

    def event_button(self, remote, buttons: int):
        btns = remote.profile.buttons

        log.info(f'Buttons {buttons:04X}')

        buttons = self.dpad_emulator.buttons(remote, buttons)

        log.info(f'Buttons dpad {buttons:04X}')

        # Don't let key presses leak across selection/activity modes
        if self.wait_for_release:
            if buttons == btns.RELEASED:
                self.active_button = btns.RELEASED
                self.button_state = buttons
                self.wait_for_release = False
            return

        if self.controller.current_activity is hdmi.no_activity:
            # We are in standby, select an activity...
            if buttons & btns.SELECT:
                self.set_activity(0)
            elif buttons & btns.UP:
                self.set_activity(1)
            elif buttons & btns.RIGHT:
                self.set_activity(2)
            elif buttons & btns.DOWN:
                self.set_activity(3)
            elif buttons & btns.LEFT:
                self.set_activity(4)
            elif buttons & btns.POWER:
                # Broadcast a standby only on the initial button press, not other state changes
                if self.button_state == btns.RELEASED:
                    self.standby()
                    self.active_button = btns.POWER
        else: # We are in an activity, control it...
            self.handle_activity_button(remote, buttons)
        self.button_state = buttons

    def swipe_callback(self, recognizer, event):
        if event.type & gestures.EventType.Detected:
            if self.active_button != 0:
                log.info(f'Swipe with active button {self.active_button}. Ignoring!')
                return
            if self.swipe_key is not None:
                log.info(f'Got swipe event {event} while swipe is in progress? Ignoring!')
                return
            if event.x < 0:
                counter = -event.x
                key = hdmi.Key.LEFT
            elif event.x > 0:
                counter = event.x
                key = hdmi.Key.RIGHT
            elif event.y < 0:
                counter = -event.y
                key = hdmi.Key.DOWN
            else: # event.y > 0
                counter = event.y
                key = hdmi.Key.UP
            log.info(f'Swiping {key} {counter} times')
            self.swipe_key = key
            self.swipe_counter = counter
            self.swipe()

    def multitap_callback(self, recognizer, event):
        if event.type & gestures.EventType.Detected:
            buttons = self.button_state | event.remote.profile.buttons.POWER
            self.event_button(event.remote, buttons)
            buttons = self.button_state & ~event.remote.profile.buttons.POWER
            self.event_button(event.remote, buttons)

    def event_touches(self, remote, touches):
        self.swipe_recognizer.touches(remote, touches)
        self.dpad_emulator.touches(remote, touches)
        self.multitap_recognizer.touches(remote, touches)

    def handle_activity_button(self, remote, button):
        btns = remote.profile.buttons

        MACRO_0 = btns.POWER | btns.SELECT
        MACRO_1 = btns.POWER | btns.UP
        MACRO_2 = btns.POWER | btns.RIGHT
        MACRO_3 = btns.POWER | btns.DOWN
        MACRO_4 = btns.POWER | btns.LEFT

        # HDMI-CEC seems to support only one key press at a time (no concurrent key presses),
        # and we want to support key repeat, so we need to track key press/release of a single
        # key.
        # Are we in the midst of a repeat of a key?
        if self.active_button != btns.RELEASED:
            # If the key is still being pressed, ignore any changes
            if button & self.active_button:
                return
            else: # The key was released
                if self.repeat_timer is not None:
                    self.repeat_timer.cancel()
                self.active_button = btns.RELEASED
                self.release_key()
                # We can process other keys now...

        released_button = self.button_state & ~button

        def is_macro(button, macro):
            return (button & macro) == macro

        if is_macro(button, MACRO_0):
            self.set_activity(0)
        elif is_macro(button, MACRO_1):
            self.set_activity(1)
        elif is_macro(button, MACRO_2):
            self.set_activity(2)
        elif is_macro(button, MACRO_3):
            self.set_activity(3)
        elif is_macro(button, MACRO_4):
            self.set_activity(4)
        elif button & btns.HOME:
            self.press_key(hdmi.Key.ROOT_MENU, self.repeat_delay_sec)
            self.active_button = btns.HOME
        elif button & btns.VOLUME_UP:
            self.press_key(hdmi.Key.VOLUME_UP, self.repeat_delay_sec)
            self.active_button = btns.VOLUME_UP
        elif button & btns.VOLUME_DOWN:
            self.press_key(hdmi.Key.VOLUME_DOWN, self.repeat_delay_sec)
            self.active_button = btns.VOLUME_DOWN
        elif button & btns.SELECT:
            self.press_key(hdmi.Key.SELECT, self.repeat_delay_sec)
            self.active_button = btns.SELECT
        elif button & btns.BACK:
            self.press_key(hdmi.Key.BACK, self.repeat_delay_sec)
            self.active_button = btns.BACK
        elif button & btns.MUTE:
            self.press_key(hdmi.Key.TOGGLE_MUTE)
            self.active_button = btns.MUTE
        elif button & btns.PLAY_PAUSE:
            self.press_key(hdmi.Key.PAUSE_PLAY, self.repeat_delay_sec)
            self.active_button = btns.PLAY_PAUSE
        elif button & btns.UP:
            self.press_key(hdmi.Key.UP, self.repeat_delay_sec)
            self.active_button = btns.UP
        elif button & btns.RIGHT:
            self.press_key(hdmi.Key.RIGHT, self.repeat_delay_sec)
            self.active_button = btns.RIGHT
        elif button & btns.DOWN:
            self.press_key(hdmi.Key.DOWN, self.repeat_delay_sec)
            self.active_button = btns.DOWN
        elif button & btns.LEFT:
            self.press_key(hdmi.Key.LEFT, self.repeat_delay_sec)
            self.active_button = btns.LEFT
        elif released_button & btns.POWER:
            self.pipe.notify_set_activity(-1)
            self.standby()

async def main():
    global args
    loop = asyncio.get_running_loop()

    interface = ui.Main()

    log.info('Loading config...')
    with open('config.yaml', 'r') as file:
        config = yaml.safe_load(file)
    log.info('Parsed activities:')
    log.info(pprint.pformat(config['activities']))
    activities = [hdmi.Activity(ad) for ad in config['activities']]
    log.info('Runtime activities:')
    log.info(pprint.pformat(activities))

    log.info(f'Initializing UI...')
    activity_names = [activity.name for activity in activities]
    interface.set_activity_names(['Off',] + activity_names)

    dev = None
    adapters = config.get('adapters')
    if adapters is not None:
        front_dev = adapters['front']
        back_dev = adapters['back']
    else:
        front_dev = '/dev/cec1'
        back_dev = '/dev/cec0'

    log.info(f'Initializing CEC on device {dev}...')
    controller = hdmi.Controller(front_dev,
                                 back_dev,
                                 'amity',
                                 loop,
                                 activities)
    hub = Hub(controller)

    # Wire hub and interface to talk to each other
    pipe = messaging.Pipe()
    hub.set_pipe(pipe)
    interface.set_pipe(pipe)

    # Write hub and remote to talk to each other
    wrapper = remote.RemoteListenerAsyncWrapper(loop, hub)

    mac = config['remote']['mac']
    log.info(f'Calling bluetoothctl to disconnect MAC {mac}')
    subprocess.run(['/usr/bin/bluetoothctl', 'disconnect', mac], capture_output=True)
    log.info(f'Connecting to remote with MAC {mac}')
    siri = asyncio.to_thread(lambda: remote.SiriRemote(mac, wrapper))

    await asyncio.gather(siri, interface.run(), *controller.wait_on())

if __name__ == '__main__':
    asyncio.run(main())
