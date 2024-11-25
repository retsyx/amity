# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

# GPIO config
# config backup/restore
# config download/upload
# log download

import asyncio, os, tempfile, yaml, zipfile

from nicegui import ui

from aconfig import config
from service import Control

class Advanced(object):
    def __init__(self, top):
        self.taskit = tools.Tasker('Advanced')
        self.name = 'Advanced'
        self.top = top
        self.gpio_status = None
        self.update()

    def ui(self):
        with ui.dialog() as dialog, ui.card():
            self.dialog = dialog
            ui.label('Change Splice Configuration?').style("font-weight: bold; font-size: 1.5em;")
            ui.label('Misconfiguration may damage your equipment.')
            with ui.row().classes('w-full justify-center'):
                ui.button('Yes', on_click=lambda: dialog.submit(True))
                ui.button('No', on_click=lambda: dialog.submit(False))

        with ui.column().classes('items-stretch'):
            with ui.card().classes('items-stretch'):
                ui.label('Configuration').classes('text-h6')
                ui.label('Download Amity configuration for backup.')
                ui.button('Download', on_click=self.download_config)
                ui.label("Configuration gone awry, and don't know what changed? Download the most recent configurations.").classes('w-64')
                ui.button('Download Recent', on_click=self.download_all_configs)
                ui.label('Upload, and restore a previous configuration.')
                ui.upload(
                    label='Upload',
                    max_file_size=65536,
                    on_rejected=lambda: ui.notify('File is too large', color='negative'),
                    on_upload=self.upload_config).classes('max-w-full')
            with ui.card().classes('items-stretch'):
                ui.label('HDMI Splice').classes('text-h6')
                def b(gpio_status):
                    if gpio_status == 'external':
                        return 'Configured for Amity Board.'
                    elif gpio_status == 'internal':
                        return 'Configured for a spliced HDMI cable.'
                    return ''
                ui.label('').bind_text_from(self, 'gpio_status', backward=b)
                btn = ui.button('', on_click=self.toggle_gpio)
                def b(gpio_status):
                    if gpio_status == 'external':
                        return 'Use with a spliced HDMI cable'
                    elif gpio_status =='internal':
                        return 'Use with Amity Board'
                    return ''
                btn.bind_text_from(self, 'gpio_status', backward=b)
                def b(gpio_status):
                    if gpio_status in ('external', 'internal'):
                        return True
                    return False
                btn.bind_visibility_from(self, 'gpio_status', backward=b)
            with ui.card().classes('items-stretch'):
                ui.label('Logs').classes('text-h6')
                ui.button('Download logs', on_click=self.download_logs)
            with ui.card().classes('items-stretch'):
                ui.label('User').classes('text-h6')
                ui.link('Logout', '/logout')
                ui.link('Change Password', '/enroll')

    def download_logs(self):
        log.info('Downloading log files')
        # Compress var/log into an archive and offer it up for download
        zip_path = compress_directory_to_zip('var/log')
        ui.download(zip_path, 'logs.zip', 'application/zip')

    def download_config(self):
        log.info('Downloading config.yaml')
        ui.download(config.filename, 'config.yaml', 'text/html; charset=utf-8')

    def download_all_configs(self):
        log.info('Downloading config and backups')
        zip_path = compress_directory_to_zip('var/config')
        ui.download(zip_path, 'configs.zip', 'application/zip')

    def upload_config(self, event):
        try:
            text = event.content.read().decode('utf-8')
        except UnicodeDecodeError:
            log.info('Uploaded config file is not valid UTF-8')
            ui.notify('File is not a valid configuration file', color='negative')
            return
        try:
            new_config = yaml.safe_load(text)
        except yaml.scanner.ScannerError:
            log.info('Uploaded config file is not valid YAML')
            ui.notify('File is not a valid configuration file', color='negative')
            return
        log.info('Uploaded config.yaml')
        config.replace_user_root(new_config)
        config.save(True)

    async def toggle_gpio(self, event):
        event.sender.enabled = False
        self.top.spinner.open()
        self.dialog.open()
        confirm = await self.dialog
        if confirm:
            if self.gpio_status == 'internal':
                cmd = 'external'
            else:
                cmd = 'internal'
            log.info(f'Setting GPIO to {cmd}')
            proc = await asyncio.create_subprocess_shell(f'./configure_gpio {cmd}')
            await proc.wait()
            self.update()
        event.sender.enabled = True
        self.top.spinner.close()

    def update(self):
        if asyncio.get_event_loop().is_running():
            self.taskit(self.update_gpio_status())

    def will_show(self):
        self.update()

    async def update_gpio_status(self):
        proc = await asyncio.create_subprocess_shell('./configure_gpio status', stdout=asyncio.subprocess.PIPE)
        output = await proc.stdout.read()
        self.gpio_status = output.decode('utf-8').strip()
        log.info(f'GPIO status {self.gpio_status}')
        await proc.wait()

def compress_directory_to_zip(source_dir):
    """
    Compresses the contents of a directory into a unique temporary zip file.

    Args:
        source_dir (str): Path to the directory to compress.

    Returns:
        str: Path to the created temporary zip file.
    """
    # Create a temporary file for the zip
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix=".zip")
    temp_zip_path = temp_zip.name
    temp_zip.close()  # Close the file so it can be written to later

    with zipfile.ZipFile(temp_zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            for file in files:
                file_path = os.path.join(root, file)
                # Add file to the zip, preserving relative path
                arcname = os.path.relpath(file_path, start=source_dir)
                zipf.write(file_path, arcname)

    return temp_zip_path
