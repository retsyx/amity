# Copyright 2026.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

from aconfig import config

config.default('mqtt.enable', False)
config.default('mqtt.broker.host', 'homeassistant')
config.default('mqtt.broker.port', 1883)
config.default('mqtt.broker.tls.enabled', False)
config.default('mqtt.broker.tls.verify_cert', True)
config.default('mqtt.broker.tls.ca_cert_content', '')
config.default('mqtt.reconnect.min_interval_sec', 0.1)
config.default('mqtt.reconnect.max_interval_sec', 60.0)
config.default('mqtt.discovery_prefix', 'homeassistant')
config.default('mqtt.device_id', 'amity')
config.default('mqtt.device_name', 'Amity')
