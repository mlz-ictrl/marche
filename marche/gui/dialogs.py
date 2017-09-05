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

from PyQt4.QtGui import QInputDialog, QDialog, QFileDialog, QDialogButtonBox

from marche.six import iteritems
from marche.gui.util import loadUi, getAvailableEditors
from marche.gui.scan import PassiveScanner


class AuthDialog(QDialog):
    def __init__(self, parent, title):
        QDialog.__init__(self, parent)
        loadUi(self, 'authdlg.ui')
        self.buttonBox.button(QDialogButtonBox.Ok).setDefault(True)
        self.nameLbl.setText(title)
        self.setWindowTitle(title)
        self.passwdLineEdit.setFocus()

    @property
    def user(self):
        return str(self.userLineEdit.text()).strip()

    @property
    def passwd(self):
        return str(self.passwdLineEdit.text()).strip()

    @property
    def save_creds(self):
        return self.saveBox.isChecked()


class PreferencesDialog(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        loadUi(self, 'preferences.ui')

        self._creds = {}
        self.editorComboBox.addItems(getAvailableEditors())

    def selectDefaultSession(self):
        name = QFileDialog.getOpenFileName(self,
                                           'Select default session',
                                           '',
                                           'Marche sessions (*.marche)')
        if name:
            self.sessionLineEdit.setText(name)

    @property
    def defaultEditor(self):
        return self.editorComboBox.currentText()

    @defaultEditor.setter
    def defaultEditor(self, value):
        index = self.editorComboBox.findText(value)

        if index == -1:
            self.editorComboBox.addItem(value)
            index = self.editorComboBox.count() - 1

        self.editorComboBox.setCurrentIndex(index)

    @property
    def pollInterval(self):
        return self.pollIntervalSpinBox.value()

    @pollInterval.setter
    def pollInterval(self, value):
        self.pollIntervalSpinBox.setValue(float(value))

    @property
    def defaultSession(self):
        return self.sessionLineEdit.text()

    @defaultSession.setter
    def defaultSession(self, value):
        self.sessionLineEdit.setText(value)

    @property
    def credentials(self):
        return self._creds

    @credentials.setter
    def credentials(self, value):
        self._creds = value
        for host, _ in iteritems(value):
            self.hostsListWidget.addItem(host)

    @property
    def sortHostListEnabled(self):
        return self.sortHostListCheckBox.isChecked()

    @sortHostListEnabled.setter
    def sortHostListEnabled(self, value):
        return self.sortHostListCheckBox.setChecked(value)

    def selectCred(self, host):
        if not host:
            self.userLineEdit.clear()
            self.pwLineEdit.clear()
            self.credApplyPushButton.setEnabled(False)
            self.userLineEdit.setEnabled(False)
            self.pwLineEdit.setEnabled(False)
            self.rmHostPushButton.setEnabled(False)
        else:
            user, passwd = self._creds[host]
            self.userLineEdit.setText(user)
            self.pwLineEdit.setText(passwd)
            self.credApplyPushButton.setEnabled(True)
            self.userLineEdit.setEnabled(True)
            self.pwLineEdit.setEnabled(True)
            self.rmHostPushButton.setEnabled(True)

    def applyCred(self):
        host = self.hostsListWidget.currentItem().text()
        user = self.userLineEdit.text()
        passwd = self.pwLineEdit.text()

        self._creds[host] = (user, passwd)

    def addCred(self):
        host, accepted = QInputDialog.getText(self, 'New host', 'New host:')

        if not accepted:
            return

        self._creds[host] = ('marche', '')
        self.hostsListWidget.addItem(host)

    def removeCred(self):
        host = self.hostsListWidget.currentItem().text()
        self.hostsListWidget.takeItem(self.hostsListWidget.currentRow())

        del self._creds[host]


class PassiveScanDialog(QDialog):
    def __init__(self, parent=None):
        QDialog.__init__(self, parent)
        loadUi(self, 'scan.ui')
        self.foundLbl.setText('Found 0 hosts running Marche.')

    def update(self, n):
        self.foundLbl.setText('Found %d host(s) running Marche.' % n)

    def run(self):
        scanner = PassiveScanner()
        scanner.foundHosts.connect(self.update)
        scanner.finished.connect(self.accept)
        scanner.start()
        if self.exec_() == QDialog.Accepted:
            return scanner.hosts
        return []
