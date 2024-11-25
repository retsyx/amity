# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio, yaml

from nicegui import ui

from aconfig import config

class Device(object):
    def __init__(self, d):
        self.osd_name = d['osd_name']
        self.role = d['role']
    def __str__(self):
        return self.osd_name

class Activity(object):
    @classmethod
    def New(self):
        return Activity(
            {'name' : None,
             'display' : None,
             'audio' : None,
             'source' : None,
             'switch' : { 'device' : None, 'input' : None },
            })

    def __init__(self, d):
        self.name = d['name']
        self.display = d['display']
        self.audio = d['audio']
        self.source = d['source']
        self.switch = d.get('switch', {}).get('device')
        self.input = d.get('switch', {}).get('input')

    def __getitem__(self, key):
        return self.__dict__[key]

    def to_dict(self):
        d = { 'name' : self.name,
            'display' : self.display,
            'audio' : self.audio,
            'source' : self.source
        }
        if self.switch and self.input is not None:
            d['switch'] = { 'device' : self.switch,
                           'input' : self.input }
        return d

    def __str__(self):
        return self.name

    def __repr__(self):
        return str(self.to_dict())

class EditActivity(object):
    def __init__(self, devices: list[Device], activity: Activity):
        self.name = 'Edit Activity'
        self.devices = devices
        self.activity : Activity = activity

        def make_list(role):
            l = [device.osd_name for device in devices if device.role == role]
            c = activity[role]
            if c not in l:
                l.insert(0, c)
            if None not in l:
                l.insert(0, None)
            return l

        self.display_devices = make_list('display')
        self.source_devices = make_list('source')
        self.audio_devices = make_list('audio')
        self.switch_devices = self.audio_devices[:]
        i = activity.input
        if i is None:
            i = 0
        self.switch_inputs = list(range(max(11, i + 1)))

    def ui(self):
        with ui.column().classes('w-full items-center'):
            ui.label('Edit Activity').style('text-align: center').style("font-weight: bold; font-size: 1.25em;")
            with ui.row().classes('w-full items-center'):
                ui.label('Name').style('width: 100px; text-align: left;')
                ui.input('').bind_value(self.activity, 'name')
            with ui.row().classes('w-full items-center'):
                ui.label('Display').style('width: 100px; text-align: left;')
                ui.select(self.display_devices, new_value_mode='add').bind_value(self.activity, 'display')
            with ui.row().classes('w-full items-center'):
                ui.label('Source').style('width: 100px; text-align: left;')
                ui.select(self.source_devices, new_value_mode='add').bind_value(self.activity, 'source')
            with ui.row().classes('w-full items-center'):
                ui.label('Audio').style('width: 100px; text-align: left;')
                ui.select(self.audio_devices, new_value_mode='add').bind_value(self.activity, 'audio')
            with ui.row().classes('w-full items-center'):
                ui.label('Switch Device').style('width: 100px; text-align: left;')
                ui.select(self.switch_devices, new_value_mode='add').bind_value(self.activity, 'switch')
            with ui.row().classes('w-full items-center').bind_visibility_from(self.activity, 'switch', backward=lambda x: not not x):
                ui.label('Input').style('width: 100px; text-align: left;')
                def f(event):
                    try:
                        i = int(event.value)
                    except:
                        i = 0
                    self.activity.input = i
                def v(value):
                    try:
                        i = int(value)
                        if i < 0:
                            return 'Must be a positive number'
                        if i > 255:
                            return 'Must be 255 or less'
                        return None
                    except:
                        return 'Must be a number'
                ui.select(self.switch_inputs, new_value_mode='add',
                        value=self.activity.input, on_change=f, validation=v)

class Activities(object):
    def __init__(self, top):
        self.name = 'Activities'
        self.top = top
        self.hdmi_scan_info = {}
        self.devices = []
        # None has a special meaning for activities (unlike an empty list). When it is None,
        # it means the user hasn't set or changed anything (at initial display), and therefore
        # the activities are to be taken from the config. On the other hand, an empty activities
        # list (e.g. []) can only occur if the user deleted all activities.
        self.activities = None
        self.recommended_activities = []
        self.discovered_devices = []
        self.discovered_device_table = None
        self.activity_table = None
        self.recommended_activity_table = None
        self.is_edited = False
        self.update()

    def ui(self):
        self.edit_activity_dialog = ui.dialog()
        with ui.column().classes('items-stretch'):
            with ui.row().style('align-items: center;'):
                self.scan_btn = ui.button('Scan HDMI', on_click=self.on_scan_hdmi)
                ui.space()
                ui.button('Discard Changes', color='negative', on_click=self.discard_changes).bind_visibility_from(self, 'is_edited')
                ui.button('Save', color='positive', on_click=self.save_activities).bind_visibility_from(self, 'is_edited')
            with ui.card().classes('items-stretch'):
                with ui.row().classes('w-full'):
                    ui.label(self.name).classes('text-2xl font-bold')
                    ui.space()
                    ui.button('', icon='add', on_click=self.add_new_activity)
                self.activity_table = ui.column().classes('items-center')
            with ui.card().classes('items-stretch') as card:
                card.bind_visibility_from(self, 'discovered_devices', backward=lambda d: not not d)
                lbl = ui.label('Recommended Activities').classes('text-2xl font-bold')
                lbl.bind_visibility_from(self, 'recommended_activities',
                                         backward=lambda x: not not x)
                self.recommended_activity_table = ui.column().classes('items-center')
                lbl = ui.label('Discovered Devices').classes('text-2xl font-bold')
                lbl.bind_visibility_from(self, 'discovered_devices',
                                         backward=lambda x: not not x)
                self.discovered_device_table = ui.column()

    def update_activity_table(self):
        if self.activity_table is None: return
        self.activity_table.clear()
        log.info(f'Showing activities {self.activities}')
        with self.activity_table:
            if not self.activities:
                log.info('No activities, showing tip')
                ui.label('No activities.').classes('w-80').style('text-align: center').style("font-weight: bold; font-size: 1.25em;")
                if not self.recommended_activities:
                    tip = 'Scan HDMI to find HDMI devices and recommend activities, or add an activity manually.'
                else:
                    tip = 'Add activities from the recommendations below, or add an activity manually.'
                ui.label(tip).classes('w-80').style('text-align: center')
            else:
                for activity in self.activities:
                    self.ui_activity_row(activity)

    def update_recommended_activity_table(self):
        if self.recommended_activity_table is None: return
        self.recommended_activity_table.clear()
        log.info(f'Showing recommended activities {self.recommended_activities}')
        with self.recommended_activity_table:
            for activity in self.recommended_activities:
                self.ui_recommended_activity_row(activity)

    def update(self):
        def is_equivalent(act1, act2):
            # Ignore the name of the activity because it is not important, and the switch
            # configuration because switch configuration is manual.
            for role in ('display', 'source', 'audio'):
                if act1[role] != act2[role]:
                    return False
            return True
        if self.activities is None:
            activities = config['activities']
            if activities is not None:
                self.activities = [Activity(d) for d in activities]
        recommended_activities = self.hdmi_scan_info.get('activities', [])
        recommended_activities = [Activity(d) for d in recommended_activities]
        if recommended_activities:
            # If no activities are already configured, then default to using the recommended
            # activities
            if self.activities is None:
                self.activities = recommended_activities
            # Only recommend new activities that aren't already configured
            new_activities = []
            for recommended_activity in recommended_activities:
                new = True
                for activity in self.activities:
                    if is_equivalent(activity, recommended_activity):
                        new = False
                        break
                if new:
                    new_activities.append(recommended_activity)
            self.recommended_activities = new_activities

        # Changes need to be saved, if activities are changed, or if scanned adapter configuration
        # is different.
        self.is_edited = False
        if self.activities is not None:
            das = [activity.to_dict() for activity in self.activities]
        else:
            das = None
        log.info(f'Activities displayed {das}')
        log.info(f'Activities configured {config["activities"]}')
        if das != config['activities'] and (das or config['activities']):
            self.is_edited = True
        log.info(f'is_edited interim {self.is_edited}')
        if not self.is_edited:
            scanned_adapters = self.hdmi_scan_info.get('adapters')
            if scanned_adapters and scanned_adapters != config['adapters']:
                self.is_edited = True
        log.info(f'is_edited final {self.is_edited}')

        # Collate all devices. Configured, and discovered.

        discovered_devices = [Device(d) for d in self.hdmi_scan_info.get('devices', [])]
        self.discovered_devices = sorted(discovered_devices, key=lambda x: x.osd_name)

        devices = {}
        for device in discovered_devices:
            devices[device.osd_name] = device
        if self.activities is not None:
            for activity in self.activities:
                def add_device_with_role(role):
                    osd_name = activity[role]
                    if osd_name and osd_name not in devices:
                        devices[osd_name] = Device({
                            'osd_name' : osd_name,
                            'role' : role
                        })
                add_device_with_role('display')
                add_device_with_role('source')
                add_device_with_role('audio')
                add_device_with_role('switch')

        devices = list(devices.values())
        devices.sort(key=lambda x: x.osd_name)
        self.devices = devices

        if self.discovered_device_table is not None:
            with self.discovered_device_table as table:
                table.clear()
                for device in self.discovered_devices:
                    icon = { 'display' : 'tv',
                             'source' : 'stream',
                             'audio' : 'volume_up',
                            }.get(device.role, 'device_unknown')
                    with ui.row().style('align-items: center;'):
                        ui.icon(icon, color='primary', size='36px')
                        ui.label(device.osd_name)

        self.update_activity_table()
        self.update_recommended_activity_table()

    def will_show(self):
        pass

    def edit_activity(self, activity):
        ed = EditActivity(self.devices, activity)
        with self.edit_activity_dialog as dialog:
            def on_ok():
                dialog.close()
                self.update()

            dialog.clear()
            with ui.card():
                with ui.column().classes('w-full justify-center'):
                    ed.ui()
                    with ui.row().classes('w-full justify-center'):
                        ui.button('OK', on_click=on_ok)
            dialog.open()

    def discard_changes(self):
        log.info('Discard changes')
        self.activities = None
        self.update()

    def save_activities(self):
        self.top.spinner.open()
        activities = [activity.to_dict() for activity in self.activities]
        log.info(f'Saving activities {activities}')
        config['activities'] = activities
        adapters = self.hdmi_scan_info.get('adapters')
        if adapters:
            log.info(f'Saving adapters {adapters}')
            config['adapters'] = adapters
        self.top.control.safe_do(lambda: config.save(True))
        self.top.spinner.close()

    def add_new_activity(self):
        activity = Activity.New()
        self.activities.append(activity)
        self.update()
        self.edit_activity(activity)

    def ui_activity_row(self, activity):
        def remove_activity():
            log.info(f'Removing activity {activity}')
            self.activities.remove(activity)
            log.info(f'Activities {self.activities}')
            self.update()
        def move_activity(up_or_down):
            log.info(f'Moving activity {activity} {up_or_down}')
            index1 = self.activities.index(activity)
            index2 = index1 + up_or_down
            if index1 < 0 or index1 >= len(self.activities) or index2 < 0 or index2 >= len(self.activities):
                return
            a = self.activities
            a[index1], a[index2] = a[index2], a[index1]
            self.update()
        def is_first_activity():
            return activity == self.activities[0]
        def is_last_activity():
            return activity == self.activities[-1]

        icons = [
            'radio_button_unchecked',
            'keyboard_double_arrow_up',
            'keyboard_double_arrow_right',
            'keyboard_double_arrow_down',
            'keyboard_double_arrow_left',
            'error'
        ]
        index = self.activities.index(activity)
        if index >= len(icons) - 1:
            icon = icons[-1]
            color = 'negative'
        else:
            icon = icons[index]
            color = 'primary'
        with ui.row().classes('w-full').style('align-items: center;'):
            ui.icon(icon, color=color, size='36px')
            ui.label('').bind_text(activity, 'name').style('width: 200px; text-align: left;')
            ui.button('', icon='edit_note', on_click=lambda: self.edit_activity(activity))
            ui.button('', icon='delete', on_click=lambda: remove_activity())
            if not is_last_activity():
                ui.button('', icon='arrow_downward', on_click=lambda: move_activity(1))
            else:
                ui.space().style('width: 56px')
            if not is_first_activity():
                ui.button('', icon='arrow_upward', on_click=lambda: move_activity(-1))
            else:
                ui.space()

    def ui_recommended_activity_row(self, activity):
        def add_recommended_activity(activity):
            self.activities.append(activity)
            self.update()
        with ui.row().classes('w-full'):
            ui.label('').bind_text(activity, 'name').style('width: 200px; text-align: left;')
            ui.space()
            ui.button('', icon='edit_note', on_click=lambda: self.edit_activity(activity))
            ui.button('', icon='add', on_click=lambda: add_recommended_activity(activity))

    async def scan_hdmi(self):
        log.info('Scanning HDMI')
        proc = await asyncio.create_subprocess_shell('./configure_hdmi -y -n recommend',
                                                         stdout=asyncio.subprocess.PIPE)
        output = await proc.stdout.read()
        self.hdmi_scan_info = yaml.safe_load(output)
        log.info(f'Scanned info {self.hdmi_scan_info}')
        if self.hdmi_scan_info is None:
            self.hdmi_scan_info = {}
        await proc.wait()
        self.update()

    async def on_scan_hdmi(self, event):
        with event.client:
            self.scan_btn.enabled = False
            self.top.spinner.open()
            await self.scan_hdmi()
            status = self.hdmi_scan_info.get('status', 'OK')
            if status != 'OK':
                ui.notify(status, color='negative')
            elif not self.hdmi_scan_info.get('adapters'):
                ui.notify('No HDMI devices found. Check HDMI connections!', color='negative')
            self.top.spinner.close()
            self.scan_btn.enabled = True
