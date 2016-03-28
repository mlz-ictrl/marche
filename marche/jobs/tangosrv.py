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
#   Michael Wagener <m.wagener@fz-juelich.de>
#
# *****************************************************************************

""".. index:: tangosrv; job

Standalone Tango Server job
===========================

Job for standalone Tango_ servers controlled by an init script.

This is basically an Init-Script job, with the additional feature of
transferring the server resources from a file into the Tango database when the
config file is edited via Marche.

This job has the following configuration parameters:

.. describe:: [job.xxx]

   .. describe:: type

      Must be ``tangosrv``.

   .. describe:: srvname

      Name of the server (for determining logfiles and config files).  Default
      is the job name.

   .. describe:: resdir

      The configuration for the server is expected in a resource file located
      in this directory.  If not given, file :file:`/etc/default/tango` should
      contain a line ``TANGO_RES_DIR=resdir``.

This job inherits from the :ref:`init-job`, and therefore supports all its
other configuration parameters.

A typical section looks like this::

    [job.Counter]
    type = tangosrv

This will start/stop via ``/etc/init.d/tango-server-counter`` (the init script
name can be overridden with the ``script`` parameter as for the init job).  The
names of potential logfiles are also automatically determined.

.. _Tango: http://tango-controls.org
"""

from os import path

from marche.jobs import Fault
from marche.jobs.init import Job as InitJob

try:
    import PyTango
except ImportError:  # pragma: no cover
    PyTango = None


class Job(InitJob):

    LOG_DIR = '/var/log/tango'
    DEFAULT_FILE = '/etc/default/tango'

    def configure(self, config):
        InitJob.configure(self, config)
        self.srvname = config.get('srvname', self.name)
        self.init_name = config.get('script', 'tango-server-' +
                                    self.srvname.lower())
        resdir = config.get('resdir', '')
        if not resdir:
            with open(self.DEFAULT_FILE) as fd:
                for line in fd:
                    if not line.startswith('#'):
                        (key, sep, value) = line.partition('=')
                        if sep:
                            key = key.replace('export', '').strip()
                            if key == 'TANGO_RES_DIR':
                                resdir = value.strip()
                                break
        if resdir:
            self.config_files = [path.join(resdir, self.srvname + '.res')]
        else:  # pragma: no cover
            self.config_files = []
        self.log_files = [path.join(self.LOG_DIR, '%s.out.log' % self.srvname),
                          path.join(self.LOG_DIR, '%s.err.log' % self.srvname)]

    def send_config(self, service, instance, filename, contents):
        db = self._connect_db()
        InitJob.send_config(self, service, instance, filename, contents)
        # transfer to Tango database
        self._update_db(db, self.config_files[0])

    def _update_db(self, db, fn):
        def processvalue(dev, res, val):
            if dev.startswith(('cmds/', 'error/')):
                return
            if val.startswith('"'):
                self._add_property(db, dev, res, [val.strip('"').strip()])
            elif ',' not in val:
                self._add_property(db, dev, res, [val.strip()])
            else:
                arr = val.split(',')
                self._add_property(db, dev, res, [v.strip() for v in arr if v])

        def processdevice(key, valpar):
            klass = key[0].title()
            if key[1] == 'localhost':
                return
            for val in valpar:
                valarr = val.strip().split('/')
                srv = klass  + '/' + valarr[0] + '_' + key[1]
                name = val.strip()
                self._add_device(db, name, valarr[1], srv)

        with open(fn) as fp:
            for line in iter(fp.readline, ''):
                if not isinstance(line, str):  # pragma: no cover
                    line = line.decode('utf-8', 'replace')
                line = line.expandtabs(1).strip()
                while line.endswith('\\'):
                    line = line.rstrip('\\ ')
                    if not line.endswith(':'):
                        line += ','
                    line += fp.readline().expandtabs(1).strip()
                if line.startswith('#'):
                    continue
                val = line.split('#', 1)
                line = val[0]
                val = line.split(':', 1)
                if len(val) < 2:
                    continue
                key = [k.strip() for k in val[0].lower().split('/')]
                if len(key) == 4:
                    processvalue(key[0] + '/' + key[1] + '/' + key[2],
                                 key[3], val[1].strip())
                elif len(key) == 3 and key[2] == 'device':
                    processdevice(key, val[1].strip().split(','))

    def _connect_db(self):  # pragma: no cover
        if PyTango is None:
            raise Fault('cannot update database: PyTango missing')
        return PyTango.Database()

    def _add_device(self, db, name, cls, srv):  # pragma: no cover
        dev_info = PyTango.DbDevInfo()
        dev_info.name = name
        dev_info.klass = cls
        dev_info.server = srv
        db.add_device(dev_info)

    def _add_property(self, db, dev, name, vals):  # pragma: no cover
        prop = PyTango.DbDatum()
        prop.name = name
        for val in vals:
            prop.value_string.append(val)
        if dev[0:6] == 'class/':
            db.put_class_property(dev.split('/')[1], prop)
        else:
            db.put_device_property(dev, prop)
