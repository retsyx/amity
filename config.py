# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools
log = tools.logger(__name__)

import os, re, shutil, stat, tempfile, time, yaml

class Config(object):
    def __init__(self, filename):
        self.default_paths = {}
        self.user_cfg = {}
        self.cfg = {}
        self.loaded = False
        self.filename = filename
        log.info(f'filename {self.filename}')

    def load(self):
        """Must be called after all default() calls have been made"""
        log.info(f'Load {self.filename}')
        try:
            with open(self.filename, 'r') as file:
                self.user_cfg = yaml.safe_load(file)
            if self.user_cfg is None:
                log.info(f'{self.filename} is empty. Defaulting to empty config.')
                self.user_cfg = {}
        except FileNotFoundError:
            log.info(f'{self.filename} not found. Defaulting to empty config.')
        self.__overlay(self.cfg, self.user_cfg)
        self.loaded = True

    def save(self, backup=False):
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
        tmp_fd, tmp_path = tempfile.mkstemp()
        with os.fdopen(tmp_fd, 'w') as file:
            yaml.safe_dump(self.user_cfg, file)
        shutil.move(tmp_path, self.filename)
        # Fixup ownership, if running as root
        if os.getuid() == 0:
            stat = os.stat('.')
            shutil.chown(self.filename, stat.st_uid, stat.st_gid)

    def save_complete(self, filename):
        with open(filename, 'w') as file:
            yaml.safe_dump(self.cfg, file)

    def __overlay(self, node, overlay_node):
        if type(node) is dict:
            # User misconfiguration if this assert triggers
            assert type(node) is type(overlay_node)
            for name, value in overlay_node.items():
                if name not in node:
                    node[name] = value
                else:
                    scalar = self.__overlay(node[name], overlay_node[name])
                    if scalar:
                        node[name] = overlay_node[name]
        elif type(node) is list:
            # User misconfiguration if this assert triggers
            assert type(node) is type(overlay_node)
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

    def default(self, path, value):
        assert not self.loaded
        assert type(path) is str
        if path in self.default_paths:
            assert value == self.default_paths[path]
        else:
            self.default_paths[path] = value
            self.__apply(self.cfg, path, value)
            log.info(f"Default '{path}' = '{value}'")

    def __apply(self, node, path, value):
        elems = list(self.__elements(path))
        end_elem = (None, None)
        elems.append(end_elem)
        for i, elem in enumerate(elems[:-1]):
            next_elem = elems[i + 1]
            sep, name = elem
            if sep == '.': # dict
                assert type(node) is dict
                if next_elem is end_elem:
                    # Set the default value
                    node[name] = value
                    return
                if name in node:
                    node = node[name]
                else:
                    next_sep, _ = next_elem
                    if next_sep == '.':
                        next_node = {}
                    else:
                        next_node = []
                    node[name] = next_node
                    node = next_node
            else: # sep == ',' # list
                assert type(node) is list
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

    def __elements(self, path):
        elems = re.split(r'(\.|,)', path)
        if elems[0] == '':
            elems.pop(0)
        else:
            elems.insert(0, '.')
        assert len(elems) % 2 == 0
        return ((elems[i], elems[i+1]) for i in range(0, len(elems), 2))

    def __getitem__(self, path):
        assert type(path) is str
        elems = self.__elements(path)
        node = self.cfg
        for sep, name in elems:
            if sep == '.': # dict
                assert type(node) is dict
                if name not in node:
                    return None
                node = node[name]
            else: # sep == ',' # list
                assert type(node) is list
                index = int(name)
                if index >= len(node):
                    return None
                node = node[index]
        return node

    def __setitem__(self, path, value):
        assert type(path) is str
        self.__apply(self.user_cfg, path, value)
        self.__apply(self.cfg, path, value)

config = Config('config.yaml')

def main():
    c = Config('test.yaml')
    c.default('remote.mac', 0)
    c.load()
    print(f'1 {c.user_cfg}')
    previous = c['remote.mac']
    c['remote.mac'] = previous + 1
    print(f'2 {c.user_cfg}')
    c.save(True)

if __name__ == '__main__':
    main()
