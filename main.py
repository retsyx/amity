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

import asyncio, pprint, signal, subprocess, traceback

from config import config
import remote, remote_adapter
import hdmi
from hdmi import Key
import homekit
import keyboard
import messaging

config.default('homekit.enable', False)
config.default('keyboard.enable', True)

class KeyState(object):
    def __init__(self, count):
        self.repeat_count = count

class Hub(remote.RemoteListener):
    REPEAT_COUNT_FLAG = 0x8000

    def __init__(self, controller):
        self.taskit = tools.Tasker('Hub')
        self.controller = controller
        self.key_state = {}
        self.wait_for_release = False
        self.pipes = []
        self.in_macro = False
        self.set_wait_for_release()

    def set_wait_for_release(self):
        self.wait_for_release = True
        loop = asyncio.get_running_loop()
        loop.call_later(1, self.auto_clear_wait_for_release)

    def auto_clear_wait_for_release(self):
        self.wait_for_release = False

    def add_pipe(self, pipe):
        self.pipes.append(pipe)
        pipe.start_server_task(self)

    # Duck typed methods for messaging
    async def client_set_activity(self, index):
        await self.set_activity(index)

    async def client_press_key(self, key, count):
        log.info(f'Client press key {key:02X} count {count}')
        hkey = key
        if count > 0:
            key |= self.REPEAT_COUNT_FLAG

        state = self.key_state.get(key)
        if state is None:
            state = KeyState(count)
            self.key_state[key] = state
        elif count > 0:
            # This key is already counting, so add to the count, and finish
            state.repeat_count += count
            return

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
            if count > 0:
                # Ignore key sequences originating from swipes...
                self.key_state.pop(key)
                return
            index = activity_map.get(hkey)
            if index is not None:
                await self.set_activity(index)
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
                    await self.set_activity(index)
                return

        if hkey == Key.POWER:
            return

        self.taskit(self.press_key(key))

    async def client_release_key(self, key):
        log.info(f'Client release key {key:02X}')
        if self.key_state.pop(key, None) is None:
            return

        if key == Key.POWER:
            if self.in_macro:
                self.in_macro = False
            else:
                await self.standby()

        if not self.key_state:
            self.wait_for_release = False
            self.in_macro = False

    async def standby(self):
        if self.controller.current_activity is hdmi.no_activity:
            log.info('Forcing standby')
            await self.controller.force_standby()
        else:
            await self.controller.standby()
        self.set_wait_for_release()
        for pipe in self.pipes:
            pipe.notify_set_activity(-1)

    async def set_activity(self, index):
        if not await self.controller.set_activity(index):
            return False
        self.set_wait_for_release()
        for pipe in self.pipes:
            pipe.notify_set_activity(index)
        return True

    async def check_release_all_keys(self):
        if self.controller.current_activity is not hdmi.no_activity:
            if (not self.key_state or
                (len(self.key_state) == 1 and Key.POWER in self.key_state)):
                await self.controller.release_key()

    async def press_key(self, key):
        hkey = key & ~self.REPEAT_COUNT_FLAG
        log.info(f'Pressing key {hkey}')
        while True:
            if not await self.controller.press_key(hkey, True):
                log.info(f'Pressing key {hkey} failed')
                break
            state = self.key_state.get(key)
            if state is None:
                break
            if state.repeat_count > 0:
                log.info(f'Repeating key {hkey} count {state.repeat_count}')
                state.repeat_count -= 1
                if state.repeat_count == 0:
                    break
        log.info(f'Pressing key {hkey} done')
        self.key_state.pop(key, None)
        await self.check_release_all_keys()

async def _main():
    global args
    loop = asyncio.get_running_loop()

    log.info('Loading config...')
    config.load()
    log.info('Parsed activities:')
    log.info(pprint.pformat(config['activities']))
    activities = [hdmi.Activity(ad) for ad in config['activities']]
    log.info('Runtime activities:')
    log.info(pprint.pformat(activities))

    activity_names = [activity.name for activity in activities]

    front_dev = config['adapters.front']
    back_dev = config['adapters.back']

    if front_dev is None or back_dev is None:
        log.error(f'Adapter devices must be set. front: {front_dev} back: {back_dev}')
        return

    log.info(f'Initializing CEC on devices front: {front_dev} back: {back_dev}...')
    controller = await hdmi.Controller(
        front_dev,
        back_dev,
        'amity',
        loop,
        activities)

    hub = Hub(controller)

    if config['keyboard.enable']:
        # Wire hub and keyboard
        kb_pipe = messaging.Pipe()
        hub.add_pipe(kb_pipe)
        kb = keyboard.Keyboard(loop, kb_pipe)
    else:
        kb = None

    mac = config['remote.mac']
    if mac is not None:
        # Wire hub and Siri remote
        sr_pipe = messaging.Pipe()
        hub.add_pipe(sr_pipe)
        ra = remote_adapter.Adapter(sr_pipe)
        wrapper = remote.RemoteListenerAsyncWrapper(loop, ra)
        log.info(f'Calling bluetoothctl to disconnect MAC {mac}')
        subprocess.run(['/usr/bin/bluetoothctl', 'disconnect', mac], capture_output=True)
        log.info(f'Connecting to remote with MAC {mac}')
        siri = asyncio.to_thread(lambda: remote.SiriRemote(mac, wrapper))
    else:
        log.info(f'Siri remote not configured. Must be using a keyboard...')
        siri = None

    if config['homekit.enable']:
        # Wire hub and HomeKit
        hk_pipe = messaging.Pipe()
        hub.add_pipe(hk_pipe)
        hk = homekit.HomeKit(activity_names, loop, hk_pipe)
        await hk.start()

    while True:
        futures = []
        if siri is not None:
            futures.append(siri)
        if kb is not None:
            futures.extend(kb.wait_on())
        await asyncio.gather(*futures)
        await asyncio.sleep(1)

# asyncio.run() swallows, and disappears exceptions on the main thread if there are other
# threads running. So... use a catchall try/except to actively kill the entire process in case of
# an exception on the main thread.
async def main():
    try:
        await _main()
    except Exception as e:
        s = f'Exiting because of exception {e}\n{traceback.print_exc()}'
        log.info(s)
        tools.die(s)

def handle_sigterm(signum, frame):
    tools.die('SIGTERM')

if __name__ == '__main__':
    signal.signal(signal.SIGTERM, handle_sigterm)
    asyncio.run(main())
