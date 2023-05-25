# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2023 by the authors, see LICENSE
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

NICOS is controlled either by its init script on older systems, or by its
systemd services on newer ones.

``nicos.target`` must be enabled for the job to configure itself.

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

import configparser
import os
from os import path

import toml

from marche.jobs import DEAD, NOT_AVAILABLE, RUNNING, WARNING
from marche.jobs.base import Job as BaseJob
from marche.utils import determine_init_system, extract_loglines


class NicosBaseJob(BaseJob):

    def configure(self, config):
        self._services = []
        self._proc = None
        self._logpath = None
        self._find_root(config)

    def _find_root(self, config):
        raise NotImplementedError

    def get_services(self):
        return self._services

    def service_output(self, service, instance):
        return list(self._output.get(instance, []))

    def service_logs(self, service, instance):
        if self._logpath is None:
            # extract nicos log directory from nicos.conf
            conffile = path.join(self._root, 'nicos.conf')
            if path.isfile(conffile):
                try:
                    with open(conffile, encoding='utf-8') as fp:
                        cfg = toml.load(fp)
                    self._logpath = cfg.get('nicos', {}).get('logging_path')
                except toml.TomlDecodeError:
                    cfg = configparser.RawConfigParser()
                    cfg.read([conffile])
                    if cfg.has_option('nicos', 'logging_path'):
                        self._logpath = cfg.get('nicos', 'logging_path')

            # fallback
            if not self._logpath:
                self._logpath = path.join(self._root, 'log')

        if not instance:
            result = {}
            for subdir in os.listdir(self._logpath):
                logfile = path.join(self._logpath, subdir, 'current')
                if path.islink(logfile):
                    result.update(extract_loglines(logfile))  # pragma: no cover
            return result
        return extract_loglines(path.join(self._logpath, instance, 'current'))


class InitJob(NicosBaseJob):
    DEFAULT_INIT = '/etc/init.d/nicos-system'

    def _find_root(self, config):
        if 'root' in config:
            self._root = config['root']
            self._script = path.join(self._root, 'etc', 'nicos-system')
        else:
            # determine the NICOS root from the init script, which is a symlink
            # to the init script in the NICOS root
            real_init = path.realpath(self.DEFAULT_INIT)
            self._root = path.dirname(path.dirname(real_init))
            self._script = self.DEFAULT_INIT

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
            if proc.retcode == 0:
                return RUNNING, ''
            elif proc.retcode == -1:
                return NOT_AVAILABLE, ''
            return DEAD, ''

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


class SystemdJob(NicosBaseJob):
    def _find_root(self, config):
        if 'root' in config:
            self._root = config['root']
        else:
            # determine the NICOS root from the generator script, which is
            # referred to in the service file
            out = self._sync_call('systemctl show -p ExecStart --value '
                                  'nicos-late-generator 2>&1').stdout
            self._root = '/usr/local/nicos'
            if out and out[0].startswith('{'):
                for kv in out[0].split():
                    if kv.startswith('path='):
                        self._root = path.dirname(path.dirname(kv[5:]))

    def check(self):
        lines = self._sync_call('systemctl is-enabled nicos.target 2>&1').stdout
        if lines[0].strip() != 'enabled':
            self.log.warning('nicos.target not enabled or present')
            return False
        return True

    def init(self):
        self._services = [('nicos', '')]
        lines = self._sync_call('systemctl list-units --all --no-legend '
                                '"nicos-*" 2>&1').stdout
        for line in lines:
            split = line.split()
            if split[0].startswith('nicos-'):
                instance = split[0][6:-8]
                if instance != 'late-generator':
                    self._services.append(('nicos', instance))
        BaseJob.init(self)

    def start_service(self, service, instance):
        if instance:
            self._async_start(instance, 'systemctl start nicos-%s' % instance)
        else:
            self._async_start(instance, 'systemctl start nicos.target')

    def stop_service(self, service, instance):
        if instance:
            self._async_stop(instance, 'systemctl stop nicos-%s' % instance)
        else:
            self._async_stop(instance, 'systemctl stop nicos.target')

    def restart_service(self, service, instance):
        if instance:
            self._async_start(instance, 'systemctl restart nicos-%s' % instance)
        else:
            self._async_start(instance, 'systemctl restart nicos.target')

    def service_status(self, service, instance):
        async_st = self._async_status_only(instance)
        if async_st is not None:
            return async_st, ''
        if not instance:
            lines = self._sync_call('systemctl list-units --all --no-legend '
                                    '"nicos-*" 2>&1').stdout
            something_dead = something_running = False
            for line in lines:
                if 'late-generator' in line:
                    continue
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
            proc = self._sync_call('systemctl is-active "nicos-%s" 2>&1' % instance)
            if proc.retcode == 0:
                return RUNNING, ''
            return DEAD, ''

    def all_service_status(self):
        result = {}
        initstates = {}
        something_dead = something_running = False
        for line in self._sync_call('systemctl list-units --all --no-legend '
                                    '"nicos-*" 2>&1').stdout:
            if 'late-generator' in line:
                continue
            if 'dead' in line:
                something_dead = True
            if 'running' in line:
                something_running = True
            name, state = line.split(None, 1)
            instance = name[6:-8]
            initstates[instance] = DEAD if 'dead' in state else RUNNING
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


def Job(*args, **kwargs):
    if determine_init_system() == 'systemd':
        job = SystemdJob(*args, **kwargs)
        if job.check():
            return job
        job.log.warning('using init.d job since systemd is not '
                        'properly set up for Nicos, fix your system')
    return InitJob(*args, **kwargs)
