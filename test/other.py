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

"""Test for the miscellaneous other APIs."""

import logging
import os
import socket
import sys

from marche import utils
from marche.protocol import Response
from test.utils import LogHandler

logger = logging.getLogger('testother')
testhandler = LogHandler()
logger.addHandler(testhandler)


def test_event_class():
    assert repr(Response()) == '<Response: {}>'


def test_utils(tmp_path):
    tmpfile = tmp_path / 'tmp'
    tmpfile.write_bytes(b'a\xf0b')
    assert utils.read_file(tmpfile) == 'a\xf0b'

    utils.write_file(tmpfile, b'a\xf0b')
    assert tmpfile.read_bytes() == b'a\xf0b'
    utils.write_file(tmpfile, 'a\xf0b')
    assert tmpfile.read_bytes() == b'a\xf0b'

    assert utils.extract_loglines(tmp_path / 'nope') == {}
    (tmp_path / 'logfile').write_text(''.join('a%d\n' % i for i in range(10)))
    (tmp_path / 'logfile.1').write_text(''.join('b%d\n' % i for i in range(10)))
    # broken chain of numbers: not included
    (tmp_path / 'logfile.3').write_text(''.join('c%d\n' % i for i in range(10)))
    logs = utils.extract_loglines(tmp_path / 'logfile', 2)
    assert len(logs) == 2
    for key, value in logs.items():
        if key.endswith('logfile'):
            assert value == 'a8\na9\n'
        elif key.endswith('logfile.1'):
            assert value == 'b8\nb9\n'
        else:
            assert False, 'unexpected key'

    fqdn = socket.getfqdn('localhost')
    assert utils.normalize_addr('localhost', 147) == (fqdn, '147')
    assert utils.normalize_addr('localhost:32', 147) == (fqdn, '32')


def test_lazy_property():
    class Test:
        @utils.lazy_property
        def prop(self):
            called.append('prop')
            return 42

    called = []
    t = Test()
    assert t.prop == 42
    assert t.prop == 42
    assert called == ['prop']
    assert isinstance(Test.prop, utils.lazy_property)


def test_async_process():
    code = '''if True:
    import sys
    sys.stdout.write("stdout\\n")
    sys.stderr.write("stderr\\n")
    sys.exit(3)
    '''
    proc = utils.AsyncProcess(42, logger, [sys.executable, '-S', '-c', code],
                              sh=False)
    proc.start()
    proc.join()
    assert proc.stderr == ['stderr\n']
    assert proc.stdout == ['stdout\n']
    assert proc.retcode == 3
    assert proc.done


class Unrepr:
    """An object whose repr() raises."""

    def __repr__(self):
        raise RuntimeError
