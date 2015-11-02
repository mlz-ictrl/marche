#  -*- coding: utf-8 -*-
# *****************************************************************************
# MLZ server control daemon
# Copyright (c) 2015 by the authors, see LICENSE
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

    def __init__(self, name, config, log):
        self.name = name
        self.config = config
        self.log = log.getChild(name)
        self._processes = {}
        self._output = {}

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
        """Check if the job can be used at all (on this system)."""
        return True

    def init(self):
        """Initialize job."""
        pass

    def get_services(self):
        return []

    def start_service(self, name):
        raise NotImplementedError('%s.start_service not implemented'
                                  % self.__class__.__name__)

    def stop_service(self, name):
        raise NotImplementedError('%s.stop_service not implemented'
                                  % self.__class__.__name__)

    def restart_service(self, name):
        raise NotImplementedError('%s.restart_service not implemented'
                                  % self.__class__.__name__)

    def service_status(self, name):
        raise NotImplementedError('%s.service_status not implemented'
                                  % self.__class__.__name__)

    def service_output(self, name):
        return list(self._output.get(name, []))

    def service_logs(self, name):
        return []
