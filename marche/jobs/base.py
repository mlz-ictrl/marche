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

import collections
import threading

from marche.jobs import Busy, Fault, STARTING, STOPPING, RUNNING, DEAD
from marche.permission import DISPLAY, CONTROL, ADMIN, parse_permissions
from marche.polling import Poller
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

    def __init__(self, name, config, log, event_callback):
        """The constructor should not be overridden, rather implement the
        configure() method.

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
        self.lock = threading.Lock()
        self._processes = {}
        self._output = {}

        self._permissions = {DISPLAY: DISPLAY,
                             CONTROL: CONTROL,
                             ADMIN: ADMIN}
        if 'permissions' in config:
            try:
                self._permissions = parse_permissions(self._permissions,
                                                      config['permissions'])
            except ValueError:
                self.log.error('could not parse permission string: %r' %
                               config['permissions'])
        self.pollinterval = 3.0
        if 'pollinterval' in config:
            try:
                self.pollinterval = float(config['pollinterval'])
            except ValueError:
                self.log.error('could not parse pollinterval: %r' %
                               config['pollinterval'])
        self.poller = Poller(self, self.pollinterval, event_callback)

        self.configure(config)

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

    def has_permission(self, level, client):
        """Query if the client with *client_level* has permission to do an
        action that would normally have *level*.
        """
        return client.level >= self._permissions[level]

    def check_permission(self, level, client):
        """Ensure that the client with *client_level* has permission to do an
        action that would normally have *level*.  If not, raises `Fault`.
        """
        if self.has_permission(level, client):
            return
        raise Fault('permission denied by Marche')

    def invalidate(self, service, instance):
        """Invalidate polled and cached status."""
        self.poller.invalidate(service, instance)

    def poll_now(self):
        """Let the poller poll now, if possible."""
        self.poller.queue.put(True)

    def polled_service_status(self, service, instance):
        """Return the service status, if possible from the poller cache."""
        result = self.poller.get(service, instance)
        if result is not None:
            return result
        return self.service_status(service, instance)

    # Public interface to be implemented by subclasses

    def configure(self, config):
        """Check and process the configuration in *config*.

        The default implementation does nothing.
        """

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

        The default is to start the poller, so the base class method should be
        normally called by subclasses.
        """
        if self.pollinterval > 0:
            self.poller.start()

    def shutdown(self):
        """Shut the job down.

        The default is to stop the poller, so the base class method should be
        normally called by subclasses.
        """
        self.poller.stop()

    def get_services(self):
        """Return a list of ``(service, instance)`` names that this job
        supports.  This should be very cheap, so the list of services should be
        determined in the constructor and only returned here.

        For jobs without sub-instances, return ``(service, '')``.

        This must be implemented by subclasses.
        """
        raise NotImplementedError('%s.get_services not implemented'
                                  % self.__class__.__name__)

    def start_service(self, service, instance):
        """Start the service with the given name.

        The method should not block; instead, if the service takes a while to
        start the returned status should be ``STARTING`` during that time.

        This must be implemented by subclasses.
        """
        raise NotImplementedError('%s.start_service not implemented'
                                  % self.__class__.__name__)

    def stop_service(self, service, instance):
        """Stop the service with the given name.

        The method should not block; instead, if the service takes a while to
        stop the returned status should be ``STOPPING`` during that time.

        This must be implemented by subclasses.
        """
        raise NotImplementedError('%s.stop_service not implemented'
                                  % self.__class__.__name__)

    def restart_service(self, service, instance):
        """Restart the service with the given name.

        The method should not block; instead, if the service takes a while to
        restart the returned status should be ``STARTING`` during that time.

        This must be implemented by subclasses.
        """
        raise NotImplementedError('%s.restart_service not implemented'
                                  % self.__class__.__name__)

    def service_status(self, service, instance):
        """Return the tuple of status constant and extended status of the
        service with the given name.

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

        The extended status is just a string with more information if needed
        and available.

        This must be implemented by subclasses.
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

        The default is to return no output.
        """
        return []

    def service_logs(self, service, instance):
        """Return the contents of the logfile(s) of the service, if possible.

        The return value must be a dictionary of file names and contents.

        The default is to return no logfiles.
        """
        return {}

    def receive_config(self, service, instance):
        """Return the contents of the config file(s) of the service, if
        possible.

        The return value must be a dict mapping the file name to the decoded
        string content for each file.

        The default is to return no config files.
        """
        return {}

    def send_config(self, service, instance, filename, contents):
        """Transfer a changed config file to the service, and update it.
        Usually, this means that the new file is written to disk, but it could
        also take some further action.

        It should *not* restart the service, even if that is necessary for the
        config file to take effect.

        If `receive_config` returns files, this must be implemented.
        """
        raise NotImplementedError('%s.send_config not implemented'
                                  % self.__class__.__name__)
