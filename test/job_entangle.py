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

"""Test for the Entangle job."""

import sys
import logging

from pytest import raises

from marche.jobs import Fault, RUNNING
from marche.jobs.entangle import Job

from test.utils import wait

logger = logging.getLogger('testentangle')

SCRIPT = '''\
import sys
print(sys.argv[2])
print(sys.argv[1])
'''

CONFIG = '''\
[entangle]
resdir = %(tmpdir)s
logdir = %(tmpdir)s
'''

RES = '''\
test/my/dev/type: rs232.StringIO
'''


def test_job(tmpdir):
    scriptfile = tmpdir.join('script.py')
    scriptfile.write(SCRIPT)
    configfile = tmpdir.join('entangle.conf')
    configfile.write(CONFIG % {'tmpdir': str(tmpdir)})
    tmpdir.join('mysrv.res').write_binary(RES.encode())
    tmpdir.mkdir('mysrv').join('current').write('log1\nlog2\n')

    Job.INITSCR = 'does/not/exist'
    job = Job('entangle', 'name', {}, logger, lambda event: None)
    assert not job.check()

    Job.CONFIG = str(configfile)
    Job.INITSCR = sys.executable

    job = Job('entangle', 'name', {}, logger, lambda event: None)
    assert job.check()
    Job.INITSCR = sys.executable + ' ' + str(scriptfile)
    job.init()

    assert job.get_services() == [('entangle', 'mysrv')]

    assert job.service_status('entangle', 'mysrv') == (RUNNING, '')

    job.start_service('entangle', 'mysrv')
    wait(100, lambda: job.service_status('entangle', 'mysrv')[0] == RUNNING)
    out = job.service_output('entangle', 'mysrv')
    assert out[0].startswith('$ ') and out[0].endswith(' start mysrv\n')
    assert out[1:] == ['mysrv\n', 'start\n']

    job.stop_service('entangle', 'mysrv')
    wait(100, lambda: job.service_status('entangle', 'mysrv')[0] == RUNNING)
    out = job.service_output('entangle', 'mysrv')
    assert out[-3].startswith('$ ') and out[-3].endswith(' stop mysrv\n')
    assert out[-2:] == ['mysrv\n', 'stop\n']

    job.restart_service('entangle', 'mysrv')
    wait(100, lambda: job.service_status('entangle', 'mysrv')[0] == RUNNING)
    out = job.service_output('entangle', 'mysrv')
    assert out[-3].startswith('$ ') and out[-3].endswith(' restart mysrv\n')
    assert out[-2:] == ['mysrv\n', 'restart\n']

    logs = job.service_logs('entangle', 'mysrv')
    assert list(logs.values()) == ['log1\nlog2\n']

    configs = job.receive_config('entangle', 'mysrv')
    assert configs == {'mysrv.res': RES}
    assert raises(Fault, job.send_config, 'entangle', 'mysrv', 'other.res', '')
    job.send_config('entangle', 'mysrv', 'mysrv.res', RES + 'foo\n')
    assert tmpdir.join('mysrv.res').read() == RES + 'foo\n'
