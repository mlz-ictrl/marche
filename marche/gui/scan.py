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
import socket
import select

from PyQt4.QtGui import QDialog
from PyQt4.QtCore import QThread, pyqtSignal

from marche.iface.udp import UDP_PORT
from marche.gui.util import loadUi


class ScanThread(QThread):
    foundHosts = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self):
        QThread.__init__(self)
        self.hosts = []

    def run(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        s.sendto(b'PING', ('255.255.255.255', UDP_PORT))
        start = time.time()
        while time.time() - start < 1.0:  # wait 1 sec max
            res = select.select([s], [], [], 0.1)
            if res[0]:
                try:
                    _msg, addr = s.recvfrom(1024)
                except socket.error:
                    continue
                try:
                    addr = socket.gethostbyaddr(addr[0])[0]
                except socket.error:
                    addr = addr[0]
                self.hosts.append(addr + ':8124')
                self.foundHosts.emit(len(self.hosts))
        self.finished.emit()


class Scanner(QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        loadUi(self, 'scan.ui')
        self.foundLbl.setText('Found 0 hosts running Marche.')

    def update(self, n):
        self.foundLbl.setText('Found %d host(s) running Marche.' % n)

    def run(self):
        scanner = ScanThread()
        scanner.foundHosts.connect(self.update)
        scanner.finished.connect(self.accept)
        scanner.start()
        if self.exec_() == QDialog.Accepted:
            return scanner.hosts
        return []
