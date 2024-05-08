#!/usr/bin/env python

# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This code is derived from code written by Yanndroid (https://github.com/Yanndroid)

import tools

log = tools.logger('log/hdmi_tool')

import argparse, logging, os, shutil, sys, time, yaml

if os.environ.get('CEC_OSD_NAME') is None:
    os.environ['CEC_OSD_NAME'] = 'amity'

import hdmi

def scan():
    controller = hdmi.Controller(None, [])
    log.info('Scanning HDMI devices...')
    devices = controller.scan_devices()
    log.info('\nName      \tVendor     \tAddress   \tPhysical Address\n')
    for device_name, device in devices.items():
        log.info(f'{device_name:10s}\t{device.vendor():10s}\t{device.address():10}\t{device.physical_address()}')

tv_address = 0
playback_device_addresses = (4, 8, 9, 11)
audio_system_address = 5

def recommend(should_write_config):
    controller = hdmi.Controller(None, [])

    devices = controller.scan_devices()

    tv_device = None
    audio_system_device = None
    playback_devices = []
    for _,  device in devices.items():
        if device.address() == tv_address:
            tv_device = device
        if device.address() == audio_system_address:
            audio_system_device = device
        if device.address() in playback_device_addresses:
            playback_devices.append(device)

    if tv_device is not None:
        tv_name = tv_device.name()
    else:
        tv_name = '~'

    activities = []
    for i, playback_device in enumerate(playback_devices):
        verb = 'Watch'
        for s in ('playstation', 'nintendo'):
            if s in playback_device.name().lower():
                verb = 'Play'
        activity = { 'name': verb + ' ' + playback_device.name(),
                     'display': tv_name,
                     'source': playback_device.name(),
                    }
        if audio_system_device is not None:
            activity['audio'] = audio_system_device.name()
            activity['switch'] = { 'device' : audio_system_device.name(),
                                   'input': '<SCAN INPUTS TO FIND ME>' }
        else:
            activity['audio'] = tv_name
            activity['switch'] = { 'device' : tv_name,
                                   'input': '<SCAN INPUTS TO FIND ME>' }
        activities.append(activity)

    log.info('This is my best guess for available activities.')
    log.info("If you don't see an activity for a device in your system, please ensure the device has\n"
        "CEC enabled, and is reachable. Use the 'scan' action to see if the device is responding.\n"
        "Some devices need to be ON to respond.")
    log.info("Unfortunately, at this time, finding the correct switch input for an activity has to be\n"
        "done through trial and error. Use the 'scan-inputs' action of this tool to scan inputs\n"
        "in your system.")
    log.info('\n')

    if should_write_config:
        config_filename = 'config.yaml'
        try:
            with open(config_filename, 'r') as file:
                config = yaml.safe_load(file)
        except FileNotFoundError:
            config = None
        if config is None:
            config = {}
        if config.get('activities') is not None:
            backup_time_str = time.strftime('%Y%m%d-%H%M%S')
            backup_filename = f'{config_filename}-{backup_time_str}'
            # Make a backup of the config file
            shutil.copy(config_filename, backup_filename)
            log.debug(f'Created backup {backup_filename}')
        # Update the config
        config['activities'] = activities
        log.debug(f'Writing remote config {config}')
        with open(config_filename, 'w') as file:
            yaml.safe_dump(config, file)
        log.info(f'{config_filename} updated.')
    else:
        s = yaml.safe_dump({'activities': activities})
        log.info(s)

def scan_input(input_device_name):
    controller = hdmi.Controller(None, [])
    log.info('Scanning HDMI devices...')
    devices = controller.scan_devices()
    if not input_device_name:
        devices_by_index = {}
        i = 1
        for device_name, device in devices.items():
            recommended = device.address() in (tv_address, audio_system_address)
            recommended_str = '*' if recommended else ' '
            log.info(f'{i}. {recommended_str} {device_name} ')
            devices_by_index[i] = device
            i += 1
        log.info('\nSelect the device to scan inputs on (* recommended)\n')
        while True:
            index_s = input(f'Enter device (1-{i-1})> ')
            try:
                index = int(index_s)
            except ValueError:
                log.info('Invalid choice')
                continue
            if index < 1 or index >= i:
                log.info('Invalid choice')
                continue
            device = devices_by_index[index]
            break
    else:
        device = devices.get(input_device_name)
        if device is None:
            log.info(f'Device {input_device_name} not found.')
            log.info('Available devices:')
            for device_name in devices:
                log.info(device_name)
            return

    log.info(f'Scanning {device.name()}')

    input('Press enter to start scanning inputs> ')
    input_index = 1
    while True:
        log.info(f'Selecting input {input_index}')
        device.set_input(input_index)
        input_index += 1
        if input_index > 10:
            input_index = 1
        s = input("Type 'q' to quit. Press enter to try next input> ")
        if 'q' in s: break

def main():
    actions = ('scan', 'recommend', 'scan-inputs')
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('action', default='', choices=actions, help='action to perform')
    arg_parser.add_argument('-d', '--debug', action='store_true', help='enable debug messages')
    arg_parser.add_argument('-i', '--input-device', type=str, default='',
                            help='name of input device to scan')
    arg_parser.add_argument('-n', '--nowrite', action='store_true',
                            help="don't write recommended activity configuration to config.yaml")
    args = arg_parser.parse_args()

    if args.debug:
        tools.set_log_level('debug')

    log.addHandler(logging.StreamHandler(sys.stdout))

    log.info('Initializing CEC...')
    hdmi.cec_init()

    if args.action == 'scan':
        scan()
    elif args.action == 'recommend':
        recommend(not args.nowrite)
    elif args.action == 'scan-inputs':
        scan_input(args.input_device)

if __name__ == '__main__':
    main()
