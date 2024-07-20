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

import asyncio, pprint, subprocess, sys, traceback, yaml

import remote, remote_adapter
import hdmi
from hdmi import Key
import keyboard
import messaging
import ui

class Hub(remote.RemoteListener):
    REPEAT_COUNT_FLAG = 0x8000

    def __init__(self, controller, pressure_threshold=None):
        self.controller = controller
        self.key_state = set()
        self.wait_for_release = False
        self.repeat_timers = {}
        self.repeat_delay_sec = 0.2
        self.repeat_period_sec = 0.1
        self.pipes = []
        self.in_macro = False
        self.set_wait_for_release()

    def set_wait_for_release(self):
        self.repeat_timers.clear()
        self.wait_for_release = True
        loop = asyncio.get_running_loop()
        loop.call_later(1, self.auto_clear_wait_for_release)

    def auto_clear_wait_for_release(self):
        self.wait_for_release = False

    def add_pipe(self, pipe):
        self.pipes.append(pipe)
        pipe.start_server_task(self)

    # Duck typed methods for messaging
    def client_set_activity(self, index):
        self.set_activity(index)

    def client_press_key(self, key, count):
        log.info(f'Client press key {key:02X} count {count}')
        hkey = key
        if count > 0:
            key |= self.REPEAT_COUNT_FLAG

        self.key_state.add(key)

        # Don't let key presses leak across selection/activity modes
        if self.wait_for_release:
            return

        activity_map = {
            Key.SELECT : 0,
            Key.UP : 1,
            Key.RIGHT : 2,
            Key.DOWN : 3,
            Key.LEFT : 4
        }

        if self.controller.current_activity is hdmi.no_activity:
            # Ignore key sequences originating from swipes...
            if count > 0:
                self.key_state.discard(key)
                return
            index = activity_map.get(hkey)
            if index is not None:
                self.set_activity(index)
            return

        macros = {
            (Key.POWER, Key.SELECT),
            (Key.POWER, Key.UP),
            (Key.POWER, Key.RIGHT),
            (Key.POWER, Key.DOWN),
            (Key.POWER, Key.LEFT),
        }

        for macro in macros:
            key_count = 0
            for k in macro:
                if k in self.key_state:
                    key_count += 1
            if key_count == len(macro):
                self.in_macro = True
                index = activity_map.get(macro[1])
                if index is not None:
                    self.set_activity(index)
                return

        if hkey == Key.POWER:
            return

        self.controller.press_key(hkey)
        loop = asyncio.get_running_loop()
        self.repeat_timers[key] = loop.call_later(self.repeat_delay_sec,
                                                  self.event_timer, key, count)

    def client_release_key(self, key):
        log.info(f'Client release key {key:02X}')
        self.key_state.discard(key)

        if key == Key.POWER:
            if self.in_macro:
                self.in_macro = False
            else:
                self.standby()

        if self.controller.current_activity is not hdmi.no_activity:
            if (not self.key_state or
                (len(self.key_state) == 1 and Key.POWER in self.key_state)):
                self.controller.release_key()
        if not self.key_state:
            self.wait_for_release = False
            self.in_macro = False

    def standby(self):
        if self.controller.current_activity is hdmi.no_activity:
            log.info('Forcing standby')
            self.controller.force_standby()
        else:
            self.controller.standby()
        self.set_wait_for_release()
        for pipe in self.pipes:
            pipe.notify_set_activity(-1)

    def set_activity(self, index):
        if not self.controller.set_activity(index):
            return False
        self.set_wait_for_release()
        for pipe in self.pipes:
            pipe.notify_set_activity(index)
        return True

    def event_timer(self, key, repeat_count):
        if key not in self.key_state:
            return

        hkey = key
        if repeat_count > 0:
            hkey &= ~self.REPEAT_COUNT_FLAG
            repeat_count -= 1
            if repeat_count == 0:
                log.info(f'Repeating key {hkey} count done')
                self.key_state.discard(key)
                return

        log.info(f'Repeating key {hkey} count {repeat_count}')
        self.controller.press_key(hkey)
        loop = asyncio.get_running_loop()
        self.repeat_timers[key] = loop.call_later(self.repeat_period_sec, self.event_timer, key, repeat_count)

async def _main():
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

    adapters = config.get('adapters')
    if adapters is not None:
        front_dev = adapters['front']
        back_dev = adapters['back']
    else:
        front_dev = '/dev/cec1'
        back_dev = '/dev/cec0'

    log.info(f'Initializing CEC on devices front: {front_dev} back: {back_dev}...')
    controller = hdmi.Controller(front_dev,
                                 back_dev,
                                 'amity',
                                 loop,
                                 activities)

    remote_config = config['remote']
    touchpad_config = remote_config.get('touchpad')
    pressure_threshold = None
    if touchpad_config:
        pressure_threshold = touchpad_config.get('pressure_threshold')
    hub = Hub(controller, pressure_threshold)

    # Wire hub and UI
    if_pipe = messaging.Pipe()
    hub.add_pipe(if_pipe)
    interface.set_pipe(if_pipe)

    # Wire hub and keyboard
    kb_pipe = messaging.Pipe()
    hub.add_pipe(kb_pipe)
    kb = keyboard.Keyboard(loop, kb_pipe)

    # Wire hub and Siri remote
    sr_pipe = messaging.Pipe()
    hub.add_pipe(sr_pipe)
    ra = remote_adapter.Adapter(sr_pipe)
    wrapper = remote.RemoteListenerAsyncWrapper(loop, ra)

    mac = config['remote']['mac']
    log.info(f'Calling bluetoothctl to disconnect MAC {mac}')
    subprocess.run(['/usr/bin/bluetoothctl', 'disconnect', mac], capture_output=True)
    log.info(f'Connecting to remote with MAC {mac}')
    siri = asyncio.to_thread(lambda: remote.SiriRemote(mac, wrapper))

    while True:
        await asyncio.gather(siri, interface.run(), *controller.wait_on(), *kb.wait_on())
        await asyncio.sleep(1)

# asyncio.run() swallows, and disappears exceptions on the main thread if there are other
# threads running. So... use a catchall try/except to actively kill the entire process in case of
# an exception on the main thread.
async def main():
    try:
        await _main()
    except Exception as e:
        log.info(f'Exiting because of exception {e}\n{traceback.print_exc()}')
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())
