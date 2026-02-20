# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-present by the authors, see LICENSE
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

import base64
import ipaddress
import shutil
import socket
from pathlib import Path

import psutil

from marche.gui.qt import PYQT_VERSION, QDialog, QSettings, uic

uipath = Path(__file__).parent
KNOWN_EDITORS = ['gedit', 'kate', 'emacs', 'scite', 'geany', 'pluma',
                 'notepad']

# any flags needed to make the editor wait until the file is closed again
EDITOR_FLAGS = {
    # technically only needed if there is already a gedit instance running
    'gedit': ['--wait'],
    # always needed, kate forks per default
    'kate': ['--block'],
    # no-session not strictly needed
    'geany': ['--new-instance', '--no-session'],
}


def loadUi(widget, uiname, subdir='ui'):
    uic.loadUi(uipath / subdir / uiname, widget)


def loadUiType(uiname, subdir='ui'):
    if PYQT_VERSION >= 0x60000:
        return uic.loadUiType(uipath / subdir / uiname)[0]
    # About resource_suffix: uic.loadUiType insists on creating
    # import statements with the name of the .qrc file followed
    # by this suffix.  Since the file is marche.qrc, this will now
    # import marche.gui.res (a dummy module).
    return uic.loadUiType(uipath / subdir / uiname,
                          resource_suffix='.gui.res')[0]


def getAvailableEditors():
    return [entry for entry in KNOWN_EDITORS if shutil.which(entry)]


def selectEditor():
    presets = getAvailableEditors()
    dlg = QDialog()
    loadUi(dlg, 'editor.ui')
    dlg.editorBox.addItems(presets)
    if not dlg.exec():
        return None
    if dlg.cmdEdit.text():
        return dlg.cmdEdit.text()
    return dlg.editorBox.currentText()


def getEditorArguments(editor):
    if editor in EDITOR_FLAGS:
         return ' '.join(EDITOR_FLAGS[editor])
    return None


def _getSettingsObj():
    return QSettings('marche-gui')


def saveSetting(name, value, settings=None):
    if settings is None:
        settings = _getSettingsObj()
    settings.setValue(name, value)


def loadSetting(name, default=None, valtype=str, settings=None):
    if settings is None:
        settings = _getSettingsObj()

    raw = settings.value(name, default)

    if raw is None:
        raw = default
    if raw is None:
        return raw

    return valtype(raw)


def saveSettings(settings_dict):
    settings = _getSettingsObj()
    for key, value in settings_dict.items():
        saveSetting(key, value, settings=settings)


def loadSettings(request):
    settings = _getSettingsObj()

    result = {}
    if isinstance(request, list):
        for key in request:
            result[key] = loadSetting(key, settings=settings)
    elif isinstance(request, dict):
        for key, default in request.items():
            result[key] = loadSetting(key, default, settings=settings)

    return result


def saveCredentials(host, user, passwd):
    settings = _getSettingsObj()

    hosts = loadSetting('creds/hosts', default=[], valtype=list,
                        settings=settings)
    hosts = set(hosts)
    hosts.add(host)
    hosts = list(hosts)

    saveSetting(f'creds/{host}/user',
                base64.b64encode(user.encode()).decode(),
                settings=settings)
    saveSetting(f'creds/{host}/passwd',
                base64.b64encode(passwd.encode()).decode(),
                settings=settings)

    saveSetting('creds/hosts', hosts, settings=settings)


def loadCredentials(host):
    settings = _getSettingsObj()

    hosts = loadSetting('creds/hosts', default=[], valtype=list,
                        settings=settings)
    if host not in hosts:
        return (None, None)

    user = loadSetting(f'creds/{host}/user', settings=settings)
    passwd = loadSetting(f'creds/{host}/passwd', settings=settings)
    if user is None or passwd is None:
        return (None, None)

    user = base64.b64decode(user.encode()).decode('utf-8')
    passwd = base64.b64decode(passwd.encode()).decode('utf-8')

    return (user, passwd)


def removeCredentials(host):
    settings = _getSettingsObj()

    hosts = loadSetting('creds/hosts', default=[], valtype=list,
                        settings=settings)
    while host in hosts:
        hosts.remove(host)

    saveSetting('creds/hosts', hosts, settings=settings)
    settings.remove(f'creds/{host}/user')
    settings.remove(f'creds/{host}/passwd')


def loadAllCredentials():
    hosts = loadSetting('creds/hosts', default=[], valtype=list)
    return {host: loadCredentials(host) for host in hosts}


def determineSubnet():
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except socket.gaierror:
        # no hostname set, or weird hosts configuration
        return None
    ifs = psutil.net_if_addrs()

    for addrs in ifs.values():
        for addr in addrs:
            if addr.address == ip:
                return str(ipaddress.ip_network(f'{ip}/{addr.netmask}', strict=False))
    return None


def getSubnetHostsAddrs(subnet):
    net = ipaddress.IPv4Network(str(subnet))
    return [str(entry) for entry in net.hosts()]
