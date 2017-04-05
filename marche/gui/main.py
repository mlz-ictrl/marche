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

from __future__ import print_function

import time
import tempfile
import subprocess
from os import path

from PyQt4.QtGui import QWidget, QInputDialog, QColor, QTreeWidget, QDialog, \
    QTreeWidgetItem, QBrush, QMessageBox, QIcon, QListWidgetItem, QMenu, \
    QPlainTextEdit, QFileDialog, QDialogButtonBox, QApplication, QTextCursor
from PyQt4.QtCore import pyqtSignature as qtsig, Qt, QSize, QSettings, \
    QByteArray

from marche.six import iteritems
from marche.six.moves import range  # pylint: disable=redefined-builtin
from marche.six.moves import xmlrpc_client as xmlrpc

import marche.gui.res  # noqa, pylint: disable=unused-import

from marche.gui.util import loadUi, selectEditor, getAvailableEditors, \
    loadSettings, saveSettings, loadSetting, saveSetting, saveCredentials, \
    loadCredentials, loadAllCredentials, removeCredentials
from marche.gui.client import Client, ClientError
from marche.gui.scan import Scanner
from marche.jobs import STATE_STR, RUNNING, NOT_RUNNING, WARNING, DEAD, \
    STARTING, STOPPING, INITIALIZING
from marche.utils import normalize_addr, read_file, write_file
from marche.version import get_version

ADDR_ROLE = 32


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


class JobButtons(QWidget):
    def __init__(self, client, service, instance, item, parent=None):
        QWidget.__init__(self, parent)
        loadUi(self, 'job.ui')

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

    @qtsig('')
    def on_startBtn_clicked(self):
        self._item.setText(3, '')
        try:
            self._client.startService(self._service, self._instance)
        except ClientError as err:
            self._item.setText(3, str(err))

    @qtsig('')
    def on_stopBtn_clicked(self):
        self._item.setText(3, '')
        try:
            self._client.stopService(self._service, self._instance)
        except ClientError as err:
            self._item.setText(3, str(err))

    @qtsig('')
    def on_restartBtn_clicked(self):
        self._item.setText(3, '')
        try:
            self._client.restartService(self._service, self._instance)
        except ClientError as err:
            self._item.setText(3, str(err))

    @qtsig('')
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
            self._item.setText(3, 'No configs to edit')
            return
        elif len(config) % 2 != 0:
            self._item.setText(3, 'Strange return value')
            return
        dtemp = tempfile.mkdtemp()
        result = []
        for i in range(0, len(config), 2):
            fn = config[i]
            contents = config[i + 1]
            localfn = path.join(dtemp, fn)
            write_file(localfn, contents)
            if not self.editLocal(editor, localfn):
                self._item.setText(3, 'Editor failed')
                return
            if QMessageBox.question(
                    self, 'Configure', 'Is the changed file ok to use?',
                    QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
                result.append(fn)
                result.append(read_file(localfn))
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

    @qtsig('')
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
        dlg.outEdit.moveCursor(QTextCursor.End)
        dlg.outEdit.ensureCursorVisible()
        dlg.exec_()

    @qtsig('')
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
            widget.moveCursor(QTextCursor.End)
            widget.ensureCursorVisible()
            dlg.tabber.addTab(widget, filename)
        dlg.exec_()


class MultiJobButtons(QWidget):
    def __init__(self, buttons, parent=None):
        QWidget.__init__(self, parent)
        loadUi(self, 'job.ui')
        self.stacker.setCurrentIndex(1)
        self._buttons = buttons
        self.setMinimumSize(QSize(30, 40))

    @qtsig('')
    def on_startBtn_clicked(self):
        for button in self._buttons:
            button.on_startBtn_clicked()

    @qtsig('')
    def on_stopBtn_clicked(self):
        for button in self._buttons:
            button.on_stopBtn_clicked()

    @qtsig('')
    def on_restartBtn_clicked(self):
        for button in self._buttons:
            button.on_restartBtn_clicked()


class HostTree(QTreeWidget):
    STATE_COLORS = {
        RUNNING:      ('green', ''),
        NOT_RUNNING:  ('black', ''),
        DEAD:         ('white', 'red'),
        WARNING:      ('black', 'yellow'),
        STARTING:     ('blue', ''),
        STOPPING:     ('blue', ''),
        INITIALIZING: ('blue', ''),
    }

    def __init__(self, parent, client):
        QTreeWidget.__init__(self, parent)
        self._client = client

        self.setColumnCount(4)
        self.headerItem().setText(0, 'Service')
        self.headerItem().setText(1, 'Status')
        self.headerItem().setText(2, 'Control')
        self.headerItem().setText(3, 'Last error')
        self._items = {}
        self._virt_items = {}
        try:
            self.fill()
        except Exception as err:
            print(err)

        self.expandAll()
        self.resizeColumnToContents(0)
        self.setColumnWidth(0, self.columnWidth(0) * 1.4)
        self.resizeColumnToContents(2)
        width = sum(self.columnWidth(i) for i in range(self.columnCount()))
        self.setMinimumWidth(width+25)
        self.itemClicked.connect(self.on_itemClicked)

    def refresh(self):
        self.clear()
        self.fill()

    def clear(self):
        self._client.stopPoller()
        self._items.clear()
        QTreeWidget.clear(self)

    def fill(self):
        self.clear()
        services = self._client.getServices()
        try:
            descrs = self._client.getServiceDescriptions(services)
        except Exception:
            descrs = {}
        self._client.startPoller(self.updateStatus)

        for service, instances in iteritems(services):
            serviceItem = QTreeWidgetItem([service])
            serviceItem.setForeground(1, QBrush(QColor('white')))
            serviceItem.setTextAlignment(1, Qt.AlignCenter)
            serviceItem.setFlags(Qt.ItemIsEnabled)
            serviceItem.setForeground(3, QBrush(QColor('red')))
            self.addTopLevelItem(serviceItem)

            btns = []
            has_empty_instance = None
            for instance in instances:
                if not instance:
                    has_empty_instance = True
                    continue
                instanceItem = QTreeWidgetItem([instance])
                instanceItem.setForeground(1, QBrush(QColor('white')))
                instanceItem.setTextAlignment(1, Qt.AlignCenter)
                instanceItem.setFlags(Qt.ItemIsEnabled)
                instanceItem.setForeground(3, QBrush(QColor('red')))
                if descrs.get((service, instance)):
                    instanceItem.setText(0, descrs[service, instance])
                serviceItem.addChild(instanceItem)

                btn = JobButtons(self._client, service, instance,
                                 instanceItem)
                btns.append(btn)
                self.setItemWidget(instanceItem, 2, btn)
                self._items[service, instance] = instanceItem
            if has_empty_instance:
                btn = JobButtons(self._client, service, '',
                                 serviceItem)
                btn.setMinimumSize(QSize(30, 40))
                self.setItemWidget(serviceItem, 2, btn)
                if descrs.get((service, '')):
                    serviceItem.setText(0, descrs[service, ''])
                self._items[service, ''] = serviceItem
            else:
                # create "virtual" job with buttons that start/stop all
                # instances of the service
                self._virt_items[service] = serviceItem
                multibtn = MultiJobButtons(btns)
                self.setItemWidget(serviceItem, 2, multibtn)

        self.expandAll()

    def updateStatus(self, service, instance, status, info):
        if service is instance is None:
            for (service, instance) in self._items:
                self.updateStatus(service, instance, status, info)
            return
        if (service, instance) not in self._items:
            return
        item = self._items[service, instance]

        colors = self.STATE_COLORS.get(status, ('gray', ''))
        item.setForeground(1, QBrush(QColor(colors[0]))
                           if colors[0] else QBrush())
        item.setBackground(1, QBrush(QColor(colors[1]))
                           if colors[1] else QBrush())
        item.setText(1, STATE_STR[status])
        item.setData(1, 32, status)
        if info is not None:
            item.setText(3, info)

        if status in [STARTING, INITIALIZING, STOPPING]:
            item.setIcon(1, QIcon(':/marche/ui-progress-bar.png'))
        else:
            item.setIcon(1, QIcon())

        if service in self._virt_items:
            self.updateParentItem(self._virt_items[service])

    def updateParentItem(self, item):
        statuses = {}
        total = item.childCount()
        for i in range(total):
            chst = item.child(i).data(1, 32)
            count = statuses.setdefault(chst, 0)
            statuses[chst] = count + 1
        if not statuses:
            return
        if None in statuses:
            item.setText(1, '')
            item.setForeground(1, QBrush(QColor('black')))
            item.setBackground(1, QBrush())
        elif len(statuses) == 1:
            status, _ = statuses.popitem()
            colors = self.STATE_COLORS.get(status, ('gray', ''))
            item.setForeground(1, QBrush(QColor(colors[0]))
                               if colors[0] else QBrush())
            item.setBackground(1, QBrush(QColor(colors[1]))
                               if colors[1] else QBrush())
            item.setText(1, 'ALL %d %s' % (total, STATE_STR[status]))
        else:
            item.setText(1, '%d/%d RUNNING' %
                         (statuses.get(RUNNING, 0), total))
            item.setForeground(1, QBrush(QColor('black')))
            item.setBackground(1, QBrush(QColor('#ffcccc')))

    def reloadJobs(self):
        self._client.reloadJobs()
        self.fill()

    def on_itemClicked(self, item, index):
        # when clicking on the error column, show the whole error in a dialog
        if index == 3:
            if item.text(3):
                QMessageBox.warning(self, 'Error view', item.text(3))


class MainWidget(QWidget):
    def __init__(self, parent=None, scan_on_startup=False):
        QWidget.__init__(self, parent)
        loadUi(self, 'main.ui')

        self.setCachedCredsVisible(False)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)
        self.leftlayout.setContentsMargins(6, 6, 0, 6)
        self.surface.layout().setContentsMargins(0, 6, 6, 6)

        settings = QSettings('marche-gui')
        self.splitter.restoreState(settings.value('split', b'', QByteArray))

        self._clients = {}
        self._cur_tree = None

        self._last_creds = None

        if loadSetting('defaultSession'):
            self.loadDefaultSession()
        elif scan_on_startup:
            self.scanNetwork()

    def loadDefaultSession(self):
        self.loadSession(loadSetting('defaultSession'))

    def saveSettings(self):
        settings = QSettings('marche-gui')
        settings.setValue('split', self.splitter.saveState())
        # settings.setValue('last_hosts', [])

    def setCachedCredsVisible(self, flag):
        flag = bool(flag and self._last_creds)
        if flag:
            self.lblCachedUserCreds.setText(self._last_creds[0])
        self.cachePanel.setVisible(flag)

    @qtsig('')
    def on_actionPreferences_triggered(self):
        dlg = PreferencesDialog(self)

        # load and enter settings
        settings = loadSettings(['defaultEditor',
                                 'pollInterval',
                                 'defaultSession'])

        if settings['defaultEditor']:
            dlg.defaultEditor = settings['defaultEditor']
        if settings['pollInterval']:
            dlg.pollInterval = settings['pollInterval']
        if settings['defaultSession']:
            dlg.defaultSession = settings['defaultSession']

        dlg.credentials = loadAllCredentials()
        oldCredHosts = set(dlg.credentials.keys())

        if dlg.exec_():
            saveSettings({
                'defaultEditor': dlg.defaultEditor,
                'pollInterval': dlg.pollInterval,
                'defaultSession': dlg.defaultSession,
            })

            for host, (user, passwd) in iteritems(dlg.credentials):
                saveCredentials(host, user, passwd)

            for host in oldCredHosts - set(dlg.credentials):
                removeCredentials(host)

            if dlg.pollInterval != settings['pollInterval'] \
               and self._cur_tree is not None:
                self._cur_tree.refresh()

    @qtsig('')
    def on_actionAdd_host_triggered(self):
        addr, accepted = QInputDialog.getText(self, 'Add host', 'New host:')
        if accepted:
            self.openHost(self.addHost(addr))

    @qtsig('')
    def on_actionScan_network_triggered(self):
        self.scanNetwork()

    @qtsig('')
    def on_actionReload_triggered(self):
        if self._cur_tree:
            self._cur_tree.reloadJobs()

    @qtsig('')
    def on_actionLoad_session_triggered(self):
        filename = QFileDialog.getOpenFileName(self, 'Load session', '',
                                               'Marche sessions (*.marche)')
        if not filename:
            return
        self.loadSession(filename)

    def loadSession(self, filename):
        try:
            with open(filename) as fp:
                firstline = fp.readline()
                if firstline.startswith('Marche session v1'):
                    hosts = [h for h in (h.strip() for h in fp) if h]
                else:
                    raise RuntimeError('Unrecognized file format.')
        except Exception as err:
            QMessageBox.critical(self, 'Error', str(err))
            return
        self.closeHost()
        self.hostList.clear()
        for host in hosts:
            self.addHost(host)

    @qtsig('')
    def on_actionSave_session_as_triggered(self):
        filename = QFileDialog.getSaveFileName(self, 'Save session', '',
                                               'Marche sessions (*.marche)')
        if not filename:
            return
        if not filename.endswith('.marche'):
            filename += '.marche'
        try:
            with open(filename, 'w') as fp:
                fp.write('Marche session v1\n')
                for i in range(self.hostList.count()):
                    fp.write(self.hostList.item(i).text() + '\n')
        except Exception as err:
            QMessageBox.critical(self, 'Error', str(err))
            return

    @qtsig('')
    def on_actionAbout_triggered(self):
        QMessageBox.about(
            self, 'About Marche GUI',
            '''
            <h2>About Marche GUI</h2>
            <p style="font-style: italic">
              (C) 2015-2016 MLZ instrument control
            </p>
            <p>
              Marche GUI is a graphical interface for the Marche process
              control system.
            </p>
            <h3>Authors:</h3>
            <ul>
              <li>Copyright (C) 2015-2016
                <a href="mailto:g.brandl@fz-juelich.de">Georg Brandl</a></li>
              <li>Copyright (C) 2015-2016
                <a href="mailto:alexander.lenz@frm2.tum.de">Alexander
                Lenz</a></li>
            </ul>
            <p>
              Marche is published under the
              <a href="http://www.gnu.org/licenses/gpl.html">GPL
                (GNU General Public License)</a>
            </p>
            <p style="font-weight: bold">
              Version: %s
            </p>
            ''' % get_version())

    @qtsig('')
    def on_actionAbout_Qt_triggered(self):
        QMessageBox.aboutQt(self, 'About Qt')

    @qtsig('')
    def on_addHostBtn_clicked(self):
        self.on_actionAdd_host_triggered()

    @qtsig('')
    def on_rescanBtn_clicked(self):
        self.on_actionScan_network_triggered()

    @qtsig('')
    def on_reloadBtn_clicked(self):
        self.on_actionReload_triggered()

    @qtsig('')
    def on_clearCredBtn_clicked(self):
        self._last_creds = None
        self.setCachedCredsVisible(False)
        self.closeHost()
        self._clients.clear()

    def on_hostList_itemClicked(self, item):
        if item:
            data = item.data(ADDR_ROLE)
            if data:
                self.openHost(item.text(), False)
        else:
            self.closeHost()

    def on_hostList_customContextMenuRequested(self, pos):
        item = self.hostList.itemAt(pos)
        if not item:
            return
        self._showHostContextMenu(pos, item)

    def _showHostContextMenu(self, pos, item):
        contextMenu = QMenu()
        removeAction = contextMenu.addAction('Remove')
        removeAction.setIcon(QIcon(':/marche/cross.png'))

        chosenAction = contextMenu.exec_(
            self.hostList.viewport().mapToGlobal(pos))
        if chosenAction == removeAction:
            addr = item.text()
            self.removeHost(addr)

    def addHost(self, addr):
        if addr.startswith('Heading: '):
            self.addHeading(addr[9:])
            return
        self.removeHost(addr)
        host, port = normalize_addr(addr, 8124)
        addr = host + ':' + port
        if addr not in self._clients:
            item = QListWidgetItem(QIcon(':/marche/server-big.png'), host)
            item.setData(ADDR_ROLE, addr)
            self.hostList.addItem(item)
        return addr

    def addHeading(self, heading):
        item = QListWidgetItem(heading)
        item.setSizeHint(QSize(10, 25))
        fnt = item.font()
        fnt.setBold(True)
        item.setFont(fnt)
        self.hostList.addItem(item)

    def clear(self):
        while self._clients:
            addr, client = self._clients.popitem()
            client.stopPoller()
            self.removeHost(addr)

    def removeHost(self, addr):
        if addr in self._clients:
            del self._clients[addr]
        for row in range(self.hostList.count()):
            item = self.hostList.item(row)
            if item.data(ADDR_ROLE) == addr:
                self.hostList.takeItem(row)
                break

    def closeHost(self):
        if self._cur_tree:
            self._cur_tree.clear()
            self._cur_tree = None
        prev = self.surface.layout().takeAt(0)
        if prev:
            prev.widget().hide()
            prev.widget().deleteLater()

    def openHost(self, addr, select_item=True):
        def try_connect(host, port, user, passwd):
            try:
                client = Client(host, port, user, passwd)
            except xmlrpc.ProtocolError as e:
                if e.errcode != 401:
                    raise
                return
            return client

        def negotiate(addr):
            host, port = normalize_addr(addr, 8124)

            # try without credentials
            client = try_connect(host, port, None, None)
            if client:
                return client

            # try saved credentials
            user, passwd = loadCredentials(host)
            client = try_connect(host, port, user, passwd)
            if client:
                return client

            # try last used credentials
            if self._last_creds:
                user, passwd = self._last_creds
                client = try_connect(host, port, user, passwd)
                if client:
                    return client

            # ask for credentials
            while True:
                dlg = AuthDialog(self, 'Authenticate at %s' % addr)
                if not dlg.exec_():
                    break
                user = dlg.user
                passwd = dlg.passwd

                if dlg.save_creds:
                    saveCredentials(host, user, passwd)

                client = try_connect(host, port, user, passwd)
                if client:
                    self._last_creds = user, passwd
                    self.setCachedCredsVisible(True)
                    return client

            # no luck!
            raise RuntimeError('valid login credentials needed')

        self.closeHost()
        if addr not in self._clients:
            try:
                self._clients[addr] = negotiate(addr)
            except xmlrpc.Fault as err:
                QMessageBox.critical(self, 'Connection failed',
                                     'Could not connect to %s: %s' %
                                     (addr, err.faultString))
                return
            except Exception as err:
                QMessageBox.critical(self, 'Connection failed',
                                     'Could not connect to %s: %s' %
                                     (addr, err))
                return

        try:
            self._clients[addr].getVersion()
        except xmlrpc.ProtocolError as e:
            QMessageBox.critical(self, 'Connection failed',
                                 'Could not connect to %s: %s' %
                                 (addr, e.errmsg))
            del self._clients[addr]
            return

        widget = HostTree(self, self._clients[addr])
        self._cur_tree = widget

        self.surface.layout().addWidget(widget)
        widget.show()

        if select_item:
            for row in range(self.hostList.count()):
                item = self.hostList.item(row)
                if item.data(ADDR_ROLE) == addr:
                    self.hostList.setCurrentItem(item)
                    break

    def scanNetwork(self):
        hosts = Scanner(self).run()
        if not hosts:
            return
        for host in hosts:
            self.addHost(host)
