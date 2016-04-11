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

import os
import sys
import base64

from PyQt4 import uic
from PyQt4.QtGui import QDialog
from PyQt4.QtCore import QSettings

try:
    from PyQt4.QtCore import QPyNullVariant  # pylint: disable=E0611
except ImportError:
    class QPyNullVariant(object):
        pass

from marche.six import iteritems


uipath = os.path.dirname(__file__)
KNOWN_EDITORS = ['gedit', 'kate', 'emacs', 'scite', 'geany', 'pluma']


def loadUi(widget, uiname, subdir='ui'):
    uic.loadUi(os.path.join(uipath, subdir, uiname), widget)


# as copied from Python 3.3
def which(cmd, mode=os.F_OK | os.X_OK, path=None):
    """Given a command, mode, and a PATH string, return the path which
    conforms to the given mode on the PATH, or None if there is no such
    file.

    `mode` defaults to os.F_OK | os.X_OK. `path` defaults to the result
    of os.environ.get("PATH"), or can be overridden with a custom search
    path.

    """
    # Check that a given file can be accessed with the correct mode.
    # Additionally check that `file` is not a directory, as on Windows
    # directories pass the os.access check.
    def _access_check(fn, mode):
        return (os.path.exists(fn) and os.access(fn, mode) and
                not os.path.isdir(fn))

    # Short circuit. If we're given a full path which matches the mode
    # and it exists, we're done here.
    if _access_check(cmd, mode):
        return cmd

    path = (path or os.environ.get("PATH", os.defpath)).split(os.pathsep)

    if sys.platform == "win32":
        # The current directory takes precedence on Windows.
        if os.curdir not in path:
            path.insert(0, os.curdir)

        # PATHEXT is necessary to check on Windows.
        pathext = os.environ.get("PATHEXT", "").split(os.pathsep)
        # See if the given file matches any of the expected path extensions.
        # This will allow us to short circuit when given "python.exe".
        matches = [cmd for ext in pathext if cmd.lower().endswith(ext.lower())]
        # If it does match, only test that one, otherwise we have to try
        # others.
        files = [cmd] if matches else [cmd + ext.lower() for ext in pathext]
    else:
        # On other platforms you don't have things like PATHEXT to tell you
        # what file suffixes are executable, so just pass on cmd as-is.
        files = [cmd]

    seen = set()
    for dir_ in path:
        dir_ = os.path.normcase(dir_)
        if dir_ not in seen:
            seen.add(dir_)
            for thefile in files:
                name = os.path.join(dir_, thefile)
                if _access_check(name, mode):
                    return name
    return None


def getAvailableEditors():
    result = []
    for entry in KNOWN_EDITORS:
        if which(entry):
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

    if isinstance(raw, QPyNullVariant):
        raw = None
    if raw is None:
        raw = default
    if raw is None:
        return raw

    return valtype(raw)


def saveSettings(settings_dict):
    settings = _getSettingsObj()
    for key, value in iteritems(settings_dict):
        saveSetting(key, value, settings=settings)


def loadSettings(request):
    settings = _getSettingsObj()

    result = {}
    if isinstance(request, list):
        for key in request:
            result[key] = loadSetting(key, settings=settings)
    elif isinstance(request, dict):
        for key, default in iteritems(request):
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
                base64.b64encode(user.encode('utf-8')).decode(),
                settings=settings)
    saveSetting('creds/%s/passwd' % host,
                base64.b64encode(passwd.encode('utf-8')).decode(),
                settings=settings)

    saveSetting('creds/hosts', hosts, settings=settings)


def loadCredentials(host):
    settings = _getSettingsObj()

    hosts = loadSetting('creds/hosts', default=[], valtype=list,
                        settings=settings)
    if host not in hosts:
        return (None, None)

    user = base64.b64decode(loadSetting('creds/%s/user' % host,
                                        settings=settings).encode()).decode('utf-8')
    passwd = base64.b64decode(loadSetting('creds/%s/passwd' % host,
                                          settings=settings).encode()).decode('utf-8')

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
