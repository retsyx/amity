#!/usr/bin/env python

# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger('var/log/pair_tool.log')

import argparse, logging, subprocess, sys

from bluepy3 import btle
from bluepy3.btle import AssignedNumbers
from aconfig import config

class Scanner(object):
    def __init__(self):
        self.scanner = btle.Scanner()
        self.scanner.withDelegate(self)
        self.pairing = False

    def handleDiscovery(self, entry, isNewDev, isNewData):
        pass

    def check_pair(self, entry):
        log.debug(f'Device RSSI {entry.rssi} addr {entry.addr} data {entry.getScanData()}')

        # First 2 bytes are manufacturer ID 004C which is Apple
        # Last 2 bytes are the PNP product ID:
        # Gen 1 - 0266
        # Gen 1.5 - 026D
        # Gen 2 - 0314
        # Gen 3 - 0315
        supported_manufacturer_strings = {
            '4c008a076602' : 'Siri Remote, Gen 1',
            '4c008a076d02' : 'Siri Remote, Gen 1.5',
            '4c00070d021403' : 'Siri Remote, Gen 2',
            '4c00070d021503' : 'Siri Remote, Gen 3',
        }
        mfr = entry.getValueText(entry.MANUFACTURER)
        name = None
        is_siri_remote = False
        for prefix, kind in supported_manufacturer_strings.items():
            if mfr.startswith(prefix):
                name = kind
                is_siri_remote = True
                break
        log.debug(f'is_siri_remote {is_siri_remote}')
        if name is None:
            service_uuids = entry.getValue(entry.COMPLETE_16B_SERVICES)
            if service_uuids is None:
                service_uuids = entry.getValue(entry.INCOMPLETE_16B_SERVICES)
            if service_uuids is None:
                service_uuids = []
            log.debug(f'service_uuids {service_uuids}')
            if AssignedNumbers.human_interface_device in service_uuids:
                name = entry.getValueText(entry.COMPLETE_LOCAL_NAME)
                if name is None:
                    name = entry.getValueText(entry.SHORT_LOCAL_NAME)
                if name is None:
                    name = 'Input Device'

        log.debug(f'name is {name}')

        # This is neither an internally supported Siri Remote, nor a generic keyboard device
        if name is None:
            return

        if entry.rssi < -50:
            log.info(f'Bring {name} closer to me!\n')
            return

        try:
            device = btle.Peripheral(entry)
        except btle.BTLEException as e:
            log.debug(f'Failed to create peripheral {e}')
            return

        log.info('Pairing...')
        try:
            self.pairing = True
            device.setBondable(True)
            device.setSecurityLevel(btle.SEC_LEVEL_MEDIUM)
            public_addr, _ = device.pair()
            self.pairing = False
            log.info(f'Paired with {name}')

            return is_siri_remote, name, public_addr
        except btle.BTLEManagementError:
            log.info('Pairing failed. Try resetting the remote.')

    def scan(self):
        while True:
            try:
                entries = self.scanner.scan(1)
                for entry in entries:
                    remote = self.check_pair(entry)
                    if remote is not None:
                        return remote
            except (btle.BTLEConnectError, BrokenPipeError) as e:
                if self.pairing:
                    log.info('Pairing failed. Try resetting the remote.')

def main():
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('-d', '--debug', action='store_true', help='enable debug messages')
    arg_parser.add_argument('-n', '--nowrite', action='store_true',
                            help="don't write remote configuration to config.yaml")
    arg_parser.add_argument('-k', '--keep', action='store_true',
                            help='keep the previous remote paired. Otherwise it will be unpaired.')
    args = arg_parser.parse_args()
    if args.debug:
        tools.set_log_level('debug')
    log.addHandler(logging.StreamHandler(sys.stdout))
    log.info('Bring the remote close to me, and start the pairing process on the remote.\n')

    scanner = Scanner()
    is_siri_remote, name, public_addr = scanner.scan()

    if is_siri_remote:
        config_path = 'remote.mac'
    else:
        # Amity intercepts keyboard events and so doesn't use the keyboard MAC address directly.
        # The MAC is tracked to allow managing keyboards here, and ensuring that only one is
        # paired at any given time.
        # Note that at the moment both a Siri remote, and a keybord can be paired at once.
        config_path = 'keyboard.mac'

    if not args.nowrite:
        old_addr = None
        backup = False
        config.load()
        if config[config_path] is not None:
            backup = True
            old_addr = config[config_path]

        # Update the config
        config[config_path] = public_addr
        config.save(backup)

        # Unpair the previous remote, if there is one
        if not args.keep and old_addr is not None and old_addr != public_addr:
            log.debug(f'Unpairing previous remote {old_addr}')
            subprocess.run(['/usr/bin/bluetoothctl', 'remove', old_addr], capture_output=True)
    else:
        if is_siri_remote:
            log.info(f'Remote configuration is:\n')
            log.info(f'remote:\n    mac: {public_addr}\n\n')

if __name__ == '__main__':
    main()
