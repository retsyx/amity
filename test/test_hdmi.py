# Copyright 2025.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import test_common

import unittest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio

import hdmi
from cec import Key, Message


class TestPrettyPhysicalAddress(unittest.TestCase):
    def test_zero_address(self):
        self.assertEqual(hdmi.pretty_physical_address(0x0000), '0.0.0.0')

    def test_typical_address(self):
        self.assertEqual(hdmi.pretty_physical_address(0x1000), '1.0.0.0')

    def test_complex_address(self):
        self.assertEqual(hdmi.pretty_physical_address(0x1500), '1.5.0.0')

    def test_full_address(self):
        self.assertEqual(hdmi.pretty_physical_address(0xABCD), 'A.B.C.D')


class TestSwitch(unittest.TestCase):
    def test_init(self):
        s = hdmi.Switch({'device': 'AVR', 'input': 3})
        self.assertEqual(s.device, 'AVR')
        self.assertEqual(s.input, 3)

    def test_repr(self):
        s = hdmi.Switch({'device': 'AVR', 'input': 3})
        r = repr(s)
        self.assertIn('AVR', r)
        self.assertIn('3', r)


class TestActivity(unittest.TestCase):
    def test_default_activity(self):
        a = hdmi.Activity()
        self.assertEqual(a.name, 'No Activity')
        self.assertIsNone(a.display)
        self.assertIsNone(a.source)
        self.assertIsNone(a.audio)
        self.assertIsNone(a.switch)

    def test_activity_with_values(self):
        d = {'name': 'Watch TV', 'display': 'TV', 'source': 'AppleTV', 'audio': 'AVR'}
        a = hdmi.Activity(d)
        self.assertEqual(a.name, 'Watch TV')
        self.assertEqual(a.display, 'TV')
        self.assertEqual(a.source, 'AppleTV')
        self.assertEqual(a.audio, 'AVR')
        self.assertIsNone(a.switch)

    def test_activity_with_switch(self):
        d = {'name': 'Play Wii', 'display': 'TV', 'source': None, 'audio': 'AVR',
             'switch': {'device': 'AVR', 'input': 4}}
        a = hdmi.Activity(d)
        self.assertIsNotNone(a.switch)
        self.assertEqual(a.switch.device, 'AVR')
        self.assertEqual(a.switch.input, 4)

    def test_devices_without_switch(self):
        d = {'name': 'Watch TV', 'display': 'TV', 'source': 'AppleTV', 'audio': 'AVR'}
        a = hdmi.Activity(d)
        devices = a.devices()
        self.assertEqual(devices, ['TV', 'AppleTV', 'AVR'])

    def test_devices_with_switch(self):
        d = {'name': 'Play Wii', 'display': 'TV', 'source': None, 'audio': 'AVR',
             'switch': {'device': 'Receiver', 'input': 4}}
        a = hdmi.Activity(d)
        devices = a.devices()
        self.assertEqual(devices, ['TV', None, 'AVR', 'Receiver'])

    def test_repr(self):
        d = {'name': 'Watch TV', 'display': 'TV', 'source': 'AppleTV', 'audio': 'AVR'}
        a = hdmi.Activity(d)
        r = repr(a)
        self.assertIn('Watch TV', r)
        self.assertIn('TV', r)
        self.assertIn('AppleTV', r)
        self.assertIn('AVR', r)


class TestQuirk(unittest.TestCase):
    def test_init_parses_hex_data(self):
        q = hdmi.Quirk({'data': '44:6D'})
        self.assertEqual(q.data, [0x44, 0x6D])

    def test_repr(self):
        q = hdmi.Quirk({'data': '44:6D'})
        self.assertEqual(repr(q), '44:6D')

    def test_single_byte(self):
        q = hdmi.Quirk({'data': 'FF'})
        self.assertEqual(q.data, [0xFF])


class TestDevice(unittest.TestCase):
    def setUp(self):
        hdmi.Device.quirks = {}
        self.mock_dev = MagicMock()
        self.mock_dev.osd_name = 'TestDevice'
        self.mock_dev.address = 4
        self.mock_dev.physical_address = 0x1500
        self.mock_dev.vendor_id = 0x001234
        self.mock_dev.standby = AsyncMock()
        self.mock_dev.key_press = AsyncMock()
        self.mock_dev.key_release = AsyncMock()
        self.mock_dev.power_on = AsyncMock()
        self.mock_dev.set_stream_path = AsyncMock()
        self.mock_dev.transmit = AsyncMock()
        self.mock_dev.get_osd_name = AsyncMock()
        self.mock_dev.parse_report_physical_address_message = MagicMock()
        self.device = hdmi.Device(self.mock_dev)

    def test_osd_name(self):
        self.assertEqual(self.device.osd_name, 'TestDevice')

    def test_address(self):
        self.assertEqual(self.device.address, 4)

    def test_physical_address(self):
        self.assertEqual(self.device.physical_address, 0x1500)

    def test_lookup_quirk_not_found(self):
        self.assertIsNone(self.device.lookup_quirk('power_on'))

    def test_lookup_quirk_found(self):
        hdmi.Device.quirks = {'001234': {'power_on': {'data': '44:6D'}}}
        q = self.device.lookup_quirk('power_on')
        self.assertIsNotNone(q)
        self.assertEqual(q.data, [0x44, 0x6D])

    def test_lookup_quirk_vendor_exists_op_missing(self):
        hdmi.Device.quirks = {'001234': {'power_off': {'data': '44:6D'}}}
        self.assertIsNone(self.device.lookup_quirk('power_on'))

    def test_handle_report_physical_address(self):
        msg = MagicMock()
        self.device.handle_report_physical_address(msg)
        self.mock_dev.parse_report_physical_address_message.assert_called_once_with(msg)

    def test_power_on_no_quirk(self):
        asyncio.run(self.device.power_on())
        self.mock_dev.power_on.assert_called_once()

    def test_power_on_with_quirk(self):
        hdmi.Device.quirks = {'001234': {'power_on': {'data': '44:6D'}}}
        asyncio.run(self.device.power_on())
        self.mock_dev.power_on.assert_not_called()
        self.mock_dev.transmit.assert_called_once_with([0x44, 0x6D])
        self.mock_dev.key_release.assert_called_once()

    def test_power_on_with_non_keypress_quirk(self):
        hdmi.Device.quirks = {'001234': {'power_on': {'data': '36'}}}
        asyncio.run(self.device.power_on())
        self.mock_dev.power_on.assert_not_called()
        self.mock_dev.transmit.assert_called_once_with([0x36])
        self.mock_dev.key_release.assert_not_called()

    def test_power_off_no_quirk(self):
        asyncio.run(self.device.power_off())
        self.mock_dev.standby.assert_called_once()

    def test_power_off_with_quirk(self):
        hdmi.Device.quirks = {'001234': {'power_off': {'data': '36'}}}
        asyncio.run(self.device.power_off())
        self.mock_dev.standby.assert_not_called()
        self.mock_dev.transmit.assert_called_once()

    def test_standby(self):
        asyncio.run(self.device.standby())
        self.mock_dev.standby.assert_called_once()

    def test_press_key(self):
        asyncio.run(self.device.press_key(Key.SELECT))
        self.mock_dev.key_press.assert_called_once_with(Key.SELECT)
        self.mock_dev.key_release.assert_called_once()

    def test_press_key_repeat(self):
        asyncio.run(self.device.press_key(Key.SELECT, repeat=True))
        self.mock_dev.key_press.assert_called_once_with(Key.SELECT)
        self.mock_dev.key_release.assert_not_called()

    def test_release_key(self):
        asyncio.run(self.device.release_key())
        self.mock_dev.key_release.assert_called_once()

    def test_set_stream_path(self):
        asyncio.run(self.device.set_stream_path())
        self.mock_dev.set_stream_path.assert_called_once()

    def test_set_input(self):
        asyncio.run(self.device.set_input(3))
        self.mock_dev.transmit.assert_called_once()
        args = self.mock_dev.transmit.call_args[0][0]
        self.assertEqual(args[0], Message.KEY_PRESS)
        self.assertEqual(args[1], Key.SET_INPUT)
        self.assertEqual(args[2], 3)
        self.mock_dev.key_release.assert_called_once()

    def test_get_osd_name(self):
        asyncio.run(self.device.get_osd_name())
        self.mock_dev.get_osd_name.assert_called_once()


def make_mock_device(osd_name, address, physical_address=0x1000, vendor_id=0):
    dev = MagicMock()
    dev.osd_name = osd_name
    dev.address = address
    dev.physical_address = physical_address
    dev.vendor_id = vendor_id
    dev.standby = AsyncMock()
    dev.key_press = AsyncMock()
    dev.key_release = AsyncMock()
    dev.power_on = AsyncMock()
    dev.set_stream_path = AsyncMock()
    dev.transmit = AsyncMock()
    dev.get_osd_name = AsyncMock()
    dev.parse_report_physical_address_message = MagicMock()
    return dev


class TestControllerImpl(unittest.TestCase):
    def setUp(self):
        hdmi.Device.quirks = {}
        self.activities = [
            hdmi.Activity({'name': 'Watch TV', 'display': 'TV', 'source': 'Living Room', 'audio': 'AVR-X3400H'}),
            hdmi.Activity({'name': 'Play PS5', 'display': 'TV', 'source': 'PlayStation5', 'audio': 'AVR-X3400H'}),
        ]

        self.loop = asyncio.new_event_loop()

        with patch('cec.Adapter'):
            self.ctrl = hdmi.ControllerImpl('/dev/cec0', '/dev/cec1', 'Amity', self.loop, self.activities)

        self.ctrl.front_adapter = MagicMock()
        self.ctrl.front_adapter.address = 0x0E
        self.ctrl.front_adapter.transmit = AsyncMock()
        self.ctrl.front_adapter.active_source = AsyncMock()
        self.ctrl.front_adapter.list_devices = AsyncMock(return_value=[])
        self.ctrl.front_adapter.broadcast = MagicMock(return_value=MagicMock(standby=AsyncMock()))

        self.ctrl.back_adapter = MagicMock()
        self.ctrl.back_adapter.address = 0x00
        self.ctrl.back_adapter.transmit = AsyncMock()
        self.ctrl.back_adapter.list_devices = AsyncMock(return_value=[])
        self.ctrl.back_adapter.broadcast = MagicMock(return_value=MagicMock(standby=AsyncMock()))

        # Populate devices
        tv_dev = make_mock_device('TV', 0, 0x0000)
        avr_dev = make_mock_device('AVR-X3400H', 5, 0x1000)
        lr_dev = make_mock_device('Living Room', 4, 0x1500)
        ps5_dev = make_mock_device('PlayStation5', 11, 0x1400)

        self.ctrl.devices = {
            'TV': hdmi.Device(tv_dev),
            'AVR-X3400H': hdmi.Device(avr_dev),
            'Living Room': hdmi.Device(lr_dev),
            'PlayStation5': hdmi.Device(ps5_dev),
        }
        self.ctrl.set_inited()

    def tearDown(self):
        self.loop.close()

    def test_set_activity_valid(self):
        result = asyncio.run(self.ctrl.set_activity(0))
        self.assertTrue(result)
        self.assertEqual(self.ctrl.current_activity.name, 'Watch TV')

    def test_set_activity_out_of_bounds(self):
        result = asyncio.run(self.ctrl.set_activity(10))
        self.assertFalse(result)

    def test_set_activity_negative_out_of_bounds(self):
        result = asyncio.run(self.ctrl.set_activity(-2))
        self.assertFalse(result)

    def test_standby(self):
        # First activate
        asyncio.run(self.ctrl.set_activity(0))
        self.assertEqual(self.ctrl.current_activity.name, 'Watch TV')
        # Then standby
        asyncio.run(self.ctrl.standby())
        self.assertEqual(self.ctrl.current_activity.name, 'No Activity')

    def test_set_activity_switches_devices(self):
        # Activate Watch TV
        asyncio.run(self.ctrl.set_activity(0))
        # Switch to Play PS5 — Living Room should get standby, PS5 should power on
        asyncio.run(self.ctrl.set_activity(1))
        self.assertEqual(self.ctrl.current_activity.name, 'Play PS5')

    def test_fix_current_activity(self):
        asyncio.run(self.ctrl.set_activity(0))
        # Calling set_activity with same index fixes it
        asyncio.run(self.ctrl.set_activity(0))
        # Should still be the same activity
        self.assertEqual(self.ctrl.current_activity.name, 'Watch TV')

    def test_get_device_found(self):
        device = asyncio.run(self.ctrl.get_device('TV'))
        self.assertIsNotNone(device)
        self.assertEqual(device.osd_name, 'TV')

    def test_get_device_not_found(self):
        device = asyncio.run(self.ctrl.get_device('NonExistent'))
        self.assertIsNone(device)

    def test_get_device_none_name(self):
        device = asyncio.run(self.ctrl.get_device(None))
        self.assertIsNone(device)

    def test_press_key_volume_goes_to_audio(self):
        asyncio.run(self.ctrl.set_activity(0))
        result = asyncio.run(self.ctrl.press_key(Key.VOLUME_UP))
        self.assertTrue(result)

    def test_press_key_select_goes_to_source(self):
        asyncio.run(self.ctrl.set_activity(0))
        result = asyncio.run(self.ctrl.press_key(Key.SELECT))
        self.assertTrue(result)

    def test_press_key_no_activity(self):
        result = asyncio.run(self.ctrl.press_key(Key.SELECT))
        # No activity means source is None, device not found
        self.assertFalse(result)

    def test_force_standby(self):
        asyncio.run(self.ctrl.force_standby())
        self.ctrl.front_adapter.broadcast.assert_called()
        self.ctrl.back_adapter.broadcast.assert_called()

    def test_front_listen_handles_give_power_status_standby(self):
        msg = MagicMock()
        msg.op = Message.GIVE_DEVICE_POWER_STATUS
        msg.dst = 0x0E
        msg.src = 0
        asyncio.run(self.ctrl.front_listen(msg))
        self.ctrl.front_adapter.transmit.assert_called_once()

    def test_front_listen_handles_give_power_status_on(self):
        asyncio.run(self.ctrl.set_activity(0))
        msg = MagicMock()
        msg.op = Message.GIVE_DEVICE_POWER_STATUS
        msg.dst = 0x0E
        msg.src = 0
        asyncio.run(self.ctrl.front_listen(msg))
        self.ctrl.front_adapter.transmit.assert_called()

    def test_front_listen_ignores_when_not_inited(self):
        self.ctrl.inited = False
        msg = MagicMock()
        msg.op = Message.GIVE_DEVICE_POWER_STATUS
        msg.dst = 0x0E
        msg.src = 0
        asyncio.run(self.ctrl.front_listen(msg))
        self.ctrl.front_adapter.transmit.assert_not_called()

    def test_stop_source_thief_actual_thief(self):
        asyncio.run(self.ctrl.set_activity(0))
        msg = MagicMock()
        msg.src = 11  # PlayStation5 address, not the current source
        asyncio.run(self.ctrl.stop_source_thief(msg))
        # Should put thief in standby
        self.ctrl.back_adapter.transmit.assert_called()

    def test_set_activity_with_switch(self):
        activity_with_switch = hdmi.Activity({
            'name': 'Play Wii',
            'display': 'TV',
            'source': 'NonExistentDevice',
            'audio': 'AVR-X3400H',
            'switch': {'device': 'AVR-X3400H', 'input': 4}
        })
        self.ctrl.activities.append(activity_with_switch)
        result = asyncio.run(self.ctrl.set_activity(2))
        self.assertTrue(result)
        self.assertEqual(self.ctrl.current_activity.name, 'Play Wii')


class TestNoActivity(unittest.TestCase):
    def test_no_activity_singleton(self):
        self.assertEqual(hdmi.no_activity.name, 'No Activity')
        self.assertIsNone(hdmi.no_activity.display)
        self.assertIsNone(hdmi.no_activity.source)
        self.assertIsNone(hdmi.no_activity.audio)


if __name__ == '__main__':
    unittest.main()
