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

"""GUI specific additions to the client."""

import threading
from collections import OrderedDict

from marche.client import Client as BaseClient, ClientError
from marche.gui.qt import QThread, pyqtSignal
from marche.gui.util import loadSetting
from marche.jobs import NOT_AVAILABLE

__all__ = ['Client', 'ClientError']


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

                for service, instances in services.items():
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


class Client(BaseClient):

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
