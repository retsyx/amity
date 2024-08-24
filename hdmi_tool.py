#!/usr/bin/env python

# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger('log/hdmi_tool')

import argparse, asyncio, glob, logging, shutil, sys, time, yaml
import cec, hdmi
from config import config

def all_adapter_devices():
    return glob.iglob('/dev/cec*')

async def scan():
    devices = []
    for devname in all_adapter_devices():
        adapter = cec.Adapter(devname=devname)
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
    return devices

tv_address = 0
source_device_addresses = (4, 8, 9, 11)
audio_system_address = 5

async def recommend(should_write_config):
    devices = await scan()

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

    if should_write_config:
        if config['activities'] is not None or config['adapters'] is not None:
            backup_time_str = time.strftime('%Y%m%d-%H%M%S')
            backup_filename = f'{config.filename}-{backup_time_str}'
            # Make a backup of the config file
            shutil.copy(config.filename, backup_filename)
            log.debug(f'Created backup {backup_filename}')
        # Update the config
        config['adapters'] = adapters
        config['activities'] = activities
        log.debug(f'Writing activity config {config}')
        config.save()
        log.info(f'{config.filename} updated.')
    else:
        config['adapters'] = adapters
        config['activities'] = activities
        s = yaml.safe_dump(config.user_cfg)
        log.info(s)

async def main():
    actions = ('scan', 'recommend')
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('action', default='', choices=actions, help='action to perform')
    arg_parser.add_argument('-d', '--debug', action='store_true', help='enable debug messages')
    arg_parser.add_argument('-n', '--nowrite', action='store_true',
                            help="don't write recommended activity configuration to config.yaml")
    args = arg_parser.parse_args()

    if args.debug:
        tools.set_log_level('debug')

    log.addHandler(logging.StreamHandler(sys.stdout))

    if args.action == 'scan':
        await scan()
    elif args.action == 'recommend':
        await recommend(not args.nowrite)

if __name__ == '__main__':
    asyncio.run(main())
