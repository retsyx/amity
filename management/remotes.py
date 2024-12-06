# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio, os, signal
from nicegui import ui, Client

from aconfig import config

class Remotes(object):
    def __init__(self, top):
        self.name = 'Remotes'
        self.top = top
        self.proc = None
        self.update()

    def ui(self):
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

    def update(self):
        if config['remote.mac']:
            self.remote_status = 'A Siri Remote is paired.'
        else:
            self.remote_status = ''
        if config['keyboard.mac']:
            self.keyboard_status = 'A keyboard is paired.'
        else:
            self.keyboard_status = ''

    def will_show(self):
        pass

    async def toggle_pair(self, event):
        if self.proc is None:
            log.info('Started')
            self.top.control.stop()
            self.proc = await asyncio.create_subprocess_shell('./pair_remote',
                        stdout=asyncio.subprocess.PIPE,
                        preexec_fn=os.setsid)
            self.top.taskit(self.read_stdout(event.client))
        else:
            try:
                log.info('Stopped')
                ui.notify('Stopped')
                # Stop the read loop in read_stdout()
                self.proc.stdout.feed_eof()
                # Kill the entire process group
                os.killpg(os.getpgid(self.proc.pid), signal.SIGINT)
            except Exception as e:
                print(e)

    async def read_stdout(self, client: Client):
        log.info('Reading pair_remote stdout')
        with client:
            while True:
                try:
                    line = await self.proc.stdout.readline()
                    if not line: break # EOF
                    line = line.decode().strip()
                    if not line: continue # Empty line
                    log.info(f'Message "{line}"')
                    ui.notify(line)
                    if 'Paired with' in line:
                        break
                except Exception as e:
                    print(str(e))
        await self.proc.wait()
        self.proc = None
        log.info('Reading pair_remote stdout done')
        self.top.control.start()
