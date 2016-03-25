#  -*- coding: utf-8 -*-
# *****************************************************************************
# MLZ server control daemon
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

""".. index:: entangle; job

Entangle Servers job
====================

This is a job for controlling all Entangle_ servers configured on the host.

.. _Entangle: https://forge.frm2.tum.de/entangle/doc/entangle-master/

This job has the following configuration parameters:

.. describe:: [job.xxx]

   .. describe:: type

      Must be ``entangle``.

   No further configuration is necessary; the job will read the Entangle
   configuration file ``/etc/entangle/entangle.conf`` and derive parameters
   like available servers and their logfiles from there.
"""

import os
import ast
from os import path

from marche.six.moves import configparser

from marche.jobs.base import Job as BaseJob
from marche.utils import extractLoglines, readFile, writeFile


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
    with open(filename, 'rb') as fp:
        for line in fp:
            line = line.decode('utf-8', 'replace').strip()
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

        self._ok = (path.exists(CONFIG) and path.exists(INITSCR))

        if not self._ok:
            return
        cfg = configparser.RawConfigParser()
        cfg.read(CONFIG)

        if cfg.has_option('entangle', 'resdir'):
            self._resdir = cfg.get('entangle', 'resdir')
        else:
            self._resdir = '/etc/entangle'
        if cfg.has_option('entangle', 'logdir'):
            self._logdir = cfg.get('entangle', 'logdir')
        else:
            self._logdir = '/var/log/entangle'

        all_servers = ['entangle.' + base for (base, ext) in
                       map(path.splitext, os.listdir(self._resdir))
                       if ext == '.res']
        self._servers = sorted(all_servers)

    def check(self):
        if not self._ok:
            self.log.error('%s or %s missing' % (CONFIG, INITSCR))
            return False
        return True

    def get_services(self):
        return self._servers

    def start_service(self, name):
        self._async_start(name, '%s start %s' % (INITSCR, name[9:]))

    def stop_service(self, name):
        self._async_stop(name, '%s stop %s' % (INITSCR, name[9:]))

    def restart_service(self, name):
        self._async_start(name, '%s restart %s' % (INITSCR, name[9:]))

    def service_status(self, name):
        # XXX check devices with Tango clients
        return self._async_status(name, '%s status %s' % (INITSCR, name[9:]))

    def service_logs(self, name):
        logname = path.join(self._logdir, name[9:], 'current')
        return extractLoglines(logname)

    def receive_config(self, name):
        cfgname = path.join(self._resdir, name[9:] + '.res')
        return [name[9:] + '.res', readFile(cfgname)]

    def send_config(self, name, data):
        cfgname = path.join(self._resdir, name[9:] + '.res')
        if len(data) != 2 or data[0] != name[9:] + '.res':
            raise RuntimeError('invalid request')
        writeFile(cfgname, data[1])
