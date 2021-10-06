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

"""Test for the configuration class."""

import os

from marche.config import Config
from marche.permission import ADMIN, DISPLAY


def test_defaults():
    config = Config()

    assert config.user is None
    assert config.group is None
    assert config.piddir == '/var/run'
    assert config.logdir == '/var/log'
    assert config.unauth_level == DISPLAY


def test_config():
    config = Config(os.path.join(os.path.dirname(__file__), 'conf'))

    assert config.user == 'marche'
    assert config.group == 'marchegroup'
    assert config.piddir == '/tmp/pid'
    assert config.logdir == '/tmp/log'
    assert config.unauth_level == ADMIN

    assert config.job_config == {'myjob': {'type': 'init'}}
    assert config.auth_config == {'simple': {'user': 'simple',
                                             'passwd': 'simple'}}
    assert config.iface_config == {'xmlrpc': {'user': 'legacy',
                                              'passwd': 'legacy'}}
