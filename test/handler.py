#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2023 by the authors, see LICENSE
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

"""Test for the central job handler class."""

import logging
import socket
import sys

from mock import patch
from pytest import fixture, raises

from marche.config import Config
from marche.handler import JobHandler
from marche.jobs import Busy, Fault
from marche.jobs.base import DEAD, RUNNING
from marche.permission import ADMIN, CONTROL, DISPLAY, ClientInfo
from marche.protocol import ConffileEvent, ControlOutputEvent, ErrorEvent, \
    LogfileEvent, ServiceListEvent, StatusEvent
from test.utils import LogHandler, MockIface, MockJob, wait

# Pretend that we are a job module.
sys.modules['marche.jobs.test'] = sys.modules[__name__]
Job = MockJob

logger = logging.getLogger('testhandler')
testhandler = LogHandler()
logger.addHandler(testhandler)


@fixture()
def handler():
    config = Config()
    config.job_config = {
        'mytest': {'type': 'test', 'permissions': 'display=control'},
        # This one should get ignored (no type).
        'strange': {},
    }
    handler = JobHandler(config, logger)
    handler.test_events = []
    handler.add_interface(MockIface(handler.test_events))
    return handler


def test_exceptions():
    config = Config()
    # Unimportable job module.
    config.job_config = {'unimportable': {'type': 'does not exist'}}
    testhandler.assert_error(JobHandler, config, logger)
    # Job that fails feasibility check.
    config.job_config = {'failure': {'type': 'test', 'fail': 'yes'}}
    testhandler.assert_error(JobHandler, config, logger)
    # Duplicate services.
    config.job_config = {'job1': {'type': 'test'},
                         'job2': {'type': 'test'}}
    testhandler.assert_error(JobHandler, config, logger)


def test_event(handler):
    ev = ErrorEvent('svc', 'inst', 42, 'string')
    handler.emit_event(ev)
    assert handler.test_events[-1] == ev


def test_joblist(handler):
    assert list(handler.jobs) == ['mytest']
    job = handler.jobs['mytest']
    assert isinstance(job, Job)

    assert handler._get_job('svc1') is job
    assert raises(Fault, handler._get_job, 'unknown')


def test_reload(handler):
    handler.trigger_reload()
    # Now that we did config.reload(), the injected config is gone
    assert not handler.jobs


def test_service_list(handler):
    # Request the service list (the job is configured to require CONTROL
    # to view services).
    ev = handler.request_service_list(ClientInfo(CONTROL))
    assert isinstance(ev, ServiceListEvent)
    assert ev.services == {
        'svc1': {
            'jobtype': 'test',
            'permissions': [DISPLAY, CONTROL],
            'instances': {'': {'desc': 'desc:',
                               'state': DEAD, 'ext_status': 'ext:'}}},
        'svc2': {
            'jobtype': 'test',
            'permissions': [DISPLAY, CONTROL],
            'instances': {'inst1': {'desc': 'desc:inst1',
                                    'state': RUNNING,
                                    'ext_status': 'ext:inst1'}}},
        'svc3': {
            'jobtype': 'test',
            'permissions': [DISPLAY, CONTROL],
            'instances': {'':      {'desc': 'desc:',
                                    'state': RUNNING, 'ext_status': 'ext:'},
                          'inst2': {'desc': 'desc:inst2',
                                    'state': RUNNING,
                                    'ext_status': 'ext:inst2'}}},
    }
    # Request the same with insufficient permission level.
    ev = handler.request_service_list(ClientInfo(DISPLAY))
    assert ev.services == {}


def test_requests(handler):
    client = ClientInfo(CONTROL)

    desc = handler.get_service_description(client, 'svc2', 'inst1')
    assert desc == 'desc:inst1'

    ev = handler.request_service_status(client, 'svc2', 'inst1')
    assert isinstance(ev, StatusEvent)
    assert ev.service == 'svc2'
    assert ev.instance == 'inst1'
    assert ev.state == RUNNING
    assert ev.ext_status == 'ext:inst1'

    ev = handler.request_control_output(client, 'svc2', 'inst1')
    assert isinstance(ev, ControlOutputEvent)
    assert ev.content == ['out:inst1']

    ev = handler.request_logfiles(client, 'svc2', 'inst1')
    assert isinstance(ev, LogfileEvent)
    assert ev.files == {'log:inst1': 'svc2'}

    client = ClientInfo(ADMIN)
    ev = handler.request_conffiles(client, 'svc2', 'inst1')
    assert isinstance(ev, ConffileEvent)
    assert ev.files == {'conf:inst1': 'svc2'}


def test_commands(handler):
    job = handler.jobs['mytest']
    client = ClientInfo(CONTROL)

    handler.start_service(client, 'svc3', '')
    assert ('svc3', '') in job.test_started

    handler.stop_service(client, 'svc3', '')
    assert ('svc3', '') in job.test_stopped

    handler.restart_service(client, 'svc3', '')
    assert ('svc3', '') in job.test_restarted

    numerrors = len(testhandler.errors)
    assert raises(Busy, handler.start_service, client, 'svc1', '')
    assert raises(Fault, handler.start_service, ClientInfo(DISPLAY),
                  'svc2', 'inst1')
    assert raises(Fault, handler.start_service, client, 'svc2', 'inst1')
    assert raises(ValueError, handler.restart_service, client, 'svc1', '')
    assert len(testhandler.errors) == numerrors + 4

    handler.send_conffile(ClientInfo(ADMIN), 'svc1', '', 'file', 'contents')
    assert job.test_configs['file'] == 'contents'


def test_filtering(handler):
    event = handler.request_service_list(ClientInfo(ADMIN))
    new_event = handler.filter_services(ClientInfo(ADMIN), event)
    assert event == new_event

    new_event = handler.filter_services(ClientInfo(DISPLAY), event)
    assert not new_event.services

    new_event = handler.filter_services(ClientInfo(CONTROL), event)
    assert event == new_event

    event = handler.request_service_status(ClientInfo(ADMIN), 'svc3', '')
    assert not handler.can_see_status(ClientInfo(DISPLAY), event)


class MockSocket:
    def __init__(self, proto, family):
        self.i = 0
        assert proto == socket.AF_INET
        assert family == socket.SOCK_DGRAM

    def setsockopt(self, sol, opt, val):
        assert sol == socket.SOL_SOCKET
        assert opt == socket.SO_BROADCAST
        assert val

    def sendto(self, msg, addr):
        assert msg == b'PING'

    def recvfrom(self, bufsize):
        self.i += 1
        if self.i == 1:
            return b'boo', ('127.0.0.1', 12345)  # wrong reply
        elif self.i == 2:
            return b'PONG', ('127.0.0.2', 12345)  # old
        elif self.i == 3:
            return b'PONG 2', ('127.0.0.3', 12345)  # old
        elif self.i == 4:
            return b'PONG x', ('127.0.0.4', 12345)  # broken
        elif self.i == 5:
            return ('PONG 41 %s' % self.uid).encode(), ('127.0.0.5', 12345)
        else:
            return b'PONG 42 other', ('127.0.0.6', 12345)


def mock_select(rlist, _wlist, _xlist, _timeout):
    return [[rlist[0]]], [], []


def mock_gethostbyaddr(addr):
    return [addr]


def mock_time():
    n = getattr(mock_time, 'n', 0)
    mock_time.n = n + 1
    if n <= 6:
        return 0.0
    return 2.0


def test_scanning(handler):
    MockSocket.uid = handler.uid
    with patch('socket.socket', MockSocket):
        with patch('select.select', mock_select):
            with patch('socket.gethostbyaddr', mock_gethostbyaddr):
                with patch('marche.scan.currenttime', mock_time):
                    del handler.test_events[:]
                    handler.scan_network()
                    wait(100, lambda: len(handler.test_events) == 3)
                    assert handler.test_events[0].version == 1
                    assert handler.test_events[1].version == 2
                    assert handler.test_events[2].version == 42
