#  -*- coding: utf-8 -*-
# *****************************************************************************
# marche - Server control daemon.
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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************

"""Permission constants and checking."""

# The three basic permission types, which also double as user levels.
#
# DISPLAY is for querying status, output and logfiles.
# CONTROL is for start/stop/restart.
# ADMIN is for configuration.
#
# The level required for a certain action on any job can be overridden to
# a different level in the configuration.  For example, a job could specify
# that its normally CONTROL level actions actually require ADMIN level.

DISPLAY = 0
CONTROL = 10
ADMIN = 20


class ClientInfo(object):
    """Information about a client passed around to check permissions."""
    def __init__(self, level):
        self.level = level


STRING_LEVELS = {
    'd': DISPLAY,
    'c': CONTROL,
    'a': ADMIN,
    'display': DISPLAY,
    'control': CONTROL,
    'admin': ADMIN,
}


def parse_permissions(original, entry):
    """Parse a permission string from the configuration.

    It looks like e.g. ``display=control, control=admin``.
    """
    for item in entry.split(','):
        item = item.strip()
        if item.count('=') != 1:
            raise ValueError('found item without one "="')
        level, req_level = item.split('=')
        level = level.lower().strip()
        req_level = req_level.lower().strip()
        try:
            level = STRING_LEVELS[level]
        except KeyError:
            raise ValueError('unrecognized permission level %r' % level)
        try:
            req_level = STRING_LEVELS[req_level]
        except KeyError:
            raise ValueError('unrecognized permission level %r' % req_level)
        original[level] = req_level
    return original
