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

"""Event classes."""

from six import add_metaclass


class EventMeta(type):
    def __new__(mcs, name, bases, attrs):
        newtype = type.__new__(mcs, name, bases, attrs)
        if newtype.name:
            newtype.registry[newtype.name] = newtype
        return newtype


@add_metaclass(EventMeta)
class Event(object):
    registry = {}

    #: Name of the event type.
    name = ''

    def serialize(self):
        if not self.name:
            raise RuntimeError('event base class cannot be serialized')
        ret = {'name': self.name}
        ret.update(vars(self))
        return ret

    @staticmethod
    def unserialize(data):
        if 'name' not in data:
            raise RuntimeError('event name not given in event data')
        if data['name'] not in Event.registry:
            # event is not recognized; ignore it for compatibility
            return None
        cls = Event.registry[data.pop('name')]
        return cls(**data)

    def __repr__(self):
        return '<%s: %r>' % (self.__class__.__name__, vars(self))


class ConnectedEvent(Event):
    name = 'Connected'

    def __init__(self, proto_version, daemon_version, unauth_permissions):
        self.proto_version = proto_version
        self.daemon_version = daemon_version
        self.unauth_permissions = unauth_permissions


class ServiceListEvent(Event):
    name = 'ServiceList'

    def __init__(self, services):
        self.services = services


class AuthEvent(Event):
    name = 'Auth'

    def __init__(self, success):
        self.success = success


class ServiceEvent(Event):
    def __init__(self, service, instance):
        self.service = service
        self.instance = instance


class StatusEvent(ServiceEvent):
    name = 'Status'

    def __init__(self, service, instance, state, ext_status):
        ServiceEvent.__init__(self, service, instance)
        self.state = state
        self.ext_status = ext_status


class ErrorEvent(ServiceEvent):
    name = 'Error'

    def __init__(self, service, instance, code, desc):
        ServiceEvent.__init__(self, service, instance)
        self.code = code
        self.desc = desc


class ControlOutputEvent(ServiceEvent):
    name = 'ControlOutput'

    def __init__(self, service, instance, content):
        ServiceEvent.__init__(self, service, instance)
        self.content = content


class FileEvent(ServiceEvent):
    def __init__(self, service, instance, files):
        ServiceEvent.__init__(self, service, instance)
        self.files = files


class ConffileEvent(FileEvent):
    name = 'Conffile'


class LogfileEvent(FileEvent):
    name = 'Logfile'
