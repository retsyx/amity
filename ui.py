# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio
import html
import logging

# Stop pygame/SDL ALSA spam messages
import os
os.environ['SDL_AUDIODRIVER'] = 'dsp'

import pygame
import pygame_gui
from pygame_gui import UIManager
from pygame_gui.elements import UIButton, UIDropDownMenu, UITextBox

from hdmi import Key

class MouseFaker(object):
    """ Process touch events into fake mouse events """
    def __init__(self, resolution):
        self.finger_id = None
        self.resolution = resolution

    def scale(self, pos):
        return (int(pos[0] * self.resolution[0]),
                int(pos[1] * self.resolution[1]))

    def process_event(self, event):
        new_event = None
        if event.type == pygame.FINGERDOWN:
            if self.finger_id is None:
                self.finger_id = event.finger_id
                new_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                               { 'pos': self.scale((event.x, event.y)),
                                                'button': 1,
                                                'touch': True,
                                                'window': None})
        elif event.type == pygame.FINGERUP:
            if self.finger_id == event.finger_id:
                self.finger_id = None
                new_event = pygame.event.Event(pygame.MOUSEBUTTONUP,
                                               { 'pos': self.scale((event.x, event.y)),
                                                'button': 1,
                                                'touch': True,
                                                'window': None})
        elif event.type == pygame.FINGERMOTION:
            if self.finger_id == event.finger_id:
                new_event = pygame.event.Event(pygame.MOUSEMOTION,
                                               { 'pos': self.scale((event.x, event.y)),
                                                 'rel': self.scale((event.dx, event.dy)),
                                                 'buttons': (1),
                                                 'touch': True,
                                                 'window': None})
        if new_event is not None:
            pygame.event.post(new_event)
            return True
        return False

class Console(logging.Handler):
    def __init__(self, max_lines = 32):
        super().__init__()
        self.text_box = None
        self.max_lines = max_lines
        self.lines = []
        formatter = logging.Formatter('%(asctime)s %(levelname)s: %(name)s %(message)s')
        self.setFormatter(formatter)
        for log in tools.all_loggers:
            log.addHandler(self)

    def emit(self, record):
        msg = self.format(record)
        self.append_text(msg)

    def set_text_box(self, text_box):
        self.text_box = text_box

    @property
    def visible(self):
        if self.text_box is None:
            return False
        return self.text_box.visible

    def show(self):
        self.text_box.show()
        self._update_text_box()

    def hide(self):
        self.text_box.hide()
        self.text_box.set_text('')

    def append_text(self, text):
        self.lines.extend(html.escape(text).split('\n'))
        if len(self.lines) > self.max_lines:
            self.lines = self.lines[-self.max_lines:]
        # The textbox implementation seems a bit inefficient, so only
        # update it when it is visible
        if self.visible:
            self._update_text_box()

    def _update_text_box(self):
        ht = '<br>'.join(self.lines)
        self.text_box.set_text(ht)
        # Scroll to the end...
        pos = self.text_box.get_text_letter_count() - 1
        self.text_box.edit_position = pos
        self.text_box.cursor_has_moved_recently = True

class Main(object):
    def __init__(self):
        pygame.init()
        pygame.mouse.set_visible(False)

        self.console = Console()

        self.resolution = (800, 480)
        self.picker_option_height = 65
        self.default_button_dim = (130, 80)
        self.margin = 30

        self.theme = {
            'button': {
                'font': {
                    'size': '40'
                }
            },
            'drop_down_menu.#drop_down_options_list': {
                'misc': {
                    'list_item_height': str(self.picker_option_height),
                },
            },
        }

        self.background_surface = pygame.Surface(self.resolution)
        self.window_surface = pygame.display.set_mode(self.resolution,
                                pygame.FULLSCREEN)
        self.clock = pygame.time.Clock()
        self.ui_manager = UIManager(self.resolution, self.theme)
        self.background_surface.fill(self.ui_manager.get_theme().get_colour('dark_bg'))
        self.mouse_faker = MouseFaker(self.resolution)
        self.activity_names = ('Off')
        self.picker_activity = None
        self.btn_vol_up = None
        self.btn_vol_down = None
        self.btn_mute = None
        self.btn_up = None
        self.btn_right = None
        self.btn_down = None
        self.btn_left = None
        self.btn_select = None
        self.btn_back = None
        self.btn_home = None
        self.btn_play_pause = None
        self.btn_debug1 = None
        self.btn_debug2 = None
        self.in_debug_mode = False
        self.pipe = None
        self.button_map = None

    def set_pipe(self, pipe):
        self.pipe = pipe
        pipe.start_client_task(self)

    def create_ui(self):
        self.picker_activity = UIDropDownMenu(self.activity_names,
                                              self.activity_names[0],
                                              pygame.Rect((10, 10),
                                                          (620, self.picker_option_height)),
                                              self.ui_manager)
        y = 120
        self.btn_vol_up = UIButton(pygame.Rect((10, y),
                                               self.default_button_dim),
                                    'Vol +',
                                    self.ui_manager,
                                    object_id='vol_up')
        y += self.default_button_dim[1] + self.margin

        self.btn_vol_down = UIButton(pygame.Rect((10, y),
                                                  self.default_button_dim),
                                    'Vol -',
                                    self.ui_manager,
                                    object_id='vol_down')

        y += self.default_button_dim[1] + self.margin
        self.btn_mute = UIButton(pygame.Rect((10, y),
                                             self.default_button_dim),
                                'Mute',
                                self.ui_manager,
                                object_id='mute')

        x = (self.resolution[0] - self.default_button_dim[0]) // 2
        y = 120
        self.btn_up = UIButton(pygame.Rect((x, y),
                                            self.default_button_dim),
                                '^',
                                self.ui_manager,
                                object_id='up')
        tx = x + self.default_button_dim[0] + self.margin
        self.btn_back = UIButton(pygame.Rect((tx, y),
                                            self.default_button_dim),
                                'Back',
                                self.ui_manager,
                                object_id='back')

        y += self.default_button_dim[1] + self.margin
        self.btn_select = UIButton(pygame.Rect((x, y),
                                             self.default_button_dim),
                                '*',
                                self.ui_manager,
                                object_id='select')
        tx = x - self.default_button_dim[0] - self.margin
        self.btn_left = UIButton(pygame.Rect((tx, y),
                                    self.default_button_dim),
                                '<',
                                self.ui_manager,
                                object_id='left')

        tx = x + self.default_button_dim[0] + self.margin
        self.btn_right = UIButton(pygame.Rect((tx, y),
                                            self.default_button_dim),
                                '>',
                                self.ui_manager,
                                object_id='right')

        tx += self.default_button_dim[0] + self.margin
        self.btn_play_pause = UIButton(pygame.Rect((tx, y),
                                        self.default_button_dim),
                                '>||',
                                self.ui_manager,
                                object_id='play_pause')

        y += self.default_button_dim[1] + self.margin
        self.btn_down = UIButton(pygame.Rect((x, y),
                                            self.default_button_dim),
                                'v',
                                self.ui_manager,
                                object_id='down')

        tx = x + self.default_button_dim[0] + self.margin
        self.btn_home = UIButton(pygame.Rect((tx, y),
                                            self.default_button_dim),
                                'Home',
                                self.ui_manager,
                                object_id='home')

        # pygame_gui sensibly draws UI elements back to front. Insensibly, it evaluates mouse
        # events in the same order, when it should evaluate them front to back.
        # In our particular application the debug button is always topmost, and visible so it should
        # always process mouse events first. However, because of the buggy behavior, it fails to get
        # events when the console is displayed underneath it.
        # We workaround the problem by creating two 'debug' buttons. One under the console, and one
        # above. The bottom button gets all events, while the top button looks pretty (albeit with
        # no highlight on press).
        x = self.resolution[0] - self.default_button_dim[0] - 10
        y = 10
        self.btn_debug1 = UIButton(pygame.Rect((x, y),
                                            self.default_button_dim),
                                'Debug',
                                self.ui_manager,
                                object_id='debug')

        text_box = UITextBox('',
                            pygame.Rect((10, 10),
                                        (self.resolution[0] - 20, self.resolution[1] - 20)),
                            self.ui_manager,
                            object_id='console')

        self.console.set_text_box(text_box)
        x = self.resolution[0] - self.default_button_dim[0] - 10
        y = 10
        self.btn_debug2 = UIButton(pygame.Rect((x, y),
                                            self.default_button_dim),
                                'Debug',
                                self.ui_manager,
                                object_id='debug')

        self.activity_buttons = (self.btn_vol_up,
                                 self.btn_vol_down,
                                 self.btn_mute,
                                 self.btn_up,
                                 self.btn_right,
                                 self.btn_down,
                                 self.btn_left,
                                 self.btn_select,
                                 self.btn_back,
                                 self.btn_home,
                                 self.btn_play_pause)
        self.update_visibility()
        self.button_map = {
            'up': Key.UP,
            'right': Key.RIGHT,
            'down': Key.DOWN,
            'left': Key.LEFT,
            'select': Key.SELECT,
            'back': Key.BACK,
            'home': Key.ROOT_MENU,
            'vol_up': Key.VOLUME_UP,
            'vol_down': Key.VOLUME_DOWN,
            'mute': Key.TOGGLE_MUTE,
            'play_pause': Key.PAUSE_PLAY,
        }

    def set_activity_names(self, activity_names):
        self.activity_names = list(zip(activity_names,
            [str(x-1) for x in range(len(activity_names))]))

    async def run(self):
        self.create_ui()
        while True:
            await asyncio.sleep(1. / 30.)
            time_delta = self.clock.tick() / 1000.0
            self.process_events()
            self.ui_manager.update(time_delta)
            self.window_surface.blit(self.background_surface, (0, 0))
            self.update_visibility()
            self.ui_manager.draw_ui(self.window_surface)
            pygame.display.update()

    def process_events(self):
        for event in pygame.event.get():
            if self.mouse_faker.process_event(event):
                continue
            if self.ui_manager.process_events(event):
                continue
            if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
                index = int(event.selected_option_id)
                log.info(f'Selected activity {index} {self.activity_names[index+1][0]}')
                self.pipe.set_activity(index)
            elif event.type == pygame_gui.UI_BUTTON_START_PRESS:
                log.info(f'Button press {event.ui_object_id}')
                if event.ui_object_id in self.button_map:
                    self.pipe.key_press(self.button_map[event.ui_object_id])
            elif event.type == pygame_gui.UI_BUTTON_PRESSED:
                log.info(f'Button release {event.ui_object_id}')
                if event.ui_object_id == 'debug':
                    self.in_debug_mode = not self.in_debug_mode
                elif event.ui_object_id in self.button_map:
                    self.pipe.key_release(self.button_map[event.ui_object_id])

    def update_visibility(self):
        if self.in_debug_mode:
            if not self.console.visible:
                self.picker_activity.hide()
                self.console.show()
            visible = False
        else:
            if self.console.visible:
                self.picker_activity.show()
                self.console.hide()
            visible = self.picker_activity.selected_option[1] != '-1'
        for btn in self.activity_buttons:
            # Calling hide() on an already hidden button generates spurious unhover events,
            # so only set show()/hide() if necessary.
            if visible:
                if not btn.visible:
                    btn.show()
            else:
                if btn.visible:
                    btn.hide()

    async def server_notify_set_activity(self, index):
        selected_option = self.activity_names[index + 1]
        self.picker_activity.selected_option = selected_option
        for part in self.picker_activity.menu_states.values():
            part.selected_option = selected_option
            if part.selected_option_button is not None:
                part.selected_option_button.set_text(selected_option[0])
        self.picker_activity._close_dropdown_if_open()

def main():
    ui = Main()
    ui.set_activity_names(('Off', 'Watch TV', 'Play PS5', 'Play Nintendo Switch',
                        'Play Music', 'Something Else'))
    asyncio.run(ui.run())

if __name__ == '__main__':
    main()
