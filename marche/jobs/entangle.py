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
from os import path

from marche.six.moves import configparser

from marche.jobs import Fault, RUNNING, DEAD
from marche.jobs.base import Job as BaseJob
from marche.utils import extract_loglines, read_file, write_file


class Job(BaseJob):

    CONFIG = '/etc/entangle/entangle.conf'
    INITSCR = '/etc/init.d/entangle'

    def check(self):
        if not (path.exists(self.CONFIG) and path.exists(self.INITSCR)):
            self.log.warning('%s or %s missing' % (self.CONFIG, self.INITSCR))
            return False
        return True

    def init(self):
        cfg = configparser.RawConfigParser()
        cfg.read(self.CONFIG)

        if cfg.has_option('entangle', 'resdir'):
            self._resdir = cfg.get('entangle', 'resdir')
        else:
            self._resdir = '/etc/entangle'  # pragma: no cover
        if cfg.has_option('entangle', 'logdir'):
            self._logdir = cfg.get('entangle', 'logdir')
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
        self._async_start(instance, '%s start %s' % (self.INITSCR, instance))

    def stop_service(self, service, instance):
        self._async_stop(instance, '%s stop %s' % (self.INITSCR, instance))

    def restart_service(self, service, instance):
        self._async_start(instance, '%s restart %s' % (self.INITSCR, instance))

    def service_status(self, service, instance):
        # XXX check devices with Tango clients
        return self._async_status(instance, '%s status %s' %
                                  (self.INITSCR, instance)), ''

    def all_service_status(self):
        result = {}
        initstates = {}
        for line in self._sync_call('%s status' % self.INITSCR).stdout:
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

    def service_output(self, service, instance):
        return list(self._output.get(instance, []))

    def service_logs(self, service, instance):
        logname = path.join(self._logdir, instance, 'current')
        return extract_loglines(logname)

    def receive_config(self, service, instance):
        cfgname = path.join(self._resdir, instance + '.res')
        return {instance + '.res': read_file(cfgname)}

    def send_config(self, service, instance, filename, contents):
        cfgname = path.join(self._resdir, instance + '.res')
        if filename != instance + '.res':
            raise Fault('invalid request')
        write_file(cfgname, contents)
