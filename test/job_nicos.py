# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2025 by the authors, see LICENSE
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

"""Test for the NICOS job."""

import logging
import sys

import pytest

from marche.jobs import DEAD, RUNNING, WARNING, Fault
from marche.jobs.nicos import Job
from test.utils import job_call_check

# ruff: noqa: SLF001

logger = logging.getLogger('testnicos')

SCRIPT = '''\
import sys
if len(sys.argv) == 1:
    sys.stderr.write('Usage: nicos-system [action] [service]\\n')
    sys.stderr.write('Possible services are cache\\n')
    sys.exit(1)
elif len(sys.argv) == 2:
    if sys.argv[1] == 'status':
        print('cache: running')
    else:
        print(sys.argv[1])
else:
    print(sys.argv[2])
    print(sys.argv[1])
'''

SCRIPT2 = '''\
print('status ...')
print('cache: running')
print('poller: dead')
'''

SCRIPT3 = '''\
print('status ...')
print('cache: dead')
print('poller: dead')
'''

SCRIPT4 = '''\
print('status ...')
print('cache: running')
print('poller: running')
'''


def test_job(tmp_path):
    (tmp_path / 'etc').mkdir()
    (tmp_path / 'etc' / 'nicos-system').write_text(SCRIPT)
    (tmp_path / 'nicos-system2').write_text(SCRIPT2)
    (tmp_path / 'nicos-system3').write_text(SCRIPT3)
    (tmp_path / 'nicos-system4').write_text(SCRIPT4)
    (tmp_path / 'log' / 'cache').mkdir(parents=True)
    (tmp_path / 'log' / 'cache' / 'current').write_text('log1\nlog2\n')

    Job.DEFAULT_INIT = 'does/not/exist'
    job = Job('nicos', 'name', {}, logger, lambda _event: None)
    assert not job.check()

    (tmp_path / 'nicos.conf').write_text('[nicos]\nlogging_path = "%s"\n' %
                                         (tmp_path / 'log'))

    job = Job('nicos', 'name', {'root': str(tmp_path)},
              logger, lambda _event: None)
    assert job.check()
    job._script = f'{sys.executable} -S {job._script}'
    job.init()

    assert job.get_services() == [('nicos', ''), ('nicos', 'cache')]
    assert job.service_status('nicos', 'cache') == (RUNNING, '')

    job_call_check(job, 'nicos', '', 'action ', ['action'])
    job_call_check(job, 'nicos', 'cache', 'action cache', ['cache', 'action'])

    assert job.service_logs('nicos', '') == {}
    logs = job.service_logs('nicos', 'cache')
    assert list(logs.values()) == ['log1\nlog2\n']

    assert job.receive_config('nicos', 'cache') == {}
    pytest.raises(Fault, job.send_config, 'nicos', 'cache', 'file', 'contents')

    job._script = f'{sys.executable} -S {tmp_path / "nicos-system2"}'
    assert job.service_status('nicos', '')[0] == WARNING

    assert job.all_service_status() == {
        ('nicos', ''): (WARNING, 'only some services running'),
        ('nicos', 'cache'): (RUNNING, ''),
    }

    job._script = f'{sys.executable} -S {tmp_path / "nicos-system3"}'
    assert job.service_status('nicos', '')[0] == DEAD

    assert job.all_service_status() == {
        ('nicos', ''): (DEAD, ''),
        ('nicos', 'cache'): (DEAD, ''),
    }

    job._script = f'{sys.executable} -S {tmp_path / "nicos-system4"}'
    assert job.all_service_status() == {
        ('nicos', ''): (RUNNING, ''),
        ('nicos', 'cache'): (RUNNING, ''),
    }
