#  -*- coding: utf-8 -*-
# *****************************************************************************
# Copyright (c) 2015-2017 by the authors, see LICENSE
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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************

import socket

from PyQt4.QtCore import QThread, pyqtSignal, QSettings, pyqtSignature as qtsig
from PyQt4.QtGui import QDialog

from marche.gui.util import loadUi, getSubnetHostsAddrs, determineSubnet
from marche.scan import scan


class SubnetInputDialog(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        loadUi(self, 'subnetinputdlg.ui')

        ownSubnet = determineSubnet()
        if ownSubnet is not None:
            self._setSubnet(ownSubnet)

        self._presets = {}
        self._loadPresets()

    @property
    def subnet(self):
        return '%s.%s.%s.%s/%s' % (self.byte1SpinBox.value(),
                                   self.byte2SpinBox.value(),
                                   self.byte3SpinBox.value(),
                                   self.byte4SpinBox.value(),
                                   self.prefixSpinBox.value())

    def accept(self):
        if self.saveCheckBox.isChecked():
            self._savePreset()
        return QDialog.accept(self)

    @qtsig('QString')
    def on_presetComboBox_currentIndexChanged(self, presetName):
        if presetName in self._presets:
            self._setSubnet(self._presets[presetName])

    def _setSubnet(self, subnet):
        ip, netmask = subnet.split('/')
        self.prefixSpinBox.setValue(int(netmask))

        ip = ip.split('.')
        for i in range(len(ip)):
            box = getattr(self, 'byte%sSpinBox' % (i + 1))
            box.setValue(int(ip[i]))

    def _loadPresets(self):
        settings = QSettings()

        settings.beginGroup('subnet')
        self._presets = settings.value('presets', {})
        settings.endGroup()

        for entry in sorted(self._presets.keys()):
            self.presetComboBox.addItem(entry)

    def _savePreset(self):
        self._presets[self.presetComboBox.currentText()] = self.subnet

        settings = QSettings()

        settings.beginGroup('subnet')
        settings.setValue('presets', self._presets)
        settings.endGroup()


class ActiveScanner(QThread):
    hostFound = pyqtSignal(object)  # host
    scanNotify = pyqtSignal(str)
    finished = pyqtSignal()

    def __init__(self, parent=None):
        QThread.__init__(self, parent)

        self._hosts = []

    def setSubnet(self, subnetid):
        self._hosts = getSubnetHostsAddrs(subnetid)

    def run(self):
        for ip in self._hosts:
            notification = 'Scanning %s' % ip
            notification += ' ...'

            self.scanNotify.emit(notification)

            try:
                s = socket.create_connection((ip, '8124'), timeout=0.1)
                s.close()

                self.hostFound.emit(ip)
            except:
                pass
        self.finished.emit()


class PassiveScanner(QThread):
    foundHosts = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self):
        QThread.__init__(self)
        self.hosts = []

    def run(self):
        for host, version in scan(''):
            self.hosts.append(host + ':8124')
            self.foundHosts.emit(len(self.hosts))
        self.finished.emit()
