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

""".. index:: taco; job

Taco Servers job
=================

This is a job for controlling all TACO_ servers (following the FRM-II standard)
configured on the host.

.. _TACO: https://forge.frm2.tum.de/wiki/projects:taco:index

This job has the following configuration parameters:

.. describe:: [job.xxx]

   .. describe:: type

      Must be ``taco``.

   .. describe:: permissions
                 pollinterval

      The :ref:`standard parameters <standard-params>` present for all jobs.

   No further configuration is necessary; the job will read the TACO
   database and derive parameters like available servers from there.
"""

import os
from os import path

from marche.six import iteritems

from marche.jobs.base import Job as BaseJob
from marche.utils import extract_loglines


class Job(BaseJob):

    INIT_DIR = '/etc/init.d'
    LOG_DIR = '/var/log/taco'
    DB_DEVLIST = '. /etc/tacoenv.sh; db_devicelist'
    DB_DEVRES = '. /etc/tacoenv.sh; db_devres'

    def configure(self, config):
        self._initscripts = {}
        self._depends = set()
        self._services = []

    def check(self):
        if path.isdir(self.INIT_DIR):
            if any(fn.startswith('taco-server-')
                   for fn in os.listdir(self.INIT_DIR)):
                return True
        self.log.warning('no TACO server init scripts found')
        return False

    def init(self):
        servers = set()
        # get all servers for which we have an init script
        for fn in os.listdir(self.INIT_DIR):
            if fn.startswith('taco-server-'):
                servers.add(fn[len('taco-server-'):])
        # read device info for servers
        serverinfo, alldevs, dev2server = self._read_devices(servers)
        # collect device dependency info for servers
        all_depends = {}
        direct_deps = {}
        for server, instances in iteritems(serverinfo):
            for instance, devs in iteritems(instances):
                direct_deps[server, instance] = \
                    self._get_dependencies(devs, alldevs, dev2server)
                all_depends[server, instance] = set()
        for key, depends in iteritems(direct_deps):
            all_depends[key].update(depends)
            for revkey in depends:
                all_depends[revkey].add(key)
        self._depends = all_depends
        # construct services
        services = []
        for server, instances in iteritems(serverinfo):
            self._initscripts['taco-' + server] = \
                path.join(self.INIT_DIR, 'taco-server-%s' % server)
            for instance in instances:
                services.append(('taco-' + server, instance))
        self._services = services
        BaseJob.init(self)

    def get_services(self):
        return self._services

    def start_service(self, service, instance):
        key = service, instance
        initscript = self._initscripts[service]
        self._async_start(key, initscript + ' start ' + instance)

    def stop_service(self, service, instance):
        key = service, instance
        initscript = self._initscripts[service]
        self._async_stop(key, initscript + ' stop ' + instance)

    def restart_service(self, service, instance):
        key = service, instance
        initscript = self._initscripts[service]
        self._async_start(key, initscript + ' restart ' + instance)

    def service_status(self, service, instance):
        key = service, instance
        initscript = self._initscripts[service]
        command = initscript + ' status ' + instance
        return self._async_status(key, command), ''

    def service_output(self, service, instance):
        key = service, instance
        return list(self._output.get(key, []))

    def service_logs(self, service, instance):
        if not path.isdir(self.LOG_DIR):
            return {}
        srvname = service[5:]  # strip "taco-"
        candidates = os.listdir(self.LOG_DIR)
        output = {}
        for filename in candidates:
            fullname = path.join(self.LOG_DIR, filename)
            # check for srvname_instance
            if filename.lower() == ('%s_%s.log' % (srvname, instance)).lower():
                output.update(extract_loglines(fullname))
            # check for srvname only
            if filename.lower() == ('%s.log' % srvname).lower():
                output.update(extract_loglines(fullname))
        return output

    # -- internal APIs --

    def _read_devices(self, restrict_servers):
        servers = {}
        alldevices = set()
        dev2server = {}
        curserver = None
        curinstance = None
        proc = self._sync_call(self.DB_DEVLIST)
        for line in proc.stdout:
            if not line.strip():
                continue
            if line.startswith('\t'):
                if curserver is None:
                    continue
                dev = line.strip()
                servers[curserver][curinstance].append(dev)
                alldevices.add(dev)
                dev2server[dev] = (curserver, curinstance)
            else:
                srv, inst = line.split()[0].split('/')
                curserver = srv[:-6]  # remove "server"
                if curserver not in restrict_servers:
                    curserver = curinstance = None
                    continue
                curinstance = inst
                servers.setdefault(curserver, {}).setdefault(curinstance, [])
        return servers, alldevices, dev2server

    def _get_dependencies(self, devs, alldevices, dev2server):
        depends = set()
        for dev in devs:
            proc = self._sync_call(self.DB_DEVRES + ' ' + dev)
            for line in proc.stdout:
                if ':' not in line.strip():
                    continue
                key, value = line.strip().split(':', 1)
                value = value.strip()
                kdev, _kres = key.rsplit('/', 1)
                assert kdev == dev
                if value in alldevices:
                    depends.add(dev2server[value])
        return depends
