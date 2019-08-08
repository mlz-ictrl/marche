#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2019 by the authors, see LICENSE
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
import socket

from marche.config import Config
from marche.iface.udp import Interface
from marche.protocol import PROTO_VERSION
from test.utils import LogHandler, MockAuthHandler, MockJobHandler

jobhandler = MockJobHandler()
authhandler = MockAuthHandler()
logger = logging.getLogger('testudp')
logger.addHandler(LogHandler())


def test_interface():
    config = Config()
    config.iface_config['udp'] = {'host': '127.0.0.1', 'port': '0'}
    iface = Interface(config, jobhandler, authhandler, logger)
    iface.run()

    port = iface.server.getsockname()[1]
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.sendto(b'PING', ('127.0.0.1', port))
    reply = ('PONG %s deadcafe' % PROTO_VERSION).encode()
    assert client.recvfrom(1024) == (reply, ('127.0.0.1', port))

    iface.shutdown()
