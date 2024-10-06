# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio

from enum import Enum, auto

class Type(Enum):
    SetActivity = auto()
    KeyPress = auto()
    KeyRelease = auto()
    BatteryState = auto()

class Message(object):
    def __init__(self, type, *values):
        self.type = type
        self.values = values

# A trivial object for connecting the Hub and UI indirectly with duck typing.
class Pipe(object):
    def __init__(self):
        self.server_q = asyncio.Queue()
        self.client_q = asyncio.Queue()
        self.server_t = None
        self.client_t = None
        self.taskit = tools.Tasker('Messaging')

    # Server calls
    def notify_set_activity(self, index):
        if self.client_t:
            self.taskit(self.client_q.put(Message(Type.SetActivity, index)))

    def notify_battery_state(self, level, is_charging, is_low):
        if self.client_t:
            self.taskit(self.client_q.put(Message(Type.BatteryState, level, is_charging, is_low)))

    def start_server_task(self, handler):
        self.server_t = self.taskit(self.server_task(handler))

    # Server handler
    async def server_task(self, handler):
        while True:
            try:
                msg = await self.server_q.get()
                match msg.type:
                    case Type.SetActivity:
                        await handler.client_set_activity(*msg.values)
                    case Type.KeyPress:
                        await handler.client_press_key(*msg.values)
                    case Type.KeyRelease:
                        await handler.client_release_key(*msg.values)
                    case Type.BatteryState:
                        await handler.client_battery_state(*msg.values)
            except AttributeError as e:
                log.debug(e)

    # Client calls
    def set_activity(self, index):
        if self.server_t:
            self.taskit(self.server_q.put(Message(Type.SetActivity, index)))

    def key_press(self, key, count=0):
        if self.server_t:
            self.taskit(self.server_q.put(Message(Type.KeyPress, key, count)))

    def key_release(self, key):
        if self.server_t:
            self.taskit(self.server_q.put(Message(Type.KeyRelease, key)))

    def battery_state(self, level, is_charging):
        if self.server_t:
            self.taskit(self.server_q.put(Message(Type.BatteryState, level, is_charging)))

    # Client handler
    def start_client_task(self, handler):
        self.client_t = self.taskit(self.client_task(handler))

    async def client_task(self, handler):
        while True:
            try:
                msg = await self.client_q.get()
                match msg.type:
                    case Type.SetActivity:
                        await handler.server_notify_set_activity(*msg.values)
                    case Type.BatteryState:
                        await handler.server_notify_battery_state(*msg.values)
            except AttributeError as e:
                log.debug(e)
