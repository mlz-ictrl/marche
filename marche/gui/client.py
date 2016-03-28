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

import time
import threading
from collections import OrderedDict

from PyQt4.QtCore import QThread, pyqtSignal

from six import iteritems
from six.moves import xmlrpc_client as xmlrpc

from marche.jobs import NOT_AVAILABLE
from marche.gui.util import loadSetting


class PollThread(QThread):
    # service, instance, status, error info
    newData = pyqtSignal(object, object, int, object)

    def __init__(self, host, port, user=None, passwd=None, loopDelay=3.0,
                 parent=None):
        QThread.__init__(self, parent)
        self._client = Client(host, port, user, passwd)
        self._loopDelay = loopDelay
        self.running = True

    def run(self):
        while self.running:
            try:
                services = self._client.getServices()
            except Exception:
                services = OrderedDict()

            for service, instances in iteritems(services):
                if not instances:
                    self.poll(service, None)
                else:
                    for instance in instances:
                        self.poll(service, instance)

            time.sleep(self._loopDelay)

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


class Client(object):
    def __init__(self, host, port, user=None, passwd=None):
        self.host = host
        self.port = port
        self.user = user
        self.passwd = passwd

        if user is not None and passwd is not None:
            self._proxy = xmlrpc.ServerProxy('http://%s:%s@%s:%s/xmlrpc'
                                             % (user, passwd, host, port),
                                             transport=HttpTransport())
        else:
            self._proxy = xmlrpc.ServerProxy('http://%s:%s/xmlrpc'
                                             % (host, port),
                                             transport=HttpTransport())
        self._lock = threading.Lock()
        self._pollThread = None
        self.version = self.getVersion()

    def stopPoller(self, join=False):
        if self._pollThread:
            self._pollThread.running = False

            if join:
                self._pollThread.wait()

    def startPoller(self, slot):
        self._pollThread = PollThread(self.host,
                                      self.port,
                                      self.user,
                                      self.passwd,
                                      loadSetting('pollInterval',
                                                  3,
                                                  valType=float))
        self._pollThread.newData.connect(slot)
        self._pollThread.start()

    def reloadJobs(self):
        with self._lock:
            self.stopPoller(True)
            self._proxy.ReloadJobs()
            self._pollThread.start()
        self.version = self.getVersion()

    def getServices(self):
        with self._lock:
            lst = self._proxy.GetServices()

        result = OrderedDict()
        singleJobs = []
        for entry in sorted(lst):
            parts = entry.split('.')

            if len(parts) > 1:
                if parts[0] not in result:
                    result[parts[0]] = []
                result[parts[0]].append(parts[1])
            else:
                singleJobs.append(parts[0])

        # sort single jobs to the end
        for entry in singleJobs:
            result[entry] = None

        return result

    def getServicePath(self, service, instance):
        return '%s.%s' % (service, instance) if instance else service

    def startService(self, service, instance=None):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                self._proxy.Start(servicePath)
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)
        if self._pollThread:
            self._pollThread.poll(service, instance)

    def stopService(self, service, instance=None):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                self._proxy.Stop(servicePath)
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)
        if self._pollThread:
            self._pollThread.poll(service, instance)

    def restartService(self, service, instance=None):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                self._proxy.Restart(servicePath)
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)
        if self._pollThread:
            self._pollThread.poll(service, instance)

    def getServiceStatus(self, service, instance=None):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                return self._proxy.GetStatus(servicePath)
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)

    def getServiceOutput(self, service, instance=None):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                return self._proxy.GetOutput(servicePath)
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)

    def getServiceLogs(self, service, instance=None):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                return self._proxy.GetLogs(servicePath)
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)

    def getVersion(self):
        with self._lock:
            return int(self._proxy.GetVersion().strip('v')[:1])

    def receiveServiceConfig(self, service, instance=None):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                return self._proxy.ReceiveConfig(servicePath)
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)

    def sendServiceConfig(self, service, instance=None, data=None):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                self._proxy.SendConfig([servicePath] + (data or []))
        except xmlrpc.Fault as f:
            raise ClientError(f.faultCode, f.faultString)
