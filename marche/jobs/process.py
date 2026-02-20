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

""".. index:: process; job

Simple Process job
==================

This is a job for directly controlling processes without an init script.

This is useful when the service has no init script, or the system has no
concept of init scripts (e.g. Windows).

This job has the following configuration parameters:

.. describe:: [job.xxx]

   .. describe:: type

      Must be ``"process"``.

   .. describe:: cmdline

      A list of the full path of the binary to start, and additional arguments.
      There is no default.

   .. describe:: oneshot

      If true, treat this process as a "one-shot" process, which is supposed to
      be started and then stop after doing it job.  The only effects of this
      flag are that the service returns "NOT RUNNING" (instead of "DEAD") when
      not running, and that the output is caught by Marche if ``outputfile`` is
      not set.  It can be retrieved by the "get output" command.

      The default is ``false``.

   .. describe:: workingdir

      The initial working directory for the process.  If not given, Marche's
      working directory is used, which depends on how the daemon was started.

   .. describe:: outputfile

      If given, the full path to a file where stdout and stderr from the
      process will be written to.  If not given, Marche's stdout is used.

   .. describe:: autostart

      If true, the process will be started when the Marche daemon is
      started.  The default is not to start the process automatically.

   .. describe:: logfiles

      List of full paths of logfiles to read and show to the client when
      requested.  If not given, the ``outputfile`` is the default.

   .. describe:: configfiles

      List of full paths of config files to transfer to the client and write
      back when updates are received.  If not given, no configs are
      transferred.

   .. describe:: description

      A nicer description for the job, to be displayed in the GUI.  Default is
      no description, and the job name will be displayed.

   .. describe:: permissions
                 pollinterval

      The :ref:`standard parameters <standard-params>` present for all jobs.

A typical section looks like this::

    [job.myprocess]
    type = "process"
    cmdline = ["MyProcess"]
    workingdir = "/tmp"
    outputfile = "/var/log/myprocess.log"
"""

import os
import signal
import sys
from pathlib import Path
from subprocess import PIPE, STDOUT, Popen
from threading import Thread
from time import sleep

from marche.jobs import DEAD, NOT_RUNNING, RUNNING
from marche.jobs.base import ConfigMixin, LogfileMixin
from marche.jobs.base import Job as BaseJob


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
        self.log.info('worker %s: started', self._cmd)
        if self._outfile is not None:
            outfile = open(self._outfile, 'wb')  # noqa: SIM115
        elif self.oneshot:
            outfile = PIPE
        else:  # pragma: no cover
            outfile = sys.stdout
            if hasattr(outfile, 'buffer'):
                outfile = outfile.buffer
        process = Popen(self._cmd, stdout=outfile, stderr=STDOUT, cwd=self._wd)
        while process.poll() is None:
            sleep(self.DELAY)
            if self.stopflag:
                if os.name == 'nt':
                    process.kill()
                else:
                    # reimplement Popen.kill() for with os.killpg()
                    # in addition to os.kill() to get rid of child sessions
                    process.poll()
                    if process.returncode is None:
                        try:
                            os.killpg(process.pid, signal.SIGKILL)
                        except ProcessLookupError:  # it's not a process group
                            try:
                                os.kill(process.pid, signal.SIGKILL)
                            except ProcessLookupError:
                                pass
                if outfile != PIPE:
                    outfile.flush()
        if self._outfile is None and self.oneshot:
            for line in iter(process.stdout.readline, b''):
                line = line.translate(None, b'\r').decode('utf-8', 'replace')
                self.output.append(line)
        self.returncode = process.returncode
        self.log.info('worker %s: return %d', self._cmd, self.returncode)


class Job(LogfileMixin, ConfigMixin, BaseJob):

    def configure(self, config):
        cmdline = config['cmdline']
        self.binary = Path(cmdline[0])
        self.args = cmdline[1:]
        cdir = config.get('workingdir', None)
        if cdir is not None:
            self.working_dir = Path(cdir)
        else:
            self.working_dir = self.binary.parent
        self.output_file = config.get('outputfile', None)
        self.one_shot = config.get('oneshot', False)
        self.autostart = config.get('autostart', False)
        self.description = config.get('description', self.name)
        self.configure_logfile_mixin(config)
        if not self.log_files and self.output_file:
            self.log_files.append(Path(self.output_file))
        self.configure_config_mixin(config)
        self._thread = None

    def check(self):
        if not self.binary.is_file():
            self.log.warning('%s missing', self.binary)
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

    def service_description(self, _service, _instance):
        return self.description

    def start_service(self, service, _instance):
        if self._thread and self._thread.is_alive():
            return
        self._output[service] = []
        self._thread = ProcessMonitor([self.binary, *self.args],
                                      self.working_dir, self.output_file,
                                      self.one_shot, self._output[service],
                                      self.log)
        self._thread.daemon = True
        self._thread.start()

    def stop_service(self, _service, _instance):
        if not (self._thread and self._thread.is_alive()):
            return
        self._thread.stopflag = True
        self._thread.join()

    def restart_service(self, service, instance):
        self.stop_service(service, instance)
        self.start_service(service, instance)

    def service_status(self, _service, _instance):
        if self._thread and self._thread.is_alive():
            return RUNNING, ''
        if self.one_shot:
            return NOT_RUNNING, ''
        return DEAD, ''

    def service_output(self, service, _instance):
        return list(self._output.get(service, []))
