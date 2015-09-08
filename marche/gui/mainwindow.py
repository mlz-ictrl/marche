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
from marche.gui.client import Client

from PyQt4.QtCore import pyqtSignature as qtsig
from PyQt4.QtGui import QMainWindow, QWidget, QVBoxLayout, QLabel, \
    QInputDialog


class JobWidget(QWidget):
    def __init__(self, parent, service, instance=None):
        QWidget.__init__(self, parent)
        loadUi(self, 'job.ui')
        self.service = service
        self.instance = instance

        self.jobNameLabel.setText(instance)

class HostWidget(QWidget):
    def __init__(self, parent, proxy):
        QWidget.__init__(self, parent)
        self._proxy = proxy

        self._layout = QVBoxLayout()
        self.setLayout(self._layout)
        self.fill()

    def fill(self):
        services = self._proxy.getServices()

        for service, instances in services.iteritems():
             self.layout().addWidget(QLabel(service))

             for instance in instances:
                 self.layout().addWidget(JobWidget(self, service, instance))

        self.layout().addStretch(1)


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        QMainWindow.__init__(self, parent)
        loadUi(self, 'mainwindow.ui')

        self._clients = {}
        self.addHost('ccr12.ictrl.frm2:8124')
        self.openHost('ccr12.ictrl.frm2:8124')

    @qtsig('')
    def on_actionAdd_host_triggered(self):
        addr, accepted = QInputDialog.getText(self, 'Add host',
                                              'New host:')
        if accepted:
            self.addHost(addr)

    def addHost(self, addr):
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
            prev.hide()
            prev.deleteLater()

        widget = HostWidget(self, self._clients[addr])

        self.surface.layout().addWidget(widget)
        widget.show()
