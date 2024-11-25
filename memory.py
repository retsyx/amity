# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger(__name__)

import asyncio, linecache, tracemalloc

class Monitor(object):
    def __init__(self, period=None):
        self.last_snapshot = None
        if period is None:
            period = 60*60
        self.period = period
        self.taskit = tools.Tasker('Memory Monitor')
        self.done = False

    def log_top(self, snapshot, key_type='lineno', limit=10):
        snapshot = snapshot.filter_traces((
            tracemalloc.Filter(False, "<frozen importlib._bootstrap>"),
            tracemalloc.Filter(False, "<unknown>"),
        ))
        top_stats = snapshot.statistics(key_type)
        log.info(f'Top {limit} lines')
        for index, stat in enumerate(top_stats[:limit], 1):
            frame = stat.traceback[0]
            log.info('#%s: %s:%s: %.1f KiB'
                % (index, frame.filename, frame.lineno, stat.size / 1024))
            line = linecache.getline(frame.filename, frame.lineno).strip()
            if line:
                log.info('    %s' % line)

        other = top_stats[limit:]
        if other:
            size = sum(stat.size for stat in other)
            log.info('%s other: %.1f KiB' % (len(other), size / 1024))
        total = sum(stat.size for stat in top_stats)
        log.info('Total allocated size: %.1f KiB' % (total / 1024))

    def checkpoint(self):
        snapshot = tracemalloc.take_snapshot()
        self.log_top(snapshot)
        if self.last_snapshot is not None:
            top_stats = snapshot.compare_to(self.last_snapshot, 'lineno')
            log.info('Top 10 differences')
            for stat in top_stats[:10]:
                log.info(stat)
        self.last_snapshot = snapshot

    async def task(self):
        while not self.done:
            self.checkpoint()
            await asyncio.sleep(self.period)

    def stop(self):
        self.done = True
        tracemalloc.stop()

    def start(self):
        tracemalloc.start()
        self.done = False
        self.taskit(self.task())

    def wait_on(self):
        return self.taskit.tasks

