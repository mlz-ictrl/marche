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

import time
import logging

from marche.jobs import Fault, Busy, DEAD
from marche.event import ServiceListEvent, StatusEvent, LogfileEvent, \
    ConffileEvent, ControlOutputEvent
from marche.auth import AuthFailed
from marche.permission import ClientInfo, ADMIN


def wait(n, callback):
    n = 0
    while not callback():
        time.sleep(0.01)
        n += 1
        if n > 100:
            raise RuntimeError('wait timeout reached')


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


class MockJobHandler(object):

    test_interface = None
    test_reloaded = False

    def emit_event(self, event):
        if self.test_interface:
            self.test_interface.emit_event(event)

    def trigger_reload(self):
        self.test_reloaded = True

    def request_service_list(self, client):
        svcs = {'svc': {'': {'desc': '', 'state': DEAD, 'ext_status': '',
                             'permissions': [], 'jobtype': ''},
                        'inst': {'desc': '', 'state': DEAD, 'ext_status': '',
                                 'permissions': [], 'jobtype': ''}}}
        self.emit_event(ServiceListEvent(services=svcs))

    def request_service_status(self, client, service, instance):
        self.emit_event(StatusEvent(service=service,
                                    instance=instance,
                                    state=DEAD,
                                    ext_status='ext_status'))

    def request_control_output(self, client, service, instance):
        self.emit_event(ControlOutputEvent(service=service,
                                           instance=instance,
                                           content=['line1', 'line2']))

    def request_logfiles(self, client, service, instance):
        self.emit_event(LogfileEvent(service=service,
                                     instance=instance,
                                     files={'file1': 'line1\nline2\n',
                                            'file2': 'line3\nline4\n'}))

    def request_conffiles(self, client, service, instance):
        self.emit_event(ConffileEvent(service=service,
                                      instance=instance,
                                      files={'file1': 'line1\nline2\n',
                                             'file2': 'line3\nline4\n'}))

    def start_service(self, client, service, instance):
        pass

    def stop_service(self, client, service, instance):
        raise Busy

    def restart_service(self, client, service, instance):
        raise Fault('cannot do this')

    def send_conffile(self, client, service, instance, filename, contents):
        raise ValueError('no conf files')


class MockAuthHandler(object):

    def needs_authentication(self):
        return True

    def authenticate(self, user, passwd):
        if user == passwd == 'test':
            return ClientInfo(ADMIN)
        raise AuthFailed
