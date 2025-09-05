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

"""Config file handling."""

from collections import OrderedDict

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from marche.permission import DISPLAY, STRING_LEVELS


class Config:
    """An object that represents all merged Marche configuration files."""

    job_config = {}
    auth_config = {}
    iface_config = {}
    unauth_level = DISPLAY

    def __init__(self, confdir=None):
        self.confdir = confdir
        self.reload()

    def reload(self):
        confdir = self.confdir
        self.__dict__.clear()
        self.confdir = confdir
        self.job_config = OrderedDict()
        self.auth_config = {}
        self.iface_config = {}
        if confdir is None or not self.confdir.is_dir():
            return

        for fn in sorted(self.confdir.glob('*.conf')):
            self._read_one(fn)

    def _read_one(self, fname):
        try:
            conf = tomllib.loads(fname.read_text())
        except tomllib.TOMLDecodeError as e:
            raise RuntimeError('TOML error in config file '
                               f'{fname}: {e}') from None

        for section, content in conf.items():
            if section == 'general':
                if 'unauth_level' in content:
                    perm = content['unauth_level']
                    self.unauth_level = STRING_LEVELS.get(perm.lower(),
                                                          DISPLAY)
            if section == 'job':
                self.job_config.update(content)
            elif section == 'auth':
                for authname, authconf in content.items():
                    if not isinstance(authconf, list):
                        authconf = [authconf]
                    self.auth_config.setdefault(authname, []).extend(authconf)
            elif section == 'interface':
                self.iface_config.update(content)
