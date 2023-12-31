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

import os
import re
import subprocess
import tempfile
import time
from os import path

from marche.gui.client import ClientError
from marche.gui.qt import QApplication, QDialog, QMenu, QMessageBox, \
    QPlainTextEdit, QSize, QTextCursor, QWidget, pyqtSlot
from marche.gui.util import loadSetting, loadUi, loadUiType, saveSetting, \
    selectEditor
from marche.utils import read_file, write_file

JobButtonsUI = loadUiType('job.ui')


class JobButtons(JobButtonsUI, QWidget):
    def __init__(self, client, service, instance, item, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)

        self._item = item
        self._client = client
        self._service = service
        self._instance = instance

        menu = QMenu(self)
        menu.addAction(self.actionShow_output)
        menu.addAction(self.actionShow_logfiles)
        menu.addSeparator()
        menu.addAction(self.actionConfigure)
        self.moreBtn.setMenu(menu)

    @pyqtSlot()
    def on_startBtn_clicked(self):
        self._item.setText(3, '')
        try:
            self._client.startService(self._service, self._instance)
        except ClientError as err:
            self._item.setText(3, str(err))

    @pyqtSlot()
    def on_stopBtn_clicked(self):
        self._item.setText(3, '')
        try:
            self._client.stopService(self._service, self._instance)
        except ClientError as err:
            self._item.setText(3, str(err))

    @pyqtSlot()
    def on_restartBtn_clicked(self):
        self._item.setText(3, '')
        try:
            self._client.restartService(self._service, self._instance)
        except ClientError as err:
            self._item.setText(3, str(err))

    @pyqtSlot()
    def on_actionConfigure_triggered(self):
        self._item.setText(3, '')
        if self._client.version < 1:
            self._item.setText(3, 'Daemon too old')
            return
        editor = loadSetting('defaultEditor')
        if not editor:
            editor = selectEditor()
            if not editor:
                return
            saveSetting('defaultEditor', editor)
        try:
            config = self._client.receiveServiceConfig(self._service,
                                                       self._instance)
        except ClientError as err:
            self._item.setText(3, str(err))
            return
        if not config:
            self._item.setText(3, 'No editable config files found')
            return
        elif len(config) % 2 != 0:
            self._item.setText(3, 'Strange return value')
            return
        dtemp = tempfile.mkdtemp()
        result = []
        for i in range(0, len(config), 2):
            fn = path.basename(config[i])
            contents = config[i + 1]
            if os.name == 'nt':
                contents = re.sub(r'(?<!\r)\n', '\r\n', contents)
            localfn = path.join(dtemp, fn)
            write_file(localfn, contents)
            if not self.editLocal(editor, localfn):
                self._item.setText(3, 'Editor failed')
                return
            if QMessageBox.question(
                    self, 'Configure', 'Is the changed file ok to use?',
                    QMessageBox.StandardButton.Yes |
                    QMessageBox.StandardButton.No) == \
                    QMessageBox.StandardButton.Yes:
                result.append(fn)
                contents = read_file(localfn)
                if os.name == 'nt':
                    contents = contents.replace('\r\n', '\n')
                result.append(contents)
        if not result:
            return
        try:
            self._client.sendServiceConfig(self._service, self._instance,
                                           result)
        except ClientError as err:
            self._item.setText(3, str(err))
            return

    def editLocal(self, editor, localfn):
        dlg = QDialog(self)
        loadUi(dlg, 'wait.ui')
        dlg.setModal(True)
        dlg.show()
        pid = subprocess.Popen('%s %s' % (editor, localfn), shell=True)
        while pid.poll() is None:
            QApplication.processEvents()
            time.sleep(0.2)
        dlg.close()
        return pid.returncode == 0

    @pyqtSlot()
    def on_actionShow_output_triggered(self):
        self._item.setText(3, '')
        try:
            output = self._client.getServiceOutput(self._service,
                                                   self._instance)
        except ClientError as err:
            self._item.setText(3, str(err))
            return
        dlg = QDialog(self)
        loadUi(dlg, 'details.ui')
        dlg.outEdit.setPlainText(''.join(output))
        dlg.outEdit.moveCursor(QTextCursor.MoveOperation.End)
        dlg.outEdit.ensureCursorVisible()
        dlg.exec()

    @pyqtSlot()
    def on_actionShow_logfiles_triggered(self):
        self._item.setText(3, '')
        try:
            loglines = self._client.getServiceLogs(self._service,
                                                   self._instance)
        except ClientError as err:
            self._item.setText(3, str(err))
            return
        if not loglines:
            self._item.setText(3, 'Service does not return logs')
            return
        dlg = QDialog(self)
        loadUi(dlg, 'details.ui')
        dlg.tabber.clear()
        logs = []
        for logline in loglines:
            filename, content = logline.split(':', 1)
            if not logs or filename != logs[-1][0]:
                logs.append((filename, []))
            logs[-1][1].append(content)
        for filename, content in logs:
            widget = QPlainTextEdit(dlg)
            font = widget.font()
            font.setFamily('Monospace')
            widget.setFont(font)
            widget.setPlainText(''.join(content))
            widget.moveCursor(QTextCursor.MoveOperation.End)
            widget.ensureCursorVisible()
            dlg.tabber.addTab(widget, filename)
        dlg.exec()


class MultiJobButtons(JobButtonsUI, QWidget):
    def __init__(self, buttons, parent=None):
        QWidget.__init__(self, parent)
        self.setupUi(self)

        self.stacker.setCurrentIndex(1)
        self._buttons = buttons
        self.setMinimumSize(QSize(30, 40))

    @pyqtSlot()
    def on_startBtn_clicked(self):
        for button in self._buttons:
            button.on_startBtn_clicked()

    @pyqtSlot()
    def on_stopBtn_clicked(self):
        for button in self._buttons:
            button.on_stopBtn_clicked()

    @pyqtSlot()
    def on_restartBtn_clicked(self):
        for button in self._buttons:
            button.on_restartBtn_clicked()
