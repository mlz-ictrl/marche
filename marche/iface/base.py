#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2021 by the authors, see LICENSE
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

"""Base interface class."""


class Interface(object):

    #: The name of the interface, must be the same as the module name.
    iface_name = 'iface'
    #: True if the interface can emit or otherwise handle events.
    needs_events = True

    def __init__(self, config, jobhandler, authhandler, log):
        self.jobhandler = jobhandler
        self.authhandler = authhandler
        self.config = config.iface_config.get(self.iface_name, {})
        self.log = log.getChild(self.iface_name)
        self.init()

    def init(self):
        """Initialize the interface.  Called by the constructor.

        The following instance attributes are set:

        ``jobhandler``
           The :class:`~marche.handler.JobHandler` instance.
        ``config``
           The config dictionary for the interface.
        ``log``
           The logger for the interface.
        """

    def emit_event(self, event):
        """Emit an event to clients.

        This method will be called from various threads; it is the interface's
        job to ensure that this is safe.
        """

    def run(self):
        """Run the interface.  This should start the main loop of the interface
        in a separate thread and return.
        """
        raise NotImplementedError('implement %s.run()' %
                                  self.__class__.__name__)

    def shutdown(self):
        """Shutdown the interface.  This should stop the main loop of the
        interface if possible.
        """
