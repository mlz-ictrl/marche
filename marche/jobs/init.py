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

      Comma-separated full paths of logfiles to read and show to the client
      when requested.  If not given, no logs are transferred.

   .. describe:: configfiles

      Comma-separated full paths of config files to transfer to the client and
      write back when updates are received.  If not given, no configs are
      transferred.

   .. describe:: description

      A nicer description for the job, to be displayed in the GUI.  Default is
      no description, and the job name will be displayed.

   .. describe:: permissions
                 pollinterval

      The :ref:`standard parameters <standard-params>` present for all jobs.

A typical section looks like this::

    [job.dhcpd]
    type = init
    logfiles = /var/log/dhcpd.log
    configfiles = /etc/dhcp/dhcpd.conf
"""

from os import path

from marche.jobs.base import ConfigMixin, Job as BaseJob, LogfileMixin


class Job(LogfileMixin, ConfigMixin, BaseJob):

    INIT_BASE = '/etc/init.d/'

    def configure(self, config):
        self.init_name = config.get('script', self.name)
        self.description = config.get('description', self.name)
        self.script = self.INIT_BASE + self.init_name
        self.configure_logfile_mixin(config)
        self.configure_config_mixin(config)

    def check(self):
        if not path.exists(self.script):
            self.log.warning('%s missing' % self.script)
            return False
        return True

    def get_services(self):
        return [(self.init_name, '')]

    def service_description(self, service, instance):
        return self.description

    def start_service(self, service, instance):
        self._async_start(service, self.script + ' start')

    def stop_service(self, service, instance):
        self._async_stop(service, self.script + ' stop')

    def restart_service(self, service, instance):
        self._async_start(service, self.script + ' restart')

    def service_status(self, service, instance):
        return self._async_status(service, self.script + ' status'), ''

    def service_output(self, service, instance):
        return list(self._output.get(service, []))
