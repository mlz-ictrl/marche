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
#
# *****************************************************************************

DEAD = 0
NOT_RUNNING = 5
STARTING = 10
INITIALIZING = 15
RUNNING = 20
WARNING = 25  # running, but not completely
STOPPING = 30
NOT_AVAILABLE = 40

STATE_STR = {
    DEAD: 'DEAD',
    NOT_RUNNING: 'NOT RUNNING',
    STARTING: 'STARTING',
    INITIALIZING: 'INITIALIZING',
    RUNNING: 'RUNNING',
    WARNING: 'WARNING',
    STOPPING: 'STOPPING',
    NOT_AVAILABLE: 'NOT AVAILABLE',
}


class Fault(Exception):
    pass


class Unauthorized(Fault):
    pass


class Busy(Exception):
    def __str__(self):
        s = Exception.__str__(self)
        return s or 'job is already busy, retry later'


# according to systemd's src/core/service.c (state_translation_table)
SYSTEMD_STATE_MAP = {
    'dead': DEAD,
    'condition': STARTING,
    'start-pre': STARTING,
    'start': STARTING,
    'start-post': STARTING,
    'running': RUNNING,
    'exited': DEAD,
    'reload': STARTING,
    'reload-signal': STARTING,
    'reload-notify': STARTING,
    'stop': STOPPING,
    'stop-watchdog': STOPPING,
    'stop-sigterm': STOPPING,
    'stop-sigkill': STOPPING,
    'stop-post': STOPPING,
    'final-watchdog': STOPPING,
    'final-sigterm': STOPPING,
    'final-sigkill': STOPPING,
    'failed': DEAD,
    'auto-restart': STARTING,
    'cleaning': WARNING,
}
