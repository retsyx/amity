# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import asyncio, logging, logging.handlers, os
from collections.abc import Coroutine
from typing import Any, NoReturn

def maybe_set_log_filename(filename: str) -> None:
    global log, log_filename
    if log_filename is not None: return
    log_filename = filename
    logger_config(filename)
    log = logger(__name__)

def logger(name: str) -> logging.Logger:
    short_name = os.path.splitext(os.path.basename(name))[0]
    l = logging.getLogger(short_name)
    l.setLevel(logging.INFO)
    all_loggers.add(l)
    if not name.endswith('.log'):
        name += '.log'
    maybe_set_log_filename(name)
    return l

def logger_config(filename: str) -> None:
    log_handler = logging.handlers.RotatingFileHandler(filename, backupCount=3, maxBytes=1024*1024)
    formatter = logging.Formatter('%(asctime)s %(levelname)s: %(name)s %(message)s')
    log_handler.setFormatter(formatter)
    logger = logging.getLogger()
    logger.addHandler(log_handler)

def set_log_level(level_s: str) -> None:
    level = { 'info' : logging.INFO,
              'debug' : logging.DEBUG,
              'warning' : logging.WARNING,
              'error': logging.ERROR,
    }.get(level_s)
    if level is None:
        assert log
        log.info(f'Unknown error level "{level_s}" requested')
        return
    for logger in all_loggers:
        logger.setLevel(level)

all_loggers: set[logging.Logger] = set()
log_filename: str | None = None
log: logging.Logger | None = None

def isiterable(o: Any) -> bool:
    try:
        iter(o)
        return True
    except:
        return False

def die(reason: str) -> NoReturn:
    assert log
    log.info(f'DIE {reason}')
    os._exit(1)

class Tasker:
    def __init__(self, name: str) -> None:
        self.name = name
        self.tasks: set[asyncio.Task[Any]] = set()

    def __call__(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        return self.go(coro)

    def go(self, coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
        task = asyncio.create_task(coro)
        self.tasks.add(task)
        task.add_done_callback(self.check_task)
        return task

    def check_task(self, task: asyncio.Task[Any]) -> None:
        self.tasks.discard(task)
        try:
            exc = task.exception()
        except asyncio.CancelledError as e:
            exc = e
        if exc is not None:
            die(f'Task {self.name} exception {type(exc)} {exc.args} {exc}')
