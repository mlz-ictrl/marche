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

"""Job for Entangle servers."""

import os
import ast
import ConfigParser
from os import path

#import PyTango

from marche.jobs import DEAD, STARTING, STOPPING, RUNNING, Busy
from marche.jobs.base import Job as BaseJob


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


CONFIG = '/etc/entangle/entangle.conf'
INITSCR = '/etc/init.d/entangle'


class Job(BaseJob):

    def __init__(self, name, config, log):
        BaseJob.__init__(self, name, config, log)
        self._server_procs = {}

    def check(self):
        if not (path.exists(CONFIG) and path.exists(INITSCR)):
            self.log.error('%s or %s missing' % (CONFIG, INITSCR))
            return False
        return True

    def get_services(self):
        cfg = ConfigParser.RawConfigParser()
        cfg.read(CONFIG)

        if cfg.has_option('entangle', 'resdir'):
            resdir = cfg.get('entangle', 'resdir')
        else:
            resdir = '/etc/entangle'

        all_servers = ['entangle.' + base for (base, ext) in
                       map(path.splitext, os.listdir(resdir)) if ext == '.res']
        all_servers.sort()

        return all_servers

    def _proc(self, name):
        proc = self._server_procs.get(name)
        if proc and not proc.done:
            return proc

    def start_service(self, name):
        if self._proc(name):
            raise Busy
        self.log.info('starting server %s' % name)
        self._server_procs[name] = self._async(STARTING,
                                               'sleep 5; %s start %s' % (INITSCR, name[9:]))

    def stop_service(self, name):
        if self._proc(name):
            raise Busy
        self.log.info('stopping server %s' % name)
        self._server_procs[name] = self._async(STOPPING,
                                               'sleep 5; %s stop %s' % (INITSCR, name[9:]))

    # XXX check devices with Tango clients

    def service_status(self, name):
        proc = self._proc(name)
        if proc:
            return proc.status
        if self._sync(0, '%s status %s' % (INITSCR, name[9:])).retcode == 0:
            return RUNNING
        return DEAD
