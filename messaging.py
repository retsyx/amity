# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio
from typing import Any, Protocol, runtime_checkable

from enum import Enum, auto

class Type(Enum):
    SetActivity = auto()
    KeyPress = auto()
    KeyRelease = auto()
    BatteryState = auto()

class Message:
    def __init__(self, type: Type, *values: Any) -> None:
        self.type = type
        self.values = values

@runtime_checkable
class ServerHandler(Protocol):
    async def client_set_activity(self, index: int) -> None: ...
    async def client_press_key(self, key: int, count: int = 0) -> None: ...
    async def client_release_key(self, key: int) -> None: ...
    async def client_battery_state(self, level: int, is_charging: bool) -> None: ...

@runtime_checkable
class ClientHandler(Protocol):
    async def server_notify_set_activity(self, index: int) -> None: ...
    async def server_notify_battery_state(self, level: int, is_charging: bool, is_low: bool) -> None: ...

# A trivial object for connecting the Hub and UI indirectly with duck typing.
class Pipe:
    def __init__(self) -> None:
        self.server_q: asyncio.Queue[Message] = asyncio.Queue()
        self.client_q: asyncio.Queue[Message] = asyncio.Queue()
        self.server_t: asyncio.Task[None] | None = None
        self.client_t: asyncio.Task[None] | None = None
        self.taskit = tools.Tasker('Messaging')

    # Server calls
    def notify_set_activity(self, index: int) -> None:
        if self.client_t:
            self.taskit(self.client_q.put(Message(Type.SetActivity, index)))

    def notify_battery_state(self, level: int, is_charging: bool, is_low: bool) -> None:
        if self.client_t:
            self.taskit(self.client_q.put(Message(Type.BatteryState, level, is_charging, is_low)))

    def start_server_task(self, handler: ServerHandler) -> None:
        self.server_t = self.taskit(self.server_task(handler))

    # Server handler
    async def server_task(self, handler: ServerHandler) -> None:
        while True:
            try:
                msg = await self.server_q.get()
                match msg.type:
                    case Type.SetActivity:
                        await handler.client_set_activity(*msg.values)  # type: ignore[arg-type]
                    case Type.KeyPress:
                        await handler.client_press_key(*msg.values)  # type: ignore[arg-type]
                    case Type.KeyRelease:
                        await handler.client_release_key(*msg.values)  # type: ignore[arg-type]
                    case Type.BatteryState:
                        await handler.client_battery_state(*msg.values)  # type: ignore[arg-type]
            except AttributeError as e:
                log.debug(e)

    # Client calls
    def set_activity(self, index: int) -> None:
        if self.server_t:
            self.taskit(self.server_q.put(Message(Type.SetActivity, index)))

    def key_press(self, key: int, count: int = 0) -> None:
        if self.server_t:
            self.taskit(self.server_q.put(Message(Type.KeyPress, key, count)))

    def key_release(self, key: int) -> None:
        if self.server_t:
            self.taskit(self.server_q.put(Message(Type.KeyRelease, key)))

    def battery_state(self, level: int, is_charging: bool) -> None:
        if self.server_t:
            self.taskit(self.server_q.put(Message(Type.BatteryState, level, is_charging)))

    # Client handler
    def start_client_task(self, handler: ClientHandler) -> None:
        self.client_t = self.taskit(self.client_task(handler))

    async def client_task(self, handler: ClientHandler) -> None:
        while True:
            try:
                msg = await self.client_q.get()
                match msg.type:
                    case Type.SetActivity:
                        await handler.server_notify_set_activity(*msg.values)  # type: ignore[arg-type]
                    case Type.BatteryState:
                        await handler.server_notify_battery_state(*msg.values)  # type: ignore[arg-type]
            except AttributeError as e:
                log.debug(e)
