# Copyright 2026.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import test_common
from test_common import make_taskit_mock

import unittest
from unittest.mock import AsyncMock, MagicMock
import asyncio

import messaging


class TestMessage(unittest.TestCase):
    def test_init_with_type_only(self):
        msg = messaging.Message(messaging.Type.KeyRelease)
        self.assertEqual(msg.type, messaging.Type.KeyRelease)
        self.assertEqual(msg.values, ())

    def test_init_with_single_value(self):
        msg = messaging.Message(messaging.Type.SetActivity, 2)
        self.assertEqual(msg.type, messaging.Type.SetActivity)
        self.assertEqual(msg.values, (2,))

    def test_init_with_multiple_values(self):
        msg = messaging.Message(messaging.Type.BatteryState, 85, True, False)
        self.assertEqual(msg.type, messaging.Type.BatteryState)
        self.assertEqual(msg.values, (85, True, False))


class TestPipeClientCalls(unittest.TestCase):
    def setUp(self):
        self.pipe = messaging.Pipe()
        self.pipe.taskit = make_taskit_mock()

    def test_set_activity_no_server(self):
        self.pipe.set_activity(0)
        self.pipe.taskit.assert_not_called()

    def test_set_activity_with_server(self):
        self.pipe.server_t = True
        self.pipe.set_activity(0)
        self.pipe.taskit.assert_called_once()

    def test_key_press_no_server(self):
        self.pipe.key_press(0x01)
        self.pipe.taskit.assert_not_called()

    def test_key_press_with_server(self):
        self.pipe.server_t = True
        self.pipe.key_press(0x01, 1)
        self.pipe.taskit.assert_called_once()

    def test_key_release_no_server(self):
        self.pipe.key_release(0x01)
        self.pipe.taskit.assert_not_called()

    def test_key_release_with_server(self):
        self.pipe.server_t = True
        self.pipe.key_release(0x01)
        self.pipe.taskit.assert_called_once()

    def test_battery_state_no_server(self):
        self.pipe.battery_state(85, True)
        self.pipe.taskit.assert_not_called()

    def test_battery_state_with_server(self):
        self.pipe.server_t = True
        self.pipe.battery_state(85, True)
        self.pipe.taskit.assert_called_once()


class TestPipeServerCalls(unittest.TestCase):
    def setUp(self):
        self.pipe = messaging.Pipe()
        self.pipe.taskit = make_taskit_mock()

    def test_notify_set_activity_no_client(self):
        self.pipe.notify_set_activity(0)
        self.pipe.taskit.assert_not_called()

    def test_notify_set_activity_with_client(self):
        self.pipe.client_t = True
        self.pipe.notify_set_activity(0)
        self.pipe.taskit.assert_called_once()

    def test_notify_battery_state_no_client(self):
        self.pipe.notify_battery_state(85, True, False)
        self.pipe.taskit.assert_not_called()

    def test_notify_battery_state_with_client(self):
        self.pipe.client_t = True
        self.pipe.notify_battery_state(85, True, False)
        self.pipe.taskit.assert_called_once()


async def run_task_once(task_coro, queue, msg):
    """Run an infinite-loop task coroutine for exactly one message dispatch."""
    queue.put_nowait(msg)
    task = asyncio.create_task(task_coro)
    # Wait just long enough for the single message to be processed
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


class TestPipeServerTask(unittest.TestCase):
    def _run_server(self, msg, handler):
        pipe = messaging.Pipe()
        asyncio.run(run_task_once(pipe.server_task(handler), pipe.server_q, msg))

    def test_dispatches_set_activity(self):
        handler = MagicMock()
        handler.client_set_activity = AsyncMock()
        self._run_server(messaging.Message(messaging.Type.SetActivity, 2), handler)
        handler.client_set_activity.assert_called_once_with(2)

    def test_dispatches_key_press(self):
        handler = MagicMock()
        handler.client_press_key = AsyncMock()
        self._run_server(messaging.Message(messaging.Type.KeyPress, 0x01, 0), handler)
        handler.client_press_key.assert_called_once_with(0x01, 0)

    def test_dispatches_key_release(self):
        handler = MagicMock()
        handler.client_release_key = AsyncMock()
        self._run_server(messaging.Message(messaging.Type.KeyRelease, 0x01), handler)
        handler.client_release_key.assert_called_once_with(0x01)

    def test_dispatches_battery_state(self):
        handler = MagicMock()
        handler.client_battery_state = AsyncMock()
        self._run_server(messaging.Message(messaging.Type.BatteryState, 85, True, False), handler)
        handler.client_battery_state.assert_called_once_with(85, True, False)


class TestPipeClientTask(unittest.TestCase):
    def _run_client(self, msg, handler):
        pipe = messaging.Pipe()
        asyncio.run(run_task_once(pipe.client_task(handler), pipe.client_q, msg))

    def test_dispatches_set_activity(self):
        handler = MagicMock()
        handler.server_notify_set_activity = AsyncMock()
        self._run_client(messaging.Message(messaging.Type.SetActivity, 3), handler)
        handler.server_notify_set_activity.assert_called_once_with(3)

    def test_dispatches_battery_state(self):
        handler = MagicMock()
        handler.server_notify_battery_state = AsyncMock()
        self._run_client(messaging.Message(messaging.Type.BatteryState, 50, False, True), handler)
        handler.server_notify_battery_state.assert_called_once_with(50, False, True)


class TestPipeStartTasks(unittest.TestCase):
    def setUp(self):
        self.pipe = messaging.Pipe()
        self.pipe.taskit = make_taskit_mock()

    def test_start_server_task(self):
        handler = MagicMock()
        self.pipe.start_server_task(handler)
        self.assertIsNotNone(self.pipe.server_t)
        self.pipe.taskit.assert_called_once()

    def test_start_client_task(self):
        handler = MagicMock()
        self.pipe.start_client_task(handler)
        self.assertIsNotNone(self.pipe.client_t)
        self.pipe.taskit.assert_called_once()


if __name__ == '__main__':
    unittest.main()
