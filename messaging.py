# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio, sys

from enum import Enum, auto

class Type(Enum):
    SetActivity = auto()
    KeyPress = auto()
    KeyRelease = auto()

class Message(object):
    def __init__(self, type, val):
        self.type = type
        self.val = val

# A trivial object for connecting the Hub and UI indirectly with duck typing.
class Pipe(object):
    def __init__(self):
        self.server_q = asyncio.Queue()
        self.client_q = asyncio.Queue()
        self.server_t = None
        self.client_t = None
        self.tasks = set()

    def taskit(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.check_task)
        return task

    # Server calls
    def notify_set_activity(self, index):
        if self.client_t:
            self.taskit(self.client_q.put(Message(Type.SetActivity, index)))

    def check_task(self, task):
        self.tasks.discard(task)
        e = task.exception()
        if e is not None:
            log.info(f'Task exception {e}')
            sys.exit(1)

    def start_server_task(self, handler):
        self.server_t = self.taskit(self.server_task(handler))

    # Server handler
    async def server_task(self, handler):
        while True:
            msg = await self.server_q.get()
            match msg.type:
                case Type.SetActivity:
                    handler.client_set_activity(msg.val)
                case Type.KeyPress:
                    handler.client_press_key(msg.val)
                case Type.KeyRelease:
                    handler.client_release_key(msg.val)

    # Client calls
    def set_activity(self, index):
        if self.server_t:
            self.taskit(self.server_q.put(Message(Type.SetActivity, index)))

    def key_press(self, key):
        if self.server_t:
            self.taskit(self.server_q.put(Message(Type.KeyPress, key)))

    def key_release(self, key):
        if self.server_t:
            self.taskit(self.server_q.put(Message(Type.KeyRelease, key)))

    # Client handler
    def start_client_task(self, handler):
        self.client_t = self.taskit(self.client_task(handler))

    async def client_task(self, handler):
        while True:
            msg = await self.client_q.get()
            match msg.type:
                case Type.SetActivity:
                    handler.server_notify_set_activity(msg.val)
