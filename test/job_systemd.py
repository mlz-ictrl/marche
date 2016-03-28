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

"""Test for the systemd unit job."""

import sys
import logging

from pytest import raises

from marche.jobs import RUNNING
from marche.jobs.systemd import Job

from test.utils import job_call_check

logger = logging.getLogger('testsystemd')

SCRIPT = '''\
import sys
if sys.argv[1] == 'journalctl':
    print('logline1\\nlogline2')
elif sys.argv[1] == 'systemctl' and sys.argv[2] == 'is-enabled':
    if sys.argv[3] != 'foo':
        sys.stderr.write('Not found\\n')
else:
    print(sys.argv[3])
    print(sys.argv[2])
'''


def test_job(tmpdir):
    scriptfile = tmpdir.join('script.py')
    scriptfile.write(SCRIPT)

    Job.SYSTEMCTL = sys.executable + ' ' + str(scriptfile) + ' systemctl'
    Job.JOURNALCTL = sys.executable + ' ' + str(scriptfile) + ' journalctl'

    job = Job('systemd', 'name', {'unit': 'nope'}, logger, lambda event: None)
    assert not job.check()

    job = Job('systemd', 'name', {'unit': 'foo'}, logger, lambda event: None)
    assert job.check()
    job.init()

    assert job.get_services() == [('foo', '')]
    assert job.service_status('foo', '') == (RUNNING, '')
    job_call_check(job, 'foo', '', 'action foo', ['foo', 'action'])

    assert job.service_logs('foo', '') == {'journal': 'logline1\nlogline2\n'}


def test_job_mixins(tmpdir):
    tmpdir.join('1.log').write('log1_line1\nlog1_line2\n')
    tmpdir.join('2.log').write('log2_line1\nlog2_line2\n')
    tmpdir.join('1.cfg').write_binary(b'conf1\n')

    config = {
        'unit': 'foo',
        'pollinterval': '0',
        'logfile': str(tmpdir.join('1.log')),
        'logfiles': '%s, %s' % (tmpdir.join('2.log'), tmpdir.join('3.log')),
        'configfiles': '%s, %s' % (tmpdir.join('1.cfg'), tmpdir.join('2.cfg')),
    }

    job = Job('systemd', 'name', config, logger, lambda event: None)
    assert job.check()
    job.init()

    logs = job.service_logs('foo', '')
    assert len(logs) == 2
    for key, value in logs.items():
        if key.endswith('1.log'):
            assert value == 'log1_line1\nlog1_line2\n'
        elif key.endswith('2.log'):
            assert value == 'log2_line1\nlog2_line2\n'
        else:
            assert False, 'unknown logfile name returned'

    assert job.receive_config('foo', '') == {'1.cfg': 'conf1\n'}
    job.send_config('foo', '', '1.cfg', 'conf1-changed\n')
    assert tmpdir.join('1.cfg').read() == 'conf1-changed\n'
    assert raises(RuntimeError, job.send_config, 'foo', '', 'nosuch', 'cfg')

    config = {
        'unit': 'foo',
        'pollinterval': '0',
        'configfile': str(tmpdir.join('1.cfg')),
        'configfiles': str(tmpdir.join('1.cfg')),
    }

    assert raises(RuntimeError, Job,
                  'systemd', 'name', config, logger, lambda event: None)
