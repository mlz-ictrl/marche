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

"""Test for the TACO job."""

import sys
import logging

from marche.jobs import RUNNING
from marche.jobs.taco import Job

from test.utils import job_call_check

logger = logging.getLogger('testtaco')

SCRIPT = '''\
import sys
print(sys.argv[2])
print(sys.argv[1])
'''

DB_DEVLIST = '''\
print('\\tstrange/dev/1')
print('mysrvserver/inst :')
print('\\tmy/dev/1')
print('\\tmy/dev/2')
print('')
print('otherserver/other :')
print('\\tother/dev/1')
'''

DB_DEVRES = '''\
import sys
if sys.argv[1] == 'my/dev/1':
    print('my/dev/1/name: 1')
    print('my/dev/1/iodev: my/dev/2')
    print('')
else:
    print('my/dev/2/name: 2')
'''


def test_job(tmpdir):
    tmpdir.join('taco-server-mysrv').write(SCRIPT)
    tmpdir.join('db_devlist').write(DB_DEVLIST)
    tmpdir.join('db_devres').write(DB_DEVRES)
    tmpdir.mkdir('log').join('Mysrv_inst.log').write('log1\nlog2\n')
    tmpdir.join('log', 'Mysrv.log').write('log3\nlog4\n')

    Job.INIT_DIR = 'does/not/exist'
    job = Job('taco', 'name', {}, logger, lambda event: None)
    assert not job.check()

    Job.INIT_DIR = str(tmpdir)
    Job.LOG_DIR = str(tmpdir.join('log'))
    Job.DB_DEVLIST = '%s -S %s' % (sys.executable, tmpdir.join('db_devlist'))
    Job.DB_DEVRES = '%s -S %s' % (sys.executable, tmpdir.join('db_devres'))

    job = Job('taco', 'name', {}, logger, lambda event: None)
    assert job.check()
    job.init()
    job._initscripts['taco-mysrv'] = '%s -S %s' % \
        (sys.executable, job._initscripts['taco-mysrv'])

    assert job.get_services() == [('taco-mysrv', 'inst')]
    assert job.service_status('taco-mysrv', 'inst') == (RUNNING, '')

    job_call_check(job, 'taco-mysrv', 'inst',
                   'action inst', ['inst', 'action'])

    logs = job.service_logs('taco-mysrv', 'inst')
    assert len(logs) == 2
    for key, value in logs.items():
        if key.endswith('Mysrv_inst.log'):
            assert value == 'log1\nlog2\n'
        elif key.endswith('Mysrv.log'):
            assert value == 'log3\nlog4\n'
        else:
            assert False, 'unknown logfile returned'

    Job.LOG_DIR = 'does/not/exist'
    assert job.service_logs('taco-mysrv', 'inst') == {}
