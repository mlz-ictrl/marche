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
#
# *****************************************************************************

"""Basic authenticator class."""


class Authenticator(object):

    def __init__(self, config, log):
        self.config = config
        self.log = log
        self.init()

    def init(self):
        """Implement to do something on init.

        The constructor has stored the configuration in ``self.config``, and
        created a logger in ``self.log``.
        """

    def authenticate(self, user, passwd):
        """Return a `marche.permission.ClientInfo` object with the assigned
        permission level if the user and password are correct.

        Otherwise, return None to give other authenticators a chance.
        """
