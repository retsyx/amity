# Copyright 2024-2026.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio, os, signal
from nicegui import ui, Client
from nicegui.events import ClickEventArguments

from aconfig import config
from impl_protocols import ManagementInterface

class Remotes:
    def __init__(self, top: ManagementInterface) -> None:
        self.name: str = 'Remotes'
        self.top: ManagementInterface = top
        self.proc: asyncio.subprocess.Process | None = None
        self.remote_status: str
        self.keyboard_status: str
        self.update()

    def ui(self) -> None:
        with ui.column().classes('w-full items-center'):
            ui.label('Pair an Apple Siri Remote, or a Bluetooth Low Energy (BLE) remote, or keyboard.')
            lbl = ui.label('').bind_text_from(self, 'remote_status')
            lbl.bind_visibility_from(self, 'remote_status', backward=lambda s: not not s)
            lbl = ui.label('').bind_text_from(self, 'keyboard_status')
            lbl.bind_visibility_from(self, 'keyboard_status', backward=lambda s: not not s)
            b = lambda proc: 'Stop' if proc else 'Pair'
            ui.button('Pair',
                        on_click=self.toggle_pair).bind_text_from(self, 'proc',
                                    backward=b)

    def update(self) -> None:
        if config['remote.mac']:
            name = config['remote.name']
            if not name:
                name = 'Siri Remote'
            self.remote_status = f'{name} is paired.'
        else:
            self.remote_status = ''
        if config['keyboard.mac']:
            name = config['keyboard.name']
            if not name:
                name = 'A keyboard'
            self.keyboard_status = f'{name} is paired.'
        else:
            self.keyboard_status = ''

    def will_show(self) -> None:
        pass

    async def toggle_pair(self, event: ClickEventArguments) -> None:
        if self.proc is None:
            log.info('Started')
            self.top.control().stop()
            self.proc = await asyncio.create_subprocess_shell('./pair_remote',
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.DEVNULL,
                        # start_new_session so that the process group kill below doesn't kill us, too
                        start_new_session=True)
            self.top.taskit(self.read_stdout(event.client))
        else:
            try:
                log.info('Stopped')
                ui.notify('Stopped')
                # Stop the read loop in read_stdout()
                assert self.proc.stdout is not None
                self.proc.stdout.feed_eof()
                # Kill the entire process group
                os.killpg(os.getpgid(self.proc.pid), signal.SIGINT)
            except Exception as e:
                print(e)

    async def read_stdout(self, client: Client) -> None:
        log.info('Reading pair_remote stdout')
        assert self.proc is not None
        assert self.proc.stdout is not None
        with client:
            while True:
                try:
                    line_bytes: bytes = await self.proc.stdout.readline()
                    if not line_bytes: break # EOF
                    line: str = line_bytes.decode().strip()
                    if not line: continue # Empty line
                    log.info(f'Message "{line}"')
                    if 'Paired with' in line:
                        ui.notify(line, type='positive')
                        break
                    ui.notify(line)
                except Exception as e:
                    print(str(e))
        await self.proc.wait()
        self.proc = None
        log.info('Reading pair_remote stdout done')
        self.top.control().start()
