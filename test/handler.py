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

"""Test for the central job handler class."""

import sys
import logging

from pytest import fixture, raises

from marche.jobs import Fault, Busy
from marche.jobs.base import DEAD, RUNNING
from marche.config import Config
from marche.handler import JobHandler
from marche.event import ServiceListEvent, ControlOutputEvent, ConffileEvent, \
    LogfileEvent, StatusEvent, ErrorEvent
from marche.permission import ClientInfo, DISPLAY, CONTROL, ADMIN

from test.utils import LogHandler, MockIface, MockJob

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
        'svc1': {'':      {'desc': 'desc:', 'jobtype': 'test',
                           'state': DEAD, 'ext_status': 'ext:',
                           'permissions': [DISPLAY, CONTROL]}},
        'svc2': {'inst1': {'desc': 'desc:inst1', 'jobtype': 'test',
                           'state': RUNNING, 'ext_status': 'ext:inst1',
                           'permissions': [DISPLAY, CONTROL]}},
        'svc3': {'':      {'desc': 'desc:', 'jobtype': 'test',
                           'state': RUNNING, 'ext_status': 'ext:',
                           'permissions': [DISPLAY, CONTROL]},
                 'inst2': {'desc': 'desc:inst2', 'jobtype': 'test',
                           'state': RUNNING, 'ext_status': 'ext:inst2',
                           'permissions': [DISPLAY, CONTROL]}},
    }
    # Request the same with insufficient permission level.
    ev = handler.request_service_list(ClientInfo(DISPLAY))
    assert ev.services == {}


def test_requests(handler):
    client = ClientInfo(CONTROL)

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
