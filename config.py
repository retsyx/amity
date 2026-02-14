# Copyright 2024-2025.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools
log = tools.logger(__name__)

import os, re, shutil, tempfile, time, yaml
from collections.abc import Callable, Generator
from typing import Any

class Config:
    def __init__(self, filename: str) -> None:
        self.default_paths: dict[str, Any] = {}
        self.user_cfg: dict[str, Any] = {}
        self.cfg: dict[str, Any] = {}
        self.loaded = False
        self.filename = filename
        self.loader_class: type[yaml.SafeLoader] = type('Loader', (yaml.SafeLoader,), {})
        self.dumper_class: type[yaml.SafeDumper] = type('Dumper', (yaml.SafeDumper,), {})
        self.default('config.max_backups', 10)
        log.info(f'filename {self.filename}')

    def register_yaml_handler(self, tag: str, data_type: type,
                              representer: Callable[..., Any],
                              constructor: Callable[..., Any]) -> None:
        self.dumper_class.add_representer(data_type, representer)
        self.loader_class.add_constructor(tag, constructor)

    def load(self) -> None:
        """Must be called after all default() calls have been made"""
        log.info(f'Load {self.filename}')
        try:
            with open(self.filename, 'r') as file:
                self.user_cfg = yaml.load(file, Loader=self.loader_class)
            if self.user_cfg is None:
                log.info(f'{self.filename} is empty. Defaulting to empty config.')
                self.user_cfg = {}
        except FileNotFoundError:
            log.info(f'{self.filename} not found. Defaulting to empty config.')
        self.__overlay(self.cfg, self.user_cfg)
        self.loaded = True

    def save(self, backup: bool = False) -> None:
        log.info(f'Save {self.filename}')
        if backup:
            # Make a backup of the config file
            backup_time_str = time.strftime('%Y%m%d-%H%M%S')
            backup_filename = f'{self.filename}-{backup_time_str}'
            try:
                shutil.copy(self.filename, backup_filename)
                log.info(f'Created backup {backup_filename}')
                # If running as root, make backup ownership the same as the original
                if os.getuid() == 0:
                    stat = os.stat(self.filename)
                    shutil.chown(backup_filename, stat.st_uid, stat.st_gid)
            except FileNotFoundError:
                pass
            self.clean_backups()

        tmp_fd, tmp_path = tempfile.mkstemp()
        with os.fdopen(tmp_fd, 'w') as file:
            yaml.dump(self.user_cfg, file, Dumper=self.dumper_class)
        shutil.move(tmp_path, self.filename)
        # Fixup ownership, if running as root
        if os.getuid() == 0:
            stat = os.stat('.')
            shutil.chown(self.filename, stat.st_uid, stat.st_gid)

    def clean_backups(self) -> None:
        path = os.path.dirname(self.filename)
        if path == '':
            path = '.'
        basename = os.path.basename(self.filename)
        entries: list[os.DirEntry[str]] = []
        m = re.compile(basename + r'-(\d{8}-\d{6})')
        for entry in os.scandir(path):
            if m.match(entry.name):
                entries.append(entry)
        entries.sort(reverse=True, key=lambda entry: entry.stat().st_ctime)
        max_backups = self['config.max_backups']
        for entry in entries[max_backups:]:
            log.info(f'Deleting backup {entry.name}')
            os.unlink(os.path.join(path, entry.name))

    def save_complete(self, filename: str) -> None:
        with open(filename, 'w') as file:
            yaml.dump(self.cfg, file, Dumper=self.dumper_class)

    def __overlay(self, node: Any, overlay_node: Any) -> bool:
        if type(node) is dict:
            if type(overlay_node) is not dict:
                raise TypeError(f'Config: expected dict but got {type(overlay_node).__name__} in user config')
            for name, value in overlay_node.items():
                if name not in node:
                    node[name] = value
                else:
                    scalar = self.__overlay(node[name], overlay_node[name])
                    if scalar:
                        node[name] = overlay_node[name]
        elif type(node) is list:
            if type(overlay_node) is not list:
                raise TypeError(f'Config: expected list but got {type(overlay_node).__name__} in user config')
            for i, value in enumerate(overlay_node):
                if i >= len(node):
                    node.append(value)
                else:
                    scalar = self.__overlay(node[i], overlay_node[i])
                    if scalar:
                        node[i] = overlay_node[i]
        else:
            return True
        return False

    def default(self, path: str, value: Any) -> None:
        if self.loaded:
            raise RuntimeError('Config: default() called after load()')
        if type(path) is not str:
            raise TypeError(f'Config: path must be str, got {type(path).__name__}')
        if path in self.default_paths:
            if value != self.default_paths[path]:
                raise ValueError(f'Config: conflicting default for {path!r}: {value!r} vs {self.default_paths[path]!r}')
        else:
            self.default_paths[path] = value
            self.__apply(self.cfg, path, value)
            log.info(f"Default '{path}' = '{value}'")

    def __apply(self, node: Any, path: str, value: Any) -> None:
        elems = list(self.__elements(path))
        end_elem = (None, None)
        elems.append(end_elem)
        for i, elem in enumerate(elems[:-1]):
            next_elem = elems[i + 1]
            sep, name = elem
            assert name is not None
            if sep == '.': # dict
                if type(node) is not dict:
                    raise TypeError(f'Config: expected dict at {name!r} in path, got {type(node).__name__}')
                if next_elem is end_elem:
                    # Set the default value
                    node[name] = value
                    return
                if name in node:
                    node = node[name]
                else:
                    next_sep, _ = next_elem
                    if next_sep == '.':
                        next_node: dict | list = {}
                    else:
                        next_node = []
                    node[name] = next_node
                    node = next_node
            else: # sep == ',' # list
                if type(node) is not list:
                    raise TypeError(f'Config: expected list at index {name!r} in path, got {type(node).__name__}')
                index = int(name)
                if index >= len(node):
                    node.extend([None] * (index - len(node) + 1))
                if next_elem is end_elem:
                    # Set the default value
                    node[index] = value
                    return
                if node[index] is None:
                    next_sep, _ = next_elem
                    if next_sep == '.':
                        next_node = {}
                    else:
                        next_node = []
                    node[index] = next_node
                node = node[index]

    def __elements(self, path: str) -> Generator[tuple[str, str] | tuple[None, None]]:
        elems = re.split(r'(\.|,)', path)
        if elems[0] == '':
            elems.pop(0)
        else:
            elems.insert(0, '.')
        if len(elems) % 2 != 0:
            raise ValueError(f'Config: malformed path {path!r}')
        return ((elems[i], elems[i+1]) for i in range(0, len(elems), 2))

    def __getitem__(self, path: str) -> Any:
        if type(path) is not str:
            raise TypeError(f'Config: path must be str, got {type(path).__name__}')
        elems = self.__elements(path)
        node = self.cfg
        for sep, name in elems:
            if sep == '.': # dict
                if type(node) is not dict:
                    raise TypeError(f'Config: expected dict at {name!r} in path, got {type(node).__name__}')
                if name not in node:
                    return None
                node = node[name]
            else: # sep == ',' # list
                if type(node) is not list:
                    raise TypeError(f'Config: expected list at index {name!r} in path, got {type(node).__name__}')
                index = int(name)
                if index >= len(node):
                    return None
                node = node[index]
        return node

    def __setitem__(self, path: str, value: Any) -> None:
        if type(path) is not str:
            raise TypeError(f'Config: path must be str, got {type(path).__name__}')
        if not path:
            if type(value) is not dict:
                raise TypeError(f'Config: root value must dict, got {type(value).__name__}')
            self.cfg = value
            self.user_cfg = value
        else:
            self.__apply(self.user_cfg, path, value)
            self.__apply(self.cfg, path, value)

    def replace_user_root(self, value: dict[str, Any]) -> None:
        """ Replace all user settings while maintaining defaults """
        self.cfg = {}
        for path, default_value in self.default_paths.items():
            self.__apply(self.cfg, path, default_value)
        self.user_cfg = value
        self.__overlay(self.cfg, self.user_cfg)
