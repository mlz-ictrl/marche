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

"""Job for single init scripts."""

import os

from marche.jobs import DEAD, RUNNING


class Job(object):

    def __init__(self, name, config, log):
        self.init_name = config.get('script', name)
        self.log = log.getChild(name)

    def get_services(self):
        return [self.init_name]

    # XXX use subprocess here...

    def start_service(self, name):
        self.log.info('starting')
        os.system('/etc/init.d/' + self.init_name + ' start')

    def stop_service(self, name):
        self.log.info('stopping')
        os.system('/etc/init.d/' + self.init_name + ' stop')

    def service_status(self, name):
        if os.system('/etc/init.d/' + self.init_name + ' status') == 0:
            return RUNNING
        return DEAD
