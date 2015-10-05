#  -*- coding: utf-8 -*-
# *****************************************************************************
# MLZ server control daemon
# Copyright (c) 2015 by the authors, see LICENSE
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

import threading
import xmlrpclib
import SimpleXMLRPCServer
import base64

from marche.jobs import Busy, Fault
from marche.handler import JobHandler, VOID

BUSY = 1
FAULT = 2
EXCEPTION = 9


class RequestHandler(SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
    rpc_paths = ('/xmlrpc',)

    def log_message(self, fmt, *args):
        self.log.debug('[%s] %s' % (self.client_address[0], fmt % args))

class AuthRequestHandler(RequestHandler):
    USER = 'marche'
    PASSWD = 'marche'

    def do_POST(self):
        auth = base64.b64encode('%s:%s' % (self.USER, self.PASSWD))

        if 'Authorization' not in self.headers:
            self.send_error(401)
            return

        authHeader = self.headers['Authorization'].split()[-1].strip()
        if auth != authHeader:
            self.send_error(401)
            return

        return SimpleXMLRPCServer.SimpleXMLRPCRequestHandler.do_POST(self)


def command(method, is_void):
    def new_method(self, *args):
        try:
            ret = method(self.jobhandler, *args)
            # returning None is not possible in XMLRPC without special options
            return True if is_void else ret
        except Busy as err:
            raise xmlrpclib.Fault(BUSY, str(err))
        except Fault as err:
            raise xmlrpclib.Fault(FAULT, str(err))
        except Exception as err:
            raise xmlrpclib.Fault(EXCEPTION, 'Unexpected exception: %s' % err)
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


class Interface(object):
    '''
    This interface allows remote access via remote procedure calls (RPC)
    over HTTP in the XML format.

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

        | The password for remote authentication.
        | If not password is given, no authentication is used.

    '''

    def __init__(self, config, jobhandler, log):
        self.config = config
        self.jobhandler = jobhandler
        self.log = RequestHandler.log = log.getChild('xmlrpc')

    def run(self):
        port = int(self.config.interface_config['xmlrpc']['port'])
        host = self.config.interface_config['xmlrpc']['host']
        user = self.config.interface_config['xmlrpc']['user']
        passwd = self.config.interface_config['xmlrpc']['passwd']


        requestHandler = RequestHandler
        if passwd:
            self.log.info('Use authentication functionality')
            requestHandler = AuthRequestHandler
            AuthRequestHandler.USER = user
            AuthRequestHandler.PASSWD = passwd

        server = SimpleXMLRPCServer.SimpleXMLRPCServer(
            (host, port), requestHandler=requestHandler)
        server.register_introspection_functions()
        server.register_instance(RPCFunctions(self.jobhandler, self.log))

        thd = threading.Thread(target=self._thread, args=(server,))
        thd.setDaemon(True)
        thd.start()
        self.log.info('listening on %s:%s' % (host, port))

    def _thread(self, server):
        server.serve_forever()
