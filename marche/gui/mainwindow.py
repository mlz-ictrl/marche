#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2018 by the authors, see LICENSE
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

import socket


from marche.six import iteritems
from marche.six.moves import range  # pylint: disable=redefined-builtin
from marche.six.moves import xmlrpc_client as xmlrpc
from marche.gui.qt import pyqtSlot, QSize, QSettings, QByteArray, QIcon, \
    QMainWindow, QInputDialog, QMessageBox, QMenu, QListWidgetItem, QFileDialog
from marche.gui.util import loadUi, loadSettings, saveSettings, loadSetting, \
    saveCredentials, loadCredentials, loadAllCredentials, removeCredentials
from marche.gui.client import Client
from marche.gui.dialogs import AuthDialog, PreferencesDialog, PassiveScanDialog
from marche.gui.hosttree import HostTree
from marche.gui.scan import SubnetInputDialog, ActiveScanner
from marche.utils import normalize_addr
from marche.version import get_version


ADDR_ROLE = 32


class MainWindow(QMainWindow):
    def __init__(self, parent=None, scan_on_startup=False):
        QMainWindow.__init__(self, parent)
        loadUi(self, 'mainwindow.ui')
        self.resize(800, 500)

        self.setCachedCredsVisible(False)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 5)
        self.leftlayout.setContentsMargins(6, 6, 0, 6)
        self.surface.layout().setContentsMargins(0, 6, 6, 6)

        self.restoreSettings()

        self._clients = {}
        self._cur_tree = None
        self._last_creds = None

        self._subnet_scanner = ActiveScanner(self)
        self._subnet_scanner.hostFound.connect(self.addHost)
        self._subnet_scanner.scanNotify.connect(self.mainStatusBar.showMessage)
        self._subnet_scanner.finished.connect(self.subnetScanFinished)

        if loadSetting('defaultSession'):
            self.loadDefaultSession()
        elif scan_on_startup:
            self.scanLocalNetwork()

    def closeEvent(self, event):
        self.saveSettings()
        return QMainWindow.closeEvent(self, event)

    def loadDefaultSession(self):
        self.loadSession(loadSetting('defaultSession'), True)

    def saveSettings(self):
        settings = QSettings('marche-gui')
        settings.setValue('split', self.splitter.saveState())
        settings.setValue('geometry', self.saveGeometry())

    def restoreSettings(self):
        settings = QSettings('marche-gui')
        self.restoreGeometry(settings.value('geometry', b'', QByteArray))
        self.splitter.restoreState(settings.value('split', b'', QByteArray))
        self.hostList.setSortingEnabled(loadSetting('sortHostListEnabled',
                                                    'false') == 'true')

    def setCachedCredsVisible(self, flag):
        flag = bool(flag and self._last_creds)
        if flag:
            self.lblCachedUserCreds.setText(self._last_creds[0])
        self.cachePanel.setVisible(flag)

    @pyqtSlot()
    def on_actionExit_triggered(self):
        self.close()

    @pyqtSlot()
    def on_actionPreferences_triggered(self):
        dlg = PreferencesDialog(self)

        # load and enter settings
        settings = loadSettings(['defaultEditor',
                                 'pollInterval',
                                 'defaultSession',
                                 'defUsername',
                                 'sortHostListEnabled'])

        if settings['defaultEditor']:
            dlg.defaultEditor = settings['defaultEditor']
        if settings['defUsername']:
            dlg.defUsername = settings['defUsername']
        if settings['pollInterval']:
            dlg.pollInterval = settings['pollInterval']
        if settings['defaultSession']:
            dlg.defaultSession = settings['defaultSession']
        if settings['sortHostListEnabled']:
            dlg.sortHostListEnabled = settings['sortHostListEnabled'] == 'true'

        dlg.credentials = loadAllCredentials()
        oldCredHosts = set(dlg.credentials.keys())

        if dlg.exec_():
            saveSettings({
                'defaultEditor': dlg.defaultEditor,
                'pollInterval': dlg.pollInterval,
                'defaultSession': dlg.defaultSession,
                'defUsername': dlg.defUsername,
                'sortHostListEnabled': dlg.sortHostListEnabled,
            })

            for host, (user, passwd) in iteritems(dlg.credentials):
                saveCredentials(host, user, passwd)

            for host in oldCredHosts - set(dlg.credentials):
                removeCredentials(host)

            if dlg.pollInterval != settings['pollInterval'] \
               and self._cur_tree is not None:
                self._cur_tree.refresh()

            self.hostList.setSortingEnabled(dlg.sortHostListEnabled)
            if dlg.sortHostListEnabled:
                self.hostList.sortItems()

    @pyqtSlot()
    def on_actionAdd_host_triggered(self):
        addr, accepted = QInputDialog.getText(self, 'Add host', 'New host:')
        if accepted:
            self.openHost(self.addHost(addr))

    @pyqtSlot()
    def on_actionAdd_network_triggered(self):
        dlg = SubnetInputDialog(self)
        if dlg.exec_():
            self.addNetwork(dlg.subnet)

    @pyqtSlot()
    def on_actionScan_local_network_triggered(self):
        self.scanLocalNetwork()

    @pyqtSlot()
    def on_actionReload_triggered(self):
        if self._cur_tree:
            self._cur_tree.reloadJobs()

    @pyqtSlot()
    def on_actionLoad_session_triggered(self):
        filename = QFileDialog.getOpenFileName(self, 'Load session', '',
                                               'Marche sessions (*.marche)')
        if not filename:
            return
        self.loadSession(filename)

    def loadSession(self, filename, silent=False):
        try:
            with open(filename) as fp:
                firstline = fp.readline()
                if firstline.startswith('Marche session v1'):
                    hosts = [h for h in (h.strip() for h in fp) if h]
                else:
                    raise RuntimeError('Unrecognized file format.')
        except Exception as err:
            if not silent:
                QMessageBox.critical(self, 'Error', str(err))
            return
        self.closeHost()
        self.hostList.clear()
        for host in hosts:
            self.addHost(host)

    @pyqtSlot()
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

    @pyqtSlot()
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
              <li>Copyright (C) 2015-2017
                <a href="mailto:g.brandl@fz-juelich.de">Georg Brandl</a></li>
              <li>Copyright (C) 2015-2017
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

    @pyqtSlot()
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

    def addNetwork(self, subnet):
        self.actionAdd_network.setEnabled(False)
        self._subnet_scanner.setSubnet(subnet)
        self._subnet_scanner.start()

    def subnetScanFinished(self):
        self.actionAdd_network.setEnabled(True)
        self.mainStatusBar.showMessage('Scan finished!')

    def addHost(self, addr):
        if addr.startswith('Heading: '):
            self.addHeading(addr[9:])
            return
        host, port = normalize_addr(addr, 8124)
        addr = host + ':' + port
        self.removeHost(addr)
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
            if item.data(ADDR_ROLE) and \
               item.data(ADDR_ROLE).split(':')[0] == addr.split(':')[0]:
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
                dlg = AuthDialog(self, 'Authenticate at %s' % addr,
                                 loadSetting('defUsername'))
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
        except socket.timeout:
            QMessageBox.critical(self, 'Connection failed',
                                 'Could not connect to %s: timeout')
            del self._clients[addr]
            return
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
                if item.data(ADDR_ROLE) and \
                   item.data(ADDR_ROLE).split(':')[0] == addr.split(':')[0]:
                    self.hostList.setCurrentItem(item)
                    break

    def scanLocalNetwork(self):
        hosts = PassiveScanDialog(self).run()
        if not hosts:
            return
        for host in hosts:
            self.addHost(host)
