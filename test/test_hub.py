# Copyright 2025.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import test_common
from test_common import make_taskit_mock

import unittest
from unittest.mock import Mock, patch, AsyncMock
import asyncio
import time

from main import Hub, KeyState
from hdmi import Key, no_activity


class MockController:
    """Mock controller for testing"""
    def __init__(self):
        self.current_activity = None
        self.press_key = AsyncMock(return_value=True)
        self.release_key = AsyncMock()
        self.set_activity = AsyncMock(return_value=True)
        self.standby = AsyncMock()
        self.force_standby = AsyncMock()
        self.fix_current_activity = AsyncMock()


class MockPipe:
    """Mock pipe for testing"""
    def __init__(self):
        self.notify_set_activity = Mock()
        self.notify_battery_state = Mock()
        self.start_server_task = Mock()


class TestKeyState(unittest.TestCase):
    """Test cases for the KeyState class"""

    def test_init(self):
        """Test KeyState initialization"""
        state = KeyState(5)
        self.assertEqual(state.repeat_count, 5)
        self.assertIsNotNone(state.timestamp)

    def test_timestamp_is_current_time(self):
        """Test that timestamp is set to current time"""
        before = time.time()
        state = KeyState(0)
        after = time.time()
        self.assertGreaterEqual(state.timestamp, before)
        self.assertLessEqual(state.timestamp, after)


class TestHubInit(unittest.TestCase):
    """Test cases for Hub initialization"""

    def setUp(self):
        """Set up test fixtures"""
        # Set config values using direct assignment
        test_common.mock_config['hub.activity_map'] = {
            Key.SELECT.value: 0,
            Key.UP.value: 1,
        }
        test_common.mock_config['hub.macros'] = [
            (Key.POWER.value, Key.SELECT.value),
        ]
        test_common.mock_config['hub.long_press.duration_sec'] = 0.5
        test_common.mock_config['hub.long_press.keymap'] = {
            Key.SELECT.value: Key.F6.value,
        }
        test_common.mock_config['hub.short_press.keymap'] = {
            Key.POWER.value: Key.SELECT.value,
        }
        test_common.mock_config['hub.play_pause.mode'] = 'emulate'
        test_common.mock_config['remote.battery.low_threshold'] = 10

        # Create mock controller
        self.controller = MockController()

    def test_init(self):
        """Test Hub initialization"""
        with patch('asyncio.get_running_loop'):
            hub = Hub(self.controller)

        self.assertIsNotNone(hub)
        self.assertEqual(hub.controller, self.controller)
        self.assertEqual(hub.key_state, {})
        self.assertTrue(hub.wait_for_release)
        self.assertEqual(hub.pipes, [])
        self.assertFalse(hub.in_macro)
        self.assertIsNone(hub.macro_index)
        self.assertFalse(hub.macro_executed)
        self.assertFalse(hub.play_pause_is_playing)

    def test_init_loads_config_values(self):
        """Test that initialization loads config values correctly"""
        with patch('asyncio.get_running_loop'):
            hub = Hub(self.controller)

        self.assertEqual(hub.activity_map[Key.SELECT.value], 0)
        self.assertEqual(hub.activity_map[Key.UP.value], 1)
        self.assertEqual(hub.long_press_duration_sec, 0.5)
        self.assertEqual(hub.play_pause_mode, 'emulate')


class TestHubSync(unittest.TestCase):
    """Synchronous test cases for the Hub class"""

    def setUp(self):
        """Set up test fixtures"""
        # Set config values using direct assignment
        test_common.mock_config['hub.activity_map'] = {
            Key.SELECT.value: 0,
            Key.UP.value: 1,
        }
        test_common.mock_config['hub.macros'] = [
            (Key.POWER.value, Key.SELECT.value),
        ]
        test_common.mock_config['hub.long_press.duration_sec'] = 0.5
        test_common.mock_config['hub.long_press.keymap'] = {
            Key.SELECT.value: Key.F6.value,
        }
        test_common.mock_config['hub.short_press.keymap'] = {
            Key.POWER.value: Key.SELECT.value,
        }
        test_common.mock_config['hub.play_pause.mode'] = 'emulate'
        test_common.mock_config['remote.battery.low_threshold'] = 10

        self.controller = MockController()
        with patch('asyncio.get_running_loop'):
            self.hub = Hub(self.controller)
        self.hub.taskit = make_taskit_mock()

    def test_add_pipe(self):
        """Test adding a pipe"""
        pipe = MockPipe()
        self.hub.add_pipe(pipe)

        self.assertEqual(len(self.hub.pipes), 1)
        self.assertEqual(self.hub.pipes[0], pipe)
        pipe.start_server_task.assert_called_once_with(self.hub)

    def test_add_multiple_pipes(self):
        """Test adding multiple pipes"""
        pipe1 = MockPipe()
        pipe2 = MockPipe()
        self.hub.add_pipe(pipe1)
        self.hub.add_pipe(pipe2)

        self.assertEqual(len(self.hub.pipes), 2)
        self.assertEqual(self.hub.pipes[0], pipe1)
        self.assertEqual(self.hub.pipes[1], pipe2)

    def test_map_key_press_long(self):
        """Test mapping a long key press"""
        key = Key.SELECT.value
        mapped_key = self.hub.map_key_press(key, 0.6)
        self.assertEqual(mapped_key, Key.F6.value)

    def test_map_key_press_exactly_at_threshold(self):
        """Test mapping at exactly the threshold duration"""
        key = Key.SELECT.value
        mapped_key = self.hub.map_key_press(key, 0.5)
        self.assertEqual(mapped_key, Key.F6.value)

    def test_map_key_press_short(self):
        """Test mapping a short key press"""
        key = Key.POWER.value
        mapped_key = self.hub.map_key_press(key, 0.3)
        self.assertEqual(mapped_key, Key.SELECT.value)

    def test_map_key_press_no_mapping(self):
        """Test key with no mapping returns same key"""
        key = Key.UP.value
        mapped_key = self.hub.map_key_press(key, 0.3)
        self.assertEqual(mapped_key, Key.UP.value)

    def test_auto_clear_wait_for_release(self):
        """Test auto clearing wait_for_release"""
        self.hub.wait_for_release = True
        self.hub.auto_clear_wait_for_release()
        self.assertFalse(self.hub.wait_for_release)

    def test_set_wait_for_release(self):
        """Test setting wait_for_release flag"""
        with patch('asyncio.get_running_loop') as mock_loop:
            mock_loop.return_value.call_later = Mock()
            self.hub.wait_for_release = False
            self.hub.set_wait_for_release()

            self.assertTrue(self.hub.wait_for_release)
            mock_loop.return_value.call_later.assert_called_once_with(
                1, self.hub.auto_clear_wait_for_release
            )


class TestHubAsync(unittest.IsolatedAsyncioTestCase):
    """Async test cases for the Hub class"""

    async def asyncSetUp(self):
        """Set up async test fixtures"""
        # Set config values using direct assignment
        test_common.mock_config['hub.activity_map'] = {
            Key.SELECT.value: 0,
            Key.UP.value: 1,
            Key.RIGHT.value: 2,
        }
        test_common.mock_config['hub.macros'] = [
            (Key.POWER.value, Key.SELECT.value),
        ]
        test_common.mock_config['hub.long_press.duration_sec'] = 0.5
        test_common.mock_config['hub.long_press.keymap'] = {
            Key.SELECT.value: Key.F6.value,
        }
        test_common.mock_config['hub.short_press.keymap'] = {
            Key.POWER.value: Key.SELECT.value,
        }
        test_common.mock_config['hub.play_pause.mode'] = 'emulate'
        test_common.mock_config['remote.battery.low_threshold'] = 10

        self.controller = MockController()
        self.hub = Hub(self.controller)
        self.hub.taskit = make_taskit_mock()

    async def test_client_set_activity(self):
        """Test setting activity through client method"""
        await self.hub.client_set_activity(1)
        self.controller.set_activity.assert_called_once_with(1)

    async def test_set_activity_success(self):
        """Test successful activity change"""
        pipe = MockPipe()
        self.hub.add_pipe(pipe)

        result = await self.hub.set_activity(2)

        self.assertTrue(result)
        self.controller.set_activity.assert_called_once_with(2)
        pipe.notify_set_activity.assert_called_once_with(2)
        self.assertTrue(self.hub.wait_for_release)

    async def test_set_activity_failure(self):
        """Test failed activity change"""
        self.controller.set_activity.return_value = False
        pipe = MockPipe()
        self.hub.add_pipe(pipe)

        result = await self.hub.set_activity(2)

        self.assertFalse(result)
        pipe.notify_set_activity.assert_not_called()

    async def test_standby_from_no_activity(self):
        """Test standby when no activity is active"""
        self.controller.current_activity = no_activity
        pipe = MockPipe()
        self.hub.add_pipe(pipe)

        await self.hub.standby()

        self.controller.force_standby.assert_called_once()
        self.controller.standby.assert_not_called()
        self.assertFalse(self.hub.play_pause_is_playing)
        self.assertTrue(self.hub.wait_for_release)
        pipe.notify_set_activity.assert_called_once_with(-1)

    async def test_standby_from_activity(self):
        """Test standby when an activity is active"""
        self.controller.current_activity = Mock()
        pipe = MockPipe()
        self.hub.add_pipe(pipe)

        await self.hub.standby()

        self.controller.standby.assert_called_once()
        self.controller.force_standby.assert_not_called()
        self.assertFalse(self.hub.play_pause_is_playing)
        pipe.notify_set_activity.assert_called_once_with(-1)

    async def test_standby_notifies_all_pipes(self):
        """Test that standby notifies all registered pipes"""
        pipe1 = MockPipe()
        pipe2 = MockPipe()
        self.hub.add_pipe(pipe1)
        self.hub.add_pipe(pipe2)
        self.controller.current_activity = Mock()

        await self.hub.standby()

        pipe1.notify_set_activity.assert_called_once_with(-1)
        pipe2.notify_set_activity.assert_called_once_with(-1)

    async def test_client_battery_state_normal(self):
        """Test battery state notification with normal level"""
        pipe = MockPipe()
        self.hub.add_pipe(pipe)

        await self.hub.client_battery_state(50, False)

        pipe.notify_battery_state.assert_called_once_with(50, False, False)

    async def test_client_battery_state_low(self):
        """Test battery state notification with low battery"""
        pipe = MockPipe()
        self.hub.add_pipe(pipe)

        await self.hub.client_battery_state(5, False)

        pipe.notify_battery_state.assert_called_once_with(5, False, True)

    async def test_client_battery_state_low_but_charging(self):
        """Test battery state - low but charging is not considered low"""
        pipe = MockPipe()
        self.hub.add_pipe(pipe)

        await self.hub.client_battery_state(5, True)

        pipe.notify_battery_state.assert_called_once_with(5, True, False)

    async def test_client_battery_state_at_threshold(self):
        """Test battery state at exact threshold"""
        pipe = MockPipe()
        self.hub.add_pipe(pipe)

        await self.hub.client_battery_state(10, False)

        pipe.notify_battery_state.assert_called_once_with(10, False, True)

    async def test_client_press_key_during_no_activity(self):
        """Test pressing unflagged key (count=0) when no activity is active"""
        self.controller.current_activity = no_activity
        self.hub.wait_for_release = False

        await self.hub.client_press_key(Key.SELECT.value, 0)

        # Unflagged keys (count=0) are kept in no_activity mode
        # (only flagged keys with count>0 are removed)
        self.assertEqual(len(self.hub.key_state), 1)
        self.assertIn(Key.SELECT.value, self.hub.key_state)

    async def test_client_press_key_with_count_during_no_activity(self):
        """Test that counted keys are removed during no_activity"""
        self.controller.current_activity = no_activity
        self.hub.wait_for_release = False

        await self.hub.client_press_key(Key.SELECT.value, 2)

        # Counted keys should be removed immediately in no_activity
        self.assertEqual(len(self.hub.key_state), 0)

    async def test_client_press_key_basic(self):
        """Test basic key press"""
        self.controller.current_activity = Mock()
        self.hub.wait_for_release = False

        await self.hub.client_press_key(Key.UP.value, 0)

        # Should have key state
        self.assertIn(Key.UP.value, self.hub.key_state)

    async def test_client_press_key_with_count(self):
        """Test key press with repeat count"""
        self.controller.current_activity = Mock()
        self.hub.wait_for_release = False

        await self.hub.client_press_key(Key.UP.value, 2)

        # Should have key state with REPEAT_COUNT_FLAG
        flagged_key = Key.UP.value | Hub.REPEAT_COUNT_FLAG
        self.assertIn(flagged_key, self.hub.key_state)
        self.assertEqual(self.hub.key_state[flagged_key].repeat_count, 2)

    async def test_client_press_key_accumulate_count(self):
        """Test accumulating repeat counts"""
        self.controller.current_activity = Mock()
        self.hub.wait_for_release = False

        await self.hub.client_press_key(Key.UP.value, 2)
        await self.hub.client_press_key(Key.UP.value, 3)

        # Should accumulate counts
        flagged_key = Key.UP.value | Hub.REPEAT_COUNT_FLAG
        self.assertEqual(self.hub.key_state[flagged_key].repeat_count, 5)

    async def test_client_press_key_max_count(self):
        """Test that repeat count is capped at 10 when accumulating"""
        self.controller.current_activity = Mock()
        self.hub.wait_for_release = False

        # First call with count=7
        await self.hub.client_press_key(Key.UP.value, 7)
        # Second call with count=8 should cap total at 10 (not 7+8=15)
        await self.hub.client_press_key(Key.UP.value, 8)

        # Should be capped at 10 when accumulating
        flagged_key = Key.UP.value | Hub.REPEAT_COUNT_FLAG
        self.assertEqual(self.hub.key_state[flagged_key].repeat_count, 10)

    async def test_client_press_key_wait_for_release(self):
        """Test that counted keys are removed during wait_for_release"""
        self.controller.current_activity = Mock()
        self.hub.wait_for_release = True

        await self.hub.client_press_key(Key.UP.value, 1)

        # Counted key state should be removed
        self.assertEqual(len(self.hub.key_state), 0)

    async def test_client_press_key_power_ignored(self):
        """Test that POWER key doesn't trigger press_key task"""
        self.controller.current_activity = Mock()
        self.hub.wait_for_release = False

        await self.hub.client_press_key(Key.POWER.value, 0)

        # Should have key state but not call press_key
        self.assertIn(Key.POWER.value, self.hub.key_state)
        # press_key should not be called for POWER key
        self.controller.press_key.assert_not_called()

    async def test_client_release_key_no_state(self):
        """Test releasing key with no prior state"""
        # Should handle gracefully without errors
        await self.hub.client_release_key(Key.UP.value)

    async def test_client_release_key_from_no_activity_to_activity(self):
        """Test releasing key to activate activity from no_activity"""
        self.controller.current_activity = no_activity
        self.hub.wait_for_release = False
        self.hub.in_macro = False

        # Simulate short press by setting timestamp in the past
        self.hub.key_state[Key.SELECT.value] = KeyState(0)
        self.hub.key_state[Key.SELECT.value].timestamp = time.time() - 0.2

        await self.hub.client_release_key(Key.SELECT.value)

        # Should set activity index 0
        self.controller.set_activity.assert_called_once_with(0)

    async def test_client_release_power_short_press_for_standby(self):
        """Test short press of POWER for standby"""
        self.controller.current_activity = Mock()
        self.hub.wait_for_release = False
        self.hub.in_macro = False

        # Simulate short press of POWER (< 0.5 seconds)
        self.hub.key_state[Key.POWER.value] = KeyState(0)
        self.hub.key_state[Key.POWER.value].timestamp = time.time() - 0.2

        await self.hub.client_release_key(Key.POWER.value)

        # Should call standby
        self.controller.standby.assert_called_once()

    async def test_client_release_power_long_press_for_fix(self):
        """Test long press of POWER for fix_current_activity"""
        self.controller.current_activity = Mock()
        self.hub.wait_for_release = False
        self.hub.in_macro = False

        # Simulate long press of POWER (>= 0.5 seconds)
        self.hub.key_state[Key.POWER.value] = KeyState(0)
        self.hub.key_state[Key.POWER.value].timestamp = time.time() - 0.6

        await self.hub.client_release_key(Key.POWER.value)

        # Should call fix_current_activity
        self.controller.fix_current_activity.assert_called_once()

    async def test_client_release_clears_state_when_empty(self):
        """Test that releasing last key clears macro state"""
        self.controller.current_activity = Mock()
        self.hub.in_macro = True
        self.hub.macro_index = 0
        self.hub.macro_executed = True

        # Add and release single key
        self.hub.key_state[Key.SELECT.value] = KeyState(0)
        self.hub.key_state[Key.SELECT.value].timestamp = time.time() - 0.2

        await self.hub.client_release_key(Key.SELECT.value)

        # Macro state should be cleared
        self.assertFalse(self.hub.in_macro)
        self.assertIsNone(self.hub.macro_index)
        self.assertFalse(self.hub.macro_executed)
        self.assertFalse(self.hub.wait_for_release)

    async def test_press_key_unflagged_with_state_removal(self):
        """Test press_key with unflagged key (repeat_count=0) - normal button press"""
        self.controller.current_activity = Mock()

        # Create event to coordinate between test and background task
        first_call_done = asyncio.Event()
        original_press_key = self.controller.press_key
        call_count = [0]  # Use list to avoid nonlocal issues

        async def press_key_wrapper(*args, **kwargs):
            call_count[0] += 1
            result = await original_press_key(*args, **kwargs)
            if call_count[0] == 1:
                first_call_done.set()  # Signal after first call
                await asyncio.sleep(0)  # Yield to give test a chance
            return result

        self.controller.press_key = press_key_wrapper

        # Unflagged key with repeat_count=0 (normal button press)
        key = Key.UP.value
        self.hub.key_state[key] = KeyState(0)

        # Create task
        task = asyncio.create_task(self.hub.press_key(key))

        # Wait for first press_key call to complete
        await asyncio.wait_for(first_call_done.wait(), timeout=1.0)

        # Now remove state so next iteration breaks
        self.hub.key_state.pop(key, None)

        # Wait for task to complete
        await asyncio.wait_for(task, timeout=1.0)

        # Should have called controller.press_key at least once
        self.assertGreaterEqual(call_count[0], 1)
        # Key state should be removed
        self.assertNotIn(key, self.hub.key_state)

    async def test_press_key_flagged_with_repeat_count(self):
        """Test press_key with flagged key (repeat_count>0) - swipe/repeat"""
        self.controller.current_activity = Mock()

        # Flagged key with repeat_count=1 (self-terminating)
        key = Key.UP.value | Hub.REPEAT_COUNT_FLAG
        self.hub.key_state[key] = KeyState(1)

        await self.hub.press_key(key)

        # Should call controller.press_key once (count goes 1->0->break)
        self.assertEqual(self.controller.press_key.call_count, 1)
        # Key state should be removed
        self.assertNotIn(key, self.hub.key_state)

    async def test_press_key_with_multiple_repeats(self):
        """Test press_key with higher repeat count (swipe with count=3)"""
        self.controller.current_activity = Mock()

        # Flagged key with repeat_count=3
        key = Key.UP.value | Hub.REPEAT_COUNT_FLAG
        self.hub.key_state[key] = KeyState(3)

        await self.hub.press_key(key)

        # Should call controller.press_key 3 times (count: 3->2, 2->1, 1->0->break)
        self.assertEqual(self.controller.press_key.call_count, 3)

    async def test_press_key_stops_on_failure(self):
        """Test press_key stops repeating if controller fails"""
        self.controller.current_activity = Mock()
        self.controller.press_key.return_value = False

        # Add key state with repeat count
        key = Key.UP.value | Hub.REPEAT_COUNT_FLAG
        self.hub.key_state[key] = KeyState(3)

        await self.hub.press_key(key)

        # Should only call once before failing
        self.assertEqual(self.controller.press_key.call_count, 1)

    async def test_press_key_pause_play_emulate_to_pause(self):
        """Test PAUSE_PLAY emulation when playing (flagged key)"""
        self.hub.play_pause_mode = 'emulate'
        self.hub.play_pause_is_playing = True

        # Use flagged key for self-terminating test
        key = Key.PAUSE_PLAY.value | Hub.REPEAT_COUNT_FLAG
        self.hub.key_state[key] = KeyState(1)

        await self.hub.press_key(key)

        # Should send PAUSE and toggle state
        self.controller.press_key.assert_called_with(Key.PAUSE.value, True)
        self.assertFalse(self.hub.play_pause_is_playing)

    async def test_press_key_pause_play_emulate_to_play(self):
        """Test PAUSE_PLAY emulation when paused (flagged key)"""
        self.hub.play_pause_mode = 'emulate'
        self.hub.play_pause_is_playing = False

        # Use flagged key for self-terminating test
        key = Key.PAUSE_PLAY.value | Hub.REPEAT_COUNT_FLAG
        self.hub.key_state[key] = KeyState(1)

        await self.hub.press_key(key)

        # Should send PLAY and toggle state
        self.controller.press_key.assert_called_with(Key.PLAY.value, True)
        self.assertTrue(self.hub.play_pause_is_playing)

    async def test_press_key_pause_play_select_mode(self):
        """Test PAUSE_PLAY in select mode (flagged key)"""
        self.hub.play_pause_mode = 'select'

        # Use flagged key for self-terminating test
        key = Key.PAUSE_PLAY.value | Hub.REPEAT_COUNT_FLAG
        self.hub.key_state[key] = KeyState(1)

        await self.hub.press_key(key)

        # Should map to SELECT
        self.controller.press_key.assert_called_with(Key.SELECT.value, True)

    async def test_press_key_pause_play_send_mode(self):
        """Test PAUSE_PLAY in send mode (flagged key)"""
        self.hub.play_pause_mode = 'send'

        # Use flagged key for self-terminating test
        key = Key.PAUSE_PLAY.value | Hub.REPEAT_COUNT_FLAG
        self.hub.key_state[key] = KeyState(1)

        await self.hub.press_key(key)

        # Should send as-is
        self.controller.press_key.assert_called_with(Key.PAUSE_PLAY.value, True)

    async def test_press_key_pause_play_unflagged(self):
        """Test PAUSE_PLAY with unflagged key (normal button press)"""
        self.hub.play_pause_mode = 'emulate'
        self.hub.play_pause_is_playing = False
        self.controller.current_activity = Mock()

        # Create event to coordinate between test and background task
        first_call_done = asyncio.Event()
        original_press_key = self.controller.press_key
        call_count = [0]  # Use list to avoid nonlocal issues

        async def press_key_wrapper(*args, **kwargs):
            call_count[0] += 1
            result = await original_press_key(*args, **kwargs)
            if call_count[0] == 1:
                first_call_done.set()  # Signal after first call
                await asyncio.sleep(0)  # Yield to give test a chance
            return result

        self.controller.press_key = press_key_wrapper

        # Unflagged key (normal press - requires external state removal)
        key = Key.PAUSE_PLAY.value
        self.hub.key_state[key] = KeyState(0)

        # Create task
        task = asyncio.create_task(self.hub.press_key(key))

        # Wait for first press_key call to complete
        await asyncio.wait_for(first_call_done.wait(), timeout=1.0)

        # Now remove state so next iteration breaks
        self.hub.key_state.pop(key, None)

        # Wait for task to complete
        await asyncio.wait_for(task, timeout=1.0)

        # Should have sent PLAY and toggled state
        self.assertGreaterEqual(call_count[0], 1)
        self.assertTrue(self.hub.play_pause_is_playing)

    async def test_check_release_all_keys_no_keys(self):
        """Test releasing all keys when no keys are pressed"""
        self.controller.current_activity = Mock()
        self.hub.key_state = {}

        await self.hub.check_release_all_keys()

        self.controller.release_key.assert_called_once()

    async def test_check_release_all_keys_only_power(self):
        """Test releasing all keys when only POWER is pressed"""
        self.controller.current_activity = Mock()
        self.hub.key_state = {Key.POWER.value: KeyState(0)}

        await self.hub.check_release_all_keys()

        self.controller.release_key.assert_called_once()

    async def test_check_release_all_keys_other_keys_pressed(self):
        """Test NOT releasing when other keys are pressed"""
        self.controller.current_activity = Mock()
        self.hub.key_state = {Key.UP.value: KeyState(0)}

        await self.hub.check_release_all_keys()

        self.controller.release_key.assert_not_called()

    async def test_check_release_all_keys_during_no_activity(self):
        """Test check_release_all_keys does nothing during no_activity"""
        self.controller.current_activity = no_activity
        self.hub.key_state = {}

        await self.hub.check_release_all_keys()

        self.controller.release_key.assert_not_called()

    async def test_macro_detection(self):
        """Test macro detection when all keys are pressed"""
        self.controller.current_activity = Mock()
        self.hub.wait_for_release = False

        # Press both keys in macro sequence
        await self.hub.client_press_key(Key.POWER.value, 0)
        await self.hub.client_press_key(Key.SELECT.value, 0)

        # Should detect macro
        self.assertTrue(self.hub.in_macro)
        self.assertEqual(self.hub.macro_index, 0)
        self.assertFalse(self.hub.macro_executed)

    async def test_macro_execution_on_release(self):
        """Test macro execution when keys are released"""
        self.controller.current_activity = Mock()
        self.hub.wait_for_release = False

        # Setup macro state
        await self.hub.client_press_key(Key.POWER.value, 0)
        await self.hub.client_press_key(Key.SELECT.value, 0)

        # Ensure SELECT key has a short press timestamp
        self.hub.key_state[Key.SELECT.value].timestamp = time.time() - 0.2

        # Release the function key (SELECT)
        await self.hub.client_release_key(Key.SELECT.value)

        # Should execute macro and set activity
        self.assertTrue(self.hub.macro_executed)
        self.controller.set_activity.assert_called()


if __name__ == '__main__':
    unittest.main(verbosity=2)
