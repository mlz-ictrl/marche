#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2022 by the authors, see LICENSE
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

This interface allows controlling services via remote procedure calls (RPC)
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
import xmlrpc.client
import xmlrpc.server

from marche.auth import AuthFailed
from marche.iface.base import Interface as BaseInterface
from marche.jobs import Busy, Fault
from marche.permission import DISPLAY, ClientInfo
from marche.protocol import PROTO_VERSION, Errors


class AuthRequestHandler(xmlrpc.server.SimpleXMLRPCRequestHandler):
    rpc_paths = ('/xmlrpc',)
    needs_auth = False
    unauth_level = DISPLAY

    def log_message(self, fmt, *args):
        self.log.debug('[%s] %s' % (self.client_address[0], fmt % args))

    def do_POST(self):
        self.client_info = ClientInfo(self.unauth_level)

        # Backwards compatibility: if we *can* auth, we make it required.
        if self.needs_auth and 'Authorization' not in self.headers:
            self.send_error(401)
            return

        header = self.headers['Authorization'].split()[-1].strip()
        decoded = base64.b64decode(header.encode()).decode('utf-8')
        try:
            user, passwd = decoded.split(':', 1)
            self.client_info = self.authhandler.authenticate(user, passwd)
        except (ValueError, AuthFailed):
            self.send_error(401)
            return

        return xmlrpc.server.SimpleXMLRPCRequestHandler.do_POST(self)

    def _dispatch(self, method, params):
        try:
            func = getattr(self.server.instance, method)
        except AttributeError:
            raise Exception('method "%s" is not supported' % method)
        return func(self.client_info, *params)


def command(method):
    def new_method(self, *args):
        try:
            ret = method(self, *args)
            return True if ret is None else ret
        except Busy as err:
            raise xmlrpc.client.Fault(Errors.BUSY, str(err))
        except Fault as err:
            raise xmlrpc.client.Fault(Errors.FAULT, str(err))
        except Exception as err:
            raise xmlrpc.client.Fault(Errors.EXCEPTION,
                                      'Unexpected exception: %s' % err)
    new_method.__name__ = method.__name__
    return new_method


class RPCFunctions(object):

    def __init__(self, jobhandler, log):
        self.jobhandler = jobhandler
        self.log = log

    def _split_name(self, name):
        if '.' in name:
            return name.split('.', 1)
        return name, ''

    @command
    def ReloadJobs(self, client_info):
        self.jobhandler.trigger_reload()

    @command
    def GetVersion(self, client_info):
        return str(PROTO_VERSION)

    @command
    def GetServices(self, client_info):
        list_event = self.jobhandler.request_service_list(client_info)
        result = []
        for svcname, info in list_event.services.items():
            for instance in info['instances']:
                if not instance:
                    result.append(svcname)
                else:
                    result.append(svcname + '.' + instance)
        return result

    @command
    def GetAllServiceInfo(self, client_info):
        list_event = self.jobhandler.request_service_list(client_info)
        return dict(list_event.services)

    @command
    def GetDescription(self, client_info, name):
        return self.jobhandler.get_service_description(
            client_info, *self._split_name(name))

    @command
    def GetStatus(self, client_info, name):
        status_event = self.jobhandler.request_service_status(
            client_info, *self._split_name(name))
        return status_event.state

    @command
    def GetOutput(self, client_info, name):
        out_event = self.jobhandler.request_control_output(
            client_info, *self._split_name(name))
        return out_event.content

    @command
    def GetLogs(self, client_info, name):
        log_event = self.jobhandler.request_logfiles(
            client_info, *self._split_name(name))
        ret = []
        for fname, contents in log_event.files.items():
            for line in contents.splitlines(True):
                ret.append(fname + ':' + line)
        return ret

    @command
    def ReceiveConfig(self, client_info, name):
        config_event = self.jobhandler.request_conffiles(
            client_info, *self._split_name(name))
        ret = []
        for fname, contents in config_event.files.items():
            ret.append(fname)
            ret.append(contents)
        return ret

    @command
    def SendConfig(self, client_info, data):
        service, instance = self._split_name(data[0])
        self.jobhandler.send_conffile(client_info, service, instance,
                                      data[1], data[2])

    @command
    def Start(self, client_info, name):
        self.jobhandler.start_service(client_info, *self._split_name(name))

    @command
    def Stop(self, client_info, name):
        self.jobhandler.stop_service(client_info, *self._split_name(name))

    @command
    def Restart(self, client_info, name):
        self.jobhandler.restart_service(client_info, *self._split_name(name))


class Interface(BaseInterface):

    iface_name = 'xmlrpc'
    needs_events = False
    poll_interval = 0.5

    def init(self):
        AuthRequestHandler.log = self.log

    def run(self):
        port = int(self.config.get('port', 8124))
        host = self.config.get('host', '0.0.0.0')

        AuthRequestHandler.authhandler = self.authhandler
        AuthRequestHandler.unauth_level = self.jobhandler.unauth_level
        AuthRequestHandler.needs_auth = self.authhandler.needs_authentication()

        self.server = xmlrpc.server.SimpleXMLRPCServer(
            (host, port), requestHandler=AuthRequestHandler)
        self.server.register_instance(RPCFunctions(self.jobhandler, self.log))

        thd = threading.Thread(target=self._thread)
        thd.setDaemon(True)
        thd.start()
        self.log.info('listening on %s:%s' % (host, port))

    def shutdown(self):
        self.server.shutdown()

    def _thread(self):
        self.server.serve_forever(poll_interval=self.poll_interval)
