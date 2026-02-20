# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-present by the authors, see LICENSE
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
PROTO_VERSION = 4


class Errors:
    BUSY = 1
    FAULT = 2
    DENIED = 3
    EXCEPTION = 9


class Response:  # noqa: PLW1641  TODO: implement hash?
    def __eq__(self, other):
        return isinstance(other, self.__class__) and \
            vars(self) == vars(other)

    def __repr__(self):
        return f'<{self.__class__.__name__}: {vars(self)!r}>'


class ServiceListResponse(Response):
    def __init__(self, services):
        self.services = services


class ServiceResponse(Response):
    def __init__(self, service, instance):
        self.service = service
        self.instance = instance


class StatusResponse(ServiceResponse):
    def __init__(self, service, instance, state, ext_status):
        ServiceResponse.__init__(self, service, instance)
        self.state = state
        self.ext_status = ext_status


class ErrorResponse(ServiceResponse):
    def __init__(self, service, instance, code, desc):
        ServiceResponse.__init__(self, service, instance)
        self.code = code
        self.desc = desc


class ControlOutputResponse(ServiceResponse):
    def __init__(self, service, instance, content):
        ServiceResponse.__init__(self, service, instance)
        self.content = content


class FileResponse(ServiceResponse):
    def __init__(self, service, instance, files):
        ServiceResponse.__init__(self, service, instance)
        self.files = files


class ConffileResponse(FileResponse):
    pass


class LogfileResponse(FileResponse):
    pass


class FoundHostResponse(Response):
    def __init__(self, host, version):
        self.host = host
        self.version = version
