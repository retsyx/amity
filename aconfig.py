# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio, os

from watchdog.observers import Observer

from config import Config

class Watcher(object):
    def __init__(self, filename, callback):
        self.loop = None
        self.observer = None
        self.watch = None
        self.full_path = filename
        path = os.path.dirname(self.full_path)
        if path == '':
            path = '.'
        self.dir_path = path
        self.filename = os.path.basename(self.full_path)
        self.callback = callback

    def start(self):
        if self.loop is None:
            self.loop = asyncio.get_event_loop()
        if self.observer is None:
            log.info(f'Start watch of {self.full_path}')
            self.observer = Observer()
            self.observer.start()
            self.watch = self.observer.schedule(self, self.dir_path, recursive=False)

    def dispatch(self, event):
        if (not event.is_directory and
                (event.src_path == self.full_path and
                 event.event_type in ('created', 'modified')) or
                 (event.src_path == self.full_path or
                  event.dest_path == self.full_path) and
                 event.event_type in ('moved', )):
            log.info(f'Event {event}')
            self.loop.call_soon_threadsafe(self.callback)

class ConfigWatcher(Watcher):
    def __init__(self, config, callback):
        super().__init__(config.filename, callback)

config = Config('var/config/config.yaml')
