# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-present by the authors, see LICENSE
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

      Must be ``"nicos"``.

   .. describe:: root

      The root of the NICOS installation, which should contain ``nicos.conf``.
      If not given, it is derived from the init script
      ``/etc/init.d/nicos-system``, which is normally a symbolic link to the
      file below the NICOS root.

   .. describe:: setup_path

      The setup path of the NICOS installation, if given, allows editing
      the setup files.

   .. describe:: permissions
                 pollinterval

      The :ref:`standard parameters <standard-params>` present for all jobs.

   No further configuration is necessary; the job will read the NICOS
   configuration file ``nicos.conf`` and derive parameters like available
   services and their logfiles from there.
"""

import os
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from marche.jobs import DEAD, NOT_AVAILABLE, RUNNING, SYSTEMD_STATE_MAP, WARNING, Fault
from marche.jobs.base import Job as BaseJob
from marche.utils import determine_init_system, extract_loglines, read_file, write_file


class NicosBaseJob(BaseJob):

    def configure(self, config):
        self._services = []
        self._proc = None
        self._logpath = None
        self._find_root(config)
        self._setup_path = config.get('setup_path', None)

    def _find_root(self, config):
        raise NotImplementedError

    def get_services(self):
        return self._services

    def service_output(self, _service, instance):
        return list(self._output.get(instance, []))

    def service_logs(self, _service, instance):
        if self._logpath is None:
            # extract nicos log directory from nicos.conf
            conffile = self._root / 'nicos.conf'
            if conffile.is_file():
                with conffile.open(mode='rb') as fp:
                    cfg = tomllib.load(fp)
                self._logpath = Path(cfg.get('nicos', {}).get('logging_path'))

            # fallback
            if not self._logpath:
                self._logpath = self._root / 'log'

        if not instance:
            result = {}
            for subdir in self._logpath.iterdir():
                logfile = subdir / 'current'
                if logfile.is_symlink():  # pragma: no cover
                    result.update(extract_loglines(logfile))
            return result
        return extract_loglines(self._logpath / instance / 'current')

    def receive_config(self, _service, instance):
        if instance not in ('', 'daemon'):
            return {}
        if self._setup_path is None:
            return {}
        setup_path = Path(self._setup_path)
        if not setup_path.is_dir():
            self.log.warning(f'setup path {setup_path} does not exist')
            return {}
        result = {}
        for candidate in setup_path.glob('*.py'):
            if candidate.is_file() and os.access(candidate, os.W_OK):
                result[candidate.name] = read_file(candidate)
        return result

    def send_config(self, _service, _instance, filename, contents):
        if self._setup_path is None:
            raise Fault('no setup path configured')
        setup_path = Path(self._setup_path)
        fullname = setup_path / filename
        if fullname.is_file():
            write_file(fullname, contents)
        else:
            raise Fault('unknown file')


class InitJob(NicosBaseJob):
    DEFAULT_INIT = '/etc/init.d/nicos-system'

    def _find_root(self, config):
        if 'root' in config:
            self._root = Path(config['root'])
            self._script = self._root / 'etc' / 'nicos-system'
        else:
            # determine the NICOS root from the init script, which is a symlink
            # to the init script in the NICOS root
            self._script = Path(self.DEFAULT_INIT).resolve()
            self._root = self._script.parents[1]

    def check(self):
        if not self._script.is_file():
            self.log.warning(f'{self._script} missing')
            return False
        return True

    def init(self):
        self._services = [('nicos', '')]
        lines = self._sync_call(f'{self._script} 2>&1').stdout
        prefix = 'Possible services are '
        if len(lines) >= 2 and lines[-1].startswith(prefix):
            self._services.extend(('nicos', entry.strip()) for entry in
                                  lines[-1][len(prefix):].split(','))
        BaseJob.init(self)

    def start_service(self, _service, instance):
        return self._async_start(instance, f'{self._script} start {instance}')

    def stop_service(self, _service, instance):
        return self._async_stop(instance, f'{self._script} stop {instance}')

    def restart_service(self, _service, instance):
        return self._async_start(instance, f'{self._script} restart {instance}')

    def service_status(self, _service, instance):
        async_st = self._async_status_only(instance)
        if async_st is not None:
            return async_st
        if not instance:
            output = self._sync_call(f'{self._script} status').stdout
            something_dead = something_running = False
            for line in output:
                if 'dead' in line:
                    something_dead = True
                if 'running' in line:
                    something_running = True
            if something_dead and something_running:
                return WARNING, 'only some services running'
            if something_running:
                return RUNNING, ''
            return DEAD, ''
        proc = self._sync_call(f'{self._script} status {instance}')
        if proc.retcode == 0:
            return RUNNING, ''
        if proc.retcode == -1:
            return NOT_AVAILABLE, ''
        return DEAD, ''

    def all_service_status(self):
        result = {}
        initstates = {}
        something_dead = something_running = False
        for line in self._sync_call(f'{self._script} status').stdout:
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
                result[service, instance] = async_st  # pragma: no cover
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
            self._root = Path(config['root'])
        else:
            # determine the NICOS root from the generator script, which is
            # referred to in the service file
            out = self._sync_call('systemctl show -p ExecStart --value '
                                  'nicos-late-generator 2>&1').stdout
            self._root = Path('/usr/local/nicos')
            if out and out[0].startswith('{'):
                for kv in out[0].split():
                    if kv.startswith('path='):
                        self._root = Path(kv[5:]).parents[1]

    def check(self):
        lines = self._sync_call('systemctl is-enabled nicos.target 2>&1').stdout
        if lines[0].strip() != 'enabled':
            self.log.warning('nicos.target not enabled or present')
            return False
        return True

    def init(self):
        # for now, just offer the basic service corresponding to nicos.target
        self._services = [('nicos', '')]
        BaseJob.init(self)

    def get_services(self):
        # repeatedly try to get the actual service list until the generator
        # has run through
        if len(self._services) > 1:
            return self._services

        # TODO: switch to `-o json` mode once we can depend on newer systemd
        lines = self._sync_call('systemctl list-units --all --no-legend '
                                '"nicos-*" 2>&1').stdout
        for line in lines:
            split = line.split()
            if len(split[0]) < 3:  # must be symbol showing unit status
                split = split[1:]
            if split[0].startswith('nicos-'):
                instance = split[0][6:-8]
                if instance != 'late-generator':
                    self._services.append(('nicos', instance))
        return self._services

    def start_service(self, _service, instance):
        if instance:
            self._async_start(instance, f'systemctl start nicos-{instance}')
        else:
            self._async_start(instance, 'systemctl start nicos.target')

    def stop_service(self, _service, instance):
        if instance:
            self._async_stop(instance, f'systemctl stop nicos-{instance}')
        else:
            self._async_stop(instance, 'systemctl stop nicos.target')

    def restart_service(self, _service, instance):
        if instance:
            self._async_start(instance, f'systemctl restart nicos-{instance}')
        else:
            self._async_start(instance, 'systemctl restart nicos.target')

    def service_status(self, service, instance):
        if not instance:
            async_st = self._async_status_only(instance)
            return async_st or self.all_service_status()[service, '']
        return self._async_status_systemd(instance, f'nicos-{instance}')

    def all_service_status(self):
        result = {}
        initstates = {}
        something_dead = something_running = False
        name = ''
        for line in self._sync_call('systemctl show -p Id -p SubState '
                                    '"nicos-*"').stdout:
            line = line.strip()
            if line.startswith('Id='):
                name = line[3:]
                continue
            if 'late-generator' in name:
                continue
            if line.startswith('SubState='):
                state = line[9:]
                stateconst = SYSTEMD_STATE_MAP.get(state, DEAD)
                if stateconst == DEAD:
                    something_dead = True
                elif stateconst == RUNNING:
                    something_running = True
                instance = name[6:-8]
                initstates[instance] = (stateconst,
                                        state if state != 'running' else '')
        for service, instance in self._services:
            async_st = self._async_status_only(instance)
            if async_st is not None:
                result[service, instance] = async_st  # pragma: no cover
            elif instance == '':
                if something_dead and something_running:
                    result[service, ''] = WARNING, 'only some services running'
                elif something_running:
                    result[service, ''] = RUNNING, ''
                else:
                    result[service, ''] = DEAD, ''
            else:
                result[service, instance] = initstates.get(instance,
                                                           (DEAD, ''))
        return result


def Job(*args, **kwargs):
    if determine_init_system() == 'systemd':
        job = SystemdJob(*args, **kwargs)
        if job.check():
            return job
        job.log.warning('using init.d job since systemd is not '
                        'properly set up for Nicos, fix your system')
    return InitJob(*args, **kwargs)
