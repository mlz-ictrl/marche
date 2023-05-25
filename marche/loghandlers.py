#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2023 by the authors, see LICENSE
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

from mlzlog import LogfileFormatter

try:
    from systemd.journal import JournalHandler as SystemdJournalHandler, send
except ImportError:
    SystemdJournalHandler = object


JOURNAL_LOGFMT = '%(name)-25s: %(message)s'
DATEFMT = '%H:%M:%S'


class JournalHandler(SystemdJournalHandler):
    """A logger handler for the systemd journal.

    Uses the handler provided by the systemd package, but subclasses it to add
    the logger name (which contains the device name) to the message instead of
    a custom attribute that is not normally printed by journalctl.
    """

    def __init__(self):
        SystemdJournalHandler.__init__(self)
        self.setFormatter(LogfileFormatter(JOURNAL_LOGFMT, DATEFMT))

    def emit(self, record):
        try:
            pri = self.mapPriority(record.levelno)
            message = self.format(record)
            send(
                message,
                PRIORITY=format(pri),
                SYSLOG_IDENTIFIER='marched',
                # this is necessary to avoid getting the location of
                # emit() in every message
                CODE_FILE='',
                # we don't use self._extra since it would supply another
                # SYSLOG_IDENTIFIER argument
            )
        except Exception:
            self.handleError(record)
