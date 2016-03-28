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

""".. index:: xmlrpc; interface

Legacy XMLRPC interface
-----------------------

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
"""

import base64
import threading

from six import iteritems
from six.moves import xmlrpc_client, xmlrpc_server

from marche.jobs import Busy, Fault
from marche.iface.base import Interface as BaseInterface
from marche.auth import AuthFailed
from marche.protocol import PROTO_VERSION
from marche.permission import ClientInfo, ADMIN

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

        header = self.headers['Authorization'].split()[-1].strip()
        decoded = base64.b64decode(header.encode()).decode('utf-8')
        try:
            user, passwd = decoded.split(':', 1)
            # Not using the returned client info.
            self.handler.authenticate(user, passwd)
        except (ValueError, AuthFailed):
            self.send_error(401)
            return

        return xmlrpc_server.SimpleXMLRPCRequestHandler.do_POST(self)


def command(method):
    def new_method(self, *args):
        try:
            ret = method(self, *args)
            return True if ret is None else ret
        except Busy as err:
            raise xmlrpc_client.Fault(BUSY, str(err))
        except Fault as err:
            raise xmlrpc_client.Fault(FAULT, str(err))
        except Exception as err:
            raise xmlrpc_client.Fault(EXCEPTION, 'Unexpected exception: %s' % err)
    new_method.__name__ = method.__name__
    return new_method


class RPCFunctions(object):

    def __init__(self, jobhandler, log, expect_event):
        self.jobhandler = jobhandler
        self.log = log
        self.expect_event = expect_event
        # We don't know the current user's level, therefore always assign
        # the highest user level.
        self.client = ClientInfo(ADMIN)

    def _split_name(self, name):
        if '.' in name:
            return name.split('.', 1)
        else:
            return name, ''

    @command
    def ReloadJobs(self):
        self.jobhandler.trigger_reload()

    @command
    def GetVersion(self):
        return str(PROTO_VERSION)

    @command
    def GetDescription(self, name):
        return ''

    @command
    def GetServices(self):
        list_event = self.expect_event(
            lambda: self.jobhandler.request_service_list(self.client))
        result = []
        for svcname, instances in iteritems(list_event.services):
            for instance in instances:
                if not instance:
                    result.append(svcname)
                else:
                    result.append(svcname + '.' + instance)
        return result

    @command
    def GetStatus(self, name):
        status_event = self.expect_event(
            lambda: self.jobhandler.request_service_status(
                self.client, *self._split_name(name)))
        return status_event.state

    @command
    def GetOutput(self, name):
        out_event = self.expect_event(
            lambda: self.jobhandler.request_control_output(
                self.client, *self._split_name(name)))
        return out_event.content

    @command
    def GetLogs(self, name):
        log_event = self.expect_event(
            lambda: self.jobhandler.request_logfiles(self.client,
                                                     *self._split_name(name)))
        ret = []
        for name, contents in iteritems(log_event.files):
            for line in contents.splitlines(True):
                ret.append(name + ':' + line)
        return ret

    @command
    def ReceiveConfig(self, name):
        config_event = self.expect_event(
            lambda: self.jobhandler.request_conffiles(self.client,
                                                      *self._split_name(name)))
        ret = []
        for name, contents in iteritems(config_event.files):
            ret.append(name)
            ret.append(contents)
        return ret

    @command
    def SendConfig(self, data):
        service, instance = self._split_name(data[0])
        self.jobhandler.send_conffile(self.client, service, instance,
                                      data[1], data[2])

    @command
    def Start(self, name):
        self.jobhandler.start_service(self.client, *self._split_name(name))

    @command
    def Stop(self, name):
        self.jobhandler.stop_service(self.client, *self._split_name(name))

    @command
    def Restart(self, name):
        self.jobhandler.restart_service(self.client, *self._split_name(name))


class Interface(BaseInterface):

    iface_name = 'xmlrpc'
    needs_events = True
    poll_interval = 0.5

    def init(self):
        self._lock = threading.RLock()
        self._events = []
        RequestHandler.log = self.log

    def run(self):
        port = int(self.config.get('port', 8124))
        host = self.config.get('host', '0.0.0.0')

        request_handler = RequestHandler
        if self.authhandler.needs_authentication():
            self.log.info('using authentication functionality')
            AuthRequestHandler.handler = self.authhandler
            request_handler = AuthRequestHandler

        self.server = xmlrpc_server.SimpleXMLRPCServer(
            (host, port), requestHandler=request_handler)
        self.server.register_introspection_functions()
        self.server.register_instance(RPCFunctions(self.jobhandler, self.log,
                                                   self.expect_event))

        thd = threading.Thread(target=self._thread)
        thd.setDaemon(True)
        thd.start()
        self.log.info('listening on %s:%s' % (host, port))

    def shutdown(self):
        self.server.shutdown()

    def expect_event(self, callback):
        # We hold the RLock, and acquire it again during emit_event(), to
        # ensure only events emitted during execution of the callback are
        # added to the events list.
        with self._lock:
            self._events = events = []
            callback()
            self._events = None
            return events[0]

    def emit_event(self, event):
        with self._lock:
            if self._events is not None:
                self._events.append(event)

    def _thread(self):
        self.server.serve_forever(poll_interval=self.poll_interval)
