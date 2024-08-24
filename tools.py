# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import asyncio, logging, logging.handlers, os

def maybe_set_log_filename(filename):
    global log, log_filename
    if log_filename is not None: return
    log_filename = filename
    logger_config()
    log = logger(__name__)

def logger(name):
    short_name = os.path.splitext(os.path.basename(name))[0]
    l = logging.getLogger(short_name)
    l.setLevel(logging.INFO)
    all_loggers.add(l)
    if not name.endswith('.log'):
        name += '.log'
    maybe_set_log_filename(name)
    return l

def logger_config():
    log_handler = logging.handlers.RotatingFileHandler(log_filename, backupCount=3, maxBytes=1024*1024)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(name)s %(message)s')
    log_handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(log_handler)

def set_log_level(level_s):
    level = { 'info' : logging.INFO,
              'debug' : logging.DEBUG,
              'warning' : logging.WARNING,
              'error': logging.ERROR,
    }.get(level_s)
    if level is None:
        log.info(f'Unknown error level "{level_s}" requested')
        return
    for logger in all_loggers:
        logger.setLevel(level)

all_loggers = set()
log_filename = None
log = None

def die(reason):
    log.info(f'DIE {reason}')
    os._exit(1)

class Tasker(object):
    def __init__(self):
        self.tasks = set()

    def __call__(self, coro):
        return self.go(coro)

    def go(self, coro):
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.check_task)
        return task

    def check_task(self, task):
        self.tasks.discard(task)
        try:
            exc = task.exception()
        except asyncio.CancelledError as e:
            exc = e
        if exc is not None:
            die(f'Task exception {exc}')
