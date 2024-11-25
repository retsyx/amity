#!/usr/bin/env python

# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import subprocess

class Control(object):
    def __init__(self, name):
        self.bin = '/usr/bin/systemctl'
        self.name = name

    def is_active(self):
        output = subprocess.run([self.bin, '--user', 'is-active', self.name], capture_output=True)
        log.info(f'Is active {output}')
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
