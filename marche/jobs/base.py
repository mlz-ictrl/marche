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

import collections

from marche.jobs import Busy, STARTING, STOPPING, RUNNING, DEAD
from marche.utils import AsyncProcess


class Job(object):
    """This is the basic job class.

    All methods that implement a Marche command should raise
    :exc:`marche.jobs.Fault` with a nice error message on error.  Other
    exceptions are caught but will cause tracebacks to be written to the
    logfile.

    All methods that start/stop services can also raise :exc:`marche.jobs.Busy`
    to indicate that the operation cannot be done at the moment, because a job
    is already starting/stopping.

    .. automethod:: __init__
    """

    def __init__(self, name, config, log):
        """The constructor can be overridden, but the base class constructor
        should always be called.

        It sets the following instance attributes:

        ``name``
           The job name (the *name* argument).
        ``config``
           The job config dictionary (the *config* argument).
        ``log``
           A logger for the job (a child of the *log* argument).
        """
        self.name = name
        self.config = config
        self.log = log.getChild(name)
        self._processes = {}
        self._output = {}

    # Utilities

    def _async_call(self, status, cmd, sh=True, output=None):
        if output is not None:
            output.append('$ %s\n' % cmd)
        proc = AsyncProcess(status, self.log, cmd, sh, output, output)
        proc.start()
        return proc

    def _sync_call(self, cmd, sh=True):
        proc = AsyncProcess(0, self.log, cmd, sh)
        proc.start()
        proc.join()
        return proc

    def _async_start(self, sub, cmd):
        if sub in self._processes and not self._processes[sub].done:
            raise Busy
        output = self._output.setdefault(sub, collections.deque(maxlen=50))
        self._processes[sub] = self._async_call(STARTING, cmd, output=output)

    def _async_stop(self, sub, cmd):
        if sub in self._processes and not self._processes[sub].done:
            raise Busy
        output = self._output.setdefault(sub, collections.deque(maxlen=50))
        self._processes[sub] = self._async_call(STOPPING, cmd, output=output)

    def _async_status_only(self, sub):
        if sub in self._processes and not self._processes[sub].done:
            return self._processes[sub].status

    def _async_status(self, sub, cmd):
        if sub in self._processes and not self._processes[sub].done:
            return self._processes[sub].status
        if self._sync_call(cmd).retcode == 0:
            return RUNNING
        return DEAD

    # Public interface

    def check(self):
        """Check if the job can be used at all (on this system).

        This is called on daemon initialization for each configured job, and if
        it returns False, the job is not further used.

        If this returns False, it should also do some logging output to inform
        the user of the reason that the job cannot work.

        The default is to return True.
        """
        return True

    def init(self):
        """Initialize the job.

        This can further configure the job after the feasibility check has run.
        By default, does nothing.
        """
        pass

    def get_services(self):
        """Return a list of ``(service, instance)`` names that this job
        supports.

        For jobs without sub-instances, return ``(service, '')``.

        The default returns no services.
        """
        return []

    def start_service(self, service, instance):
        """Start the service with the given name.

        The method should not block; instead, if the service takes a while to
        start the returned status should be ``STARTING`` during that time.
        """
        raise NotImplementedError('%s.start_service not implemented'
                                  % self.__class__.__name__)

    def stop_service(self, service, instance):
        """Stop the service with the given name.

        The method should not block; instead, if the service takes a while to
        stop the returned status should be ``STOPPING`` during that time.
        """
        raise NotImplementedError('%s.stop_service not implemented'
                                  % self.__class__.__name__)

    def restart_service(self, service, instance):
        """Restart the service with the given name.

        The method should not block; instead, if the service takes a while to
        restart the returned status should be ``STARTING`` during that time.
        """
        raise NotImplementedError('%s.restart_service not implemented'
                                  % self.__class__.__name__)

    def service_status(self, service, instance):
        """Return the status of the service with the given name.

        The status should be one of the constants defined in the
        :mod:`marche.jobs` module:

        * ``DEAD`` (not running, for services that should run continuously)
        * ``NOT_RUNNING`` (not running, for one-shot services)
        * ``STARTING`` (currently starting to run)
        * ``INITIALIZING`` (process running, but not started up)
        * ``RUNNING`` (running OK)
        * ``WARNING`` (running, but not completely/with errors)
        * ``STOPPING`` (currently stopping to run)
        * ``NOT_AVAILABLE`` (not running, cannot start) -- this should only be
          necessary if the feasibility check cannot already rule it out

        Not all states have to be supported; the most basic set of states to
        return is ``DEAD`` or ``RUNNING``.
        """
        raise NotImplementedError('%s.service_status not implemented'
                                  % self.__class__.__name__)

    def service_description(self, service, instance):
        """Return a long string description of the service with the given
        name.
        """
        return '(no long description provided)'

    def service_output(self, service, instance):
        """Return the console output of the last attempt to start/stop/restart
        the service, as a list of strings (lines).
        """
        return []

    def service_logs(self, service, instance):
        """Return the contents of the logfile(s) of the service, if possible.

        The return value must be a dictionary of file names and contents.
        """
        return {}

    def receive_config(self, service, instance):
        """Return the contents of the config file(s) of the service, if
        possible.

        The return value must be a dict mapping the file name to the decoded
        string content for each file.
        """
        raise NotImplementedError('%s.receive_config not implemented'
                                  % self.__class__.__name__)

    def send_config(self, service, instance, data):
        """Transfer changed config file(s) to the service, and update them.

        Usually, this means that the new file is written to disk, but it could
        also take some further action.

        It should *not* restart the service, even if that is necessary for the
        config file to take effect.

        The format of the ``data`` argument is the same as for the return value
        of `receive_config`.
        """
        raise NotImplementedError('%s.send_config not implemented'
                                  % self.__class__.__name__)
