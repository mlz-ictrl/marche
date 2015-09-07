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

"""Job for Entangle servers."""

import os
import ast
import ConfigParser
from os import path

#import PyTango

from marche.jobs import DEAD, STARTING, RUNNING


def convert_value(value):
    """Handle arrays and quoted values in resfile entries."""
    value = value.strip()
    # evaluate quoted values as Python strings, allows for
    # embedding escape sequences
    if value.startswith('"') and value.endswith('"'):
        values = [str(ast.literal_eval(value))]
    else:
        values = []
        for item in value.split(','):
            item = item.strip()
            if item.startswith('"') and item.endswith('"'):
                item = str(ast.literal_eval(item))
            values.append(item)
    return values


def read_resfile(filename):
    """Read device names and properties from a resource file."""
    devices = {}
    with open(filename) as fp:
        for line in fp:
            line = line.strip()
            # comments
            if not line or line.startswith(('#', '%')):
                continue
            try:
                key, value = line.split(':', 1)
                cat1, cat2, devname, propname = key.strip().split('/')
                value = convert_value(value)
            except ValueError:
                continue
            devname = '%s/%s/%s' % (cat1, cat2, devname)
            devices.setdefault(devname, {})[propname] = value
    for dev in list(devices):
        if 'type' not in devices[dev]:
            del devices[dev]
    return devices


class Job(object):

    def __init__(self, name, config, log):
        self.config = config
        self.log = log.getChild(name)

    def get_services(self):
        cfg = ConfigParser.RawConfigParser()
        cfg.read('/etc/entangle.conf')

        if cfg.has_option('entangle', 'resdir'):
            resdir = cfg.get('entangle', 'resdir')
        else:
            resdir = '/etc/entangle'

        all_servers = ['entangle.' + base for (base, ext) in
                       map(path.splitext, os.listdir(resdir)) if ext == '.res']
        all_servers.sort()

        return all_servers

    # XXX use subprocess here...

    def start_service(self, name):
        self.log.info('starting server %s' % name)
        os.system('/etc/init.d/entangle start ' + name[9:])

    def stop_service(self, name):
        self.log.info('stopping server %s' % name)
        os.system('/etc/init.d/entangle stop ' + name[9:])

    # XXX check devices with Tango clients

    def service_status(self, name):
        if os.system('/etc/init.d/entangle status ' + name[9:]) == 0:
            return RUNNING
        return DEAD
