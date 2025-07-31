# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2025 by the authors, see LICENSE
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
from pathlib import Path

from marche.gui.client import ClientError
from marche.gui.qt import QApplication, QDialog, QMenu, QMessageBox, \
    QPlainTextEdit, QSize, QTextCursor, QWidget, pyqtSlot
from marche.gui.util import getEditorArguments, loadSetting, loadUi, \
    loadUiType, saveSetting, selectEditor
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
        menu.addAction(self.actionShow_config)
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
        if len(config) % 2 != 0:
            self._item.setText(3, 'Strange return value')
            return
        dtemp = Path(tempfile.mkdtemp())
        result = []
        for i in range(0, len(config), 2):
            fn = config[i]
            contents = config[i + 1]
            if os.name == 'nt':
                contents = re.sub(r'(?<!\r)\n', '\r\n', contents)
            localfn = dtemp / fn
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
        flags = getEditorArguments(editor)
        if flags:
            command = '%s %s %s' % (editor, flags, localfn)
        else:
            command = '%s %s' % (editor, localfn)
        pid = subprocess.Popen(command, shell=True)
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
        self.showDetails('Start/stop script output', [('Output', output)])

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
        logs = []
        for logline in loglines:
            filename, content = logline.split(':', 1)
            if not logs or filename != logs[-1][0]:
                logs.append((filename, []))
            logs[-1][1].append(content)
        self.showDetails('Log files', logs)

    @pyqtSlot()
    def on_actionShow_config_triggered(self):
        self._item.setText(3, '')
        if self._client.version < 1:
            self._item.setText(3, 'Daemon too old')
            return
        try:
            config = self._client.viewServiceConfig(self._service,
                                                    self._instance)
        except ClientError as err:
            self._item.setText(3, str(err))
            return
        if not config:
            self._item.setText(3, 'No config files found')
            return
        if len(config) % 2 != 0:
            self._item.setText(3, 'Strange return value')
            return
        configs = []
        for i in range(0, len(config), 2):
            configs.append((config[i], [config[i + 1]]))
        self.showDetails('Config files', configs)

    def showDetails(self, title, files):
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        loadUi(dlg, 'details.ui')
        dlg.tabber.clear()
        for filename, content in files:
            widget = QPlainTextEdit(dlg)
            widget.setReadOnly(True)
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
