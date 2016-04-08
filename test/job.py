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

"""Basic test for jobs and polling."""

import logging

from mock import patch
from pytest import raises

from marche.jobs import Fault, Busy, DEAD, RUNNING, STARTING, STOPPING
from marche.jobs.base import Job as BaseJob
from marche.protocol import StatusEvent
from marche.permission import ClientInfo, ADMIN, CONTROL, DISPLAY

from test.utils import wait, LogHandler, MockAsyncProcess

logger = logging.getLogger('testjob')
testhandler = LogHandler()
logger.addHandler(testhandler)


class EmptyJob(BaseJob):
    def configure(self, config):
        self.test_configured = True


def test_job_base():
    testhandler.assert_error(EmptyJob, 'test', 'test',
                             {'pollinterval': 'nada'}, logger,
                             lambda event: None)
    testhandler.assert_error(EmptyJob, 'test', 'test',
                             {'permissions': 'nada'}, logger,
                             lambda event: None)

    job = EmptyJob('test', 'test', {'pollinterval': '0',
                                    'permissions': 'admin=control'},
                   logger, lambda event: None)
    assert job.test_configured
    assert job.check()
    job.init()

    job.check_permission(ADMIN, ClientInfo(CONTROL))
    with raises(Fault):
        job.check_permission(ADMIN, ClientInfo(DISPLAY))
    assert job.determine_permissions(ClientInfo(DISPLAY)) == [DISPLAY]

    # Check default implementations
    assert job.service_output('foo', 'bar') == []
    assert job.service_logs('foo', 'bar') == {}
    assert job.receive_config('foo', 'bar') == {}
    assert job.service_description('foo', 'bar') == ''
    assert raises(Fault, job.send_config, 'foo', 'bar', '', '')

    # Check required implementations
    assert raises(NotImplementedError, job.get_services)
    assert raises(NotImplementedError, job.start_service, 'foo', 'bar')
    assert raises(NotImplementedError, job.stop_service, 'foo', 'bar')
    assert raises(NotImplementedError, job.restart_service, 'foo', 'bar')
    assert raises(NotImplementedError, job.service_status, 'foo', 'bar')
    assert raises(NotImplementedError, job.polled_service_status, 'foo', 'bar')

    job.shutdown()


def test_job_helpers():
    job = EmptyJob('test', 'test', {'pollinterval': '0'},
                   logger, lambda event: None)
    out = []
    with patch('marche.jobs.base.AsyncProcess', MockAsyncProcess):

        # Check async and sync calls.
        proc = job._async_call(0, 'cmd', output=out)
        proc.join()
        assert out == ['$ cmd\n', 'output\n', 'error\n']

        proc = job._sync_call(0, 'cmd')
        assert proc.stdout == ['output\n']

        # Simulate starting the process.
        job._async_start('sub', 'cmd')
        assert job._processes['sub'].done
        assert list(job._output['sub']) == ['$ cmd\n', 'output\n', 'error\n']

        assert job._async_status('sub', 'cmd') == RUNNING
        assert job._async_status('sub', 'fail') == DEAD

        # Simulate the start process being still busy.
        job._processes['sub'].done = False
        assert raises(Busy, job._async_start, 'sub', 'cmd')
        assert job._async_status('sub', 'cmd') == STARTING

        # Simulate stopping the process.
        job._processes['sub'].done = True
        job._async_stop('sub', 'cmd')

        # Simulate the stop process being still busy.
        job._processes['sub'].done = False
        assert raises(Busy, job._async_stop, 'sub', 'cmd')
        assert job._async_status('sub', 'cmd') == STOPPING
        assert job._async_status_only('sub') == STOPPING


class Job(BaseJob):
    test_raise = False
    test_state = DEAD
    test_ext_status = 'ext'

    def get_services(self):
        return [('svc', 'inst')]

    def service_status(self, service, instance):
        if self.test_raise:
            raise RuntimeError
        return self.test_state, self.test_ext_status


def test_job_poller():
    events = []

    job = Job('test', 'test', {'pollinterval': '0.001'}, logger, events.append)
    job.init()

    wait(100, lambda: events)
    ev = events[0]
    assert isinstance(ev, StatusEvent)
    assert ev.service == 'svc'
    assert ev.instance == 'inst'
    assert ev.state == DEAD
    assert ev.ext_status == 'ext'

    del events[:]
    job.test_state = RUNNING
    wait(100, lambda: events)
    assert events[0].state == RUNNING

    job.poller.stop()
    job.poller.interval = 100.0  # stop automatic polling
    job.poller.start()

    del events[:]
    job.invalidate('svc', 'inst')
    job.poll_now()
    wait(100, lambda: events)
    assert job.polled_service_status('svc', 'inst') == (RUNNING, 'ext')

    job.poller.stop()
    job.test_raise = True
    job.poller.start()
    job.invalidate('svc', 'inst')
    job.poll_now()
    assert raises(RuntimeError, job.polled_service_status, 'svc', 'inst')

    job.shutdown()
