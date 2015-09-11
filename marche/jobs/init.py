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

from os import path

from marche.utils import extractLoglines
from marche.jobs.base import Job as BaseJob


class Job(BaseJob):

    def __init__(self, name, config, log):
        BaseJob.__init__(self, name, config, log)
        self.init_name = config.get('script', name)
        self.log_file = config.get('logfile', '')

    def check(self):
        script = '/etc/init.d/%s' % self.init_name
        if not path.exists(script):
            self.log.error('%s missing' % script)
            return False
        return True

    def get_services(self):
        return [self.init_name]

    def start_service(self, name):
        self._async_start(name, '/etc/init.d/%s start' % self.init_name)

    def stop_service(self, name):
        self._async_stop(name, '/etc/init.d/%s stop' % self.init_name)

    def restart_service(self, name):
        self._async_start(name, '/etc/init.d/%s restart' % self.init_name)

    def service_status(self, name):
        return self._async_status(name, '/etc/init.d/%s status' % self.init_name)

    def service_logs(self, name):
        if self.log_file:
            return extractLoglines(self.log_file)
        return []
