#!/usr/bin/env python

# Copyright 2024-2026.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger('var/log/hdmi_tool')

import argparse, asyncio, glob, logging, sys, yaml
from collections.abc import Iterator, Sequence
from typing import Any

import cec, hdmi
from aconfig import config

def all_adapter_devices() -> Iterator[str]:
    return glob.iglob('/dev/cec*')

tv_address: int = 0
source_device_addresses: Sequence[int] = (1, 2, 3, 4, 6, 7, 8, 9, 10, 11)
audio_system_address: int = 5

class MockAdapter:
    def __init__(self, devname: str) -> None:
        self.devname: str = devname

class MockDevice:
    def __init__(self, adapters: dict[str, MockAdapter], d: dict[str, Any]) -> None:
        self.osd_name: str = d['osd_name']
        self.address: int = d['address']
        self.vendor_id: int = d['vendor_id']
        self.physical_address: int = d['physical_address']
        self.adapter: MockAdapter = adapters[d['adapter']]

def mock_devices() -> list[MockDevice] | None:
    try:
        with open('mock_hdmi_devices.yaml', 'r') as file:
            log.info('Using mock devices')
            data = yaml.safe_load(file)
            adapters = {devname:MockAdapter(devname) for devname in data['adapters']}
            devices = [MockDevice(adapters, device) for device in data['devices']]
    except FileNotFoundError:
        return None
    return devices

async def scan(args: argparse.Namespace) -> list[Any]:
    mock = mock_devices()
    devices: list[Any] = mock if mock is not None else []
    if mock is None:
        for devname in all_adapter_devices():
            try:
                adapter = cec.Adapter(devname=devname)
            except cec.AdapterInitException:
                continue

            if adapter.caps.driver != b'cec-gpio':
                continue
            log.info(f'Scanning for devices on cec-gpio device {devname}')
            try:
                devices.extend(await adapter.list_devices())
            except OSError as e:
                log.info(f'{devname} is not connected')

    log.info('\nName      \tVendor     \tAddress   \tPhysical Address\tAdapter\n')
    for device in devices:
        pa = hdmi.pretty_physical_address(device.physical_address)
        log.info(f'{device.osd_name:10s}\t{device.vendor_id:10}\t{device.address:10}\t{pa}\t\t\t{device.adapter.devname}')

    if args.yaml:
        entries: list[dict[str, Any]] = []
        for device in devices:
            if device.address == tv_address:
                role = 'display'
            elif device.address in source_device_addresses:
                role = 'source'
            elif device.address == audio_system_address:
                role = 'audio'
            entry = {
                'osd_name' : device.osd_name,
                'address' : device.address,
                'physical_address' : device.physical_address,
                'adapter' : device.adapter.devname,
                'role': role,
            }
            entries.append(entry)
        s = yaml.safe_dump({'status' : 'OK', 'devices' : entries})
        log.info(f'YAML:\n{s}')
        print(s)

    return devices

async def recommend(args: argparse.Namespace) -> None:
    devices = await scan(args)
    if devices is None:
        return None
    tv_device = None
    audio_system_device = None
    source_devices = []
    for device in devices:
        if device.address == tv_address:
            tv_device = device
        if device.address == audio_system_address:
            audio_system_device = device
        if device.address in source_device_addresses:
            source_devices.append(device)

    adapters =  {}
    if tv_device is not None:
        tv_name = tv_device.osd_name
        adapters['front'] = tv_device.adapter.devname
    else:
        log.info("Can't find a TV... Assuming there is none.")
        tv_name = '~'

    activities = []
    for i, source_device in enumerate(source_devices):
        if 'back' not in adapters:
            adapters['back'] = source_device.adapter.devname
        verb = 'Watch'
        for s in ('playstation', 'nintendo'):
            if s in source_device.osd_name.lower():
                verb = 'Play'
        activity = { 'name': verb + ' ' + source_device.osd_name,
                     'display': tv_name,
                     'source': source_device.osd_name,
                    }
        if audio_system_device is not None:
            activity['audio'] = audio_system_device.osd_name
        activities.append(activity)

    log.info('This is my best guess for available activities.')
    log.info("If you don't see an activity for a device in your system, please ensure the device has\n"
        "CEC enabled, and is reachable. Use the 'scan' action to see if the device is responding.\n"
        "Some devices need to be ON to respond.")
    log.info('\n')

    config.load()

    if args.nowrite:
        config['adapters'] = adapters
        config['activities'] = activities
        s = yaml.safe_dump(config.user_cfg)
        log.info(s)
    else:
        # Update the config
        backup = config['activities'] is not None or config['adapters']
        config['adapters'] = adapters
        config['activities'] = activities
        config.save(backup)
        log.info(f'{config.filename} updated.')

    if args.yaml:
        output = {
            'adapters' : adapters,
            'activities' : activities
        }
        s = yaml.safe_dump(output)
        log.info(f'YAML:\n{s}')
        print(s)


async def main() -> None:
    actions = ('scan', 'recommend')
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('action', default='', choices=actions, help='action to perform')
    arg_parser.add_argument('-d', '--debug', action='store_true', help='enable debug messages')
    arg_parser.add_argument('-n', '--nowrite', action='store_true',
                            help="don't write recommended activity configuration to config.yaml")
    arg_parser.add_argument('-y', '--yaml', action='store_true',
                            help='YAML output')
    args = arg_parser.parse_args()

    if not args.yaml:
        if args.debug:
            tools.set_log_level('debug')
        log.addHandler(logging.StreamHandler(sys.stdout))

    if args.action == 'scan':
        await scan(args)
    elif args.action == 'recommend':
        await recommend(args)

if __name__ == '__main__':
    asyncio.run(main())
