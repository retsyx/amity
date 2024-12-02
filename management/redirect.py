#!/usr/bin/env python

# Copyright 2024.
# This file is part of Amity.
# Amity is free software: you can redistribute it and/or modify it under the terms of the
# GNU General Public License as published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.

import tools

log = tools.logger('var/log/redirect.log')

from contextlib import redirect_stdout, redirect_stderr

from http.server import HTTPServer, BaseHTTPRequestHandler

class StreamLogger(object):
    def write(self, buf):
        log.info(buf)
    def flush(self):
        pass

class RedirectHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(301)
        self.send_header('Location', f'https://{self.headers["Host"]}{self.path}')
        self.end_headers()

if __name__ == '__main__':
    slog = StreamLogger()
    with redirect_stdout(slog):
        with redirect_stderr(slog):
            httpd = HTTPServer(('0.0.0.0', 80), RedirectHandler)
            httpd.serve_forever()
