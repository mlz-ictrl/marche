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

"""Test for the process monitoring job."""

import sys
import logging

from marche.jobs import DEAD, NOT_RUNNING, RUNNING
from marche.jobs.process import Job, ProcessMonitor

from test.utils import wait

ProcessMonitor.DELAY = 0.01

logger = logging.getLogger('testprocess')

SUBPROCESS = '''\
import sys
import time
while 1:
    sys.stdout.write('alive\\n')
    sys.stdout.flush()
    time.sleep(0.1)
'''


def test_job(tmpdir):
    outputfile = tmpdir.join('output')

    config = {
        'binary': sys.executable,
        'args': '-c "%s"' % SUBPROCESS,
        'outputfile': str(outputfile),
        'oneshot': 'false',
        'autostart': 'true',
    }

    job = Job('process', 'name', config, logger, lambda event: None)
    assert job.check()
    job.init()

    assert job.get_services() == [('name', '')]

    assert job._thread.isAlive()
    assert job.service_status('name', '')[0] == RUNNING
    job.start_service('name', '')
    job.restart_service('name', '')
    wait(100, outputfile.size)
    job.stop_service('name', '')
    assert not job._thread.isAlive()
    job.stop_service('name', '')
    assert job.service_status('name', '')[0] == DEAD

    assert outputfile.readlines()[0] == 'alive\n'
    logs = job.service_logs('name', '')
    assert len(logs) == 1
    keys = list(logs)
    assert keys[0].endswith('output')
    assert logs[keys[0]] == 'alive\n'

    assert job.service_output('name', '') == []


def test_oneshot():
    config = {
        'binary': sys.executable,
        'args': '-c "print(\'output\')"',
        'oneshot': 'true',
    }

    job = Job('process', 'name', config, logger, lambda event: None)
    assert job.check()
    job.init()

    job.start_service('name', '')
    wait(100, lambda: job.service_status('name', '')[0] == NOT_RUNNING)
    job.stop_service('name', '')
    assert not job._thread.isAlive()

    assert job.service_output('name', '') == ['output\n']


def test_check():
    config = {
        'binary': 'nonexisting_binary'
    }

    job = Job('process', 'name', config, logger, lambda event: None)
    assert not job.check()
