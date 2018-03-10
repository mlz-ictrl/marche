#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2018 by the authors, see LICENSE
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

""".. index:: simple; authenticator

Simple authenticator
--------------------

This authenticator allows the configuration of a single user/password pair and
a user permission level right in the config file.  It is the most basic
authenticator and useful for simple services.

.. describe:: [auth.simple]

   The configuration settings that can be set within the **auth.simple**
   section are:

   .. describe:: user

      **Default:** marche

      The username to accept for authentication.

   .. describe:: passwd

      **Default:** no password

      The password matching the username.

   .. describe:: level

      **Default:** admin

      The permission level to return (one of ``display``, ``control`` and
      ``admin``).
"""

from marche.auth.base import Authenticator as BaseAuthenticator
from marche.permission import ClientInfo, STRING_LEVELS


class Authenticator(BaseAuthenticator):

    def __init__(self, config, log):
        BaseAuthenticator.__init__(self, config, log)
        self.username = config.get('user', 'marche')
        self.password = config.get('passwd', '')
        self.level = STRING_LEVELS[config.get('level', 'admin').lower()]

    def authenticate(self, user, passwd):
        if not self.password:
            if user == self.username:
                return ClientInfo(self.level)
        if user == self.username and passwd == self.password:
            return ClientInfo(self.level)
