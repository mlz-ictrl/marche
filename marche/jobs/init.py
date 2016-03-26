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

""".. index:: init; job

.. _init-job:

Init script job
===============

This is a job for controlling services started by an init script.

This is a very simple job, because it defers most of its action to the existing
init script for a service, found in ``/etc/init.d``.

Features not provided by the init script are the retrieval of logfiles, and the
possibility to retrieve and transfer back configuration files.

This job has the following configuration parameters:

.. describe:: [job.xxx]

   .. describe:: type

      Must be ``init``.

   .. describe:: script

      The name of the init script (as a file in ``/etc/init.d``).  If not
      given, it is the same as the name of the job.

   .. describe:: logfiles

      Comma-separated paths of logfiles to read and show to the client when
      requested.  If not given, no logs are transferred.

   .. describe:: configfile

      The full path of the config file to transfer to the client and write back
      when updates are received.  If not given, no config is transferred.

A typical section looks like this::

    [job.dhcpd]
    type = init
    logfile = /var/log/dhcpd.log
    configfile = /etc/dhcp/dhcpd.conf
"""

from os import path

from marche.utils import extractLoglines, readFile, writeFile
from marche.jobs.base import Job as BaseJob


class Job(BaseJob):

    def __init__(self, name, config, log):
        BaseJob.__init__(self, name, config, log)
        self.init_name = config.get('script', name)
        self.log_files = []
        singlelog = config.get('logfile', '')
        if singlelog:
            self.log_files.append(singlelog)
        multilog = config.get('logfiles', '').split(',')
        for log in multilog:
            if log.strip():
                self.log_files.append(log.strip())
        self.config_file = config.get('configfile', '')

    def check(self):
        script = '/etc/init.d/%s' % self.init_name
        if not path.exists(script):
            self.log.warning('%s missing' % script)
            return False
        return True

    def get_services(self):
        return [(self.init_name, '')]

    def start_service(self, service, instance):
        self._async_start(service, '/etc/init.d/%s start' % self.init_name)

    def stop_service(self, service, instance):
        self._async_stop(service, '/etc/init.d/%s stop' % self.init_name)

    def restart_service(self, service, instance):
        self._async_start(service, '/etc/init.d/%s restart' % self.init_name)

    def service_status(self, service, instance):
        return self._async_status(service, '/etc/init.d/%s status' %
                                  self.init_name)

    def service_logs(self, service, instance):
        ret = []
        for log_file in self.log_files:
            ret.extend(extractLoglines(log_file))
        return ret

    def receive_config(self, service, instance):
        if not self.config_file:
            return []
        return [path.basename(self.config_file), readFile(self.config_file)]

    def send_config(self, service, instance, filename, contents):
        if filename != path.basename(self.config_file):
            raise RuntimeError('invalid request')
        writeFile(self.config_file, contents)
