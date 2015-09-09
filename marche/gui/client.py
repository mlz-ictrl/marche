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

import time
import threading
from xmlrpclib import ServerProxy, Fault
from collections import OrderedDict

from PyQt4.QtCore import QThread, pyqtSignal


class PollThread(QThread):
    # service, instance, status
    newData = pyqtSignal(object, object, int)

    def __init__(self, host, port, loopDelay=3.0, parent=None):
        QThread.__init__(self, parent)
        self._client = Client(host, port)
        self._loopDelay = loopDelay

    def run(self):
        while True:
            services = self._client.getServices()

            for service, instances in services.iteritems():
                if not instances:
                    status = self._client.getServiceStatus(service)
                    self.newData.emit(service, None, status)
                else:
                    for instance in instances:
                        status = self._client.getServiceStatus(service, instance)
                        self.newData.emit(service, instance, status)

            time.sleep(self._loopDelay)

    def poll(self, service, instance):
        status = self._client.getServiceStatus(service, instance)
        self.newData.emit(service, instance, status)


class ClientError(Exception):
    def __init__(self, code, string):
        self.code = code
        Exception.__init__(self, string)


class Client(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._proxy = ServerProxy('http://%s:%s/xmlrpc' % (host, port))
        self._lock = threading.Lock()
        self._pollThread = None

    def _from_fault(self, f):
        return ClientError(f.faultCode, f.faultString)

    def startPoller(self, slot):
        self._pollThread = PollThread(self.host, self.port)
        self._pollThread.newData.connect(slot)
        self._pollThread.start()

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

    def startService(self, service, instance=None):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                self._proxy.Start(servicePath)
        except Fault as f:
            raise self._from_fault(f)
        if self._pollThread:
            self._pollThread.poll(service, instance)

    def stopService(self, service, instance=None):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                self._proxy.Stop(servicePath)
        except Fault as f:
            raise self._from_fault(f)
        if self._pollThread:
            self._pollThread.poll(service, instance)

    def restartService(self, service, instance=None):
        servicePath = self.getServicePath(service, instance)
        try:
            with self._lock:
                self._proxy.Restart(servicePath)
        except Fault as f:
            raise self._from_fault(f)
        if self._pollThread:
            self._pollThread.poll(service, instance)

    def getServiceStatus(self, service, instance=None):
        servicePath = self.getServicePath(service, instance)
        with self._lock:
            return self._proxy.GetStatus(servicePath)

    def getServicePath(self, service, instance):
        return '%s.%s' % (service, instance) if instance else service
