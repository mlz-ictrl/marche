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
#   Michael Wagener <m.wagener@fz-juelich.de>
#
# *****************************************************************************

"""Job for single init scripts."""

from PyTango import Database, DbDatum, DbDevInfo

from marche.jobs.init import Job as InitJob


class TangoSrvJob(InitJob):
    """Special job for legacy Tango servers (not using Entangle)."""

    def send_config(self, name, data):
        InitJob.send_config(self, name, data)
        # transfer to Tango database
        self._update_db(self.config_file)

    def _update_db(self, fn):
        db = Database()

        def add_device(name, cls, srv):
            dev_info = DbDevInfo()
            dev_info.name   = name
            dev_info.klass  = cls
            dev_info.server = srv
            db.add_device(dev_info)

        def add_property(dev, name, vals):
            if dev.startswith(("cmds/", "error/")):
                return
            val = val.strip()
            prop = DbDatum()
            prop.name = name
            for val in vals:
                prop.value_string.append(val)
            if dev[0:6] == "class/":
                db.put_class_property(s = dev.split("/")[1], prop)
            else:
                db.put_device_property(dev, prop)

        def processvalue(key, res, val):
            if val.startswith('"'):
                add_property(key, res, [val.strip('"')])
            elif ',' not in val:
                add_property(key, res, [val])
            else:
                arr = val.split(',')
                add_property(key, res, [val for val in arr if val])

        def processdevice(key, valpar):
            klass = key[0].upper()
            for val in valpar:
                valarr = val.strip().split('/')
                srv = klass  + '/' + valarr[0] + '_' + key[1]
                name = val.strip()
                add_device(name, valarr[1], srv)

        fp = open(fn)
        for line in iter(fp.readline, ''):
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
            key = val[0].lower().split('/')
            if len(key) == 4:
                processvalue(key[0].strip() + '/' + key[1].strip() + '/' +
                             key[2].strip(), key[3], val[1].strip())
        fp.close()
