# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-present by the authors, see LICENSE
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

import logging
import sys

import pytest

from marche.jobs import RUNNING, Fault
from marche.jobs.systemd import Job
from test.utils import job_call_check

# ruff: noqa: SLF001

logger = logging.getLogger('testsystemd')

SCRIPT = '''\
import sys
if sys.argv[1] == 'journalctl':
    print('logline1\\nlogline2')
elif sys.argv[1] == 'systemctl' and sys.argv[2] == 'is-enabled':
    if sys.argv[3] != 'foo':
        sys.stderr.write('Not found\\n')
elif sys.argv[1] == 'systemctl' and sys.argv[2] == 'show':
    print('SubState=running')
else:
    print(sys.argv[3])
    print(sys.argv[2])
'''


def test_job(tmp_path):
    scriptfile = tmp_path / 'script.py'
    scriptfile.write_text(SCRIPT)

    Job.SYSTEMCTL = f'{sys.executable} -S {scriptfile} systemctl'
    Job._JOURNALCTL = f'{sys.executable} -S {scriptfile} journalctl'

    job = Job('systemd', 'name', {'unit': 'nope'}, logger, lambda _event: None)
    assert not job.check()

    job = Job('systemd', 'name', {'unit': 'foo'}, logger, lambda _event: None)
    assert job.check()
    job.init()

    assert job.get_services() == [('foo', '')]
    assert job.service_description('foo', '') == 'name'
    assert job.service_status('foo', '') == (RUNNING, '')
    job_call_check(job, 'foo', '', 'action foo', ['foo', 'action'])

    assert job.service_logs('foo', '') == {'journal': 'logline1\nlogline2\n'}

    (tmp_path / '1.log').write_text('log1_line1\nlog1_line2\n')
    (tmp_path / '1.cfg').write_text('conf1\n')

    config = {
        'unit': 'foo',
        'pollinterval': 0,
        'logfiles': [tmp_path / '1.log', tmp_path / '2.log'],
        'configfiles': [tmp_path / '1.cfg', tmp_path / '2.cfg'],
    }

    job = Job('systemd', 'name', config, logger, lambda _event: None)
    assert job.check()
    job.init()

    logs = job.service_logs('foo', '')
    assert len(logs) == 1
    for key, value in logs.items():
        if key.endswith('1.log'):
            assert value == 'log1_line1\nlog1_line2\n'
        else:
            raise AssertionError('unknown logfile name returned')

    assert job.receive_config('foo', '') == {'1.cfg': 'conf1\n'}
    job.send_config('foo', '', '1.cfg', 'conf1-changed\n')
    assert (tmp_path / '1.cfg').read_text() == 'conf1-changed\n'
    pytest.raises(Fault, job.send_config, 'foo', '', 'nosuch', 'cfg')

    config = {
        'unit': 'foo',
        'pollinterval': '0',
        'configfiles': str(tmp_path / '1.cfg'),
    }

    pytest.raises(RuntimeError, Job,
                  'systemd', 'name', config, logger, lambda _event: None)
