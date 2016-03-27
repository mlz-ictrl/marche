#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2016 by the authors, see LICENSE
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc.,
# 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
# Module authors:
#   Georg Brandl <g.brandl@fz-juelich.de>
#
# *****************************************************************************

"""Utilities for the tests."""

import logging
import time


def wait(n, callback):
    n = 0
    while not callback():
        time.sleep(0.01)
        n += 1
        if n > 100:
            raise RuntimeError('wait timeout reached')


class ErrorLogged(Exception):
    pass


class LogHandler(logging.Handler):
    def __init__(self):
        logging.Handler.__init__(self)
        self.errors = []
        self.warnings = []
        self.messages = 0

    def assert_error(self, func, *args):
        nerrors = len(self.errors)
        func(*args)
        assert len(self.errors) > nerrors

    def emit(self, record):
        if record.levelno >= logging.ERROR:
            self.errors.append(record)
        elif record.levelno >= logging.WARNING:
            self.warnings.append(record)
        else:
            self.messages += 1


class MockAsyncProcess(object):
    def __init__(self, status, log, cmd, sh, stdout=None, stderr=None):
        self.status = status
        self.log = log
        self.cmd = cmd
        self.use_sh = sh
        self.stdout = stdout if stdout is not None else []
        self.stderr = stderr if stderr is not None else []
        self.done = False
        self.retcode = None

    def start(self):
        time.sleep(0.01)
        self.stdout.append('output\n')
        self.stderr.append('error\n')
        self.retcode = 1 if self.cmd == 'fail' else 0
        self.done = True

    def join(self):
        pass
