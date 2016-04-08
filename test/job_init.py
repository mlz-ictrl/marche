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

from test.utils import job_call_check

logger = logging.getLogger('testinit')

SCRIPT = '''\
import sys
print(sys.argv[1])
print(sys.argv[2])
'''


def test_job(tmpdir):
    scriptfile = tmpdir.join('script.py')
    scriptfile.write(SCRIPT)

    Job.INIT_BASE = sys.executable + ' -S ' + str(scriptfile) + ' '

    config = {
        'script': 'foo',
        'description': 'descr',
    }

    job = Job('init', 'name', config, logger, lambda event: None)
    real_script = job.script
    assert not job.check()
    job.script = str(scriptfile)
    assert job.check()

    job.script = real_script
    job.init()

    assert job.get_services() == [('foo', '')]
    assert job.service_description('foo', '') == 'descr'
    assert job.service_status('foo', '') == (RUNNING, '')
    job_call_check(job, 'foo', '', 'action', ['foo', 'action'])
