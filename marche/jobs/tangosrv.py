# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2025 by the authors, see LICENSE
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

Job for standalone Tango_ servers controlled by a systemd service.

This is basically a systemd job, with the additional feature of transferring
the server resources from a file into the Tango database when the config file
is edited via Marche.

This job has the following configuration parameters:

.. describe:: [job.xxx]

   .. describe:: type

      Must be ``"tangosrv"``.

   .. describe:: srvname

      Name of the server (for determining config files).  Default is the job
      name.

   .. describe:: resdir

      The configuration for the server is expected in a resource file located
      in this directory.  If not given, file :file:`/etc/default/tango` should
      contain a line ``TANGO_RES_DIR=resdir``.

   .. describe:: resformat

      The resource file may have different formats: ``"legacy"`` or
      ``"tango"``.

      The 'legacy' format is default and is the original one derived from the
      TACO resource file format.

      The 'tango' format is the 'official' one, which is used by the Jive tool.
      https://tango-controls.readthedocs.io/en/9.2.5/manual/F-property.html#property-file-syntax


This job inherits from the :ref:`systemd-job`, and therefore supports all its
other configuration parameters.

A typical section looks like this::

    [job.Counter]
    type = tangosrv

This will start/stop via ``tango-server-counter.service`` (the unit name can be
overridden with the ``unit`` parameter as for the systemd job).

.. _Tango: http://tango-controls.org
"""

from pathlib import Path

from marche.jobs import Fault
from marche.jobs.systemd import Job as SystemdJob

try:
    import tango
except ImportError:  # pragma: no cover
    tango = None


class Job(SystemdJob):

    DEFAULT_FILE = Path('/etc/default/tango')

    def configure(self, config):
        SystemdJob.configure(self, config)
        self.srvname = config.get('srvname', self.name)
        self.unit = config.get('unit', f'tango-server-{self.srvname.lower()}')
        self.description = config.get('description', f'{self.srvname} server')
        self.resformat = config.get('resformat', 'legacy')
        resdir = config.get('resdir')
        if not resdir:
            with self.DEFAULT_FILE.open(encoding='utf-8') as fd:
                for line in fd:
                    if not line.startswith('#'):
                        (key, sep, value) = line.partition('=')
                        if sep:
                            key = key.replace('export', '').strip()
                            if key == 'TANGO_RES_DIR':
                                resdir = Path(value.strip())
                                break
        else:
            resdir = Path(resdir)
        if resdir:
            self.config_files = [resdir / f'{self.srvname}.res']
        else:  # pragma: no cover
            self.config_files = []
        if self.config_files:
            if config.get('nodb', False):
                db = self._connect_db()
                self._update_db(db, self.config_files[0])
            else:
                db = None

    def send_config(self, service, instance, filename, contents):
        db = self._connect_db()
        SystemdJob.send_config(self, service, instance, filename, contents)
        # transfer to Tango database
        self._update_db(db, self.config_files[0])

    def _update_db(self, db, fn):
        devices = set()

        def processlegacy(fn):
            def processvalue(dev, res, val):
                if dev.startswith(('cmds/', 'error/')):
                    return
                if val.startswith('"'):
                    self._add_property(db, dev, res, [val.strip('"').strip()],
                                       devices)
                elif ',' not in val:
                    self._add_property(db, dev, res, [val.strip()], devices)
                else:
                    arr = val.split(',')
                    self._add_property(db, dev, res,
                                       [v.strip() for v in arr if v], devices)

            def processdevice(key, valpar):
                klass = key[0].title()
                if key[1] == 'localhost':
                    return
                for val in valpar:
                    valarr = val.strip().split('/')
                    srv = klass + '/' + valarr[0] + '_' + key[1]
                    name = val.strip()
                    self._add_device(db, name, valarr[1], srv)
                    devices.add(name.lower())

            with fn.open(encoding='utf-8', errors='replace') as fp:
                # for line in fp:
                for line in iter(fp.readline, ''):
                    line = line.expandtabs(1).strip()
                    while line.endswith('\\'):
                        line = line.rstrip('\\ ')
                        if not line.endswith(':'):
                            line += ','
                        line += fp.readline().expandtabs(1).strip()
                    line = line.split('#', 1)[0]
                    if not line:
                        continue
                    val = line.split(':', 1)
                    if len(val) < 2:
                        continue
                    key = [k.strip() for k in val[0].lower().split('/')]
                    if len(key) == 4:
                        processvalue('/'.join(key[:3]), key[3], val[1].strip())
                    elif len(key) == 3 and key[2] == 'device':
                        processdevice(key, val[1].strip().split(','))

        def processtango(fn):

            def processdevice(key, devices):
                server, dev, klass = key.rsplit('/', 2)
                if dev == "DEVICE":
                    for devname in devices:
                        self._add_device(db, devname, klass, server)

            def processvalue(dev, propname, values):
                self._add_property(db, dev, propname, values, [])

            with fn.open(encoding='utf-8', errors='replace') as fp:
                lines = iter(fp)
                for line in lines:
                    line = line.split('#', 1)[0].strip()
                    if not line:
                        continue
                    try:
                        key, val = line.split(':', 1)
                    except ValueError:
                        continue
                    values = []
                    key = key.strip()
                    while val.endswith('\\'):
                        val = val.rstrip(',\\ ').strip().strip('"')
                        values.append(val)
                        val = next(lines).split('#', 1)[0].strip()
                    val = val.rstrip(',\\ ').strip().strip('"')
                    values.append(val)
                    if key.count('->') == 1:  # property handling
                        processvalue(*key.split('->'), values)
                    elif key.count('/') == 3:  # device handling
                        processdevice(key, values)

        if self.resformat == 'tango':
            processtango(fn)
        else:
            processlegacy(fn)

    def _connect_db(self):  # pragma: no cover
        if tango is None:
            raise Fault('cannot update database: tango module missing')
        return tango.Database()

    def _add_device(self, db, name, cls, srv):  # pragma: no cover
        dev_info = tango.DbDevInfo()
        dev_info.name = name
        dev_info.klass = cls
        dev_info.server = srv
        db.add_device(dev_info)

    def _add_property(self, db, dev, name, vals, devices):  # pragma: no cover
        prop = tango.DbDatum()
        prop.name = name
        for val in vals:
            prop.value_string.append(val)
        if self.resformat == 'tango':
            if dev.split('/', 1)[0] == 'CLASS':
                db.put_class_property(dev.split('/')[1], prop)
            elif dev.count('/') == 2:
                db.put_device_property(dev, prop)
            elif dev.count('/') == 3:
                db.put_device_attribute_property(dev, prop)
            else:
                db.put_property(dev, prop)
        else:
            if dev[0:6] == 'class/':
                db.put_class_property(dev.split('/')[1], prop)
            elif dev.lower() not in devices:
                db.put_property(dev, prop)
            else:
                db.put_device_property(dev, prop)
