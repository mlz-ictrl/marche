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
#
# *****************************************************************************

"""Package with authenticators for Marche."""


class AuthFailed(Exception):
    pass


class AuthHandler:

    def __init__(self, config, log):
        self.auths = []
        self.log = log.getChild('auth')
        for authname in config.auth_config:
            try:
                mod = __import__('marche.auth.%s' % authname, {}, {},
                                 ['Authenticator'])
            except Exception as err:
                log.exception('could not import authenticator %r: %s',
                              authname, err)
                continue
            log.info('adding authenticator: %s' % authname)
            try:
                auth = mod.Authenticator(config.auth_config[authname], log)
            except Exception as err:
                log.exception('could not instantiate authenticator %r: %s',
                              authname, err)
                continue
            self.auths.append(auth)

    def needs_authentication(self):
        return bool(self.auths)

    def authenticate(self, user, passwd):
        for auth in self.auths:
            info = auth.authenticate(user, passwd)
            if info:
                return info
        raise AuthFailed('credentials not accepted')
