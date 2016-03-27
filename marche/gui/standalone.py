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

import sys
import optparse

from PyQt4.QtGui import QApplication, QMainWindow
from PyQt4.QtCore import Qt, QSettings, QByteArray

from marche.gui.main import MainWidget


class MainWindow(QMainWindow):
    def __init__(self, parent=None, scan_on_startup=False):
        QMainWindow.__init__(self, parent)
        self.resize(800, 500)
        self._widget = MainWidget(self, scan_on_startup=scan_on_startup)
        self.setCentralWidget(self._widget)
        settings = QSettings()
        self.restoreGeometry(settings.value('geometry', b'', QByteArray))
        self.setWindowTitle('Marche')

        menu = self.menuBar()
        menuFile = menu.addMenu('File')
        menuFile.addAction(self._widget.actionAdd_host)
        menuFile.addAction(self._widget.actionScan_network)
        menuFile.addSeparator()
        menuFile.addAction(self._widget.actionLoad_session)
        menuFile.addAction(self._widget.actionSave_session_as)
        menuFile.addSeparator()
        menuFile.addAction(self._widget.actionExit)
        self._widget.actionExit.triggered.connect(self.close)
        menuEdit = menu.addMenu('Edit')
        menuEdit.addAction(self._widget.actionPreferences)
        menuJobs = menu.addMenu('Jobs')
        menuJobs.addAction(self._widget.actionReload)
        menuHelp = menu.addMenu('Help')
        menuHelp.addAction(self._widget.actionAbout)
        menuHelp.addAction(self._widget.actionAbout_Qt)

        self.statusBar().showMessage('Welcome!', 1000)

    def addHost(self, host):
        self._widget.openHost(self._widget.addHost(host))

    def loadSession(self, filename):
        self._widget.loadSession(filename)

    def closeEvent(self, event):
        self._widget.saveSettings()
        settings = QSettings()
        settings.setValue('geometry', self.saveGeometry())
        return QMainWindow.closeEvent(self, event)


def main():
    parser = optparse.OptionParser()
    parser.add_option('-B', dest='noscan', action='store_true',
                      help='do not scan local network for hosts')
    opts, args = parser.parse_args()

    app = QApplication(sys.argv)
    app.setAttribute(Qt.AA_DontShowIconsInMenus, False)
    app.setOrganizationName('mlz')
    app.setApplicationName('marche-gui')

    win = MainWindow(scan_on_startup=not opts.noscan)

    for arg in args:
        if arg.endswith('.marche'):
            win.loadSession(arg)
        else:
            win.addHost(arg)

    win.show()

    return app.exec_()
