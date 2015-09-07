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

"""Job control dispatcher."""


class JobHandler(object):

    def __init__(self, config, log):
        self.config = config
        self.log = log
        self.jobs = {}
        self.service2job = {}
        self._add_jobs()

    def _add_jobs(self):
        for (name, config) in self.config.job_config.items():
            if 'type' not in config:
                self.log.warning('job %r has no type assigned, ignoring' % name)
                continue
            try:
                mod = __import__('marche.jobs.%s' % config['type'], {}, {}, 'Job')
            except Exception as err:
                self.log.exception('could not import module %r for job %s: %s' %
                                   (config['type'], name, err))
                continue
            try:
                job = mod.Job(name, config, self.log)
                for service in job.get_services():
                    self.service2job[service] = job
            except Exception as err:
                self.log.exception('could not initialize job %s: %s' % (name, err))
            else:
                self.jobs[name] = job

    def get_services(self):
        return self.service2job.keys()

    def start_service(self, name):
        self.service2job[name].start_service(name)

    def stop_service(self, name):
        self.service2job[name].stop_service(name)

    def service_status(self, name):
        return self.service2job[name].service_status(name)
