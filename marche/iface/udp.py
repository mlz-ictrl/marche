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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************

""".. index:: udp; interface

.. _udp-iface:

UDP interface
-------------

This interface allows discovery of running Marche daemons.  It does not allow
controlling services, it just responds to a "ping"-type packet to let clients
know there is a Marche daemon running on the host.  This is especially useful
with UDP broadcasts that search all hosts within a network.

.. describe:: [interfaces.udp]

   The configuration settings that can be set within the **interfaces.udp**
   section are:

   .. describe:: port

      **Default:** 11691

      The port to listen for UDP packets.

   .. describe:: host

      **Default:** 0.0.0.0

      The host to bind to.  The broadcast option will be set on the socket.
"""

import socket
import threading

from marche.protocol import PROTO_VERSION
from marche.iface.base import Interface as BaseInterface

UDP_PORT = 11691


class Interface(BaseInterface):

    iface_name = 'udp'
    needs_events = False

    def run(self):
        host = self.config.get('host', '0.0.0.0')
        port = int(self.config.get('port', UDP_PORT))
        self.server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server.bind((host, port))
        self.log.info('listening on %s:%s' % (host, port))
        self._stoprequest = False
        thread = threading.Thread(target=self._thread, args=())
        thread.setDaemon(True)
        thread.start()

    def shutdown(self):
        self._stoprequest = True

    def _thread(self):
        reply = ('PONG %s' % PROTO_VERSION).encode()
        while not self._stoprequest:
            data, addr = self.server.recvfrom(1024)
            if data == b'PING':
                self.server.sendto(reply, addr)
