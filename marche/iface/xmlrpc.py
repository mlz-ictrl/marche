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

from marche.jobs import Busy, Fault
from marche.handler import JobHandler, VOID

BUSY = 1
FAULT = 2
EXCEPTION = 9


class RequestHandler(SimpleXMLRPCServer.SimpleXMLRPCRequestHandler):
    rpc_paths = ('/xmlrpc',)

    def log_message(self, fmt, *args):
        self.log.debug('[%s] %s' % (self.client_address[0], fmt % args))


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
    setattr(RPCFunctions, mname, command(method, method.outtype == VOID))


class Interface(object):

    def __init__(self, config, jobhandler, log):
        self.config = config
        self.jobhandler = jobhandler
        self.log = RequestHandler.log = log.getChild('xmlrpc')

    def run(self):
        port = int(self.config.interface_config['xmlrpc']['port'])
        host = self.config.interface_config['xmlrpc']['host']
        server = SimpleXMLRPCServer.SimpleXMLRPCServer(
            (host, port), requestHandler=RequestHandler)
        server.register_introspection_functions()
        server.register_instance(RPCFunctions(self.jobhandler, self.log))

        thd = threading.Thread(target=self._thread, args=(server,))
        thd.setDaemon(True)
        thd.start()
        self.log.info('listening on %s:%s' % (host, port))

    def _thread(self, server):
        server.serve_forever()
