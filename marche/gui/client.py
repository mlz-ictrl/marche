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

from xmlrpclib import ServerProxy

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


class Client(object):
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self._proxy = ServerProxy('http://%s:%s/xmlrpc' % (host, port))

    def getServices(self):
        lst = self._proxy.GetServices()

        result = {}
        for entry in lst:
            parts = entry.split('.')

            if len(parts) > 1:
                if parts[0] not in result:
                    result[parts[0]] = []
                result[parts[0]].append(parts[1])
            else:
                result[parts[0]] = None

        return result

    def startService(self, service, instance=None):
        servicePath = self.getServicePath(service, instance)
        if not self._proxy.Start(servicePath):
            raise RuntimeError('Could not start: %s' % servicePath)

    def stopService(self, service, instance=None):
        servicePath = self.getServicePath(service, instance)
        if not self._proxy.Stop(servicePath):
            raise RuntimeError('Could not stop: %s' % servicePath)

    def getServiceStatus(self, service, instance=None):
        servicePath = self.getServicePath(service, instance)
        return self._proxy.GetStatus(servicePath)

    def getServicePath(self, service, instance):
        return '%s.%s' % (service, instance) if instance else service
