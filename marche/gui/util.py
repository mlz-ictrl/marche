#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2022 by the authors, see LICENSE
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
import os
import shutil
import socket

import psutil

from marche.gui.qt import QDialog, QSettings, uic
from marche.utils import bytencode

try:
    import ipaddress
except ImportError:
    import ipaddr as ipaddress


uipath = os.path.dirname(__file__)
KNOWN_EDITORS = ['gedit', 'kate', 'emacs', 'scite', 'geany', 'pluma',
                 'notepad']


def loadUi(widget, uiname, subdir='ui'):
    uic.loadUi(os.path.join(uipath, subdir, uiname), widget)


def loadUiType(uiname, subdir='ui'):
    # About resource_suffix: uic.loadUiType insists on creating
    # import statements with the name of the .qrc file followed
    # by this suffix.  Since the file is marche.qrc, this will now
    # import marche.gui.res (a dummy module).
    return uic.loadUiType(os.path.join(uipath, subdir, uiname),
                          resource_suffix='.gui.res')[0]


def getAvailableEditors():
    result = []
    for entry in KNOWN_EDITORS:
        if shutil.which(entry):
            result.append(entry)

    return result


def selectEditor():
    presets = getAvailableEditors()
    dlg = QDialog()
    loadUi(dlg, 'editor.ui')
    dlg.editorBox.addItems(presets)
    if not dlg.exec_():
        return None
    if dlg.cmdEdit.text():
        return dlg.cmdEdit.text()
    return dlg.editorBox.currentText()


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

    saveSetting('creds/%s/user' % host,
                base64.b64encode(bytencode(user)).decode(),
                settings=settings)
    saveSetting('creds/%s/passwd' % host,
                base64.b64encode(bytencode(passwd)).decode(),
                settings=settings)

    saveSetting('creds/hosts', hosts, settings=settings)


def loadCredentials(host):
    settings = _getSettingsObj()

    hosts = loadSetting('creds/hosts', default=[], valtype=list,
                        settings=settings)
    if host not in hosts:
        return (None, None)

    user = loadSetting('creds/%s/user' % host, settings=settings)
    passwd = loadSetting('creds/%s/passwd' % host, settings=settings)
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
    settings.remove('creds/%s/user' % host)
    settings.remove('creds/%s/passwd' % host)


def loadAllCredentials():
    hosts = loadSetting('creds/hosts', default=[], valtype=list)
    return dict((host, loadCredentials(host)) for host in hosts)


def determineSubnet():
    try:
        ip = socket.gethostbyname(socket.gethostname())
    except socket.gaierror:
        # no hostname set, or weird hosts configuration
        return None
    ifs = psutil.net_if_addrs()

    for _, addrs in ifs.items():
        for addr in addrs:
            if addr.address == ip:
                return str(ipaddress.ip_network(u'%s/%s' %
                                                (ip, addr.netmask), False))
    return None


def getSubnetHostsAddrs(subnet):
    net = ipaddress.IPv4Network(str(subnet))

    # ipaddr compatiblity
    if hasattr(net, 'iterhosts'):
        net.hosts = net.iterhosts

    return [str(entry) for entry in net.hosts()]
