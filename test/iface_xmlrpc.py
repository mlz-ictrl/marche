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

"""Test for the XMLRPC interface."""

import logging
import xmlrpc.client

from pytest import fixture, raises

from marche.config import Config
from marche.iface.xmlrpc import Interface
from marche.jobs import DEAD
from marche.protocol import PROTO_VERSION, Errors
from test.utils import LogHandler, MockAuthHandler, MockJobHandler

jobhandler = MockJobHandler()
authhandler = MockAuthHandler()
logger = logging.getLogger('testxmlrpc')
logger.addHandler(LogHandler())

# Make waiting for shutdown faster.
Interface.poll_interval = 0.05


@fixture(scope='module')
def xmlrpc_iface(request):  # pylint: disable=unused-argument
    """Create a Marche XMLRPC interface."""
    config = Config()
    config.iface_config['xmlrpc'] = {'host': '127.0.0.1', 'port': '0'}
    iface = Interface(config, jobhandler, authhandler, logger)
    jobhandler.test_interface = iface
    iface.run()
    yield iface
    iface.shutdown()


@fixture()
def proxy(xmlrpc_iface):
    """Create an authenticated XMLRPC proxy."""
    port = xmlrpc_iface.server.server_address[1]
    proxy = xmlrpc.client.ServerProxy(
        'http://test:test@localhost:%d/xmlrpc' % port)
    yield proxy


def test_authentication(xmlrpc_iface):
    port = xmlrpc_iface.server.server_address[1]
    proxy = xmlrpc.client.ServerProxy('http://localhost:%d/xmlrpc' % port)
    assert raises(xmlrpc.client.ProtocolError, proxy.GetVersion)
    proxy = xmlrpc.client.ServerProxy(
        'http://wrong:creds@localhost:%d/xmlrpc' % port)
    assert raises(xmlrpc.client.ProtocolError, proxy.GetVersion)
    proxy = xmlrpc.client.ServerProxy(
        'http://guest:guest@localhost:%d/xmlrpc' % port)
    with raises(xmlrpc.client.Fault) as exc_info:
        proxy.Start('svc.inst')
    assert 'no permission' in exc_info.value.faultString


def test_simple_queries(proxy):
    assert proxy.GetVersion() == str(PROTO_VERSION)
    assert proxy.GetDescription('svc.inst') == 'desc'
    assert set(proxy.GetServices()) == set(['svc.inst', 'svc'])
    assert raises(xmlrpc.client.Fault, proxy.NonexistingMethod)


def test_event_queries(proxy):
    assert proxy.GetStatus('svc.inst') == DEAD
    assert proxy.GetOutput('svc.inst') == ['line1', 'line2']
    assert set(proxy.GetLogs('svc.inst')) == \
        set(['file1:line1\n', 'file1:line2\n',
             'file2:line3\n', 'file2:line4\n'])
    config = proxy.ReceiveConfig('svc.inst')
    assert config[config.index('file1') + 1] == 'line1\nline2\n'
    assert config[config.index('file2') + 1] == 'line3\nline4\n'


def test_commands(proxy):
    assert proxy.Start('svc.inst') is True  # succeeds

    assert proxy.ReloadJobs() is True
    assert jobhandler.test_reloaded

    # wrong arguments
    with raises(xmlrpc.client.Fault) as exc_info:
        proxy.Start()
    assert exc_info.value.faultCode == Errors.EXCEPTION
    assert exc_info.value.faultString.startswith('Unexpected exception: ')

    # errors raised by handler
    with raises(xmlrpc.client.Fault) as exc_info:
        proxy.Stop('svc.inst')
    assert exc_info.value.faultCode == Errors.BUSY
    assert exc_info.value.faultString == 'job is already busy, retry later'

    with raises(xmlrpc.client.Fault) as exc_info:
        proxy.Restart('svc.inst')
    assert exc_info.value.faultCode == Errors.FAULT
    assert exc_info.value.faultString == 'cannot do this'

    with raises(xmlrpc.client.Fault) as exc_info:
        proxy.SendConfig('svc.inst')
    assert exc_info.value.faultCode == Errors.EXCEPTION
    assert exc_info.value.faultString == 'Unexpected exception: no conf files'
