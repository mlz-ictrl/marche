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

import os
import socket
import threading

import PyTango
from PyTango import AttrQuality, AttrWriteType, DispLevel, DevState
from PyTango.server import Device, DeviceMeta, attribute, command


class ProcessController(Device):
    __metaclass__ = DeviceMeta

    def init_device(self):
        Device.init_device(self)
        self.set_state(DevState.ON)

    @command(dtype_in=None, dtype_out='DevVarStringArray')
    def GetServices(self):
        return self.jobhandler.get_services()

    @command(dtype_in=str, doc_in="Start service", dtype_out=bool)
    def Start(self, service):
        self.jobhandler.start_service(service)
        return True

    @command(dtype_in=str, doc_in="Stop service", dtype_out=bool)
    def Stop(self, service):
        self.jobhandler.stop_service(service)
        return True

    @command(dtype_in=str, doc_in="Status of service", dtype_out=int)
    def GetStatus(self, service):
        return self.jobhandler.service_status(service)


class Interface(object):
    def __init__(self, config, jobhandler, log):
        self.config = config
        ProcessController.jobhandler = jobhandler
        self.log = log.getChild('tango')

        if 'tango_host' in config.extended:
            os.environ['TANGO_HOST'] = config.extended['tango_host']

        try:
            hostname = socket.gethostname()
        except socket.error:
            hostname = 'localhost'
        self.fqdn = socket.getfqdn(hostname)

    def run(self):
        db = PyTango.Database()
        instname = 'Marche/' + self.fqdn
        if instname not in db.get_server_list():
            self.log.info('registering Tango server instance %r' % instname)
            di = PyTango.DbDevInfo()
            di.name = 'dserver/' + instname
            di._class = 'DServer'
            di.server = instname
            db.add_device(di)
            di = PyTango.DbDevInfo()
            di.name = 'marche/control/%s' % self.fqdn
            di._class = 'ProcessController'
            di.server = instname
            db.add_device(di)

        util = PyTango.Util(['Marche', self.fqdn])
        util.add_class(ProcessController.TangoClassClass,
                       ProcessController,
                       ProcessController.TangoClassName)
        u_inst = PyTango.Util.instance()
        u_inst.server_init()
        self.log.info('Startup successful')
        u_inst.server_run()
