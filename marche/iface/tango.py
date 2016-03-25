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
#
# *****************************************************************************

""".. index:: tango; interface

Tango interface
---------------

This interface allows control of services via a Tango_ device.  If active, the
Marche daemon will register itself as a Tango device and provide a Tango
command for each Marche protocol command.

.. describe:: [interfaces.tango]

   The configuration settings that can be set within the **interfaces.tango**
   section are:

   .. describe:: tango_host

      **Default:** nothing

      The host of the Tango database to register the server in.  The default
      is to use the existing ``TANGO_HOST`` environment variable.

.. _Tango: http://tango-controls.org
"""

import os
import socket

import PyTango
from PyTango.server import Device, DeviceMeta, command

from marche.handler import JobHandler, VOID, STRING, STRINGLIST, INTEGER
from marche.jobs import Busy, Fault

dtype_map = {
    VOID: None,
    STRING: str,
    STRINGLIST: 'DevVarStringArray',
    INTEGER: int,
}


def interface_command(method):
    def tango_method(self, *args):
        try:
            return method(self.jobhandler, *args)
        except Busy as err:
            PyTango.Except.throw_exception('Marche_Busy', str(err), '')
        except Fault as err:
            PyTango.Except.throw_exception('Marche_Fault', str(err), '')
        except Exception as err:
            PyTango.Except.throw_exception('Marche_Unexpected', str(err), '')
    tango_method.__name__ = method.__name__
    return command(dtype_in=dtype_map[method.intype],
                   dtype_out=dtype_map[method.outtype],
                   doc_in=(method.__doc__ or '').strip())(tango_method)


def MarcheDeviceMeta(name, bases, attrs):
    for mname in dir(JobHandler):
        method = getattr(JobHandler, mname)
        if not hasattr(method, 'is_command'):
            continue
        attrs[mname] = interface_command(method)
    return DeviceMeta(name, bases, attrs)


class ProcessController(Device):
    __metaclass__ = MarcheDeviceMeta

    def init_device(self):
        Device.init_device(self)
        self.set_state(PyTango.DevState.ON)


class Interface(object):
    def __init__(self, config, jobhandler, log):
        self.config = config
        ProcessController.jobhandler = jobhandler
        self.log = log.getChild('tango')

        hostconfig = config.interface_config['tango']['tango_host']
        if hostconfig:
            os.environ['TANGO_HOST'] = hostconfig

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
        try:
            devclass = ProcessController.TangoClassClass
            devclass_name = ProcessController.TangoClassName
        except AttributeError:  # older PyTangos
            devclass = ProcessController._DeviceClass
            devclass_name = ProcessController._DeviceClassName
        util.add_class(devclass, ProcessController, devclass_name)
        u_inst = PyTango.Util.instance()
        u_inst.server_init()
        self.log.info('startup successful')
        u_inst.server_run()
