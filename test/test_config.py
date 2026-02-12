# Copyright 2025.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import test_common

import unittest
import os
import tempfile
import yaml

from config import Config


def save_and_read_yaml(c):
    """Save config to a temp file and read back as raw Python dicts/lists."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        fname = f.name
    try:
        c.save_complete(fname)
        with open(fname, 'r') as f:
            return yaml.safe_load(f)
    finally:
        os.unlink(fname)


class TestConfig(unittest.TestCase):
    def test_init_sets_defaults(self):
        c = Config('dummy.yaml')
        self.assertEqual(c.filename, 'dummy.yaml')
        self.assertIsNone(c['nonexistent.key'])

    def test_simple_default(self):
        c = Config('dummy.yaml')
        c.default('remote.mac', 0)
        self.assertEqual(c['remote.mac'], 0)
        c['remote.mac'] = 42
        self.assertEqual(c['remote.mac'], 42)
        self.assertEqual(c['remote']['mac'], 42)
        self.assertEqual(c['']['remote']['mac'], 42)

    def test_nested_default(self):
        c = Config('dummy.yaml')
        c.default('hdmi.front.physical_address', 0x1000)
        self.assertEqual(c['hdmi.front.physical_address'], 0x1000)
        self.assertEqual(c['hdmi.front']['physical_address'], 0x1000)
        self.assertEqual(c['hdmi']['front']['physical_address'], 0x1000)

    def test_duplicate_defaults(self):
        c = Config('dummy.yaml')
        c.default('remote.mac', 0)
        c.default('remote.mac', 0)  # same value should not raise
        self.assertEqual(c['remote.mac'], 0)
        with self.assertRaises(AssertionError):
            c.default('remote.mac', 1)

    def test_default_after_load_raises(self):
        c = Config('dummy.yaml')
        c.default('key.value', 'default')
        c.load()  # file doesn't exist, loads empty
        self.assertEqual(c['key.value'], 'default')
        with self.assertRaises(AssertionError):
            c.default('new.key', 'value')

    def test_list_path_default(self):
        c = Config('dummy.yaml')
        c.default('items,0', 'first')
        c.default('items,1', 'second')
        self.assertEqual(c['items,0'], 'first')
        self.assertEqual(c['items'][0], 'first')
        self.assertEqual(c['items,1'], 'second')
        self.assertEqual(c['items'][1], 'second')

    def test_list_with_gap(self):
        c = Config('dummy.yaml')
        c.default('items,2', 'third')
        self.assertIsNone(c['items,0'])
        self.assertIsNone(c['items'][0])
        self.assertIsNone(c['items,1'])
        self.assertIsNone(c['items'][1])
        self.assertEqual(c['items,2'], 'third')
        self.assertEqual(c['items'][2], 'third')

    def test_get_partially_missing_path(self):
        c = Config('dummy.yaml')
        c.default('a.b', 1)
        self.assertIsNone(c['a.c'])

    def test_get_list_out_of_bounds(self):
        c = Config('dummy.yaml')
        c.default('items,0', 'first')
        self.assertIsNone(c['items,5'])

    def test_set_persists_through_save_reload(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            fname = f.name
        try:
            c = Config(fname)
            c.default('remote.mac', 0)
            c.load()
            c['remote.mac'] = 42
            c.save()

            c2 = Config(fname)
            c2.default('remote.mac', 0)
            c2.load()
            self.assertEqual(c2['remote.mac'], 42)
        finally:
            os.unlink(fname)

    def test_load_existing_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'key': {'value': 'from_file'}}, f)
            fname = f.name
        try:
            c = Config(fname)
            c.default('key.value', 'default')
            c.load()
            self.assertEqual(c['key.value'], 'from_file')
        finally:
            os.unlink(fname)

    def test_load_empty_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write('')
            fname = f.name
        try:
            c = Config(fname)
            c.default('key.value', 'default')
            c.load()
            self.assertEqual(c['key.value'], 'default')
        finally:
            os.unlink(fname)

    def test_save_complete(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            fname = f.name
        try:
            c = Config('dummy.yaml')
            c.default('key.value', 'default')
            c.load()
            c.save_complete(fname)

            with open(fname, 'r') as f:
                saved = yaml.safe_load(f)
            self.assertEqual(saved['key']['value'], 'default')
        finally:
            os.unlink(fname)

    def test_user_adds_new_keys(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'remote': {'mac': 1}, 'extra': 'data'}, f)
            fname = f.name
        try:
            c = Config(fname)
            c.default('remote.mac', 0)
            c.load()
            self.assertEqual(c['remote.mac'], 1)
            self.assertEqual(c['extra'], 'data')
        finally:
            os.unlink(fname)

    def test_nested_dict_overlay(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'a': {'b': {'c': 'user_val'}}}, f)
            fname = f.name
        try:
            c = Config(fname)
            c.default('a.b.c', 'default_val')
            c.default('a.b.d', 'only_default')
            c.load()
            self.assertEqual(c['a.b.c'], 'user_val')
            self.assertEqual(c['a.b.d'], 'only_default')
        finally:
            os.unlink(fname)

    def test_list_overlay(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'items': ['user_first', 'user_second']}, f)
            fname = f.name
        try:
            c = Config(fname)
            c.default('items,0', 'default_first')
            c.default('items,1', 'default_second')
            c.load()
            self.assertEqual(c['items,0'], 'user_first')
            self.assertEqual(c['items,1'], 'user_second')
        finally:
            os.unlink(fname)


class TestConfigReplaceUserRoot(unittest.TestCase):
    def test_replace_preserves_defaults(self):
        c = Config('dummy.yaml')
        c.default('key.value', 'default')
        c.default('key.other', 'other_default')
        c.load()
        c.replace_user_root({'key': {'value': 'replaced'}})
        self.assertEqual(c['key.value'], 'replaced')
        self.assertEqual(c['key.other'], 'other_default')

    def test_replace_with_empty(self):
        c = Config('dummy.yaml')
        c.default('key.value', 'default')
        c.load()
        c['key.value'] = 'modified'
        c.replace_user_root({})
        self.assertEqual(c['key.value'], 'default')

    def test_replace_adds_new_user_keys(self):
        c = Config('dummy.yaml')
        c.default('key.value', 'default')
        c.load()
        c.replace_user_root({'key': {'value': 'new'}, 'extra': 'data'})
        self.assertEqual(c['key.value'], 'new')
        self.assertEqual(c['extra'], 'data')

class TestConfigSaveRoundtrip(unittest.TestCase):
    """Verify that saved config YAML matches the in-memory structure."""

    def test_dict_structure_roundtrip(self):
        c = Config('dummy.yaml')
        c.default('hdmi.front.physical_address', 0x1000)
        c.default('hdmi.front.name', 'amity')
        raw = save_and_read_yaml(c)
        self.assertEqual(raw['hdmi']['front']['physical_address'], 0x1000)
        self.assertEqual(raw['hdmi']['front']['name'], 'amity')

    def test_list_structure_roundtrip(self):
        c = Config('dummy.yaml')
        c.default('items,0', 'alpha')
        c.default('items,1', 'beta')
        raw = save_and_read_yaml(c)
        self.assertIsInstance(raw['items'], list)
        self.assertEqual(raw['items'][0], 'alpha')
        self.assertEqual(raw['items'][1], 'beta')

    def test_mixed_structure_roundtrip(self):
        c = Config('dummy.yaml')
        c.default('theater.devices,0.name', 'TV')
        c.default('theater.devices,0.address', 0)
        c.default('theater.devices,1.name', 'AVR')
        raw = save_and_read_yaml(c)
        self.assertIsInstance(raw['theater']['devices'], list)
        self.assertEqual(raw['theater']['devices'][0]['name'], 'TV')
        self.assertEqual(raw['theater']['devices'][1]['name'], 'AVR')

    def test_setitem_roundtrip(self):
        c = Config('dummy.yaml')
        c.default('data.items,0.name', 'old')
        c['data.items,0.name'] = 'new'
        raw = save_and_read_yaml(c)
        self.assertEqual(raw['data']['items'][0]['name'], 'new')


class TestConfigPartialOverlay(unittest.TestCase):
    """Verify partial updates: user config specifies only some entries of a default dict/list."""

    def test_partial_dict_overlay_preserves_unset_defaults(self):
        """Default dict has 3 keys, user file overrides only 1."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'display': {'brightness': 80}}, f)
            fname = f.name
        try:
            c = Config(fname)
            c.default('display.brightness', 50)
            c.default('display.contrast', 70)
            c.default('display.gamma', 2.2)
            c.load()
            self.assertEqual(c['display.brightness'], 80)  # overridden
            self.assertEqual(c['display.contrast'], 70)     # default kept
            self.assertEqual(c['display.gamma'], 2.2)       # default kept
        finally:
            os.unlink(fname)

    def test_partial_nested_dict_overlay(self):
        """Nested dict: user overrides one leaf, others stay default."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'audio': {'eq': {'bass': 10}}}, f)
            fname = f.name
        try:
            c = Config(fname)
            c.default('audio.eq.bass', 0)
            c.default('audio.eq.mid', 0)
            c.default('audio.eq.treble', 0)
            c.load()
            self.assertEqual(c['audio.eq.bass'], 10)
            self.assertEqual(c['audio.eq.mid'], 0)
            self.assertEqual(c['audio.eq.treble'], 0)
        finally:
            os.unlink(fname)

    def test_partial_list_overlay_shorter_user_list(self):
        """Default list has 3 elements, user list has only 1 — the rest stay default."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'slots': ['user_a']}, f)
            fname = f.name
        try:
            c = Config(fname)
            c.default('slots,0', 'default_a')
            c.default('slots,1', 'default_b')
            c.default('slots,2', 'default_c')
            c.load()
            self.assertEqual(c['slots,0'], 'user_a')      # overridden
            self.assertEqual(c['slots,1'], 'default_b')    # default kept
            self.assertEqual(c['slots,2'], 'default_c')    # default kept
        finally:
            os.unlink(fname)

    def test_partial_list_overlay_longer_user_list(self):
        """User list has more elements than defaults — extra elements are appended."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'slots': ['user_a', 'user_b', 'user_c']}, f)
            fname = f.name
        try:
            c = Config(fname)
            c.default('slots,0', 'default_a')
            c.load()
            self.assertEqual(c['slots,0'], 'user_a')
            self.assertEqual(c['slots,1'], 'user_b')
            self.assertEqual(c['slots,2'], 'user_c')
        finally:
            os.unlink(fname)

    def test_partial_dict_in_list_overlay(self):
        """List of dicts: user overrides one field in the first element only."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'activities': [{'name': 'My Activity'}]}, f)
            fname = f.name
        try:
            c = Config(fname)
            c.default('activities,0.name', 'Default Activity')
            c.default('activities,0.source', 'AppleTV')
            c.default('activities,0.display', 'TV')
            c.load()
            self.assertEqual(c['activities,0.name'], 'My Activity')   # overridden
            self.assertEqual(c['activities,0.source'], 'AppleTV')     # default kept
            self.assertEqual(c['activities,0.display'], 'TV')         # default kept
        finally:
            os.unlink(fname)

    def test_partial_overlay_via_replace_user_root(self):
        """replace_user_root with partial data preserves defaults."""
        c = Config('dummy.yaml')
        c.default('network.host', 'localhost')
        c.default('network.port', 8080)
        c.default('network.tls', False)
        c.load()
        c.replace_user_root({'network': {'port': 9090}})
        self.assertEqual(c['network.host'], 'localhost')  # default
        self.assertEqual(c['network.port'], 9090)         # replaced
        self.assertEqual(c['network.tls'], False)          # default

    def test_partial_overlay_via_setitem_preserves_siblings(self):
        """Setting one key in a dict doesn't affect sibling keys."""
        c = Config('dummy.yaml')
        c.default('server.host', 'localhost')
        c.default('server.port', 80)
        c.default('server.debug', False)
        c['server.port'] = 443
        self.assertEqual(c['server.host'], 'localhost')
        self.assertEqual(c['server.port'], 443)
        self.assertEqual(c['server.debug'], False)

    def test_deep_partial_overlay(self):
        """3-level deep partial overlay: user sets one leaf in a nested structure."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.safe_dump({'a': {'b': {'x': 'user_x'}}}, f)
            fname = f.name
        try:
            c = Config(fname)
            c.default('a.b.x', 'default_x')
            c.default('a.b.y', 'default_y')
            c.default('a.b.z', 'default_z')
            c.default('a.c', 'default_c')
            c.load()
            self.assertEqual(c['a.b.x'], 'user_x')
            self.assertEqual(c['a.b.y'], 'default_y')
            self.assertEqual(c['a.b.z'], 'default_z')
            self.assertEqual(c['a.c'], 'default_c')
        finally:
            os.unlink(fname)


if __name__ == '__main__':
    unittest.main()
