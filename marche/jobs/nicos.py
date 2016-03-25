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
#
# *****************************************************************************

"""Job for NICOS_ services.

.. _NICOS: http://nicos-controls.org/
"""

import ConfigParser
from os import path

from marche.jobs import DEAD, STARTING, RUNNING, WARNING
from marche.jobs.base import Job as BaseJob
from marche.utils import extractLoglines

DEFAULT_INIT = '/etc/init.d/nicos-system'


class Job(BaseJob):

    def __init__(self, name, config, log):
        BaseJob.__init__(self, name, config, log)
        self.config = config
        self.log = log.getChild(name)
        self._services = []
        self._proc = None
        if 'root' in config:
            self._root = config['root']
            self._script = path.join(self._root, 'etc', 'nicos-system')
        else:
            # determine the NICOS root from the init script, which is a symlink
            # to the init script in the NICOS root
            self._root = path.dirname(path.dirname(path.realpath(DEFAULT_INIT)))
            self._script = DEFAULT_INIT
        self._logpath = None

    def check(self):
        if not path.exists(self._script):
            self.log.error('%s missing' % self._script)
            return False
        return True

    def get_services(self):
        proc = self._async_call(STARTING, '%s 2>&1' % self._script)
        proc.join()
        lines = proc.stdout
        if len(lines) >= 2 and lines[-1].startswith('Possible services are'):
            self._services = [entry.strip() for entry in
                              lines[-1][len('Possible services are '):].split(',')]

        return ['nicos-system'] + ['nicos.%s' % s for s in self._services]

    def start_service(self, name):
        if name == 'nicos-system':
            return self._async_start(None, '%s start' % self._script)
        else:
            return self._async_start(None, '%s start %s' % (self._script, name[6:]))

    def stop_service(self, name):
        if name == 'nicos-system':
            return self._async_stop(None, '%s stop' % self._script)
        else:
            return self._async_stop(None, '%s stop %s' % (self._script, name[6:]))

    def restart_service(self, name):
        if name == 'nicos-system':
            return self._async_start(None, '%s restart' % self._script)
        else:
            return self._async_start(None, '%s restart %s' % (self._script, name[6:]))

    def service_status(self, name):
        async_st = self._async_status_only(None)
        if async_st is not None:
            return async_st
        if name == 'nicos-system':
            output = self._sync_call('%s status' % self._script).stdout
            something_dead = something_running = False
            for line in output:
                if 'dead' in line:
                    something_dead = True
                if 'running' in line:
                    something_running = True
            if something_dead and something_running:
                return WARNING
            elif something_running:
                return RUNNING
            return DEAD
        else:
            retcode = self._sync_call('%s status %s' % (self._script, name[6:])).retcode
            return RUNNING if retcode == 0 else DEAD

    def service_logs(self, name):
        if name == 'nicos-system':
            return []
        if self._logpath is None:
            # extract nicos log directory
            cfg = ConfigParser.RawConfigParser()
            cfg.read([path.join(self._root, 'nicos.conf')])
            if cfg.has_option('nicos', 'logging_path'):
                self._logpath = cfg.get('nicos', 'logging_path')
            else:
                self._logpath = path.join(self._root, 'log')
        return extractLoglines(path.join(self._logpath, name[6:], 'current'))
