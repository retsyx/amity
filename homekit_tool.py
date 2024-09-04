#!/usr/bin/env python

# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger('log/homekit_tool')

import argparse, os, subprocess, time

from config import config

config_homekit_enable_path = 'homekit.enable'
homekit_state_path = 'homekit.state'
homekit_code_path = 'homekit.code'

class AmityControl(object):
    def __init__(self):
        self.bin = '/usr/bin/systemctl'
        self.name = 'amity'

    def is_active(self):
        output = subprocess.run([self.bin, '--user', 'is-active', self.name], capture_output=True)
        return output.stdout.decode('utf-8').strip() == 'active'

    def stop(self):
        log.info(f'Stopping {self.name}')
        subprocess.run([self.bin, '--user', 'stop', self.name], capture_output=True)

    def start(self):
        log.info(f'Starting {self.name}')
        subprocess.run([self.bin, '--user', 'start', self.name], capture_output=True)

    def safe_do(self, op):
        active = self.is_active()
        if active:
            self.stop()
        op()
        if active:
            self.start()

def enable(control):
    log.info('Enable')
    try:
        stat = os.stat(homekit_code_path)
        mtime = stat.st_mtime
    except FileNotFoundError:
        mtime = 0
    if config[config_homekit_enable_path] != True:
        def op():
            config[config_homekit_enable_path] = True
            config.save(True)
        control.safe_do(op)
    if not control.is_active():
        s = 'Amity not running'
        log.info(s)
        print(s)
        return
    start = time.time()
    while time.time() - start < 20.0:
        try:
            stat = os.stat(homekit_code_path)
            if mtime != stat.st_mtime:
                break
        except FileNotFoundError:
            pass
        time.sleep(.5)
    code(control)

def read_code_file():
    try:
        with open(homekit_code_path, 'r') as file:
            s = file.read()
    except FileNotFoundError:
        s = 'No code. Is HomeKit enabled?'
    return s

def code(control):
    log.info('Code')
    if not config[config_homekit_enable_path]:
        s = 'HomeKit is disabled'
    elif not control.is_active():
        s = 'Amity not running'
    else:
        s = read_code_file()
    log.info(s)
    print(s)

def disable(control):
    log.info('Disable')
    if config[config_homekit_enable_path] == False:
        return
    def op():
        config[config_homekit_enable_path] = False
        config.save(True)
    control.safe_do(op)

def reset(control):
    log.info('Reset')
    def op():
        try:
            os.unlink(homekit_state_path)
        except FileNotFoundError:
            pass
        try:
            os.unlink(homekit_code_path)
        except FileNotFoundError:
            pass
    control.safe_do(op)
    if not control.is_active():
        return
    start = time.time()
    while time.time() - start < 20.0:
        try:
            stat = os.stat(homekit_code_path)
            break
        except FileNotFoundError:
            pass
        time.sleep(.5)
    code(control)

def main():
    actions = ('enable', 'code', 'disable', 'reset')
    arg_parser = argparse.ArgumentParser()
    arg_parser.add_argument('action', default='', choices=actions, help='action to perform')
    args = arg_parser.parse_args()
    config.load()
    control = AmityControl()
    match args.action:
        case 'enable':
            enable(control)
        case 'code':
            code(control)
        case 'disable':
            disable(control)
        case 'reset':
            reset(control)

if __name__ == '__main__':
    main()
