# Copyright 2026.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__ + " ") # aiomqtt hijacks the mqtt logger

from aconfig import config

import asyncio
import json
import ssl
from typing import Any

import yaml

import aiomqtt

from hdmi import Key
from messaging import Pipe
import mqtt_defaults

# MQTT certificate paths
MQTT_DIR = 'var/mqtt'
MQTT_CREDENTIALS_FILE = f'{MQTT_DIR}/credentials.yaml'

# Media control buttons and their HDMI-CEC key mappings
BUTTON_KEY_MAP = {
    'play': Key.PLAY,
    'pause': Key.PAUSE,
    'stop': Key.STOP,
    'rewind': Key.REWIND,
    'fast_forward': Key.FAST_FORWARD,
    'next': Key.FORWARD,
    'previous': Key.BACKWARD,
    'up': Key.UP,
    'down': Key.DOWN,
    'left': Key.LEFT,
    'right': Key.RIGHT,
    'select': Key.SELECT,
    'back': Key.BACK,
    'root_menu': Key.ROOT_MENU,
    'volume_up': Key.VOLUME_UP,
    'volume_down': Key.VOLUME_DOWN,
    'mute': Key.TOGGLE_MUTE,
}


class MQTT:
    def __init__(self, activity_names: list[str], loop: asyncio.AbstractEventLoop, pipe: Pipe | None) -> None:
        self.activity_names = activity_names
        self.loop = loop
        self.pipe = pipe
        self.client: aiomqtt.Client | None = None
        self.taskit = tools.Tasker('MQTT')

        # State tracking
        self.current_activity: int = -1  # -1 = standby
        self.battery_level: int = 100
        self.battery_charging: bool = False
        self.battery_low: bool = False

        # MQTT configuration
        self.broker_host: str = config['mqtt.broker.host']
        self.broker_port: int = config['mqtt.broker.port']

        credentials: dict[str, Any] = {}
        try:
            with open(MQTT_CREDENTIALS_FILE, 'r') as f:
                credentials = yaml.safe_load(f)
        except Exception:
            pass

        self.broker_username: str | None = credentials.get('username')
        self.broker_password: str | None = credentials.get('password')

        self.tls_enabled = config['mqtt.broker.tls.enabled']
        self.tls_verify_cert = config['mqtt.broker.tls.verify_cert']
        self.tls_ca_cert_content = config['mqtt.broker.tls.ca_cert_content']
        self.reconnect_min_interval = config['mqtt.reconnect.min_interval_sec']
        self.reconnect_max_interval = config['mqtt.reconnect.max_interval_sec']
        self.discovery_prefix = config['mqtt.discovery_prefix']
        self.device_id = config['mqtt.device_id']
        self.device_name = config['mqtt.device_name']

        # Base topic paths for each entity type
        switch_base = f"{self.discovery_prefix}/switch/{self.device_id}/power"
        select_base = f"{self.discovery_prefix}/select/{self.device_id}/source"
        state_sensor_base = f"{self.discovery_prefix}/sensor/{self.device_id}/state"
        battery_level_base = f"{self.discovery_prefix}/sensor/{self.device_id}/battery_level"
        battery_charging_base = f"{self.discovery_prefix}/binary_sensor/{self.device_id}/battery_charging"

        self.switch_state_topic = f"{switch_base}/state"
        self.switch_command_topic = f"{switch_base}/set"
        self.switch_config_topic = f"{switch_base}/config"

        self.select_state_topic = f"{select_base}/state"
        self.select_command_topic = f"{select_base}/set"
        self.select_config_topic = f"{select_base}/config"

        self.button_base = f"{self.discovery_prefix}/button/{self.device_id}"

        self.state_sensor_state_topic = f"{state_sensor_base}/state"
        self.state_sensor_config_topic = f"{state_sensor_base}/config"

        self.battery_level_state_topic = f"{battery_level_base}/state"
        self.battery_level_config_topic = f"{battery_level_base}/config"
        self.battery_charging_state_topic = f"{battery_charging_base}/state"
        self.battery_charging_config_topic = f"{battery_charging_base}/config"

        if self.pipe is not None:
            self.pipe.start_client_task(self)

    async def start(self) -> None:
        """Start MQTT client with reconnection handling"""
        log.info('Starting MQTT')
        self.taskit(self._connection_handler())

    async def _connection_handler(self) -> None:
        """Handle MQTT connection with automatic reconnection"""
        reconnect_interval = self.reconnect_min_interval

        while True:
            try:
                # Setup TLS if enabled
                tls_context = None
                if self.tls_enabled:
                    tls_context = await self._create_tls_context()

                # Create MQTT client
                async with aiomqtt.Client(
                    hostname=self.broker_host,
                    port=self.broker_port,
                    username=self.broker_username if self.broker_username else None,
                    password=self.broker_password if self.broker_password else None,
                    tls_context=tls_context,
                    identifier=f"{self.device_id}_client"
                ) as client:
                    self.client = client

                    # Publish discovery messages
                    await self._publish_discovery()

                    # Publish initial state
                    await self._publish_state()

                    # Subscribe to all command topics
                    await self.client.subscribe(self.switch_command_topic)
                    await self.client.subscribe(self.select_command_topic)
                    # Subscribe to all button command topics
                    for button_name in BUTTON_KEY_MAP.keys():
                        await self.client.subscribe(f"{self.button_base}/{button_name}/set")

                    log.info('MQTT connected successfully')
                    reconnect_interval = self.reconnect_min_interval

                    # Handle messages
                    async for message in self.client.messages:
                        try:
                            await self._handle_command(message)
                        except Exception as e:
                            log.error(f'Error handling MQTT message: {e}')

            except aiomqtt.MqttError as e:
                log.error(f'MQTT connection error: {e}. Reconnecting in {reconnect_interval:.1f} seconds...')
                self.client = None
                await asyncio.sleep(reconnect_interval)
                reconnect_interval = min(reconnect_interval * 2, self.reconnect_max_interval)

    def wait_on(self) -> set[asyncio.Task[Any]]:
        return self.taskit.tasks

    async def _create_tls_context(self) -> ssl.SSLContext:
        """Create TLS context from certificate content and files"""
        tls_context = ssl.create_default_context()

        # Skip certificate verification if verify_cert is disabled
        if not self.tls_verify_cert:
            tls_context.check_hostname = False
            tls_context.verify_mode = ssl.CERT_NONE
        elif self.tls_ca_cert_content:
            # Load CA certificate if provided - can use cadata parameter directly
            tls_context.load_verify_locations(cadata=self.tls_ca_cert_content)

        return tls_context

    async def _publish_discovery(self) -> None:
        """Publish Home Assistant MQTT Discovery messages"""
        log.info('Publishing discovery messages')

        # Device information shared across all entities
        device_info = {
            'identifiers': [self.device_id],
            'name': self.device_name,
            'manufacturer': 'Amity',
            'model': 'Amity HDMI-CEC Hub',
            'sw_version': '1.0'
        }

        assert self.client is not None

        # Switch for power on/off
        switch_config = {
            'name': f"{self.device_name} Power",
            'unique_id': f"{self.device_id}_power",
            'device': device_info,
            'state_topic': self.switch_state_topic,
            'command_topic': self.switch_command_topic,
            'payload_on': 'ON',
            'payload_off': 'OFF',
            'state_on': 'ON',
            'state_off': 'OFF',
            'icon': 'mdi:power',
        }
        await self.client.publish(
            self.switch_config_topic,
            payload=json.dumps(switch_config),
            retain=True
        )

        # Select for source/activity selection
        select_config = {
            'name': f"{self.device_name} Source",
            'unique_id': f"{self.device_id}_source",
            'device': device_info,
            'state_topic': self.select_state_topic,
            'command_topic': self.select_command_topic,
            'options': ['Standby'] + list(self.activity_names),
            'icon': 'mdi:video-input-hdmi',
        }
        await self.client.publish(
            self.select_config_topic,
            payload=json.dumps(select_config),
            retain=True
        )

        # Buttons for media controls
        for button_name, key in BUTTON_KEY_MAP.items():
            button_config = {
                'name': f"{self.device_name} {button_name.replace('_', ' ').title()}",
                'unique_id': f"{self.device_id}_button_{button_name}",
                'device': device_info,
                'command_topic': f"{self.button_base}/{button_name}/set",
                'payload_press': 'PRESS',
                'icon': self._get_button_icon(button_name),
            }
            await self.client.publish(
                f"{self.button_base}/{button_name}/config",
                payload=json.dumps(button_config),
                retain=True
            )

        # State sensor
        state_sensor_config = {
            'name': f"{self.device_name} State",
            'unique_id': f"{self.device_id}_state",
            'device': device_info,
            'state_topic': self.state_sensor_state_topic,
            'icon': 'mdi:information-outline',
        }
        await self.client.publish(
            self.state_sensor_config_topic,
            payload=json.dumps(state_sensor_config),
            retain=True
        )

        # Battery level sensor discovery
        battery_level_config = {
            'name': f"{self.device_name} Battery",
            'unique_id': f"{self.device_id}_battery_level",
            'device': device_info,
            'state_topic': self.battery_level_state_topic,
            'device_class': 'battery',
            'unit_of_measurement': '%',
            'state_class': 'measurement',
        }
        await self.client.publish(
            self.battery_level_config_topic,
            payload=json.dumps(battery_level_config),
            retain=True
        )

        # Battery charging sensor discovery
        battery_charging_config = {
            'name': f"{self.device_name} Battery Charging",
            'unique_id': f"{self.device_id}_battery_charging",
            'device': device_info,
            'state_topic': self.battery_charging_state_topic,
            'device_class': 'battery_charging',
            'payload_on': 'ON',
            'payload_off': 'OFF',
        }
        await self.client.publish(
            self.battery_charging_config_topic,
            payload=json.dumps(battery_charging_config),
            retain=True
        )

    def _get_button_icon(self, button_name: str) -> str:
        """Get Material Design Icon for button"""
        icon_map = {
            'play': 'mdi:play',
            'pause': 'mdi:pause',
            'stop': 'mdi:stop',
            'rewind': 'mdi:rewind',
            'fast_forward': 'mdi:fast-forward',
            'next': 'mdi:skip-next',
            'previous': 'mdi:skip-previous',
            'up': 'mdi:arrow-up',
            'down': 'mdi:arrow-down',
            'left': 'mdi:arrow-left',
            'right': 'mdi:arrow-right',
            'select': 'mdi:checkbox-marked-circle',
            'back': 'mdi:arrow-left-circle',
            'root_menu': 'mdi:home',
            'volume_up': 'mdi:volume-plus',
            'volume_down': 'mdi:volume-minus',
            'mute': 'mdi:volume-mute',
        }
        return icon_map.get(button_name, 'mdi:gesture-tap-button')

    async def _publish_state(self) -> None:
        """Publish current state to Home Assistant"""
        if not self.client:
            return

        # Determine state and source
        if self.current_activity == -1:
            power_state = 'OFF'
            source = 'Standby'
            state_text = 'Standby'
        else:
            power_state = 'ON'
            source = self.activity_names[self.current_activity]
            state_text = f'{source}'

        # Publish switch state (power on/off)
        await self.client.publish(self.switch_state_topic, payload=power_state)

        # Publish select state (current source/activity)
        await self.client.publish(self.select_state_topic, payload=source)

        # Publish state sensor
        await self.client.publish(self.state_sensor_state_topic, payload=state_text)

        # Publish battery state
        await self.client.publish(
            self.battery_level_state_topic,
            payload=str(self.battery_level)
        )

        await self.client.publish(
            self.battery_charging_state_topic,
            payload='ON' if self.battery_charging else 'OFF'
        )

    async def _handle_command(self, message: aiomqtt.Message) -> None:
        """Handle commands from Home Assistant"""
        topic = message.topic.value
        payload = message.payload.decode('utf-8')
        log.info(f'Received command on {topic}: {payload}')

        try:
            # Handle switch commands (power on/off)
            if topic == self.switch_command_topic:
                if payload == 'ON':
                    log.info('Power on - starting first activity')
                    if self.pipe:
                        self.pipe.set_activity(0)
                elif payload == 'OFF':
                    log.info('Power off - going to standby')
                    if self.pipe:
                        self.pipe.set_activity(-1)

            # Handle select commands (source/activity selection)
            elif topic == self.select_command_topic:
                if payload == 'Standby':
                    log.info('Selected Standby')
                    if self.pipe:
                        self.pipe.set_activity(-1)
                elif payload in self.activity_names:
                    index = self.activity_names.index(payload)
                    log.info(f'Selected source: {payload} (index {index})')
                    if self.pipe:
                        self.pipe.set_activity(index)
                else:
                    log.warning(f'Unknown source: {payload}')

            # Handle button commands
            elif topic.startswith(self.button_base):
                # Extract button name from topic
                button_name = topic.replace(f"{self.button_base}/", "").replace("/set", "")

                if button_name in BUTTON_KEY_MAP:
                    key = BUTTON_KEY_MAP[button_name]
                    log.info(f'Button pressed: {button_name} -> {key:02X}')
                    if self.pipe:
                        self.pipe.key_press(key.value, 1)
                else:
                    log.warning(f'Unknown button: {button_name}')

            else:
                log.warning(f'Unknown command topic: {topic}')

        except Exception as e:
            log.error(f'Error processing command: {e}')

    # Server notification handlers (called by Hub via pipe)
    async def server_notify_set_activity(self, index: int) -> None:
        """Called when activity changes"""
        log.info(f'Activity changed to index {index}')
        self.current_activity = index
        await self._publish_state()

    async def server_notify_battery_state(self, level: int, is_charging: bool, is_low: bool) -> None:
        """Called when battery state changes"""
        log.info(f'Notifying battery state {level} {is_charging} {is_low}')
        self.battery_level = level
        self.battery_charging = is_charging
        self.battery_low = is_low
        await self._publish_state()
