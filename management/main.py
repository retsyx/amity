#!/usr/bin/env python

# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger('var/log/management.log')

import asyncio, os

from nicegui import app, ui

from aconfig import config, ConfigWatcher
from service import Control

# Authentication
import authentication

# Management pages
from activities import Activities
from remotes import Remotes
from homekit import HomeKit
from advanced import Advanced

class Management(object):
    def __init__(self):
        self.watcher = ConfigWatcher(config, self.update)
        self.taskit = tools.Tasker('Management')
        self.control = Control('amity-hub')
        self.current_tab = None
        self.pages = [cls(self) for cls in (Activities, Remotes, HomeKit, Advanced)]
        self.tabs = []

        @ui.page('/')
        async def root():
            ui.dark_mode(value = None)
            ui.page_title('Amity')
            self.spinner = ui.dialog().classes("items-center justify-center").props('persistent')
            with self.spinner:
                ui.spinner(size="lg")

            with ui.tabs().classes('w-full') as tabs:
                tabs.bind_value_to(self, 'current_tab', forward=self.on_tab_change)
                for page in self.pages:
                    self.tabs.append(ui.tab(page.name))
            with ui.tab_panels(tabs, value=self.tabs[0]).classes('w-full'):
                for tab, page in zip(self.tabs, self.pages):
                    with ui.tab_panel(tab).classes('items-center'):
                        page.ui()
            self.update()

    def on_tab_change(self, name):
        for page in self.pages:
            if page.name == name:
                page.will_show()
        return name

    def async_env_start(self):
        self.watcher.start()

    def update(self):
        config.load()
        for page in self.pages:
            page.update()

def main():
    os.environ['NICEGUI_STORAGE_PATH'] = 'var/nicegui'
    mgmt = Management()
    app.add_middleware(authentication.AuthMiddleware)
    app.on_startup(mgmt.async_env_start)
    ui.run(reload=False,
           show=False,
           port=443,
           ssl_certfile='var/gui/cert.pem',
           ssl_keyfile='var/gui/key.pem',
           storage_secret=authentication.get_storage_secret(),
           title='Amity',
           favicon='management/favicon.png')

main()
