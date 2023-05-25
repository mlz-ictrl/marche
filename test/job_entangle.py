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

"""Test for the Entangle job."""

import logging
import sys

from pytest import fixture, raises

from marche.jobs import RUNNING, Fault
from marche.jobs.entangle import InitJob, Job, SystemdJob
from marche.utils import determine_init_system
from test.utils import job_call_check

logger = logging.getLogger('testentangle')

SCRIPT = '''\
import sys
if len(sys.argv) < 3:
    print('status...')
    print('mysrv : running')
elif sys.argv[1] == '-n':
    print('log1\\nlog2')
else:
    print(sys.argv[2])
    print(sys.argv[1])
'''

CONFIG = '''\
[entangle]
resdir = "%(tmpdir)s"
logdir = "%(tmpdir)s"
'''

RES = '''\
test/my/dev/type: rs232.StringIO
'''


@fixture(scope='function')
def tempconf(tmpdir):
    scriptfile = tmpdir.join('script.py')
    scriptfile.write(SCRIPT)
    configfile = tmpdir.join('entangle.conf')
    configfile.write(CONFIG % {'tmpdir': str(tmpdir)})
    tmpdir.join('mysrv.res').write_binary(RES.encode())
    tmpdir.mkdir('mysrv').join('current').write('log1\nlog2\n')

    return tmpdir, scriptfile, configfile


def test_init_job(tempconf):
    _test_job_cls(InitJob, tempconf)


def test_systemd_job(tempconf):
    _test_job_cls(SystemdJob, tempconf, prefix='entangle@')


def test_job():
    job = Job('entangle', 'name', {}, logger, lambda event: None)
    if determine_init_system() == 'systemd':
        assert isinstance(job, SystemdJob)
    else:
        assert isinstance(job, InitJob)


def _test_job_cls(jobcls, tempconf, prefix=''):
    tmpdir, scriptfile, configfile = tempconf

    job = jobcls('entangle', 'name', {'controltool': 'does/not/exist'},
                 logger, lambda event: None)
    assert not job.check()

    job = jobcls('entangle', 'name', {'configfile': str(configfile),
                                      'controltool': sys.executable},
                 logger, lambda event: None)
    assert job.check()
    job._control_tool = sys.executable + ' -S ' + str(scriptfile)
    job.JOURNAL_TOOL = job._control_tool
    job.init()

    assert job.get_services() == [('entangle', 'mysrv')]

    assert job.service_status('entangle', 'mysrv') == (RUNNING, '')
    assert job.all_service_status() == {('entangle', 'mysrv'): (RUNNING, '')}

    job_call_check(job, 'entangle', 'mysrv',
                   'action %smysrv' % prefix, [prefix + 'mysrv', 'action'])

    logs = job.service_logs('entangle', 'mysrv')
    assert list(logs.values()) == ['log1\nlog2\n']

    configs = job.receive_config('entangle', 'mysrv')
    assert configs == {'mysrv.res': RES}
    assert raises(Fault, job.send_config, 'entangle', 'mysrv', 'other.res', '')
    job.send_config('entangle', 'mysrv', 'mysrv.res', RES + 'foo\n')
    assert tmpdir.join('mysrv.res').read() == RES + 'foo\n'
