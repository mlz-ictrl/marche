#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2022 by the authors, see LICENSE
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

   .. describe:: permissions
                 pollinterval

      The :ref:`standard parameters <standard-params>` present for all jobs.

   No further configuration is necessary; the job will read the Entangle
   configuration file ``/etc/entangle/entangle.conf`` and derive parameters
   like available servers and their logfiles from there.
"""

import os
import socket
import sys
from os import path

from six.moves import configparser

from marche.jobs import DEAD, RUNNING, Fault
from marche.jobs.base import Job as BaseJob
from marche.utils import determine_init_system, extract_loglines, read_file, \
    write_file


class EntangleBaseJob(BaseJob):
    CONFIG = '/etc/entangle/entangle.conf'
    CONTROL_TOOL = '/etc/init.d/entangle'

    START_CMD = '{control_tool} start {instance}'
    STOP_CMD = '{control_tool} stop {instance}'
    RESTART_CMD = '{control_tool} restart {instance}'
    STATUS_CMD = '{control_tool} status {instance}'

    def configure(self, config):
        self._config = config.get('configfile', self.CONFIG)
        self._control_tool = config.get('controltool', self.CONTROL_TOOL)
        if os.name == 'nt':
            self.log.info('Windows: prefix commands with Python executable')
            python = sys.executable + ' '
            self.START_CMD = python + self.START_CMD
            self.STOP_CMD = python + self.STOP_CMD
            self.RESTART_CMD = python + self.RESTART_CMD
            self.STATUS_CMD = python + self.STATUS_CMD

    def check(self):
        if not path.exists(self._config):
            self.log.warning('Configuration file %s missing' % self._config)
            return False
        if not path.exists(self._control_tool):
            self.log.warning('Control tool %s missing' % self._control_tool)
            return False
        return True

    def init(self):
        substitutions = {
            'hostname': socket.gethostname().split('.')[0]
        }

        cfg = configparser.SafeConfigParser(defaults=substitutions)
        cfg.read(self._config)

        if cfg.has_option('entangle', 'resdir'):
            self._resdir = cfg.get('entangle', 'resdir').strip('"\'')
            self._resdir = self._resdir.format(**substitutions)
        else:
            self._resdir = '/etc/entangle'  # pragma: no cover
        if cfg.has_option('entangle', 'logdir'):
            self._logdir = cfg.get('entangle', 'logdir').strip('"\'')
        else:
            self._logdir = '/var/log/entangle'  # pragma: no cover

        all_servers = [('entangle', base) for (base, ext) in
                       map(path.splitext, os.listdir(self._resdir))
                       if ext == '.res']
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
        return self._async_status(
            instance,
            self._format_cmd(self.STATUS_CMD, service, instance)
        ), ''

    def service_output(self, service, instance):
        return list(self._output.get(instance, []))

    def service_logs(self, service, instance):
        logname = path.join(self._logdir, instance, 'current')
        return extract_loglines(logname)

    def receive_config(self, service, instance):
        cfgname = path.join(self._resdir, instance + '.res')
        # don't send conffiles which we can't write
        if os.access(cfgname, os.W_OK):
            return {instance + '.res': read_file(cfgname)}
        return {}

    def send_config(self, service, instance, filename, contents):
        cfgname = path.join(self._resdir, instance + '.res')
        if filename != instance + '.res':
            raise Fault('invalid request')
        write_file(cfgname, contents)

    def _format_cmd(self, cmd, service, instance):
        return cmd.format(control_tool=self._control_tool, instance=instance)


class InitJob(EntangleBaseJob):
    def all_service_status(self):
        result = {}
        initstates = {}
        for line in self._sync_call('%s status' % self._control_tool).stdout:
            if ':' not in line:
                continue
            name, state = line.split(':', 1)
            initstates[name.strip()] = DEAD if 'dead' in state else RUNNING
        for service, instance in self._services:
            async_st = self._async_status_only(instance)
            if async_st is not None:
                result[service, instance] = async_st, ''  # pragma: no cover
            else:
                result[service, instance] = initstates.get(instance, DEAD), ''
        return result


class SystemdJob(EntangleBaseJob):
    CONTROL_TOOL = '/bin/systemctl'
    START_CMD = '{control_tool} start entangle@{instance}'
    STOP_CMD = '{control_tool} stop entangle@{instance}'
    RESTART_CMD = '{control_tool} restart entangle@{instance}'
    STATUS_CMD = '{control_tool} is-active entangle@{instance}'
    JOURNAL_TOOL = 'journalctl'

    def service_logs(self, service, instance):
        proc = self._sync_call('%s -n 500 -u entangle@%s' %
                               (self.JOURNAL_TOOL, instance))
        return {'journal': ''.join(proc.stdout)}


def Job(*args, **kwargs):
    if determine_init_system() == 'systemd':
        return SystemdJob(*args, **kwargs)
    return InitJob(*args, **kwargs)
