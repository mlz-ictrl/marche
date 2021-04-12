#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2019 by the authors, see LICENSE
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

""".. index:: process; job

Simple Process job
==================

This is a job for directly controlling processes without an init script.

This is useful when the service has no init script, or the system has no
concept of init scripts (e.g. Windows).

This job has the following configuration parameters:

.. describe:: [job.xxx]

   .. describe:: type

      Must be ``process``.

   .. describe:: binary

      The full path of the binary to start.  If not given, defaults to the job
      name.

   .. describe:: args

      Additional arguments to pass to the binary.  They will be split in a
      shell-like fashion, i.e., you can use quotes to include spaces in one
      argument.  If not given, no arguments are passed.

   .. describe:: oneshot

      If ``yes``, treat this process as a "one-shot" process, which is supposed
      to be started and then stop after doing it job.  The only effects of this
      flag are that the service returns "NOT RUNNING" (instead of "DEAD") when
      not running, and that the output is caught by Marche if ``outputfile`` is
      not set.  It can be retrieved by the "get output" command.

      The default is "no".

   .. describe:: workingdir

      The initial working directory for the process.  If not given, Marche's
      working directory is used, which depends on how the daemon was started.

   .. describe:: outputfile

      If given, the full path to a file where stdout and stderr from the
      process will be written to.  If not given, Marche's stdout is used.

   .. describe:: autostart

      If ``yes``, the process will be started when the Marche daemon is
      started.  The default is not to start the process automatically.

   .. describe:: logfiles

      Comma-separated full paths of logfiles to read and show to the client
      when requested.  If not given, the ``outputfile`` is the default.

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

    [job.myprocess]
    type = process
    binary = MyProcess
    workingdir = /tmp
    outputfile = /var/log/myprocess.log
"""

import shlex
import sys
from os import path
from subprocess import PIPE, STDOUT, Popen
from threading import Thread
from time import sleep

from marche.jobs import DEAD, NOT_RUNNING, RUNNING
from marche.jobs.base import ConfigMixin, Job as BaseJob, LogfileMixin


class ProcessMonitor(Thread):
    DELAY = 0.1

    def __init__(self, cmd, wd, outfile, oneshot, output, log):
        Thread.__init__(self)
        self.returncode = None
        self.stopflag = False
        self.log = log
        self.oneshot = oneshot
        self.output = output
        self._wd = wd
        self._cmd = cmd
        self._outfile = outfile

    def run(self):
        self.log.info('worker %s: started' % self._cmd)
        if self._outfile is not None:
            outfile = open(self._outfile, 'wb')
        elif self.oneshot:
            outfile = PIPE
        else:  # pragma: no cover
            outfile = sys.stdout
            if hasattr(outfile, 'buffer'):
                outfile = outfile.buffer  # pylint: disable=no-member
        process = Popen(self._cmd, stdout=outfile, stderr=STDOUT, cwd=self._wd)
        while process.poll() is None:
            sleep(self.DELAY)
            if self.stopflag:
                process.kill()
                if outfile != PIPE:
                    outfile.flush()
        if self._outfile is None and self.oneshot:
            for line in iter(process.stdout.readline, b''):
                line = line.translate(None, b'\r').decode('utf-8', 'replace')
                self.output.append(line)
        self.returncode = process.returncode
        self.log.info('worker %s: return %d' % (self._cmd, self.returncode))


class Job(LogfileMixin, ConfigMixin, BaseJob):

    def configure(self, config):
        self.binary = config.get('binary', self.name)
        self.args = shlex.split(config.get('args', ''))
        self.working_dir = config.get('workingdir', None)
        self.output_file = config.get('outputfile', None)
        self.one_shot = config.get('oneshot', '').lower() in ('yes', 'true')
        if self.working_dir is None:
            self.working_dir = path.dirname(self.binary)
        self.autostart = config.get('autostart', '').lower() in ('yes', 'true')
        self.description = config.get('description', self.name)
        self.configure_logfile_mixin(config)
        if not self.log_files and self.output_file:
            self.log_files.append(self.output_file)
        self.configure_config_mixin(config)
        self._thread = None

    def check(self):
        if not path.exists(self.binary):
            self.log.warning('%s missing' % self.binary)
            return False
        return True

    def init(self):
        if self.autostart:
            self.start_service(self.name, '')
        BaseJob.init(self)

    def shutdown(self):
        self.stop_service(self.name, '')
        BaseJob.shutdown(self)

    def get_services(self):
        return [(self.name, '')]

    def service_description(self, service, instance):
        return self.description

    def start_service(self, service, instance):
        if self._thread and self._thread.is_alive():
            return
        self._output[service] = []
        self._thread = ProcessMonitor([self.binary] + self.args,
                                      self.working_dir, self.output_file,
                                      self.one_shot, self._output[service],
                                      self.log)
        self._thread.setDaemon(True)
        self._thread.start()

    def stop_service(self, service, instance):
        if not (self._thread and self._thread.is_alive()):
            return
        self._thread.stopflag = True
        self._thread.join()

    def restart_service(self, service, instance):
        self.stop_service(service, instance)
        self.start_service(service, instance)

    def service_status(self, service, instance):
        if self._thread and self._thread.is_alive():
            return RUNNING, ''
        if self.one_shot:
            return NOT_RUNNING, ''
        return DEAD, ''

    def service_output(self, service, instance):
        return list(self._output.get(service, []))
