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

"""Test for the main daemon."""

import sys

from marche.daemon import Daemon
from marche.iface.base import Interface as BaseInterface

sys.modules['marche.iface.broken'] = sys.modules[__name__]


class Interface(BaseInterface):
    """A broken interface (run() raises NotImplementedError)."""


class MyDaemon(Daemon):
    def wait(self):
        pass


TEST_CONFIG = '''\
[general]
interfaces = udp, broken, nonexisting

[interface.udp]
port = 0

[job.test]
type = process
'''


def test_daemon(tmp_path):
    (tmp_path / 'marche.conf').write_text(TEST_CONFIG % {'tmpdir': tmp_path})
    assert MyDaemon().run(['-c', str(tmp_path)]) == 0


TEST_CONFIG_1 = '''\
[general]
interfaces =
'''

TEST_CONFIG_2 = '''\
[general]
interfaces = xmlrpc
'''


def test_errors(tmp_path):
    (tmp_path / 'marche.conf').write_text(TEST_CONFIG_1 % {'tmpdir': tmp_path})
    assert MyDaemon().run(['-c', str(tmp_path)]) == 1

    (tmp_path / 'marche.conf').write_text(TEST_CONFIG_2 % {'tmpdir': tmp_path})
    assert MyDaemon().run(['-c', str(tmp_path)]) == 1
