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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************

import socket
import threading
from collections import OrderedDict
from functools import partial

import requests
from six import iteritems
from six.moves import xmlrpc_client as xmlrpc

from marche.gui.qt import QThread, pyqtSignal
from marche.gui.util import loadSetting
from marche.jobs import NOT_AVAILABLE


class PollThread(QThread):
    # service, instance, status, error info
    newData = pyqtSignal(object, object, int, object)
    newBulkData = pyqtSignal(object)

    def __init__(self, host, port, user=None, passwd=None, loopDelay=3.0,
                 parent=None):
        QThread.__init__(self, parent)
        self._loopDelay = loopDelay
        self._creds = (host, port, user, passwd)
        self._client = None
        # use an event instead of sleep() to be able to interrupt
        self._event = threading.Event()
        self.running = True

    def run(self):
        self._client = Client(*self._creds)
        while self.running:
            if self._client is None:
                break  # thread has been deleted

            if self._client.version >= 3:
                try:
                    services = self._client.getAllServiceInfo()
                except Exception:
                    self.newBulkData.emit(None)
                else:
                    self.newBulkData.emit(services)

            else:
                try:
                    services = self._client.getServices()
                except Exception:
                    services = OrderedDict()
                    self.newData.emit(None, None, NOT_AVAILABLE, '')

                for service, instances in iteritems(services):
                    for instance in instances:
                        self.poll(service, instance)

            self._event.wait(self._loopDelay)

    def poll(self, service, instance):
        try:
            status = self._client.getServiceStatus(service, instance)
            info = None
        except Exception as err:
            status, info = NOT_AVAILABLE, str(err)
        self.newData.emit(service, instance, status, info)


class ClientError(Exception):
    def __init__(self, code, string):
        self.code = code
        Exception.__init__(self, string)


class HttpTransport(xmlrpc.Transport):
    def make_connection(self, host):
        retval = xmlrpc.Transport.make_connection(self, host)
        self._connection[1].timeout = 2.0
        return retval


class ServerProxy(xmlrpc.ServerProxy):
    def __del__(self):
        self('close')()


class JsonProxy(object):
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


class Client(object):
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
        except Exception as e:
            self._proxy = ServerProxy(url, transport=HttpTransport())

        self._lock = threading.Lock()
        self._pollThread = None
        self.version = self.getVersion()

    def stopPoller(self, join=False):
        if self._pollThread:
            self._pollThread.running = False
            self._pollThread._client = None
            self._pollThread._event.set()
            if join:
                self._pollThread.wait()

    def startPoller(self, slot, slot2):
        self._pollThread = PollThread(self.host,
                                      self.port,
                                      self.user,
                                      self.passwd,
                                      loadSetting('pollInterval', 3,
                                                  valtype=float))
        self._pollThread.newData.connect(slot)
        self._pollThread.newBulkData.connect(slot2)
        self._pollThread.start()

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
            for service, svcinfo in iteritems(services):
                for instance, instinfo in iteritems(svcinfo['instances']):
                    result[service, instance] = instinfo['desc']
            return result
        with self._lock:
            for service, instances in iteritems(services):
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
            raise ClientError(99, 'marched: %s' % e)
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)
        if self._pollThread:
            self._pollThread.poll(service, instance)

    def stopService(self, service, instance=''):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                self._proxy.Stop(servicePath)
        except socket.error as e:
            raise ClientError(99, 'marched: %s' % e)
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)
        if self._pollThread:
            self._pollThread.poll(service, instance)

    def restartService(self, service, instance=''):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                self._proxy.Restart(servicePath)
        except socket.error as e:
            raise ClientError(99, 'marched: %s' % e)
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)
        if self._pollThread:
            self._pollThread.poll(service, instance)

    def getServiceStatus(self, service, instance=''):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                return self._proxy.GetStatus(servicePath)
        except socket.error as e:
            raise ClientError(99, 'marched: %s' % e)
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)

    def getServiceOutput(self, service, instance=''):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                return self._proxy.GetOutput(servicePath)
        except socket.error as e:
            raise ClientError(99, 'marched: %s' % e)
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)

    def getServiceLogs(self, service, instance=''):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                return self._proxy.GetLogs(servicePath)
        except socket.error as e:
            raise ClientError(99, 'marched: %s' % e)
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)

    def getVersion(self):
        with self._lock:
            return int(self._proxy.GetVersion().strip('v')[:1])

    def receiveServiceConfig(self, service, instance=''):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                return self._proxy.ReceiveConfig(servicePath)
        except socket.error as e:
            raise ClientError(99, 'marched: %s' % e)
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)

    def sendServiceConfig(self, service, instance='', data=None):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                self._proxy.SendConfig([servicePath] + (data or []))
        except socket.error as e:
            raise ClientError(99, 'marched: %s' % e)
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)
