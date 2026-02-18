# Copyright 2024-2026.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio, os
from collections.abc import Callable

from watchdog.events import FileSystemEvent, FileSystemEventHandler
from watchdog.observers import Observer
from watchdog.observers.api import ObservedWatch, BaseObserver

from config import Config

class Watcher(FileSystemEventHandler):
    def __init__(self, filename: str, callback: Callable[[], None]) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.observer: BaseObserver | None = None
        self.watch: ObservedWatch | None = None
        self.full_path = filename
        path = os.path.dirname(self.full_path)
        if path == '':
            path = '.'
        self.dir_path = path
        self.filename = os.path.basename(self.full_path)
        self.callback = callback

    def start(self) -> None:
        if self.loop is None:
            self.loop = asyncio.get_event_loop()
        if self.observer is None:
            log.info(f'Start watch of {self.full_path}')
            self.observer = Observer()
            self.observer.start()
            self.watch = self.observer.schedule(self, self.dir_path, recursive=False)

    def dispatch(self, event: FileSystemEvent) -> None:
        if (not event.is_directory and
                (event.src_path == self.full_path and
                 event.event_type in ('created', 'modified')) or
                 (event.src_path == self.full_path or
                  event.dest_path == self.full_path) and
                 event.event_type in ('moved', )):
            log.info(f'Event {event}')
            if self.loop is not None:
                self.loop.call_soon_threadsafe(self.callback)

class ConfigWatcher(Watcher):
    def __init__(self, config: Config, callback: Callable[[], None]) -> None:
        super().__init__(config.filename, callback)

config = Config('var/config/config.yaml')
