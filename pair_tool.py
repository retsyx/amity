#!/usr/bin/env python

# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger("log/pair_tool.log")

import argparse, logging, os, subprocess, shutil, sys, time

from bluepy import btle
from bluepy.btle import AssignedNumbers
from config import config
from remote import PnpInfo

class Scanner(object):
    def __init__(self):
        self.scanner = btle.Scanner()
        self.scanner.withDelegate(self)
        self.pairing = False

    def handleDiscovery(self, entry, isNewDev, isNewData):
        pass

    def check_pair(self, entry):
        manufacturer = entry.getValueText(255)
        log.debug(f'Device RSSI {entry.rssi} addr {entry.addr} data {entry.getScanData()}')

        if manufacturer is None:
            return

        # First 2 bytes are manufacturer ID 004C which is Apple
        # Last 2 bytes are the PNP product ID:
        # Gen 1 - 0266
        # Gen 1.5 - 026D
        # Gen 2 - 0314
        # Gen 3 - 0315
        if (not manufacturer.startswith('4c008a076602') # gen 1
            and not manufacturer.startswith('4c008a076d02') # gen 1.5
            and not manufacturer.startswith('4c00070d021403') # gen 2
            and not manufacturer.startswith('4c00070d021503') # gen 3
            ):
            return

        if entry.rssi < -50:
            log.info('Bring the remote closer to me!\n')
            return

        try:
            device = btle.Peripheral(entry)
        except btle.BTLEException as e:
            return

        log.info('Pairing...')
        try:
            self.pairing = True
            device.setBondable(True)
            device.setSecurityLevel(btle.SEC_LEVEL_MEDIUM)
            public_addr, _ = device.pair()
            self.pairing = False
            log.info('Paired!')

            device.getServices()
            device_info_svc = device.getServiceByUUID(AssignedNumbers.device_information)
            pnp_data = None
            serial_number = None
            for ch in device_info_svc.getCharacteristics():
                if ch.uuid == AssignedNumbers.pnp_id:
                    pnp_data = device.readCharacteristic(ch.getHandle())
                elif ch.uuid == AssignedNumbers.serial_number_string:
                    serial_number = device.readCharacteristic(ch.getHandle()).decode()

            pnp_info = PnpInfo(pnp_data)
            log.debug(f'PNP {pnp_info}')

            return serial_number, public_addr
        except btle.BTLEManagementError:
            log.info('Pairing failed. Try resetting the remote.')
            log.info('Trying again!\n')

    def scan(self):
        while True:
            try:
                entries = self.scanner.scan(1)
                for entry in entries:
                    remote = self.check_pair(entry)
                    if remote is not None:
                        return remote
            except (btle.BTLEDisconnectError, BrokenPipeError) as e:
                if self.pairing:
                    log.info('Pairing failed. Try resetting the remote.')
                    log.info('Trying again!\n')

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
    serial_number, public_addr = scanner.scan()

    log.info(f'Paired with remote {serial_number}')

    if not args.nowrite:
        old_addr = None
        config.load()
        if config['remote.mac'] is not None:
            old_addr = config['remote.mac']
            # Make a backup of the config file
            backup_time_str = time.strftime('%Y%m%d-%H%M%S')
            backup_filename = f'{config.filename}-{backup_time_str}'
            shutil.copy(config.filename, backup_filename)
            # This is running as root, so chown the backup to match the original config file
            stat = os.stat(config.filename)
            shutil.chown(backup_filename, stat.st_uid, stat.st_gid)
            log.debug(f'Created backup {backup_filename}')

        # Update the config
        config['remote.mac'] = public_addr
        log.debug(f'Writing remote config {config}')
        config.save()

        # Make sure the configuration file has the right ownership
        stat = os.stat('.')
        shutil.chown(config.filename, stat.st_uid, stat.st_gid)

        # Unpair the previous remote, if there is one
        if not args.keep and old_addr is not None and old_addr != public_addr:
            log.debug(f'Unpairing previous remote {old_addr}')
            subprocess.run(['/usr/bin/bluetoothctl', 'remove', old_addr], capture_output=True)
    else:
        log.info(f'Remote configuration is:\n')
        log.info(f'remote:\n    mac: {public_addr}\n\n')

if __name__ == '__main__':
    main()
