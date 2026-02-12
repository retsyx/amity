# Copyright 2025.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import asyncio
from unittest.mock import MagicMock

# Mock tools before importing anything that depends on it
mock_tools = MagicMock()
mock_tools.logger = MagicMock(return_value=MagicMock())
mock_tools.Tasker = MagicMock()
sys.modules['tools'] = mock_tools

# Create a real Config object (tools must be mocked first since config.py imports it)
from config import Config
mock_config = Config('test_config.yaml')

# Mock aconfig to provide our config instance
mock_aconfig = MagicMock()
mock_aconfig.config = mock_config
sys.modules['aconfig'] = mock_aconfig


# Common test utilities
def make_taskit_mock():
    """Create a MagicMock for taskit that closes coroutine args to avoid warnings."""
    mock = MagicMock()
    def side_effect(*args):
        for arg in args:
            if asyncio.iscoroutine(arg):
                arg.close()
        return MagicMock()
    mock.side_effect = side_effect
    return mock
