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

"""Test for the Tango server job."""

import logging

from marche.jobs.tangosrv import Job

logger = logging.getLogger('testtangosrv')

DEFAULT = '''\
# comment here

export TANGO_RES_DIR=%(tmpdir)s
'''

RESFILE = '''\
# Some resoure file...

CLASS/Mysrv/DEFAULT/devpath:            /dev/path
CLASS/Mysrv/DEFAULT/inoffset:           0
CLASS/Mysrv/DEFAULT/outoffset:          0

Mysrv/host/device: \\
    test/mysrv/dev1 \\
    test/mysrv/dev2

Mysrvtest/localhost/device: test/mysrv/dev3

# ---
test/mysrv/dev1/min:                    -45.0  # some comment
test/mysrv/dev1/max:                    40.0
test/mysrv/dev1/unit:                   deg

# ---
test/mysrv/dev2/min:                    "0"
test/mysrv/dev2/max:                    "40"
test/mysrv/dev2/units:                  deg, rad, grd

cmds/mysrv/null/value:                  5
'''


def test_job(tmpdir):
    defaultfile = tmpdir.join('default')
    defaultfile.write(DEFAULT % {'tmpdir': str(tmpdir)})

    Job.INIT_BASE = str(tmpdir)
    Job.DEFAULT_FILE = str(defaultfile)

    job = Job('tangosrv', 'name', {'srvname': 'Mysrv'},
              logger, lambda event: None)
    job.init()

    assert job.get_services() == [('tango-server-mysrv', '')]

    devices = []
    properties = []

    def new_add_device(_self, _db, name, cls, srv):
        devices.append((name, cls, srv))

    def new_add_property(_self, _db, dev, name, vals, _devs):
        properties.append((dev, name, vals))

    Job._connect_db = lambda self: None
    Job._add_device = new_add_device
    Job._add_property = new_add_property

    job.send_config('tango-server-mysrv', 'inst', 'Mysrv.res', RESFILE)

    assert devices == [('test/mysrv/dev1', 'mysrv', 'Mysrv/test_host'),
                       ('test/mysrv/dev2', 'mysrv', 'Mysrv/test_host')]
    assert properties == [
        ('class/mysrv/default', 'devpath', ['/dev/path']),
        ('class/mysrv/default', 'inoffset', ['0']),
        ('class/mysrv/default', 'outoffset', ['0']),
        ('test/mysrv/dev1', 'min', ['-45.0']),
        ('test/mysrv/dev1', 'max', ['40.0']),
        ('test/mysrv/dev1', 'unit', ['deg']),
        ('test/mysrv/dev2', 'min', ['0']),
        ('test/mysrv/dev2', 'max', ['40']),
        ('test/mysrv/dev2', 'units', ['deg', 'rad', 'grd'])
    ]
