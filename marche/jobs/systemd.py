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
#
# *****************************************************************************

""".. index:: systemd; job

Systemd service job
===================

This is a job for controlling services using systemd_.

.. _systemd: https://www.freedesktop.org/wiki/Software/systemd/

This is a simple job, because it defers most of its action to systemd.

This job has the following configuration parameters:

.. describe:: [job.xxx]

   .. describe:: type

      Must be ``systemd``.

   .. describe:: unit

      The name of the systemd unit.  It can be given in full, i.e.
      ``foo.service`` or ``foo.slice``, or just ``foo``.

      If not given, this defaults to the job name.

   .. describe:: logfiles

      Comma-separated paths of logfiles to read and show to the client when
      requested.  If not given, the systemd journal is queried for log lines.

   .. describe:: configfile

      The full path of the config file to transfer to the client and write back
      when updates are received.  If not given, no config is transferred.

A typical section looks like this::

    [job.dhcpd]
    type = systemd
    configfile = /etc/dhcp/dhcpd.conf
"""

from os import path

from marche.utils import extractLoglines, readFile, writeFile
from marche.jobs.base import Job as BaseJob


class Job(BaseJob):

    def __init__(self, name, config, log, event_callback):
        BaseJob.__init__(self, name, config, log, event_callback)
        self.unit = config.get('unit', name)
        self.log_files = []
        multilog = config.get('logfiles', '').split(',')
        for log in multilog:
            if log.strip():
                self.log_files.append(log.strip())
        self.config_file = config.get('configfile', '')

    def check(self):
        proc = self._sync_call('systemctl is-enabled %s' % self.unit)
        if not proc.stdout and proc.stderr:
            self.log.warning('unit file for %s does not exist' % self.unit)
            return False
        return True

    def get_services(self):
        return [(self.unit, '')]

    def start_service(self, service, instance):
        self._async_start(service, 'systemctl start %s' % self.unit)

    def stop_service(self, service, instance):
        self._async_stop(service, 'systemctl stop %s' % self.unit)

    def restart_service(self, service, instance):
        self._async_start(service, 'systemctl restart %s' % self.unit)

    def service_status(self, service, instance):
        return self._async_status(service,
                                  'systemctl is-active %s' % self.unit), ''

    def service_output(self, service, instance):
        return list(self._output.get(service, []))

    def service_logs(self, service, instance):
        ret = {}
        if self.log_files:
            for log_file in self.log_files:
                ret.update(extractLoglines(log_file))
        else:
            ret['journal'] = self._sync_call('journalctl -n 500 -u %s').stdout
        return ret

    def receive_config(self, service, instance):
        if not self.config_file:
            return {}
        return {path.basename(self.config_file): readFile(self.config_file)}

    def send_config(self, service, instance, filename, contents):
        if filename != path.basename(self.config_file):
            raise RuntimeError('invalid request')
        writeFile(self.config_file, contents)
