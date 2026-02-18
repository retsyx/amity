# Copyright 2026.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio
import yaml
from typing import Any, TYPE_CHECKING

from nicegui import ui
from nicegui.events import ClickEventArguments

from aconfig import config
import mqtt_defaults

if TYPE_CHECKING:
    from main import Management

mqtt_credentials_file: str = 'var/mqtt/credentials.yaml'


class MQTT:
    def __init__(self, top: 'Management') -> None:
        self.name: str = 'MQTT'
        self.top: 'Management' = top
        self.has_unsaved_changes: bool = False
        self.disable_dialog: ui.dialog
        self.toggle_btn: ui.button
        self.host_input: ui.input
        self.port_input: ui.number
        self.username_input: ui.input
        self.password_input: ui.input
        self.tls_enabled_input: ui.checkbox
        self.tls_verify_cert_input: ui.checkbox
        self.ca_cert_input: ui.textarea
        self.device_id_input: ui.input
        self.device_name_input: ui.input
        self.discovery_prefix_input: ui.input
        self.enabled: bool
        self.amity_is_active: bool
        self.status_str: str
        self.saved_broker_host: str
        self.saved_broker_port: int
        self.saved_broker_username: str
        self.saved_broker_password: str
        self.saved_tls_enabled: bool
        self.saved_tls_verify_cert: bool
        self.saved_tls_ca_cert_content: str
        self.saved_discovery_prefix: str
        self.saved_device_id: str
        self.saved_device_name: str
        self.update()

    def ui(self) -> None:
        with ui.dialog() as disable_dialog, ui.card():
            disable_dialog.classes('items-center')
            self.disable_dialog = disable_dialog
            ui.label('Disable MQTT?').style("font-weight: bold; font-size: 1.5em;")
            ui.label('This will stop publishing to the MQTT broker.')
            with ui.row().classes('w-full justify-center'):
                ui.button('Yes', on_click=lambda: disable_dialog.submit(True))
                ui.button('No', on_click=lambda: disable_dialog.submit(False))

        with ui.column().classes('w-full items-center'):
            lbl = ui.label('Status')
            lbl.bind_text_from(self, 'status_str')

            # Configuration section
            with ui.card().classes('w-full max-w-2xl'):
                ui.label('Broker Configuration').style("font-weight: bold; font-size: 1.2em;")

                with ui.row().classes('w-full'):
                    self.host_input = ui.input('Broker Host', value=self.saved_broker_host, on_change=self.check_for_changes).classes('flex-grow')
                    self.port_input = ui.number('Port', value=self.saved_broker_port, min=1, max=65535,
                                                precision=0, on_change=self.check_for_changes).classes('w-32')

                with ui.row().classes('w-full'):
                    self.username_input = ui.input('Username',
                                                   value=self.saved_broker_username, on_change=self.check_for_changes).classes('flex-grow')
                    self.password_input = ui.input('Password',
                                                   value=self.saved_broker_password,
                                                   password=True, password_toggle_button=True, on_change=self.check_for_changes).classes('flex-grow')

                self.tls_enabled_input = ui.checkbox('Enable TLS/SSL', value=self.saved_tls_enabled, on_change=self.check_for_changes)

                with ui.column().classes('w-full').bind_visibility_from(self.tls_enabled_input, 'value'):
                    self.tls_verify_cert_input = ui.checkbox('Verify broker certificate', value=self.saved_tls_verify_cert, on_change=self.check_for_changes)
                    with ui.column().classes('w-full').bind_visibility_from(self.tls_verify_cert_input, 'value'):
                        self.ca_cert_input = ui.textarea(placeholder='CA Certificate (optional)', value=self.saved_tls_ca_cert_content, on_change=self.check_for_changes) \
                            .classes('w-full font-mono text-sm').props('rows=6')

                ui.separator()
                ui.label('Device Configuration').style("font-weight: bold; font-size: 1.2em;")

                self.device_id_input = ui.input('Device ID', value=self.saved_device_id, on_change=self.check_for_changes).classes('w-full')
                self.device_name_input = ui.input('Device Name', value=self.saved_device_name, on_change=self.check_for_changes).classes('w-full')
                self.discovery_prefix_input = ui.input('Discovery Prefix',
                                                       value=self.saved_discovery_prefix, on_change=self.check_for_changes).classes('w-full')

                # Action buttons - different layout based on enabled state
                # When disabled: Test and Enable
                # When enabled: Test, Discard (if changes), Save (if changes), and Disable
                with ui.row().classes('w-full gap-2'):
                    ui.button('Test Connection', on_click=self.test_connection).classes('flex-grow')
                    btn = ui.button('Discard Changes', color='negative', on_click=self.discard_changes).classes('flex-grow')
                    btn.bind_visibility_from(self, 'has_unsaved_changes')
                    btn = ui.button('Enable', on_click=self.toggle_enabled).classes('flex-grow')
                    btn.bind_visibility_from(self, 'amity_is_active')
                    b = lambda enabled: 'Disable' if enabled else 'Enable'
                    btn.bind_text_from(self, 'enabled', backward=b)
                    self.toggle_btn = btn

    def update(self) -> None:
        self.enabled = not not config['mqtt.enable']

        credentials: dict[str, Any] = {}
        try:
            with open(mqtt_credentials_file, 'r') as f:
                credentials = yaml.safe_load(f)
        except Exception:
            pass

        # Store saved config values for change tracking
        self.saved_broker_host = config['mqtt.broker.host']
        self.saved_broker_port = config['mqtt.broker.port']
        self.saved_broker_username = credentials.get('username', '')
        self.saved_broker_password = credentials.get('password', '')
        self.saved_tls_enabled = config['mqtt.broker.tls.enabled']
        self.saved_tls_verify_cert = config['mqtt.broker.tls.verify_cert']
        self.saved_tls_ca_cert_content = config['mqtt.broker.tls.ca_cert_content']
        self.saved_discovery_prefix = config['mqtt.discovery_prefix']
        self.saved_device_id = config['mqtt.device_id']
        self.saved_device_name = config['mqtt.device_name']

        # Update UI input fields if the UI has been populated
        if hasattr(self, 'host_input'):
            self.host_input.value = self.saved_broker_host
            self.port_input.value = self.saved_broker_port
            self.username_input.value = self.saved_broker_username
            self.password_input.value = self.saved_broker_password
            self.tls_enabled_input.value = self.saved_tls_enabled
            self.tls_verify_cert_input.value = self.saved_tls_verify_cert
            self.ca_cert_input.value = self.saved_tls_ca_cert_content
            self.device_id_input.value = self.saved_device_id
            self.device_name_input.value = self.saved_device_name
            self.discovery_prefix_input.value = self.saved_discovery_prefix

        if not config['adapters.front'] or not config['adapters.back']:
            self.amity_is_active = False
        else:
            self.amity_is_active = self.top.control().is_active()

        # Update status string
        if self.amity_is_active:
            if self.enabled:
                self.status_str = 'Enabled.'
            else:
                self.status_str = 'Disabled.'
        else:
            self.status_str = 'Amity is not ready. Scan HDMI, and save in the Activities tab.'

        # Check for unsaved changes
        self.check_for_changes()

    def will_show(self) -> None:
        self.update()

    def check_for_changes(self) -> None:
        """Check if current UI values differ from saved config"""
        if not hasattr(self, 'host_input'):
            return

        self.has_unsaved_changes = (
            self.host_input.value != self.saved_broker_host or
            self.port_input.value != self.saved_broker_port or
            self.username_input.value != self.saved_broker_username or
            self.password_input.value != self.saved_broker_password or
            self.tls_enabled_input.value != self.saved_tls_enabled or
            self.tls_verify_cert_input.value != self.saved_tls_verify_cert or
            self.ca_cert_input.value != self.saved_tls_ca_cert_content or
            self.device_id_input.value != self.saved_device_id or
            self.device_name_input.value != self.saved_device_name or
            self.discovery_prefix_input.value != self.saved_discovery_prefix
        )

    async def _save_settings(self) -> bool:
        """Save current UI values via configure_mqtt set-config and set-credentials."""

        # Validate inputs
        if not self.host_input.value:
            ui.notify('Broker host is required', type='negative')
            return False

        if not self.device_id_input.value:
            ui.notify('Device ID is required', type='negative')
            return False

        log.info('Saving MQTT credentials')

        # Save credentials
        cmd_parts: list[str] = ['./configure_mqtt', 'set-credentials']
        cmd_parts.extend(['--username', self.username_input.value])
        cmd_parts.extend(['--password', self.password_input.value])
        proc = await asyncio.create_subprocess_shell(' '.join(cmd_parts))
        await proc.wait()

        log.info('Saving MQTT configuration')

        # Save configuration
        cmd_parts = [
            './configure_mqtt', 'set-config',
            '--host', self.host_input.value,
            '--port', str(int(self.port_input.value)),
            '--device-id', self.device_id_input.value,
            '--device-name', self.device_name_input.value,
            '--discovery-prefix', self.discovery_prefix_input.value,
            '--tls' if self.tls_enabled_input.value else '--no-tls',
            '--verify-cert' if self.tls_verify_cert_input.value else '--no-verify-cert',
            '--ca-cert', self.ca_cert_input.value or '',
        ]
        proc = await asyncio.create_subprocess_shell(' '.join(cmd_parts))
        await proc.wait()
        self.update()
        return True

    async def toggle_enabled(self, event: ClickEventArguments) -> None:
        with event.client:
            self.toggle_btn.enabled = False
            self.top.spinner_show()
            if self.enabled:
                self.disable_dialog.open()
                confirm = await self.disable_dialog
                if confirm:
                    log.info('Disabling MQTT')
                    proc = await asyncio.create_subprocess_shell('./configure_mqtt disable')
                    await proc.wait()
            else:
                log.info('Enabling MQTT')
                if await self._save_settings():
                    proc = await asyncio.create_subprocess_shell('./configure_mqtt enable')
                    await proc.wait()

            self.update()
            self.toggle_btn.enabled = True
            self.top.spinner_hide()

    async def test_connection(self, event: ClickEventArguments) -> None:
        with event.client:
            self.top.spinner_show()

            # Validate inputs
            if not self.host_input.value:
                ui.notify('Broker host is required', type='negative')
                self.top.spinner_hide()
                return

            # Build command with parameters - don't modify config
            cmd_parts = ['./configure_mqtt', 'test']
            cmd_parts.extend(['--host', self.host_input.value])
            cmd_parts.extend(['--port', str(int(self.port_input.value))])

            if self.username_input.value:
                cmd_parts.extend(['--username', self.username_input.value])
            if self.password_input.value:
                cmd_parts.extend(['--password', self.password_input.value])
            cmd_parts.append('--tls' if self.tls_enabled_input.value else '--no-tls')
            cmd_parts.append('--verify-cert' if self.tls_verify_cert_input.value else '--no-verify-cert')
            if self.ca_cert_input.value:
                cmd_parts.extend(['--ca-cert', self.ca_cert_input.value])

            log.info('Testing MQTT connection')
            log.info(f'Command: {" ".join(cmd_parts)}')
            proc = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            output = stdout.decode('utf-8').strip() if stdout else ''
            error = stderr.decode('utf-8').strip() if stderr else ''

            log.info(f'Return code: {proc.returncode}')
            log.info(f'Stdout: {repr(output)}')
            log.info(f'Stderr: {repr(error)}')

            if output == 'OK':
                ui.notify('Connection successful!', type='positive')
            else:
                # Show error from stderr if output is empty
                message = output if output else (error if error else 'Connection failed')
                ui.notify(message, type='negative')

            self.top.spinner_hide()

    async def discard_changes(self, event: ClickEventArguments) -> None:
        with event.client:
            self.host_input.value = self.saved_broker_host
            self.port_input.value = self.saved_broker_port
            self.username_input.value = self.saved_broker_username
            self.password_input.value = self.saved_broker_password
            self.tls_enabled_input.value = self.saved_tls_enabled
            self.tls_verify_cert_input.value = self.saved_tls_verify_cert
            self.ca_cert_input.value = self.saved_tls_ca_cert_content
            self.device_id_input.value = self.saved_device_id
            self.device_name_input.value = self.saved_device_name
            self.discovery_prefix_input.value = self.saved_discovery_prefix
            self.check_for_changes()

    async def save_config(self, event: ClickEventArguments) -> None:
        with event.client:
            self.top.spinner_show()
            if not await self._save_settings():
                self.top.spinner_hide()
                return
            self.update()
            self.top.spinner_hide()
