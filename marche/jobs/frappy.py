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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************

""".. index:: frappy; job

Frappy (SECoP) Nodes job
========================

This is a job for controlling all Frappy SECoP nodes configured on the host
via systemd.

This job has the following configuration parameters:

.. describe:: [job.xxx]

   .. describe:: type

      Must be ``frappy``.

   .. describe:: configdir

      Directory where the Frappy configuration files are located.  Default is
      ``/etc/frappy``.

   .. describe:: permissions
                 pollinterval

      The :ref:`standard parameters <standard-params>` present for all jobs.

   No further configuration is necessary; the job will read the Frappy
   configuration from ``/etc/frappy`` and derive parameters
   like available servers and their logfiles from there.
"""

import os
from os import path

from marche.jobs import Fault
from marche.jobs.base import Job as BaseJob
from marche.utils import read_file, write_file


class Job(BaseJob):
    default_config = '/etc/frappy'
    default_control_tool = '/bin/systemctl'
    _start_cmd = '{control_tool} start frappy@{instance}'
    _stop_cmd = '{control_tool} stop frappy@{instance}'
    _restart_cmd = '{control_tool} restart frappy@{instance}'
    _status_cmd = '{control_tool} is-active frappy@{instance}'
    _journal_tool = 'journalctl'

    def configure(self, config):
        self._config = config.get('configdir', self.default_config)
        self._control_tool = config.get('controltool',
                                        self.default_control_tool)

    def check(self):
        if not path.isdir(self._config):
            self.log.warning('Configuration dir %s missing' % self._config)
            return False
        if not path.exists(self._control_tool):
            self.log.warning('Control tool %s missing' % self._control_tool)
            return False
        return True

    def init(self):
        try:
            nodes = [('frappy', fn[:-7]) for fn in os.listdir(self._config)
                     if fn.endswith('_cfg.py')]
        except IOError:
            nodes = []
        self._services = sorted(nodes)
        BaseJob.init(self)

    def get_services(self):
        return self._services

    def start_service(self, service, instance):
        self._async_start(instance, self._format_cmd(self._start_cmd, service,
                                                     instance))

    def stop_service(self, service, instance):
        self._async_stop(instance, self._format_cmd(self._stop_cmd, service,
                                                    instance))

    def restart_service(self, service, instance):
        self._async_start(instance, self._format_cmd(self._restart_cmd, service,
                                                     instance))

    def service_status(self, service, instance):
        return self._async_status(
            instance,
            self._format_cmd(self._status_cmd, service, instance)
        ), ''

    def service_output(self, service, instance):
        return list(self._output.get(instance, []))

    def service_logs(self, service, instance):
        proc = self._sync_call('%s -n 500 -u frappy@%s' %
                               (self._journal_tool, instance))
        return {'journal': ''.join(proc.stdout)}

    def receive_config(self, service, instance):
        cfgname = path.join(self._config, instance + '_cfg.py')
        # don't send conffiles which we can't write
        if os.access(cfgname, os.W_OK):
            return {instance + '_cfg.py': read_file(cfgname)}
        return {}

    def send_config(self, service, instance, filename, contents):
        cfgname = path.join(self._config, instance + '_cfg.py')
        if filename != instance + '_cfg.py':
            raise Fault('invalid request')
        write_file(cfgname, contents)

    def _format_cmd(self, cmd, service, instance):
        return cmd.format(control_tool=self._control_tool, instance=instance)
