#!/usr/bin/env python
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

import argparse

from marche.gui.mainwindow import MainWindow
from marche.gui.qt import QApplication, Qt


def parse_args(argv):
    parser = argparse.ArgumentParser(description='Marche control GUI',
                                     conflict_handler='resolve')
    parser.add_argument('-B', '--noscan', action='store_true',
                        help='Do not scan local network for hosts',
                        default=False)
    parser.add_argument('session_or_host', type=str,
                        help='Session or host to load', nargs='*')
    return parser.parse_args(argv)


def main(argv):
    args = parse_args(argv[1:])

    app = QApplication(argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)
    app.setOrganizationName('mlz')
    app.setApplicationName('marche-gui')

    win = MainWindow(scan_on_startup=not args.noscan)

    last_host = None
    for arg in args.session_or_host:
        if arg.endswith('.marche'):
            win.loadSession(arg)
        else:
            win.addHost(arg)
            last_host = arg
    if last_host:
        win.openHost(last_host)

    win.show()

    return app.exec()
