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

"""Test for the miscellaneous other APIs."""

import os
import sys
import json
import time
import socket
import logging

from pytest import raises
from marche.six import StringIO

from marche.protocol import Events, Event, AuthEvent
from marche import utils, colors, loggers

from test.utils import LogHandler

logger = logging.getLogger('testother')
testhandler = LogHandler()
logger.addHandler(testhandler)


def test_event_class():
    assert raises(RuntimeError, Event().serialize)
    assert raises(RuntimeError, Event.unserialize, b'{}')
    assert Event.unserialize(json.dumps({'type': 1423}).encode()) is None

    ev = AuthEvent(success=True)
    serialized = ev.serialize()
    assert Event.unserialize(serialized) == ev

    assert repr(Event()) == '<Event: {}>'


def test_utils(tmpdir):
    utils.ensure_directory(str(tmpdir.join('my', 'sub')))
    assert tmpdir.join('my', 'sub').check(dir=True)

    pidfile = tmpdir.join('marched.pid')
    utils.write_pidfile(str(tmpdir))
    assert pidfile.check(file=True)
    assert pidfile.read() == str(os.getpid())
    utils.remove_pidfile(str(tmpdir))
    assert pidfile.check(exists=False)

    tmpfile = tmpdir.join('tmp')
    tmpfile.write_binary(b'a\xf0b')
    assert utils.read_file(str(tmpfile)) == 'a\xf0b'

    utils.write_file(str(tmpfile), b'a\xf0b')
    assert tmpfile.read_binary() == b'a\xf0b'
    utils.write_file(str(tmpfile), u'a\xf0b')
    assert tmpfile.read_binary() == b'a\xf0b'

    assert utils.extract_loglines(str(tmpdir.join('nope'))) == {}
    tmpdir.join('logfile').write(''.join('a%d\n' % i for i in range(10)))
    tmpdir.join('logfile.1').write(''.join('b%d\n' % i for i in range(10)))
    # broken chain of numbers: not included
    tmpdir.join('logfile.3').write(''.join('c%d\n' % i for i in range(10)))
    logs = utils.extract_loglines(str(tmpdir.join('logfile')), 2)
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
    class Test(object):
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


def test_async_process(tmpdir):
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


def test_colors():
    blue = colors.colorcode('blue')
    reset = colors.colorcode('reset')
    if os.name != 'nt':
        assert blue == '\x1b[34;01m'
        assert reset == '\x1b[39;49;00m'
        assert colors.colorize('blue', 'text') == blue + 'text' + reset
    colors.nocolor()
    assert colors.colorize('blue', 'text') == 'text'


class Unrepr(object):
    """An object whose repr() raises."""

    def __repr__(self):
        raise RuntimeError


def test_loggers(tmpdir):
    logfile_hdlr = loggers.LogfileHandler(str(tmpdir), 'log', dayfmt='first')
    logger = logging.getLogger('testloggers')
    logger.addHandler(loggers.ColoredConsoleHandler(StringIO()))
    logger.addHandler(logfile_hdlr)
    logger.setLevel(logging.DEBUG)

    logger.debug('debüg')
    logger.info('infö')
    logger.warn('wärn')
    logfile_hdlr._dayfmt = 'second'
    logfile_hdlr.rollover_at = time.time() - 2
    logger.error(u'ärror')
    _unrepr = Unrepr()
    try:
        raise ZeroDivisionError('nästy')
    except Exception:
        logger.exception('caught äxception')
        logfile_hdlr.formatter.extended_traceback = False
        logger.exception('caught äxception')

    assert tmpdir.join('log', 'log-first.log').check(file=True)
    lines = tmpdir.join('log', 'log-first.log').readlines()
    assert 'debüg' in lines[0]
    assert 'infö' in lines[1]
    assert 'wärn' in lines[2]
    assert tmpdir.join('log', 'log-second.log').check(file=True)
    lines = tmpdir.join('log', 'log-second.log').readlines()
    assert sum(1 for line in lines if 'cannot be displayed' in line) == 1
    assert sum(1 for line in lines if 'nästy' in line) == 4

    if hasattr(os, 'symlink') and hasattr(tmpdir, 'readlink'):
        assert tmpdir.join('log', 'current').check(link=True)
        assert tmpdir.join('log', 'current').readlink() == 'log-second.log'

    logfile_hdlr.close()
    logger.info('another message, still works')
