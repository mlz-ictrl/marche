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
#
# *****************************************************************************

"""Config file handling."""

import os
import ConfigParser
from os import path


class CasePreservingConfigParser(ConfigParser.SafeConfigParser):
    def optionxform(self, key):
        return key


class Config(object):
    """An object that represents all """

    user = None
    group = None
    piddir = '/var/run'
    logdir = '/var/log'
    extended = {}

    job_config = {}
    interface_config = {
        'xmlrpc' : {
            'port' : 8124
            },
        'tango' : {}
            }
    interfaces = ['xmlrpc', 'tango']

    def __init__(self, confdir):
        self.confdir = confdir
        self.reload()

    def reload(self):
        confdir = self.confdir
        self.__dict__.clear()
        self.confdir = confdir
        self.job_config = {}
        if not path.isdir(self.confdir):
            return

        for fn in os.listdir(self.confdir):
            if fn.endswith('.conf'):
                self._read_one(path.join(self.confdir, fn))

    def _read_one(self, fname):
        parser = CasePreservingConfigParser()
        parser.read(fname)

        for section in parser.sections():
            if section == 'general':
                if parser.has_option('general', 'user'):
                    self.user = parser.get('general', 'user')
                if parser.has_option('general', 'group'):
                    self.group = parser.get('general', 'group')
                if parser.has_option('general', 'piddir'):
                    self.piddir = parser.get('general', 'piddir')
                if parser.has_option('general', 'logdir'):
                    self.logdir = parser.get('general', 'logdir')
                if parser.has_option('general', 'interfaces'):
                    self.interfaces = [
                        i.strip() for i in
                        parser.get('general', 'interfaces').split(',')]
                self.extended = parser.items('general')
            elif section.startswith('job.'):
                self.job_config[section[4:]] = dict(parser.items(section))
            elif section.startswith('interface.'):
                if not section[10:] in self.interface_config:
                    self.interface_config[section[10:]] = {}
                self.interface_config[section[10:]].update(dict(parser.items(section)))
