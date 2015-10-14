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

from xmlrpclib import ProtocolError, Fault

import marche.gui.res  # noqa

from marche.gui.util import loadUi
from marche.gui.client import Client, ClientError
from marche.gui.scan import Scanner
from marche.jobs import STATE_STR, RUNNING, WARNING, DEAD, STARTING, STOPPING, \
    INITIALIZING
from marche.utils import normalizeAddr
from marche.version import get_version

from PyQt4.QtCore import pyqtSignature as qtsig, Qt, QSize, QSettings, QByteArray
from PyQt4.QtGui import QWidget, QInputDialog, QColor, QTreeWidget, QDialog, \
    QTreeWidgetItem, QBrush, QMessageBox, QIcon, QListWidgetItem, QLabel, QMenu, \
    QPlainTextEdit, QFileDialog, QDialogButtonBox


class AuthDialog(QDialog):
    def __init__(self, parent, title):
        QDialog.__init__(self, parent)
        loadUi(self, 'authdlg.ui')
        self.buttonBox.button(QDialogButtonBox.Ok).setDefault(True)
        self.nameLbl.setText(title)
        self.setWindowTitle(title)

    @property
    def user(self):
        return str(self.userLineEdit.text()).strip()

    @property
    def passwd(self):
        return str(self.passwdLineEdit.text()).strip()


class JobButtons(QWidget):
    def __init__(self, client, service, instance, item, parent=None):
        QWidget.__init__(self, parent)
        loadUi(self, 'job.ui')

        self._item = item
        self._client = client
        self._service = service
        self._instance = instance

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
    def on_outputBtn_clicked(self):
        self._item.setText(3, '')
        try:
            output = self._client.getServiceOutput(self._service, self._instance)
            loglines = self._client.getServiceLogs(self._service, self._instance)
        except ClientError as err:
            self._item.setText(3, str(err))
        dlg = QDialog(self)
        loadUi(dlg, 'details.ui')
        dlg.outEdit.setPlainText(''.join(output))
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
            dlg.tabber.addTab(widget, 'Logfile: ' + filename)
        dlg.exec_()


class HostTree(QTreeWidget):
    STATE_COLORS = {
        RUNNING:      ('green', ''),
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
        try:
            self.fill()
        except Exception:
            pass

        self.expandAll()
        self.resizeColumnToContents(0)
        self.setColumnWidth(0, self.columnWidth(0) * 1.4)
        self.resizeColumnToContents(2)
        width = sum([self.columnWidth(i) for i in range(self.columnCount())])
        self.setMinimumWidth(width+25)
        # self.collapseAll()

    def clear(self):
        self._client.stopPoller()
        self._items.clear()
        QTreeWidget.clear(self)

    def fill(self):
        self.clear()
        services = self._client.getServices()
        self._client.startPoller(self.updateStatus)

        for service, instances in services.iteritems():
            serviceItem = QTreeWidgetItem([service])
            serviceItem.setForeground(1, QBrush(QColor('white')))
            serviceItem.setTextAlignment(1, Qt.AlignCenter)
            serviceItem.setFlags(Qt.ItemIsEnabled)
            serviceItem.setForeground(3, QBrush(QColor('red')))
            self.addTopLevelItem(serviceItem)

            if not instances:
                self._items[service] = serviceItem
                btn = JobButtons(self._client, service, None, serviceItem)
                self.setItemWidget(serviceItem, 2, btn)
            else:
                lbl = QLabel(self)
                lbl.setMinimumSize(QSize(30, 30))
                self.setItemWidget(serviceItem, 2, lbl)
                self._items[service] = {}
                for instance in instances:
                    instanceItem = QTreeWidgetItem([instance])
                    instanceItem.setForeground(1, QBrush(QColor('white')))
                    instanceItem.setTextAlignment(1, Qt.AlignCenter)
                    instanceItem.setFlags(Qt.ItemIsEnabled)
                    instanceItem.setForeground(3, QBrush(QColor('red')))
                    serviceItem.addChild(instanceItem)

                    btn = JobButtons(self._client, service, instance, instanceItem)
                    self.setItemWidget(instanceItem, 2, btn)

                    self._items[service][instance] = instanceItem

    def updateStatus(self, service, instance, status):
        if service not in self._items:
            return
        item = self._items[service]

        if instance:
            if instance not in self._items[service]:
                return
            item = self._items[service][instance]

        colors = self.STATE_COLORS.get(status, ('gray', ''))
        item.setForeground(1, QBrush(QColor(colors[0])) if colors[0] else QBrush())
        item.setBackground(1, QBrush(QColor(colors[1])) if colors[1] else QBrush())
        item.setText(1, STATE_STR[status])

        if status in [STARTING, INITIALIZING, STOPPING]:
            item.setIcon(1, QIcon(':/marche/ui-progress-bar.png'))
        else:
            item.setIcon(1, QIcon())

    def reloadJobs(self):
        self._client.reloadJobs()
        self.fill()
        self.expandAll()


class MainWidget(QWidget):
    def __init__(self, parent=None, scan_on_startup=False):
        QWidget.__init__(self, parent)
        loadUi(self, 'main.ui')

        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 3)
        self.leftlayout.setContentsMargins(6, 6, 0, 6)
        self.surface.layout().setContentsMargins(0, 6, 6, 6)

        settings = QSettings('marche-gui')
        self.splitter.restoreState(settings.value('split', b'', QByteArray))

        self._clients = {}
        self._cur_tree = None

        if scan_on_startup:
            self.scanNetwork()

    def saveSettings(self):
        settings = QSettings('marche-gui')
        settings.setValue('split', self.splitter.saveState())
        # settings.setValue('last_hosts', [])

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
                    hosts = [h.strip() for h in fp]
                else:
                    raise RuntimeError('Unrecognized file format.')
        except Exception as err:
            QMessageBox.critical(self, 'Error', str(err))
            return
        self.closeHost()
        self.hostList.clear()
        for host in hosts:
            self.addHost(host)
        if hosts:
            self.openHost(hosts[-1])

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
              (C) 2015 MLZ instrument control
            </p>
            <p>
              Marche GUI is a graphical interface for the Marche process control system.
            </p>
            <h3>Authors:</h3>
            <ul>
              <li>Copyright (C) 2015
                <a href="mailto:g.brandl@fz-juelich.de">Georg Brandl</a></li>
              <li>Copyright (C) 2015
                <a href="mailto:alexander.lenz@frm2.tum.de">Alexander Lenz</a></li>
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

    def on_hostList_itemClicked(self, item):
        if item:
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

        chosenAction = contextMenu.exec_(self.hostList.viewport().mapToGlobal(pos))
        if chosenAction == removeAction:
            addr = item.text()
            self.removeHost(addr)

    def addHost(self, addr):
        self.removeHost(addr)
        host, port = normalizeAddr(addr, 8124)
        addr = host + ':' + port
        if addr not in self._clients:
            item = QListWidgetItem(QIcon(':/marche/server-big.png'), addr)
            self.hostList.addItem(item)
        return addr

    def removeHost(self, addr):
        if addr in self._clients:
            del self._clients[addr]
        items = self.hostList.findItems(addr, Qt.MatchExactly)
        if items:
            self.hostList.takeItem(self.hostList.row(items[0]))

    def closeHost(self):
        if self._cur_tree:
            self._cur_tree.clear()
            self._cur_tree = None
        prev = self.surface.layout().takeAt(0)
        if prev:
            prev.widget().hide()
            prev.widget().deleteLater()

    def openHost(self, addr, select_item=True):
        self.closeHost()
        if addr not in self._clients:
            host, port = normalizeAddr(addr, 8124)

            try:
                client = Client(host, port)
                client.getVersion()
            except ProtocolError as e:
                if e.errcode != 401:
                    raise
                user = 'marche'
                passwd = 'marche'

                dlg = AuthDialog(self, 'Authenticate at %s' % addr)
                if dlg.exec_():
                    user = dlg.user
                    passwd = dlg.passwd

                    client = Client(host, port, user, passwd)
            except Fault as err:
                QMessageBox.critical(self, 'Connection failed',
                                     'Could not connect to %s: %s' %
                                     (addr, err.faultString))
                return
            except Exception as err:
                QMessageBox.critical(self, 'Connection failed',
                                     'Could not connect to %s: %s' %
                                     (addr, err))
                return

            self._clients[addr] = client

        try:
            self._clients[addr].getVersion()
        except ProtocolError as e:
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
            item = self.hostList.findItems(addr, Qt.MatchExactly)[0]
            self.hostList.setCurrentItem(item)

    def scanNetwork(self):
        hosts = Scanner(self).run()
        if not hosts:
            return
        for host in hosts:
            self.addHost(host)
