#  -*- coding: utf-8 -*-
# *****************************************************************************
# MLZ server control daemon
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

""".. index:: xmlrpc; interface

XMLRPC interface
----------------

This interface allows controlling sservice via remote procedure calls (RPC)
over HTTP in the XML format.  This is the main interface of Marche and should
always be enabled.

.. describe:: [interfaces.xmlrpc]

   The configuration settings that can be set within the **interfaces.xmlrpc**
   section are:

   .. describe:: port

      **Default:** 8124

      The port to listen for xmlrpc requests.

   .. describe:: host

      **Default:** 0.0.0.0

      The host to bind to.

   .. describe:: user

      **Default:** marche

      The user for remote authentication.

   .. describe:: passwd

      **Default:** None

      The password for remote authentication.  If not password is given, no
      authentication is used.
"""

import base64
import threading

from marche.six.moves import xmlrpc_client, xmlrpc_server

from marche.jobs import Busy, Fault
from marche.iface.base import Interface as BaseInterface
from marche.handler import JobHandler, VOID

BUSY = 1
FAULT = 2
EXCEPTION = 9


class RequestHandler(xmlrpc_server.SimpleXMLRPCRequestHandler):
    rpc_paths = ('/xmlrpc',)

    def log_message(self, fmt, *args):
        self.log.debug('[%s] %s' % (self.client_address[0], fmt % args))


class AuthRequestHandler(RequestHandler):
    encoded_auth = ''

    def do_POST(self):
        if 'Authorization' not in self.headers:
            self.send_error(401)
            return

        authHeader = self.headers['Authorization'].split()[-1].strip()
        if authHeader != self.encoded_auth:
            self.send_error(401)
            return

        return xmlrpc_server.SimpleXMLRPCRequestHandler.do_POST(self)


def command(method, is_void):
    def new_method(self, *args):
        try:
            ret = method(self.jobhandler, *args)
            # returning None is not possible in XMLRPC without special options
            return True if is_void else ret
        except Busy as err:
            raise xmlrpc_client.Fault(BUSY, str(err))
        except Fault as err:
            raise xmlrpc_client.Fault(FAULT, str(err))
        except Exception as err:
            raise xmlrpc_client.Fault(EXCEPTION, 'Unexpected exception: %s' % err)
    new_method.__name__ = method.__name__
    return new_method


class RPCFunctions(object):

    def __init__(self, jobhandler, log):
        self.jobhandler = jobhandler
        self.log = log

    for mname in dir(JobHandler):
        method = getattr(JobHandler, mname)
        if not hasattr(method, 'is_command'):
            continue
        locals()[mname] = command(method, method.outtype == VOID)


class Interface(BaseInterface):

    iface_name = 'xmlrpc'

    def init(self):
        RequestHandler.log = self.log

    def run(self):
        port = int(self.config['port'])
        host = self.config['host']
        user = self.config['user']
        passwd = self.config['passwd']

        request_handler = RequestHandler
        if passwd:
            self.log.info('using authentication functionality')
            request_handler = AuthRequestHandler
            try:
                enc_auth = base64.b64encode(('%s:%s' % (user, passwd))
                                            .encode('utf-8')).decode().strip()
            except UnicodeError:
                self.log.error('could not encode user/password')
            else:
                AuthRequestHandler.encoded_auth = enc_auth

        server = xmlrpc_server.SimpleXMLRPCServer(
            (host, port), requestHandler=request_handler)
        server.register_introspection_functions()
        server.register_instance(RPCFunctions(self.jobhandler, self.log))

        thd = threading.Thread(target=self._thread, args=(server,))
        thd.setDaemon(True)
        thd.start()
        self.log.info('listening on %s:%s' % (host, port))

    def _thread(self, server):
        server.serve_forever()
