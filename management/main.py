#!/usr/bin/env python

# Copyright 2024-2026.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger('var/log/management.log')

import asyncio, os
from collections.abc import Coroutine
from typing import Any
from impl_protocols import Page

os.environ['NICEGUI_STORAGE_PATH'] = 'var/gui/nicegui'

from nicegui import app, ui

from aconfig import config, ConfigWatcher
from service import Control

# Authentication
import authentication

# Management pages
from activities import Activities
from remotes import Remotes
from homekit import HomeKit
from mqtt import MQTT
from advanced import Advanced

class Management:
    def __init__(self) -> None:
        self.watcher: ConfigWatcher = ConfigWatcher(config, self.update)
        self._taskit: tools.Tasker = tools.Tasker('Management')
        self._control: Control = Control('amity-hub')
        self.current_tab: str | None = None
        self.pages: list[Page] = [cls(self) for cls in (Activities, Remotes, HomeKit, MQTT, Advanced)]
        self.tabs: list[ui.tab] = []
        self.spinner: ui.dialog | None = None

        @ui.page('/')
        async def root() -> None:
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

    def on_tab_change(self, name: str) -> str:
        for page in self.pages:
            if page.name == name:
                page.will_show()
        return name

    def async_env_start(self) -> None:
        self.watcher.start()

    def update(self) -> None:
        config.load()
        for page in self.pages:
            page.update()

    def taskit(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        return self._taskit(coro)

    def control(self) -> Control:
        return self._control

    def spinner_show(self) -> None:
        assert self.spinner is not None
        self.spinner.open()

    def spinner_hide(self) -> None:
        assert self.spinner is not None
        self.spinner.close()

def main() -> None:
    mgmt: Management = Management()
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
