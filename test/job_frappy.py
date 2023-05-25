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

"""Test for the Frappy job."""

import logging
import sys

from pytest import fixture, raises

from marche.jobs import RUNNING, Fault
from marche.jobs.frappy import Job
from test.utils import job_call_check

logger = logging.getLogger('testfrappy')

SCRIPT = '''\
import sys
if len(sys.argv) < 3:
    print('status...')
    print('mynode : running')
elif sys.argv[1] == '-n':
    print('log1\\nlog2')
else:
    print(sys.argv[2])
    print(sys.argv[1])
'''

RES = '''\
test/my/dev/type: rs232.StringIO
'''


@fixture(scope='function')
def tempconf(tmpdir):
    scriptfile = tmpdir.join('script.py')
    scriptfile.write(SCRIPT)
    tmpdir.join('mynode_cfg.py').write_binary(RES.encode())
    tmpdir.mkdir('mynode').join('current').write('log1\nlog2\n')

    return tmpdir, scriptfile


def test_job(tempconf):
    tmpdir, scriptfile = tempconf

    job = Job('frappy', 'name', {'controltool': 'does/not/exist'},
              logger, lambda event: None)
    assert not job.check()

    job = Job('frappy', 'name', {'configdir': str(tmpdir),
                                 'controltool': sys.executable},
              logger, lambda event: None)
    assert job.check()
    job._control_tool = sys.executable + ' -S ' + str(scriptfile)
    job._journal_tool = job._control_tool
    job.init()

    assert job.get_services() == [('frappy', 'mynode')]

    assert job.service_status('frappy', 'mynode') == (RUNNING, '')
    assert job.all_service_status() == {('frappy', 'mynode'): (RUNNING, '')}

    job_call_check(job, 'frappy', 'mynode',
                   'action frappy@mynode', ['frappy@mynode', 'action'])

    logs = job.service_logs('frappy', 'mynode')
    assert list(logs.values()) == ['log1\nlog2\n']

    configs = job.receive_config('frappy', 'mynode')
    assert configs == {'mynode_cfg.py': RES}
    assert raises(Fault, job.send_config, 'frappy', 'mynode',
                  'other_cfg.py', '')
    job.send_config('frappy', 'mynode', 'mynode_cfg.py', RES + 'foo\n')
    assert tmpdir.join('mynode_cfg.py').read() == RES + 'foo\n'
