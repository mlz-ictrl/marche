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

""".. index:: entangle; job

Entangle Servers job
====================

This is a job for controlling all Entangle_ servers configured on the host.

.. _Entangle: https://forge.frm2.tum.de/entangle/doc/entangle-master/

This job has the following configuration parameters:

.. describe:: [job.xxx]

   .. describe:: type

      Must be ``"entangle"``.

   .. describe:: configfile

      The path to the Entangle configuration file.  Default is
      ``"/etc/entangle/entangle.conf"``.

   .. describe:: permissions
                 pollinterval

      The :ref:`standard parameters <standard-params>` present for all jobs.

   No further configuration is necessary; the job will read the Entangle
   configuration file ``/etc/entangle/entangle.conf`` and derive parameters
   like available servers and their logfiles from there.
"""

import os
import re
import socket
import sys
import uuid
from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib

from marche.jobs import DEAD, RUNNING, Fault
from marche.jobs.base import Job as BaseJob
from marche.utils import determine_init_system, extract_loglines, read_file, write_file


class EntangleBaseJob(BaseJob):
    CONFIG = '/etc/entangle/entangle.conf'
    CONTROL_TOOL = '/etc/init.d/entangle'

    START_CMD = '{control_tool} start {instance}'
    STOP_CMD = '{control_tool} stop {instance}'
    RESTART_CMD = '{control_tool} restart {instance}'
    STATUS_CMD = '{control_tool} status {instance}'

    def configure(self, config):
        self._config = Path(config.get('configfile', self.CONFIG))
        self._control_tool = Path(config.get('controltool', self.CONTROL_TOOL))
        if os.name == 'nt':
            self.log.info('Windows: prefix commands with Python executable')
            python = sys.executable + ' '
            self.START_CMD = python + self.START_CMD
            self.STOP_CMD = python + self.STOP_CMD
            self.RESTART_CMD = python + self.RESTART_CMD
            self.STATUS_CMD = python + self.STATUS_CMD

    def check(self):
        if not self._config.is_file():
            self.log.warning('Configuration file %s missing', self._config)
            return False
        if not self._control_tool.is_file():
            self.log.warning('Control tool %s missing', self._control_tool)
            return False
        return True

    def init(self):
        substitutions = {
            'hostname': socket.gethostname().split('.')[0],
            'macaddress': ':'.join(re.findall('..', f'{uuid.getnode():012x}')),
        }

        try:
            with self._config.open(mode='rb') as fp:
                cfg = tomllib.load(fp)
        except OSError:  # let TOML errors pass through
            cfg = {}

        section = cfg.get('entangle', {})
        if 'resdir' in section:
            self._resdir = Path(section['resdir'].format(**substitutions))
        else:
            self._resdir = Path('/etc/entangle')  # pragma: no cover
        self._logdir = Path(section.get('logdir', '/var/log/entangle'))

        all_servers = [('entangle', entry.stem) for entry in
                       self._resdir.glob('*.res')]
        self._services = sorted(all_servers)
        BaseJob.init(self)

    def get_services(self):
        return self._services

    def start_service(self, service, instance):
        self._async_start(instance, self._format_cmd(self.START_CMD, service,
                                                     instance))

    def stop_service(self, service, instance):
        self._async_stop(instance, self._format_cmd(self.STOP_CMD, service,
                                                    instance))

    def restart_service(self, service, instance):
        self._async_start(instance, self._format_cmd(self.RESTART_CMD, service,
                                                     instance))

    def service_status(self, service, instance):
        return self._async_status_exitcode(
            instance,
            self._format_cmd(self.STATUS_CMD, service, instance),
        )

    def service_output(self, _service, instance):
        return list(self._output.get(instance, []))

    def service_logs(self, _service, instance):
        logname = self._logdir / instance / 'current'
        return extract_loglines(logname)

    def receive_config(self, _service, instance):
        cfgname = self._resdir / f'{instance}.res'
        # don't send conffiles which we can't write
        if os.access(cfgname, os.W_OK):
            return {instance + '.res': read_file(cfgname)}
        return {}

    def send_config(self, _service, instance, filename, contents):
        cfgname = self._resdir / f'{instance}.res'
        if filename != instance + '.res':
            raise Fault('invalid request')
        write_file(cfgname, contents)

    def _format_cmd(self, cmd, _service, instance):
        return cmd.format(control_tool=self._control_tool, instance=instance)


class InitJob(EntangleBaseJob):
    def all_service_status(self):
        result = {}
        initstates = {}
        for line in self._sync_call(f'{self._control_tool} status').stdout:
            if ':' not in line:
                continue
            name, state = line.split(':', 1)
            initstates[name.strip()] = DEAD if 'dead' in state else RUNNING
        for service, instance in self._services:
            async_st = self._async_status_only(instance)
            result[service, instance] = \
                async_st or (initstates.get(instance, DEAD), '')
        return result


class SystemdJob(EntangleBaseJob):
    CONTROL_TOOL = '/bin/systemctl'
    START_CMD = '{control_tool} start entangle@{instance}'
    STOP_CMD = '{control_tool} stop entangle@{instance}'
    RESTART_CMD = '{control_tool} restart entangle@{instance}'

    def service_logs(self, _service, instance):
        return self._journalctl_logs(f'entangle@{instance}')

    def service_status(self, _service, instance):
        return self._async_status_systemd(instance, f'entangle@{instance}',
                                          self._control_tool)


def Job(*args, **kwargs):
    if determine_init_system() == 'systemd':
        return SystemdJob(*args, **kwargs)
    return InitJob(*args, **kwargs)
