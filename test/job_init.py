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

"""Test for the init script job."""

import sys
import logging

from marche.jobs import RUNNING
from marche.jobs.init import Job

from test.utils import wait

logger = logging.getLogger('testinit')

SCRIPT = '''\
import sys
print(sys.argv[1])
print(sys.argv[2])
'''


def test_job(tmpdir):
    scriptfile = tmpdir.join('script.py')
    scriptfile.write(SCRIPT)

    Job.INIT_BASE = sys.executable + ' ' + str(scriptfile) + ' '

    config = {
        'script': 'foo',
    }

    job = Job('init', 'name', config, logger, lambda event: None)
    real_script = job.script
    assert not job.check()
    job.script = str(scriptfile)
    assert job.check()
    job.script = real_script

    job.init()

    assert job.get_services() == [('foo', '')]

    assert job.service_status('foo', '') == (RUNNING, '')

    job.start_service('foo', '')
    wait(100, lambda: job.service_status('foo', '')[0] == RUNNING)
    out = job.service_output('foo', '')
    assert out[0].startswith('$ ') and out[0].endswith(' start\n')
    assert out[1:] == ['foo\n', 'start\n']

    job.stop_service('foo', '')
    wait(100, lambda: job.service_status('foo', '')[0] == RUNNING)
    out = job.service_output('foo', '')
    assert out[-3].startswith('$ ') and out[-3].endswith(' stop\n')
    assert out[-2:] == ['foo\n', 'stop\n']

    job.restart_service('foo', '')
    wait(100, lambda: job.service_status('foo', '')[0] == RUNNING)
    out = job.service_output('foo', '')
    assert out[-3].startswith('$ ') and out[-3].endswith(' restart\n')
    assert out[-2:] == ['foo\n', 'restart\n']
