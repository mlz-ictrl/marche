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

from marche.gui.util import loadUi
from marche.gui.client import Client, PollThread
from marche.jobs import STATE_STR, RUNNING, DEAD

from PyQt4.QtCore import pyqtSignature as qtsig, QTimer, QThread
from PyQt4.QtGui import QMainWindow, QWidget, QVBoxLayout, QLabel, \
    QInputDialog, QPalette, QColor


class JobWidget(QWidget):

    STATE_COLORS = {
        RUNNING : 'green',
        DEAD : 'red'
    }

    def __init__(self, parent, proxy, service, instance=None):
        QWidget.__init__(self, parent)
        loadUi(self, 'job.ui')
        self._proxy = proxy
        self._service = service
        self._instance = instance

        if instance:
            self.jobNameLabel.setText(instance)
        else:
            self.jobNameLabel.setText(service)

    def on_startBtn_clicked(self):
        self._proxy.startService(self._service, self._instance)

    def on_stopBtn_clicked(self):
        self._proxy.stopService(self._service, self._instance)

    def on_restartBtn_clicked(self):
        self.on_stopBtn_clicked()
        self.on_startBtn_clicked()

    def refreshState(self, service, instance, status):
        if service != self._service or instance != self._instance:
            return

        stylesheet = ('QLineEdit {background-color: %s; color: white}'
                      % self.STATE_COLORS.get(status,QPalette(QColor('gray'))))
        self.statusLineEdit.setStyleSheet(stylesheet)

        status = STATE_STR.get(status, 'UNKNOWN')
        self.statusLineEdit.setText(status)

class HostWidget(QWidget):
    def __init__(self, parent, client):
        QWidget.__init__(self, parent)
        self._client = client
        self._pollThread = PollThread(client.host, client.port)

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self.fill()
        self._pollThread.start()

    def fill(self):
        services = self._client.getServices()

        for service, instances in services.iteritems():
            self.layout().addWidget(QLabel(service))

            widget = None
            if not instances:
                widget = JobWidget(self, self._client, service)
            else:
                for instance in instances:
                    widget = JobWidget(self, self._client, service, instance)

            self._pollThread.newData.connect(widget.refreshState)
            self.layout().addWidget(widget)

        self.layout().addStretch(1)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        loadUi(self, 'mainwindow.ui')

        self.resize(800, 500)
        self.splitter.setStretchFactor(0, 20)
        self.splitter.setStretchFactor(1, 5)


        self._clients = {}

    @qtsig('')
    def on_actionAdd_host_triggered(self):
        addr, accepted = QInputDialog.getText(self, 'Add host',
                                              'New host:')
        if accepted:
            self.addHost(addr)

    def on_hostListWidget_currentItemChanged(self, current, previous):
        self.openHost(current.text())

    def addHost(self, addr):
        if ':' not in addr:
            addr += ':8124'
        host, port = addr.split(':')
        self._clients[addr] = Client(host, port)

        self.hostListWidget.addItem(addr)

    def removeHost(self, addr):
        if addr in self._clients:
            del self._clients[addr]

        item = self.hostListWidget.findItem(addr)
        self.hostListWidget.takeItem(item)

    def openHost(self, addr):
        prev = self.surface.layout().takeAt(0)

        if prev:
            prev.widget().hide()
            prev.widget().deleteLater()

        widget = HostWidget(self, self._clients[addr])

        self.surface.layout().addWidget(widget)
        widget.show()
