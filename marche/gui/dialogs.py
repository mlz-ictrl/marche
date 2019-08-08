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

from six import iteritems

from marche.gui.qt import QDialog, QDialogButtonBox, QFileDialog, QInputDialog
from marche.gui.scan import PassiveScanner
from marche.gui.util import getAvailableEditors, loadUi


class AuthDialog(QDialog):
    def __init__(self, parent, title, defuser):
        QDialog.__init__(self, parent)
        loadUi(self, 'authdlg.ui')
        self.buttonBox.button(QDialogButtonBox.Ok).setDefault(True)
        self.userEdit.setText(defuser or 'marche')
        self.nameLbl.setText(title)
        self.setWindowTitle(title)
        self.passwdEdit.setFocus()

    @property
    def user(self):
        return str(self.userEdit.text()).strip()

    @property
    def passwd(self):
        return str(self.passwdEdit.text()).strip()

    @property
    def save_creds(self):
        return self.saveBox.isChecked()


class PreferencesDialog(QDialog):
    def __init__(self, parent):
        QDialog.__init__(self, parent)
        loadUi(self, 'preferences.ui')

        self._creds = {}
        self.editorBox.addItems(getAvailableEditors())

    def selectDefaultSession(self):
        name = QFileDialog.getOpenFileName(self,
                                           'Select default session',
                                           '',
                                           'Marche sessions (*.marche)')
        if name:
            self.sessionEdit.setText(name)

    @property
    def defaultEditor(self):
        return self.editorBox.currentText()

    @defaultEditor.setter
    def defaultEditor(self, value):
        index = self.editorBox.findText(value)

        if index == -1:
            self.editorBox.addItem(value)
            index = self.editorBox.count() - 1

        self.editorBox.setCurrentIndex(index)

    @property
    def pollInterval(self):
        return self.pollIntervalBox.value()

    @pollInterval.setter
    def pollInterval(self, value):
        self.pollIntervalBox.setValue(float(value))

    @property
    def defaultSession(self):
        return self.sessionEdit.text()

    @defaultSession.setter
    def defaultSession(self, value):
        self.sessionEdit.setText(value)

    @property
    def defUsername(self):
        return self.defUserEdit.text()

    @defUsername.setter
    def defUsername(self, value):
        self.defUserEdit.setText(value)

    @property
    def credentials(self):
        return self._creds

    @credentials.setter
    def credentials(self, value):
        self._creds = value
        for host, _ in iteritems(value):
            self.hostsList.addItem(host)

    @property
    def sortHostListEnabled(self):
        return self.sortHostListBox.isChecked()

    @sortHostListEnabled.setter
    def sortHostListEnabled(self, value):
        return self.sortHostListBox.setChecked(value)

    def selectCred(self, host):
        if not host:
            self.userEdit.clear()
            self.passwdEdit.clear()
            self.credApplyBtn.setEnabled(False)
            self.userEdit.setEnabled(False)
            self.passwdEdit.setEnabled(False)
            self.rmHostBtn.setEnabled(False)
        else:
            user, passwd = self._creds[host]
            self.userEdit.setText(user)
            self.passwdEdit.setText(passwd)
            self.credApplyBtn.setEnabled(True)
            self.userEdit.setEnabled(True)
            self.passwdEdit.setEnabled(True)
            self.rmHostBtn.setEnabled(True)

    def applyCred(self):
        host = self.hostsList.currentItem().text()
        user = self.userEdit.text()
        passwd = self.passwdEdit.text()

        self._creds[host] = (user, passwd)

    def addCred(self):
        host, accepted = QInputDialog.getText(self, 'New host', 'New host:')

        if not accepted:
            return

        self._creds[host] = ('marche', '')
        self.hostsList.addItem(host)

    def removeCred(self):
        host = self.hostsList.currentItem().text()
        self.hostsList.takeItem(self.hostsList.currentRow())

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
