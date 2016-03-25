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

   No further configuration is necessary; the job will read the TACO
   database and derive parameters like available servers from there.
"""

import os
from os import path

from marche.six import iteritems

from marche.utils import extractLoglines
from marche.jobs.base import Job as BaseJob


class Job(BaseJob):

    def __init__(self, name, config, log):
        BaseJob.__init__(self, name, config, log)
        self._initscripts = {}
        self._depends = set()

    def check(self):
        if any(fn.startswith('taco-server-')
               for fn in os.listdir('/etc/init.d')):
            return True
        self.log.warning('no TACO server init scripts found')
        return False

    def get_services(self):
        servers = set()
        # get all servers for which we have an init script
        for fn in os.listdir('/etc/init.d'):
            if fn.startswith('taco-server-'):
                name = 'taco.' + fn[len('taco-server-'):]
                servers.add(name[5:])
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
            for instance in instances:
                servicename = 'taco-%s.%s' % (server, instance)
                services.append(servicename)
                self._initscripts[servicename] = '/etc/init.d/taco-server-%s' % server
        return services

    def start_service(self, name):
        initscript = self._initscripts[name]
        self._async_start(name, initscript + ' start ' + name.split('.')[1])

    def stop_service(self, name):
        initscript = self._initscripts[name]
        self._async_stop(name, initscript + ' stop ' + name.split('.')[1])

    def restart_service(self, name):
        initscript = self._initscripts[name]
        self._async_start(name, initscript + ' restart ' + name.split('.')[1])

    def service_status(self, name):
        initscript = self._initscripts[name]
        command = initscript + ' status ' + name.split('.')[1]
        return self._async_status(name, command)

    def service_logs(self, name):
        if not path.isdir('/var/log/taco'):
            return []
        srvname, instance = name.split('.', 1)
        srvname = srvname[5:]  # strip "taco-"
        candidates = os.listdir('/var/log/taco')
        output = []
        for filename in candidates:
            # check for srvname_instance
            if filename.lower() == ('%s_%s.log' % (srvname, instance)).lower():
                output.extend(extractLoglines(path.join('/var/log/taco', filename)))
            # check for srvname only
            if filename.lower() == ('%s.log' % srvname).lower():
                output.extend(extractLoglines(path.join('/var/log/taco', filename)))
        return output

    # -- internal APIs --

    def _read_devices(self, restrict_servers):
        p = self._sync_call('. /etc/tacoenv.sh; db_devicelist').stdout
        servers = {}
        alldevices = set()
        dev2server = {}
        curserver = None
        curinstance = None
        for line in p:
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
            p = self._sync_call('. /etc/tacoenv.sh; db_devres %s' % dev).stdout
            for line in p:
                if ':' not in line.strip():
                    continue
                key, value = line.strip().split(':', 1)
                value = value.strip()
                kdev, _kres = key.rsplit('/', 1)
                assert kdev == dev
                if value in alldevices:
                    depends.add(dev2server[value])
        return depends
