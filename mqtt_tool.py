#!/usr/bin/env python

# Copyright 2025.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger('var/log/mqtt_tool')

import argparse
import asyncio
import ssl
import aiomqtt
import yaml

from aconfig import config
import mqtt_defaults
import service

config_mqtt_enable_path = 'mqtt.enable'
mqtt_dir = 'var/mqtt'
mqtt_credentials_file = f'{mqtt_dir}/credentials.yaml'

def enable(control):
    log.info('Enable')
    if config[config_mqtt_enable_path]:
        return
    def op():
        config[config_mqtt_enable_path] = True
        config.save(True)
    control.safe_do(op)

def status(control):
    log.info('Status')
    if not config[config_mqtt_enable_path]:
        s = 'MQTT is disabled'
    elif not control.is_active():
        s = 'Amity not running'
    else:
        broker = config['mqtt.broker.host']
        port = config['mqtt.broker.port']
        device_id = config['mqtt.device_id']
        s = f'MQTT enabled - broker: {broker}:{port}, device: {device_id}'
    log.info(s)
    print(s)


def disable(control):
    log.info('Disable')
    if config[config_mqtt_enable_path] == False:
        return
    def op():
        config[config_mqtt_enable_path] = False
        config.save(True)
    control.safe_do(op)

async def _test_connection_async(broker_host, broker_port, broker_username, broker_password,
                                 tls_enabled, tls_verify_cert, tls_ca_cert_content):
    """Test MQTT broker connection with provided parameters"""
    # Setup TLS if enabled
    tls_context = None

    try:
        if tls_enabled:
            tls_context = ssl.create_default_context()

            # Skip certificate verification if verify_cert is disabled
            if not tls_verify_cert:
                tls_context.check_hostname = False
                tls_context.verify_mode = ssl.CERT_NONE
            elif tls_ca_cert_content:
                # Load CA certificate if provided - use cadata parameter directly
                tls_context.load_verify_locations(cadata=tls_ca_cert_content)

        # Try to connect
        try:
            async with aiomqtt.Client(
                hostname=broker_host,
                port=broker_port,
                username=broker_username if broker_username else None,
                password=broker_password if broker_password else None,
                tls_context=tls_context,
                identifier="amity_test_client"
            ) as client:
                # If we get here, connection was successful
                return True, f'Successfully connected to {broker_host}:{broker_port}'

        except aiomqtt.MqttError as e:
            return False, f'Connection failed: {e}'
        except Exception as e:
            return False, f'Unexpected error: {e}'

    except Exception as e:
        return False, f'Error setting up TLS: {e}'


def test(control, args):
    log.info('Test')

    success, message = asyncio.run(_test_connection_async(
        args.host, args.port, args.username, args.password,
        args.tls, args.verify_cert, args.ca_cert
    ))

    if success:
        log.info('OK')
        print('OK')
    else:
        log.error(message)
        print(message)


def set_credentials(control, args):
    log.info('Set MQTT credentials')

    creds = {}
    try:
        with open(mqtt_credentials_file, 'r') as f:
            creds = yaml.safe_load(f)
    except Exception:
        pass

    if args.username is not None:
        creds['username'] = args.username
    if args.password is not None:
        creds['password'] = args.password

    def op():
        with open(mqtt_credentials_file, 'w') as f:
            yaml.safe_dump(creds, f)
    control.safe_do(op)


def set_config(control, args):
    log.info('Set MQTT configuration')

    if args.host is not None:
        config['mqtt.broker.host'] = args.host
    if args.port is not None:
        config['mqtt.broker.port'] = args.port
    if args.tls is not None:
        config['mqtt.broker.tls.enabled'] = args.tls
    if args.verify_cert is not None:
        config['mqtt.broker.tls.verify_cert'] = args.verify_cert
    if args.ca_cert is not None:
        config['mqtt.broker.tls.ca_cert_content'] = args.ca_cert
    if args.device_id is not None:
        config['mqtt.device_id'] = args.device_id
    if args.device_name is not None:
        config['mqtt.device_name'] = args.device_name
    if args.discovery_prefix is not None:
        config['mqtt.discovery_prefix'] = args.discovery_prefix

    control.safe_do(lambda: config.save(True))

def main():
    arg_parser = argparse.ArgumentParser()
    subparsers = arg_parser.add_subparsers(dest='action', required=True)

    subparsers.add_parser('enable')
    subparsers.add_parser('status')
    subparsers.add_parser('disable')

    # test: requires connection parameters
    test_parser = subparsers.add_parser('test')
    test_parser.add_argument('--host', required=True, help='MQTT broker hostname')
    test_parser.add_argument('--port', type=int, required=True, help='MQTT broker port')
    test_parser.add_argument('--username', nargs='?', const='', type=str, default=None, help='MQTT username')
    test_parser.add_argument('--password', nargs='?', const='', type=str, default=None, help='MQTT password')
    test_parser.add_argument('--tls', action=argparse.BooleanOptionalAction, required=True, help='Enable TLS')
    test_parser.add_argument('--verify-cert', action=argparse.BooleanOptionalAction, required=True, help='Verify TLS certificate')
    test_parser.add_argument('--ca-cert', nargs='?', const='', type=str, default=None, help='CA certificate content')

    # set-credentials
    creds_parser = subparsers.add_parser('set-credentials')
    creds_parser.add_argument('--username', nargs='?', const='', type=str, default=None, help='MQTT username')
    creds_parser.add_argument('--password', nargs='?', const='', type=str, default=None, help='MQTT password')

    # set-config: all optional for partial updates
    config_parser = subparsers.add_parser('set-config')
    config_parser.add_argument('--host', help='MQTT broker hostname')
    config_parser.add_argument('--port', type=int, help='MQTT broker port')
    config_parser.add_argument('--tls', action=argparse.BooleanOptionalAction, default=None, help='Enable TLS')
    config_parser.add_argument('--verify-cert', action=argparse.BooleanOptionalAction, default=None, help='Verify TLS certificate')
    config_parser.add_argument('--ca-cert', nargs='?', const='', type=str, default=None, help='CA certificate content')
    config_parser.add_argument('--device-id', help='Device ID')
    config_parser.add_argument('--device-name', help='Device name')
    config_parser.add_argument('--discovery-prefix', help='MQTT discovery prefix')

    args = arg_parser.parse_args()
    config.load()
    control = service.Control('amity-hub')
    match args.action:
        case 'enable':
            enable(control)
        case 'status':
            status(control)
        case 'disable':
            disable(control)
        case 'test':
            test(control, args)
        case 'set-credentials':
            set_credentials(control, args)
        case 'set-config':
            set_config(control, args)


if __name__ == '__main__':
    main()
