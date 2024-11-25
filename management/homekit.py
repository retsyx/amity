# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio, os, re

from nicegui import ui

from aconfig import config

class HomeKit(object):
    def __init__(self, top):
        self.name = 'HomeKit'
        self.top = top
        self.code_img_column = None
        self.update()

    def ui(self):
        with ui.dialog() as dialog, ui.card():
            dialog.classes('items-center')
            self.dialog = dialog
            ui.label('Disable HomeKit?').style("font-weight: bold; font-size: 1.5em;")
            ui.label('This will deactivate Amity in HomeKit.')
            with ui.row().classes('w-full justify-center'):
                ui.button('Yes', on_click=lambda: dialog.submit(True))
                ui.button('No', on_click=lambda: dialog.submit(False))
        with ui.column().classes('w-full items-center'):
            b = lambda enabled: 'Disable' if enabled else 'Enable'
            btn = ui.button('Enable', on_click=self.toggle_enabled)
            btn.bind_visibility_from(self, 'amity_is_active')
            btn.bind_text_from(self, 'enabled', backward=b)
            self.toggle_btn = btn
            lbl = ui.label('Scan this code with the Home app on your iOS device.')
            lbl.bind_text_from(self, 'status_str')
            lbl = ui.label('If viewing this page on your iOS device, tap and hold the code, then select Open in Home.')
            lbl.bind_visibility_from(self, 'have_code')
            self.code_img_column = ui.column().classes('w-full items-center')
            self.create_code_image()
            b = lambda pin: f'Or enter this code in the Home app on your iOS device: {pin}'
            lbl = ui.label('PIN')
            lbl.bind_visibility_from(self, 'have_code')
            lbl.bind_text_from(self, 'pin', backward=b)

    def create_code_image(self):
        # ui.image() has a force_reload() function. However, if the image doesn't exist when
        # when the ui.image() is created, then force_reload() won't reload the image that was
        # created later. The HomeKit pairing code image doesn't exist if HomeKit is initially off.
        # The workaround for the ui.image() bug is to create a container for the ui.image(). Then,
        # to force a reload, empty the container, and recreate the ui.image() element.
        if self.code_img_column is None:
            return
        with self.code_img_column as col:
            col.clear()
            img = ui.image('var/homekit/code.png').props('width=50% height=50%')
            img.bind_visibility_from(self, 'have_code')
            img.force_reload()

    def update(self):
        self.enabled = not not config['homekit.enable']
        self.pin = ''
        self.paired = True
        if not config['adapters.front'] or not config['adapters.back']:
            self.amity_is_active = False
        else:
            self.amity_is_active = self.top.control.is_active()

        try:
            with open('var/homekit/code', 'r') as f:
                pair_instructions = f.read()
            if pair_instructions != 'Paired':
                self.paired = False
                match = re.search('[0-9]+-[0-9]+-[0-9]+', pair_instructions)
                self.pin = match.group()
        except FileNotFoundError:
            self.paired = False

        if self.amity_is_active:
            if self.paired:
                self.status_str = 'Paired.'
                self.have_code = False
            else:
                if self.enabled:
                    self.status_str = 'Scan this code with the Home app on your iOS device.'
                    self.have_code = os.path.isfile('var/homekit/code.png')
                else:
                    self.status_str = 'Enable to begin HomeKit pairing.'
                    self.have_code = False
        else:
            self.status_str = 'Amity is not ready. Scan HDMI, and save in the Activities tab.'
            self.have_code = False

        log.info(f'Have code {self.have_code}')

        self.create_code_image()

    def will_show(self):
        self.update()

    async def toggle_enabled(self, event):
        with event.client:
            self.toggle_btn.enabled = False
            self.top.spinner.open()
            if self.enabled:
                self.dialog.open()
                confirm = await self.dialog
                if confirm:
                    log.info('Disabling HomeKit')
                    proc = await asyncio.create_subprocess_shell('./configure_homekit disable')
                    await proc.wait()
                    proc = await asyncio.create_subprocess_shell('./configure_homekit reset')
                    await proc.wait()
            else:
                log.info('Enabling HomeKit')
                proc = await asyncio.create_subprocess_shell('./configure_homekit enable')
                await proc.wait()
            self.update()
            self.toggle_btn.enabled = True
            self.top.spinner.close()
