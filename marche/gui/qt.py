#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2022 by the authors, see LICENSE
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

"""Qt 4/5 compatibility layer."""

# pylint: disable=wildcard-import,unused-import,unused-wildcard-import

import sys

try:
    import PyQt5

except (ImportError, RuntimeError):
    import sip
    sip.setapi('QString', 2)
    sip.setapi('QVariant', 2)

    from PyQt4 import uic
    from PyQt4.QtCore import *
    from PyQt4.QtGui import *

    import marche.gui.res_qt4

    try:
        from PyQt4.QtCore import QPyNullVariant  # pylint: disable=E0611
    except ImportError:
        class QPyNullVariant:
            pass

else:
    # Do not abort on exceptions in signal handlers.
    sys.excepthook = lambda *args: sys.__excepthook__(*args)

    from PyQt5 import uic
    from PyQt5.QtCore import *
    from PyQt5.QtGui import *
    from PyQt5.QtWidgets import *

    import marche.gui.res_qt5

    class QPyNullVariant:
        pass
