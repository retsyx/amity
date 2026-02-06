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

class LogAndPrint(object):
    def __init__(self, log, stdout):
        self.log = log
        self.stdout = stdout

    def debug(self, *args):
        self.log.debug(*args)
        if self.log.getEffectiveLevel() <= logging.DEBUG:
            self.stdout.write(*args)
            self.stdout.write('\n')

    def info(self, *args):
        self.log.info(*args)
        if self.log.getEffectiveLevel() <= logging.INFO:
            self.stdout.write(*args)
            self.stdout.write('\n')

class Detector(object):
    def __init__(self, log):
        self.is_siri_remote = False
        self.log = log

class SiriRemoteDetector(Detector):
    def __init__(self, log):
        super().__init__(log)
        self.is_siri_remote = True

        # First 2 bytes are manufacturer ID 004C which is Apple
        # Last 2 bytes are the PNP product ID:
        # Gen 1 - 0266
        # Gen 1.5 - 026D
        # Gen 2 - 0314
        # Gen 3 - 0315
        self.supported_manufacturer_strings = {
            '4c008a076602' : 'Siri Remote, Gen 1',
            '4c008a076d02' : 'Siri Remote, Gen 1.5',
            '4c00070d021403' : 'Siri Remote, Gen 2',
            '4c00070d021503' : 'Siri Remote, Gen 3',
        }

    def probe(self, entry):
        mfr = entry.getValueText(entry.MANUFACTURER).lower()
        for prefix, name in self.supported_manufacturer_strings.items():
            if mfr.startswith(prefix):
                return name
        return None

class LgMagicRemoteDetector(Detector):
    def __init__(self, log):
        super().__init__(log)
        self.magic = ''.join((f'{ord(c):02x}' for c in 'webOS'))

    def probe(self, entry):
        mfr = entry.getValueText(entry.MANUFACTURER).lower()
        if not mfr.startswith('c400'):
            return None
        if self.magic not in mfr[2:]:
            return None
        name = entry.getValueText(entry.COMPLETE_LOCAL_NAME)
        if name is None:
            name = entry.getValueText(entry.SHORT_LOCAL_NAME)
        if name is None:
            name = 'LG Magic Remote'
        return name

class KeyboardDetector(Detector):
    def __init__(self, log):
        super().__init__(log)

    def probe(self, entry):
        name = None
        service_uuids = entry.getValue(entry.COMPLETE_16B_SERVICES)
        if service_uuids is None:
            service_uuids = entry.getValue(entry.INCOMPLETE_16B_SERVICES)
        if service_uuids is None:
            service_uuids = []
        self.log.debug(f'service_uuids {service_uuids}')
        if AssignedNumbers.human_interface_device in service_uuids:
            name = entry.getValueText(entry.COMPLETE_LOCAL_NAME)
            if name is None:
                name = entry.getValueText(entry.SHORT_LOCAL_NAME)
            if name is None:
                name = 'A keyboard'
        return name

class Scanner(object):
    def __init__(self):
        self.scanner = btle.Scanner()
        self.scanner.withDelegate(self)
        self.pairing = False
        self.known_addresses = set()
        sys.stdout.reconfigure(line_buffering=True)
        self.log = LogAndPrint(log, sys.stdout)
        self.detectors = tuple((det(self.log) for det in (
            SiriRemoteDetector,
            LgMagicRemoteDetector,
            KeyboardDetector,
        )))

    def handleDiscovery(self, entry, isNewDev, isNewData):
        pass

    def check_pair(self, entry):
        device_str = f'Device RSSI {entry.rssi} addr {entry.addr} data {entry.getScanData()}'
        if entry.addr not in self.known_addresses:
            self.known_addresses.add(entry.addr)
            self.log.debug(device_str)
            log.info(device_str)

        name = None
        for detector in self.detectors:
            name = detector.probe(entry)
            if name is not None:
                is_siri_remote = detector.is_siri_remote
                break

        self.log.debug(f'name is {name}')

        # This is neither an internally supported Siri Remote, nor a generic keyboard device
        if name is None:
            return

        self.log.debug(f'is_siri_remote {is_siri_remote}')

        if entry.rssi < -50:
            self.log.info(f'Bring {name} closer to me!\n')
            return

        try:
            device = btle.Peripheral(entry)
        except btle.BTLEException as e:
            self.log.debug(f'Failed to create peripheral {e}')
            return

        self.log.info('Pairing...')
        try:
            self.pairing = True
            device.setBondable(True)
            device.setSecurityLevel(btle.SEC_LEVEL_MEDIUM)
            public_addr, _ = device.pair()
            # Disconnect locally in bluepy3 so bluetoothctl can connect below
            device.disconnect()
            # Enable trust for the device
            subprocess.run(['/usr/bin/bluetoothctl', 'trust', public_addr], capture_output=True)
            # And connect to it to tickle the system to auto-connect in the future (ZOMG!?)
            subprocess.run(['/usr/bin/bluetoothctl', 'connect', public_addr], capture_output=True)

            self.pairing = False
            self.log.info(f'Paired with {name}')

            return is_siri_remote, name, public_addr
        except btle.BTLEManagementError:
            self.log.info('Pairing failed. Try resetting the remote.')

    def scan(self):
        self.log.info('Bring the remote close to me, and start the pairing process on the remote.\n')
        while True:
            try:
                entries = self.scanner.scan(1)
                for entry in entries:
                    remote = self.check_pair(entry)
                    if remote is not None:
                        return remote
            except (btle.BTLEConnectError, BrokenPipeError) as e:
                if self.pairing:
                    self.log.info('Pairing failed. Try resetting the remote.')

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
    scanner = Scanner()
    is_siri_remote, name, public_addr = scanner.scan()

    if is_siri_remote:
        mac_path = 'remote.mac'
        name_path = 'remote.name'
        other_mac_path = 'keyboard.mac'
        other_name_path = 'keyboard.name'
    else:
        # Amity intercepts keyboard events and so doesn't use the keyboard MAC to connect.
        # The MAC is tracked to allow managing keyboards here, to ensure that only one is
        # paired at any given time. The MAC is also used to monitor keyboard battery level, if
        # it is available.
        mac_path = 'keyboard.mac'
        name_path = 'keyboard.name'
        other_mac_path = 'remote.mac'
        other_name_path = 'remote.name'

    if not args.nowrite:
        # Only one remote can be paired at any given time.
        config.load()
        old_addrs = (config['remote.mac'], config['keyboard.mac'])
        backup = any(old_addrs)

        # Update the config
        config[mac_path] = public_addr
        config[name_path] = name
        if not args.keep:
            config[other_mac_path] = None
            config[other_name_path] = None
        config.save(backup)

        # Unpair the previous remote, if there is one
        if not args.keep:
            for old_addr in old_addrs:
                if old_addr is not None and old_addr != public_addr:
                    log.info(f'Unpairing previous remote {old_addr}')
                    subprocess.run(['/usr/bin/bluetoothctl', 'remove', old_addr], capture_output=True)
    else:
        if is_siri_remote:
            log.info(f'Remote configuration is:\n')
            log.info(f'remote:\n    mac: {public_addr}\n\n')

if __name__ == '__main__':
    main()
