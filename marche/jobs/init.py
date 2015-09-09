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

"""Job for single init scripts."""

import os
from os import path

from marche.jobs import DEAD, RUNNING, STARTING, STOPPING, Busy
from marche.jobs.base import Job as BaseJob
from marche.utils import AsyncProcess


class Job(BaseJob):

    def __init__(self, name, config, log):
        BaseJob.__init__(self, name, config, log)
        self.init_name = config.get('script', name)
        self._proc = None

    def check(self):
        script = '/etc/init.d/%s' % self.init_name
        if not path.exists(script):
            self.log.error('%s missing' % script)
            return False
        return True

    def get_services(self):
        return [self.init_name]

    def start_service(self, name):
        if self._proc and not self._proc.done:
            raise Busy
        self.log.info('starting')
        self._proc = AsyncProcess(STARTING, self.log,
                                  '/etc/init.d/' + self.init_name + ' start')
        self._proc.start()

    def stop_service(self, name):
        if self._proc and not self._proc.done:
            raise Busy
        self.log.info('stopping')
        self._proc = AsyncProcess(STOPPING, self.log,
                                  '/etc/init.d/' + self.init_name + ' stop')
        self._proc.start()

    def service_status(self, name):
        if self._proc and not self._proc.done:
            return self._proc.status
        if os.system('/etc/init.d/' + self.init_name + ' status') == 0:
            return RUNNING
        return DEAD
