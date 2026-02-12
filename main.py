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
    arg_parser.add_argument('--log', default='var/log/hub.log', help='log file path')
    args = arg_parser.parse_args()
    log_name = args.log
else:
    log_name = 'hub'

log = tools.logger(log_name)

import asyncio, pprint, signal, time, traceback

from aconfig import config, ConfigWatcher
import remote, remote_adapter
import hdmi
from hdmi import Key
import homekit
import mqtt
import evdev_input, keyboard, solarcell
import memory
import messaging

def _key_representer(dumper, data):
    return dumper.represent_scalar('!Key', data.name)

def _key_constructor(loader, node):
    return Key[loader.construct_scalar(node)]

config.register_yaml_handler('!Key', Key, _key_representer, _key_constructor)

config.default('hub.activity_map', {
    Key.SELECT : 0,
    Key.UP : 1,
    Key.RIGHT : 2,
    Key.DOWN : 3,
    Key.LEFT : 4,
    Key.F1 : 0,
    Key.F2 : 1,
    Key.F3 : 2,
    Key.F4 : 3,
    Key.F5 : 4,
    Key.F6 : 5,
    Key.F7 : 6,
    Key.F8 : 7,
    Key.F9 : 8,
    Key.F10 : 9,
})
config.default('hub.macros', [
    (Key.POWER, Key.SELECT),
    (Key.POWER, Key.UP),
    (Key.POWER, Key.RIGHT),
    (Key.POWER, Key.DOWN),
    (Key.POWER, Key.LEFT),
    (Key.F1, ), # Not really a macro... But always use F keys for activity selection
    (Key.F2, ),
    (Key.F3, ),
    (Key.F4, ),
    (Key.F5, ),
    (Key.F6, ),
    (Key.F7, ),
    (Key.F8, ),
    (Key.F9, ),
    (Key.F10, ),
])
config.default('hub.long_press.duration_sec', .5)
config.default('hub.long_press.keymap', {
    Key.SELECT : Key.F6,
    Key.UP : Key.F7,
    Key.RIGHT : Key.F8,
    Key.DOWN : Key.F9,
    Key.LEFT : Key.F10,
    Key.F1 : Key.F6,
    Key.F2 : Key.F7,
    Key.F3 : Key.F8,
    Key.F4 : Key.F9,
    Key.F5 : Key.F10,
})
config.default('hub.short_press.keymap', {
    Key.POWER : Key.SELECT,
})
config.default('hub.play_pause.mode', 'emulate')
config.default('keyboard.enable', True)
config.default('memory.monitor.enable', False)
config.default('memory.monitor.period_sec', 5*60)
config.default('remote.battery.low_threshold', 10)

class KeyState(object):
    def __init__(self, count):
        self.timestamp = time.time()
        self.repeat_count = count

class Hub(remote.RemoteListener):
    # Used to ensure that repeat counted keys use a different KeyState than non-repeat counted
    # keys.
    REPEAT_COUNT_FLAG = 0x8000

    def __init__(self, controller):
        self.activity_map = config['hub.activity_map']
        self.macros = config['hub.macros']
        self.long_press_keymap = config['hub.long_press.keymap']
        self.long_press_duration_sec = config['hub.long_press.duration_sec']
        self.short_press_keymap = config['hub.short_press.keymap']
        self.play_pause_mode = config['hub.play_pause.mode']
        self.taskit = tools.Tasker('Hub')
        self.controller = controller
        self.key_state = {}
        self.wait_for_release = False
        self.pipes = []
        self.in_macro = False
        self.macro_index = None
        self.macro_executed = False
        self.play_pause_is_playing = False
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
        # unwrap enums, and use ints consistently
        if type(key) is Key:
            key = key.value
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
            count += state.repeat_count
            state.repeat_count = min(count, 10) # Don't accumulate too many key presses
            return

        # Don't let key presses leak across selection/activity modes
        if self.wait_for_release:
            log.info('Waiting for release')
            if state.repeat_count > 0:
                self.key_state.pop(key, None)
            return

        if self.controller.current_activity is hdmi.no_activity:
            if count > 0:
                # Ignore key sequences originating from swipes...
                self.key_state.pop(key)
            return

        if not self.in_macro:
            for macro_index, macro in enumerate(self.macros):
                key_count = 0
                for k in macro:
                    if k in self.key_state:
                        key_count += 1
                if key_count == len(macro):
                    self.in_macro = True
                    self.macro_index = macro_index
                    self.macro_executed = False
                    return

        if hkey == Key.POWER:
            return

        self.taskit(self.press_key(key))

    def map_key_press(self, key, time_pressed_sec):
        if time_pressed_sec >= self.long_press_duration_sec:
            key = self.long_press_keymap.get(key, key)
            log.info(f'Long press key {key:02X}')
        else:
            key = self.short_press_keymap.get(key, key)
            log.info(f'Short press key {key:02X}')
        return key

    async def client_release_key(self, key):
        # unwrap enums, and use ints consistently
        if type(key) is Key:
            key = key.value
        log.info(f'Client release key {key:02X}')

        state = self.key_state.pop(key, None)
        if state is None:
            log.info('No state for key?')
            return

        if self.controller.current_activity is hdmi.no_activity:
            if not self.in_macro:
                key = self.map_key_press(key, time.time() - state.timestamp)
                if key == Key.POWER:
                    await self.standby()
                else:
                    index = self.activity_map.get(key)
                    if index is not None:
                        await self.set_activity(index)
        else:
            if self.in_macro and not self.macro_executed:
                skip = False
                now = time.time()
                fn_key = self.macros[self.macro_index][-1]
                if key == Key.POWER:
                    # The macro's power key has been released
                    fn_state = self.key_state.get(fn_key, None)
                    if fn_state is not None:
                        time_pressed_sec = now - fn_state.timestamp
                    else:
                        log.error('Macro state is inconsistent')
                        skip = True
                elif fn_key == key:
                    # The macro's function key has been released
                    time_pressed_sec = now - state.timestamp
                else:
                    # Some other key has been released
                    skip = True

                if not skip:
                    key = self.map_key_press(fn_key, time_pressed_sec)
                    index = self.activity_map.get(key)
                    if index is not None:
                        await self.set_activity(index)
                    self.macro_executed = True
            elif not self.in_macro and key == Key.POWER:
                if time.time() - state.timestamp >= self.long_press_duration_sec:
                    await self.controller.fix_current_activity()
                else:
                    await self.standby()

        if not self.key_state:
            self.wait_for_release = False
            self.in_macro = False
            self.macro_index = None
            self.macro_executed = False

    async def client_battery_state(self, level, is_charging):
        is_low = level <= config['remote.battery.low_threshold'] and not is_charging
        log.info(f'Notifying battery state {level} {is_charging} {is_low}')
        for pipe in self.pipes:
            pipe.notify_battery_state(level, is_charging, is_low)

    async def standby(self):
        if self.controller.current_activity is hdmi.no_activity:
            log.info('Forcing standby')
            await self.controller.force_standby()
        else:
            await self.controller.standby()
        self.play_pause_is_playing = False
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
        log.info(f'Pressing key {hkey:02X}')
        if hkey == Key.PAUSE_PLAY:
            match self.play_pause_mode:
                case 'send':
                    pass
                case 'select':
                    log.info('Mapping PLAY_PAUSE to SELECT')
                    hkey = Key.SELECT
                case _: # emulate
                    hkey = Key.PAUSE if self.play_pause_is_playing else Key.PLAY
                    self.play_pause_is_playing = not self.play_pause_is_playing
                    log.info(f'Emulating PLAY_PAUSE as key {hkey:02X}')
        while True:
            if not await self.controller.press_key(hkey, True):
                log.info(f'Pressing key {hkey:02X} failed')
                break
            state = self.key_state.get(key)
            if state is None:
                break
            if state.repeat_count > 0:
                log.info(f'Repeating key {hkey} count {state.repeat_count}')
                state.repeat_count -= 1
                if state.repeat_count == 0:
                    break
        log.info(f'Pressing key {hkey:02X} done')
        self.key_state.pop(key, None)
        await self.check_release_all_keys()

def config_update():
    log.info('Config was updated. Exiting.')
    tools.die('Config update')

async def _main():
    watcher = ConfigWatcher(config, config_update)
    watcher.start()
    global args
    loop = asyncio.get_running_loop()

    log.info('Loading config...')
    config.load()
    log.info('Parsed activities:')
    activities = config['activities']
    if not activities:
        log.error('No activities configured. Waiting for config update.')
        await asyncio.Event().wait()

    log.info(pprint.pformat(activities))
    activities = [hdmi.Activity(ad) for ad in activities]
    log.info('Runtime activities:')
    log.info(pprint.pformat(activities))

    if config['memory.monitor.enable']:
        mem = memory.Monitor(config['memory.monitor.period_sec'])
        mem.start()
    else:
        mem = None

    activity_names = [activity.name for activity in activities]

    front_dev = config['adapters.front']
    back_dev = config['adapters.back']

    if front_dev is None or back_dev is None:
        log.error(f'Adapter devices must be set. front: {front_dev} back: {back_dev}. Waiting for config update.')
        await asyncio.Event().wait()

    while True:
        log.info(f'Initializing CEC on devices front: {front_dev} back: {back_dev}...')
        try:
            controller = await hdmi.Controller(
                front_dev,
                back_dev,
                'amity',
                loop,
                activities)
            break
        except hdmi.cec.AdapterInitException:
            log.info('Will retry in 10 seconds')
            await asyncio.sleep(10)


    hub = Hub(controller)

    if config['keyboard.enable']:
        # Wire hub and keyboard
        kb_pipe = messaging.Pipe()
        hub.add_pipe(kb_pipe)
        kb = keyboard.Handler(kb_pipe)

        # Wire hub and SolarCell
        sc_pipe = messaging.Pipe()
        hub.add_pipe(sc_pipe)
        sc = solarcell.Handler(sc_pipe)
        inp = evdev_input.EvdevInput([kb, sc], loop)
    else:
        inp = None

    if config['homekit.enable']:
        # Wire hub and HomeKit
        hk_pipe = messaging.Pipe()
        hub.add_pipe(hk_pipe)
        hk = homekit.HomeKit(activity_names, loop, hk_pipe)
        await hk.start()

    if config['mqtt.enable']:
        # Wire hub and MQTT
        mqtt_pipe = messaging.Pipe()
        hub.add_pipe(mqtt_pipe)
        mq = mqtt.MQTT(activity_names, loop, mqtt_pipe)
        await mq.start()
    else:
        mq = None

    mac = config['remote.mac']
    if mac is not None:
        # Wire hub and Siri remote
        sr_pipe = messaging.Pipe()
        hub.add_pipe(sr_pipe)
        ra = remote_adapter.Adapter(sr_pipe)
        wrapper = remote.RemoteListenerAsyncWrapper(loop, ra)
        log.info(f'Connecting to remote with MAC {mac}')
        siri = asyncio.to_thread(lambda: remote.SiriRemote(mac, wrapper))
    else:
        log.info(f'Siri remote not configured. Must be using a keyboard...')
        siri = None

    while True:
        futures = []
        if siri is not None:
            futures.append(siri)
        if inp is not None:
            futures.extend(inp.wait_on())
        if mem is not None:
            futures.extend(mem.wait_on())
        if mq is not None:
            futures.extend(mq.wait_on())
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
