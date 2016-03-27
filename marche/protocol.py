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
#
# *****************************************************************************

"""Constants for use with the new Marche protocol."""

# Increment this when making changes to the protocol.
PROTO_VERSION = 2


class Commands(object):
    TRIGGER_RELOAD = 'reload'
    START_SERVICE = 'start'
    STOP_SERVICE = 'stop'
    RESTART_SERVICE = 'restart'
    REQUEST_SERVICE_LIST = 'services?'
    REQUEST_SERVICE_STATUS = 'status?'
    REQUEST_CONTROL_OUTPUT = 'output?'
    REQUEST_LOG_FILES = 'logfiles?'
    REQUEST_CONF_FILES = 'conffiles?'
    SEND_CONF_FILE = 'sendconfig'


class Events(object):
    CONNECTED = 'connected'
    AUTH_RESULT = 'authresult'
    SERVICE_LIST = 'services'
    ERROR = 'error'
    STATUS = 'status'
    CONTROL_OUTPUT = 'output'
    CONF_FILES = 'conffiles'
    LOG_FILES = 'logfiles'
