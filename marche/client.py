#  -*- coding: utf-8 -*-
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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************

import socket
import threading
import xmlrpc.client
from collections import OrderedDict
from functools import partial

import requests


class ClientError(Exception):
    def __init__(self, code, string):
        self.code = code
        Exception.__init__(self, string)


class HttpTransport(xmlrpc.client.Transport):
    def make_connection(self, host):
        retval = xmlrpc.client.Transport.make_connection(self, host)
        self._connection[1].timeout = 2.0
        return retval


class ServerProxy(xmlrpc.client.ServerProxy):
    def __del__(self):
        self('close')()


class JsonProxy:
    def __init__(self, url):
        self.url = url
        self.ses = requests.Session()

        result = self.ses.post(self.url, json={
            'jsonrpc': '2.0',
            'method': 'GetVersion',
            'id': 1,
        })
        if result.headers.get('content-type') != 'application/json':
            raise RuntimeError('not a jsonrpc server')

    def _request(self, method, *args):
        result = self.ses.post(self.url, json={
            'jsonrpc': '2.0',
            'method': method,
            'id': 1,
            'params': args or None,
        })
        if result.status_code != 200 or result.headers.get('content-type') != \
           'application/json':
            raise ClientError(result.status_code, 'not a successful request')
        result = result.json()
        if result.get('error'):
            raise ClientError(result['error']['code'], result['error']['message'])
        return result['result']

    def __getattr__(self, method):
        return partial(self._request, method)


class Client:
    def __init__(self, host, port, user=None, passwd=None):
        self.host = host
        self.port = port
        self.user = user
        self.passwd = passwd

        if user is not None and passwd is not None:
            url = 'http://%s:%s@%s:%s/xmlrpc' % (user, passwd, host, port)
        else:
            url = 'http://%s:%s/xmlrpc' % (host, port)

        try:
            self._proxy = JsonProxy(url)
        except Exception:
            self._proxy = ServerProxy(url, transport=HttpTransport())

        self._lock = threading.Lock()
        self._pollThread = None
        self.version = self.getVersion()

    def reloadJobs(self):
        self.stopPoller(True)
        with self._lock:
            self._proxy.ReloadJobs()
        self.version = self.getVersion()

    def getServices(self):
        with self._lock:
            lst = self._proxy.GetServices()

        result = OrderedDict()
        singleJobs = []
        for entry in lst:
            parts = entry.split('.')

            if len(parts) > 1:
                if parts[0] not in result:
                    result[parts[0]] = []
                result[parts[0]].append(parts[1])
            else:
                singleJobs.append(parts[0])

        # sort job instances
        for entry in result.values():
            entry.sort()

        # sort single jobs to the end
        for entry in singleJobs:
            if entry in result:
                result[entry].append('')
            else:
                result[entry] = ['']

        return result

    def getServiceDescriptions(self, services):
        result = {}
        if self.version >= 3:
            services = self.getAllServiceInfo()
            for service, svcinfo in services.items():
                for instance, instinfo in svcinfo['instances'].items():
                    result[service, instance] = instinfo['desc']
            return result
        with self._lock:
            for service, instances in services.items():
                for instance in instances:
                    path = self.getServicePath(service, instance)
                    result[service, instance] = \
                        self._proxy.GetDescription(path)
        return result

    def getAllServiceInfo(self):
        # New in protocol version 3.
        with self._lock:
            return self._proxy.GetAllServiceInfo()

    def getServicePath(self, service, instance):
        return '%s.%s' % (service, instance) if instance else service

    def startService(self, service, instance=''):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                self._proxy.Start(servicePath)
        except socket.error as e:
            raise ClientError(99, 'marched: %s' % e) from None
        except xmlrpc.client.Fault as f:
            raise ClientError(f.faultCode, f.faultString) from None
        if self._pollThread:
            self._pollThread.poll(service, instance)

    def stopService(self, service, instance=''):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                self._proxy.Stop(servicePath)
        except socket.error as e:
            raise ClientError(99, 'marched: %s' % e) from None
        except xmlrpc.client.Fault as f:
            raise ClientError(f.faultCode, f.faultString) from None
        if self._pollThread:
            self._pollThread.poll(service, instance)

    def restartService(self, service, instance=''):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                self._proxy.Restart(servicePath)
        except socket.error as e:
            raise ClientError(99, 'marched: %s' % e) from None
        except xmlrpc.client.Fault as f:
            raise ClientError(f.faultCode, f.faultString) from None
        if self._pollThread:
            self._pollThread.poll(service, instance)

    def getServiceStatus(self, service, instance=''):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                return self._proxy.GetStatus(servicePath)
        except socket.error as e:
            raise ClientError(99, 'marched: %s' % e) from None
        except xmlrpc.client.Fault as f:
            raise ClientError(f.faultCode, f.faultString) from None

    def getServiceOutput(self, service, instance=''):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                return self._proxy.GetOutput(servicePath)
        except socket.error as e:
            raise ClientError(99, 'marched: %s' % e) from None
        except xmlrpc.client.Fault as f:
            raise ClientError(f.faultCode, f.faultString) from None

    def getServiceLogs(self, service, instance=''):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                return self._proxy.GetLogs(servicePath)
        except socket.error as e:
            raise ClientError(99, 'marched: %s' % e) from None
        except xmlrpc.client.Fault as f:
            raise ClientError(f.faultCode, f.faultString) from None

    def getVersion(self):
        with self._lock:
            return int(self._proxy.GetVersion().strip('v')[:1])

    def receiveServiceConfig(self, service, instance=''):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                return self._proxy.ReceiveConfig(servicePath)
        except socket.error as e:
            raise ClientError(99, 'marched: %s' % e) from None
        except xmlrpc.client.Fault as f:
            raise ClientError(f.faultCode, f.faultString) from None

    def sendServiceConfig(self, service, instance='', data=None):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                self._proxy.SendConfig([servicePath] + (data or []))
        except socket.error as e:
            raise ClientError(99, 'marched: %s' % e) from None
        except xmlrpc.client.Fault as f:
            raise ClientError(f.faultCode, f.faultString) from None
