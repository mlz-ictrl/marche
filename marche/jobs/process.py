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

      A comma-separated list of logfiles to transfer to the client on request.
      If not given, the ``outputfile`` is the default.

A typical section looks like this::

    [job.myprocess]
    type = process
    binary = MyProcess
    workingdir = /tmp
    outputfile = /var/log/myprocess.log
"""

import sys
import shlex
from os import path
from time import sleep
from threading import Thread
from subprocess import Popen, STDOUT

from marche.utils import extractLoglines
from marche.jobs import RUNNING, DEAD
from marche.jobs.base import Job as BaseJob


class ProcessMonitor(Thread):
    def __init__(self, cmd, wd, outfile, log):
        Thread.__init__(self)
        self.returncode = None
        self.stopflag = False
        self.log = log
        self._wd = wd
        self._cmd = cmd
        self._outfile = outfile

    def run(self):
        self.log.info('worker %s: started' % self._cmd)
        if self._outfile is not None:
            outfile = open(self._outfile, 'wb+')
        else:
            outfile = sys.stdout
            if hasattr(outfile, 'buffer'):
                outfile = outfile.buffer
        process = Popen(self._cmd, stdout=outfile, stderr=STDOUT, cwd=self._wd)
        while process.poll() is None:
            sleep(0.1)
            if self.stopflag:
                process.kill()
        self.returncode = process.returncode
        self.log.info('worker %s: return %d' % (self._cmd, self.returncode))


class Job(BaseJob):

    def __init__(self, name, config, log):
        BaseJob.__init__(self, name, config, log)
        self.binary = config.get('binary', name)
        self.args = shlex.split(config.get('args', ''))
        self.working_dir = config.get('workingdir', None)
        self.output_file = config.get('outputfile', None)
        if self.working_dir is None:
            self.working_dir = path.dirname(self.binary)
        self.autostart = config.get('autostart', '').lower() in ('yes', 'true')
        self.log_files = []
        for log in config.get('logfiles', self.output_file or '').split(','):
            if log.strip():
                self.log_files.append(log.strip())
        self._thread = None

    def check(self):
        if not path.exists(self.binary):
            self.log.error('%s missing' % self.binary)
            return False
        return True

    def init(self):
        if self.autostart:
            self.start_service(self.name)

    def get_services(self):
        return [self.name]

    def start_service(self, name):
        if self._thread and self._thread.isAlive():
            return
        self._thread = ProcessMonitor([self.binary] + self.args,
                                      self.working_dir, self.output_file,
                                      self.log)
        self._thread.setDaemon(True)
        self._thread.start()

    def stop_service(self, name):
        if not (self._thread and self._thread.isAlive()):
            return
        self._thread.stopflag = True
        self._thread.join()

    def restart_service(self, name):
        self.stop_service(name)
        self.start_service(name)

    def service_status(self, name):
        if self._thread and self._thread.isAlive():
            return RUNNING
        return DEAD

    def service_logs(self, name):
        ret = []
        for log_file in self.log_files:
            ret.extend(extractLoglines(log_file))
        return ret
