#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2018 by the authors, see LICENSE
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

""".. index:: nicos; job

NICOS job
=========

This is a job for controlling all NICOS_ services configured on the host.

.. _NICOS: http://nicos-controls.org/

This job has the following configuration parameters:

.. describe:: [job.xxx]

   .. describe:: type

      Must be ``nicos``.

   .. describe:: root

      The root of the NICOS installation, which should contain ``nicos.conf``.
      If not given, it is derived from the init script
      ``/etc/init.d/nicos-system``, which is normally a symbolic link to the
      file below the NICOS root.

   .. describe:: permissions
                 pollinterval

      The :ref:`standard parameters <standard-params>` present for all jobs.

   No further configuration is necessary; the job will read the NICOS
   configuration file ``nicos.conf`` and derive parameters like available
   services and their logfiles from there.
"""

import os
from os import path

from marche.six.moves import configparser

from marche.jobs import DEAD, RUNNING, WARNING
from marche.jobs.base import Job as BaseJob
from marche.utils import extract_loglines


class Job(BaseJob):

    DEFAULT_INIT = '/etc/init.d/nicos-system'

    def configure(self, config):
        self._services = []
        self._proc = None
        if 'root' in config:
            self._root = config['root']
            self._script = path.join(self._root, 'etc', 'nicos-system')
        else:
            # determine the NICOS root from the init script, which is a symlink
            # to the init script in the NICOS root
            real_init = path.realpath(self.DEFAULT_INIT)
            self._root = path.dirname(path.dirname(real_init))
            self._script = self.DEFAULT_INIT
        self._logpath = None

    def check(self):
        if not path.exists(self._script):
            self.log.warning('%s missing' % self._script)
            return False
        return True

    def init(self):
        self._services = [('nicos', '')]
        lines = self._sync_call('%s 2>&1' % self._script).stdout
        prefix = 'Possible services are '
        if len(lines) >= 2 and lines[-1].startswith(prefix):
            self._services.extend(('nicos', entry.strip()) for entry in
                                  lines[-1][len(prefix):].split(','))
        BaseJob.init(self)

    def get_services(self):
        return self._services

    def start_service(self, service, instance):
        return self._async_start(instance, self._script + ' start %s' % instance)

    def stop_service(self, service, instance):
        return self._async_stop(instance, self._script + ' stop %s' % instance)

    def restart_service(self, service, instance):
        return self._async_start(instance, self._script + ' restart %s' % instance)

    def service_status(self, service, instance):
        async_st = self._async_status_only(instance)
        if async_st is not None:
            return async_st, ''
        if not instance:
            output = self._sync_call('%s status' % self._script).stdout
            something_dead = something_running = False
            for line in output:
                if 'dead' in line:
                    something_dead = True
                if 'running' in line:
                    something_running = True
            if something_dead and something_running:
                return WARNING, 'only some services running'
            elif something_running:
                return RUNNING, ''
            return DEAD, ''
        else:
            proc = self._sync_call(self._script + ' status %s' % instance)
            return RUNNING if proc.retcode == 0 else DEAD, ''

    def all_service_status(self):
        result = {}
        initstates = {}
        something_dead = something_running = False
        for line in self._sync_call('%s status' % self._script).stdout:
            if ':' not in line:
                continue
            if 'dead' in line:
                something_dead = True
            if 'running' in line:
                something_running = True
            name, state = line.split(':', 1)
            initstates[name.strip()] = DEAD if 'dead' in state else RUNNING
        for service, instance in self._services:
            async_st = self._async_status_only(instance)
            if async_st is not None:
                result[service, instance] = async_st, ''  # pragma: no cover
            elif instance == '':
                if something_dead and something_running:
                    result[service, ''] = WARNING, 'only some services running'
                elif something_running:
                    result[service, ''] = RUNNING, ''
                else:
                    result[service, ''] = DEAD, ''
            else:
                result[service, instance] = initstates.get(instance, DEAD), ''
        return result

    def service_output(self, service, instance):
        return list(self._output.get(instance, []))

    def service_logs(self, service, instance):
        if self._logpath is None:
            # extract nicos log directory
            cfg = configparser.RawConfigParser()
            cfg.read([path.join(self._root, 'nicos.conf')])
            if cfg.has_option('nicos', 'logging_path'):  # pragma: no cover
                self._logpath = cfg.get('nicos', 'logging_path')
            else:
                self._logpath = path.join(self._root, 'log')
        if not instance:
            result = {}
            for subdir in os.listdir(self._logpath):
                logfile = path.join(self._logpath, subdir, 'current')
                if path.islink(logfile):
                    result.update(extract_loglines(logfile))  # pragma: no cover
            return result
        return extract_loglines(path.join(self._logpath, instance, 'current'))
