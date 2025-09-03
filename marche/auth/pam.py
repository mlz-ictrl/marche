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
#
# *****************************************************************************

""".. index:: simple; authenticator

PAM authenticator
-----------------

This authenticator checks credentials against Linux' PAM.

.. describe:: [auth.pam]

   The configuration settings that can be set within the **auth.pam** section
   are:

   .. describe:: service

      **Default:** ``"login"``

      The PAM service to use.  The default service, "login", allows the same
      users to connect that can log into the system.  However, a custom service
      (e.g. "marche") can be configured in PAM, to place different restrictions
      on the possible logins.

   .. describe:: adminusers

      **Default:** ``["root"]``

      A list of user names who get ADMIN access.

   .. describe:: controlusers

      **Default:** ``[]``

      A list of user names who get CONTROL access.

   .. describe:: displayusers

      **Default:** ``[]``

      A list of user names who get DISPLAY access.

   .. describe:: defaultlevel

      **Default:** ``"display"``

      The permission level to return for any user no in one of the above lists.
      Can be "none" to deny any other users.
"""

import hashlib

import pamela

from marche.auth.base import Authenticator as BaseAuthenticator
from marche.permission import ADMIN, CONTROL, DISPLAY, NONE, STRING_LEVELS, \
    ClientInfo
from marche.utils import bytencode


class Authenticator(BaseAuthenticator):

    def __init__(self, config, log):
        BaseAuthenticator.__init__(self, config, log)
        self._cache = set()
        self.service = config.get('service', 'login')
        self.adminusers = config.get('adminusers', ['root'])
        self.controlusers = config.get('controlusers', [])
        self.displayusers = config.get('displayusers', [])
        self.defaultlevel = STRING_LEVELS[
            config.get('defaultlevel', 'display').lower()]

    def authenticate(self, user, passwd):
        key = hashlib.sha1(bytencode(user + ':' + passwd)).digest()
        if key not in self._cache:
            try:
                pamela.authenticate(user, passwd, self.service)
            except pamela.PAMError as e:
                self.log.error('could not authenticate %s: %s', user, e)
                return None
            self._cache.add(key)
        if user in self.adminusers:
            return ClientInfo(ADMIN)
        if user in self.controlusers:
            return ClientInfo(CONTROL)
        if user in self.displayusers:
            return ClientInfo(DISPLAY)
        if self.defaultlevel == NONE:
            return None
        return ClientInfo(self.defaultlevel)
