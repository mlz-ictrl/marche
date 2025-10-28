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

"""Test for the authentication and permission classes."""

import logging
import os
import sys
from unittest.mock import patch

import bcrypt
import pytest

from marche.auth import AuthFailed, AuthHandler
from marche.auth.base import Authenticator as BaseAuthenticator
from marche.config import Config
from marche.permission import ADMIN, CONTROL, DISPLAY, parse_permissions
from test.utils import LogHandler

# Pretend that we are an auth module.
sys.modules['marche.auth.test'] = sys.modules[__name__]

logger = logging.getLogger('testauth')
testhandler = LogHandler()
logger.addHandler(testhandler)


class Authenticator(BaseAuthenticator):
    def init(self):
        raise RuntimeError


def test_errors():
    config = Config()
    # No such module.
    config.auth_config = {'nonexisting': [{}]}
    testhandler.assert_error(AuthHandler, config, logger)
    # Error on init.
    config.auth_config = {'test': [{}]}
    testhandler.assert_error(AuthHandler, config, logger)


def test_simple():
    config = Config()
    config.auth_config = {'simple': [{
        'user': 'user',
        'passwd': bcrypt.hashpw(b'passwd', bcrypt.gensalt(8)).decode('utf-8'),
        'level': 'control',
    }]}

    handler = AuthHandler(config, logger)
    assert handler.needs_authentication()
    assert handler.authenticate('user', 'passwd').level == CONTROL
    pytest.raises(AuthFailed, handler.authenticate, 'user', 'wrong')

    config.auth_config = {'simple': [{'user': 'user', 'passwd': '',
                                      'level': 'display'}]}
    handler = AuthHandler(config, logger)
    assert handler.authenticate('user', 'anypass').level == DISPLAY


@pytest.mark.skipif(os.name == 'nt', reason='PAM not available on Windows')
def test_pam():
    config = Config()
    config.auth_config = {'pam': [{'service': 'marche',
                                   'adminusers': ['admin'],
                                   'controlusers': ['ctrl'],
                                   'displayusers': ['disp'],
                                   'defaultlevel': 'control'}]}

    class Pamela:
        def authenticate(self, _user, password, service):
            assert service == 'marche'
            if password != 'pass':  # noqa: S105
                raise self.PAMError

        class PAMError(Exception):
            pass

    with patch('marche.auth.pam.pamela', Pamela()):
        handler = AuthHandler(config, logger)
        assert handler.authenticate('admin', 'pass').level == ADMIN
        assert handler.authenticate('ctrl', 'pass').level == CONTROL
        assert handler.authenticate('disp', 'pass').level == DISPLAY
        assert handler.authenticate('user', 'pass').level == CONTROL
        pytest.raises(AuthFailed, handler.authenticate, 'user', 'wrong')

    config.auth_config = {'pam': [{'service': 'marche',
                                   'defaultlevel': 'none'}]}

    with patch('marche.auth.pam.pamela', Pamela()):
        handler = AuthHandler(config, logger)
        pytest.raises(AuthFailed, handler.authenticate, 'admin', 'pass')


def test_parse_permissions():
    pdict = {DISPLAY: DISPLAY, CONTROL: CONTROL, ADMIN: ADMIN}
    parse_permissions(pdict, dict(display='control', control='admin',
                                  admin='display'))
    assert pdict == {DISPLAY: CONTROL, CONTROL: ADMIN, ADMIN: DISPLAY}

    pytest.raises(ValueError, parse_permissions, pdict, 'foo')
    pytest.raises(ValueError, parse_permissions, pdict, ['display'])
    pytest.raises(ValueError, parse_permissions, pdict, {'display': 'foo'})
    pytest.raises(ValueError, parse_permissions, pdict, {'foo': 'display'})
