# Copyright 2024-2026.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import os, re

from fastapi import Request
from fastapi.responses import RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware

from nicegui import app, ui

import scrypt

from config import Config
from aconfig import config

max_user_storage_path = 'management.authentication.max_user_storage'
config.default(max_user_storage_path, 10)

auth_db = Config('var/gui/auth_db.yaml')
credential_path = 'credentials'
auth_db.default(credential_path, {})
auth_db.load()

def hash_password(password, maxtime=1.0, salt_bytes=16):
    return scrypt.encrypt(os.urandom(salt_bytes), password, maxtime=maxtime)

def verify_password(hash, password, maxtime=1.0):
    try:
        scrypt.decrypt(hash, password, maxtime, encoding=None)
        return True
    except scrypt.error:
        return False

def have_any_credentials():
    return not not auth_db[credential_path]

def create(username, password):
    username = username.lower()
    credentials = auth_db[credential_path]
    hash = credentials.get(username)
    if hash:
        return False
    hash = hash_password(password)
    credentials[username] = hash
    auth_db[credential_path] = credentials
    auth_db.save()
    log.info(f'Created user {username}')
    return True

def change(username, old_password, new_password):
    username = username.lower()
    credentials = auth_db[credential_path]
    hash = credentials.get(username)
    if not hash:
        return False
    if not verify_password(hash, old_password):
        return False
    hash = hash_password(new_password)
    credentials[username] = hash
    auth_db[credential_path] = credentials
    auth_db.save()
    log.info(f'Changed password for user {username}')
    return True

def verify(username, password):
    username = username.lower()
    credentials = auth_db[credential_path]
    hash = credentials.get(username)
    if not hash:
        return False
    if not verify_password(hash, password):
        return False
    log.info(f'Verified password for {username}')
    return True

def cleanup_user_storage():
    # Allow only the max configured youngest storages
    m = re.compile(r'storage-user.*\.json')
    entries = []
    for entry in os.scandir('var/gui/nicegui'):
        if m.match(entry.name):
            entries.append(entry)
    entries.sort(reverse=True, key=lambda entry: entry.stat().st_ctime)
    max_user_storages = config[max_user_storage_path]
    for entry in entries[max_user_storages:]:
        log.info(f'Deleting old user storage {entry.name}')
        os.unlink(entry.path)

def get_storage_secret():
    secret = auth_db['storage_secret']
    if not secret:
        auth_db['storage_secret'] = os.urandom(16)
        auth_db.save()
        secret = auth_db['storage_secret']
    return secret

unrestricted_page_paths = { '/login', '/enroll' }

class AuthMiddleware(BaseHTTPMiddleware):
    """This middleware restricts access to all pages.
        It redirects the user to the login page if they are not authenticated.
    """
    async def dispatch(self, request: Request, call_next):
        if not app.storage.user.get('authenticated', False):
            if not request.url.path.startswith('/_nicegui') and request.url.path not in unrestricted_page_paths:
                log.info(f'dispatch {request.url} deny')
                if have_any_credentials():
                    return RedirectResponse('/login')
                else:
                    return RedirectResponse('/enroll')
        return await call_next(request)

@ui.page('/login')
async def login():
    def try_login():
        if not verify(username.value, password.value):
            ui.notify('Wrong username or password', color='negative')
            return

        app.storage.user.update({'username': username.value, 'authenticated': True})
        ui.navigate.to('/')
        log.info(f'Login {username.value}')

    ui.dark_mode(value = None)
    if app.storage.user.get('authenticated', False):
        return RedirectResponse('/')

    if not have_any_credentials():
        return RedirectResponse('/enroll')

    cleanup_user_storage()

    with ui.card().classes('absolute-center'):
        username = ui.input('Username').on('keydown.enter', try_login)
        password = ui.input('Password', password=True, password_toggle_button=True).on('keydown.enter', try_login)
        ui.button('Log in', on_click=try_login)
    return None

# Set initial password, or change password
@ui.page('/enroll')
async def enroll():
    def try_enroll():
        if password.value != confirm_password.value:
            ui.notify('Password mismatch', color='negative')
            return
        if have_creds:
            if not change(username.value, old_password.value, password.value):
                ui.notify('Wrong username or password', color='negative')
                return
        else:
            if not create(username.value, password.value):
                ui.notify('Wrong username or password', color='negative')
                return
        ui.navigate.to('/')

    ui.dark_mode(value = None)
    have_creds = have_any_credentials()
    with ui.card().classes('absolute-center'):
        if have_creds:
            title = 'Change Password'
            btn_text = 'Change'
        else:
            title = 'Create a User To Get Started'
            btn_text = 'Create'
        ui.label(title).classes('text-h6')
        username = ui.input('Username').on('keydown.enter', try_enroll)
        if have_creds:
            old_password = ui.input('Old Password', password=True, password_toggle_button=True).on('keydown.enter', try_enroll)
        password = ui.input('Password', password=True, password_toggle_button=True).on('keydown.enter', try_enroll)
        confirm_password = ui.input('Confirm Password', password=True, password_toggle_button=True).on('keydown.enter', try_enroll)
        ui.button(btn_text, on_click=try_enroll)

# Logout current user
@ui.page('/logout')
async def logout():
    username = app.storage.user.get('username')
    if username:
        log.info(f'Logout {username}')
    ui.dark_mode(value = None)
    app.storage.user.update({'authenticated' : False})
    ui.navigate.to('/')
