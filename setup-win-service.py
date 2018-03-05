#!/usr/bin/env python
#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2018 by the authors, see LICENSE
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
#   Christian Felder <c.felder@fz-juelich.de>
#
# *****************************************************************************

from __future__ import print_function

import sys
import argparse
from os import path
from subprocess import Popen, PIPE
try:
    import _winreg as winreg
except ImportError:
    import winreg
import marche

def parse_args(argv):
    parser = argparse.ArgumentParser(description="Marche MS Windows Service "
                                                  "Setup")
    parser.add_argument("environments", type=str, nargs='*',
                        help="Environment settings, "
                             "e.g. TANGO_HOST=localhost:10000")
    return parser.parse_args(argv)


def main(argv):
    environment = list(parse_args(argv[1:]).environments)

    search_directories = [
        path.join(path.realpath(sys.prefix), "Scripts"),
        path.join(path.dirname(path.dirname(path.realpath(marche.__file__))),
                  "bin"),
    ]

    servicename = "marched"
    marcheroot = None
    for pdir in search_directories:
        marched = path.join(pdir, "marched")
        if path.isfile(marched):
            marcheroot = path.dirname(pdir)
            break
    else:
        marched = None

    if marcheroot:
        print("AppDirectory:", marcheroot)
        print(" Application:", marched)
    else:
        print("marched not found in:", ', '.join(search_directories), file=sys.stderr)
        sys.exit(-1)

    service_subkey = "SYSTEM\\CurrentControlSet\\services\\" + servicename
    service = None
    try:
        service = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, service_subkey, 0,
                                 winreg.KEY_WRITE)
    except WindowsError:
        print("Creating service:", servicename)
        cmd = [
            "sc.exe", "create", servicename, "start=", "auto",
            "binPath=", "srvany.exe",
        ]
        print(' '.join(cmd))
        print()
        stdout, stderr = Popen(cmd, stdout=PIPE, stderr=PIPE).communicate()
        print(stdout)
        print(stderr)
    finally:
        if service:
            service.Close()

        print("Updating registry")
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, service_subkey, 0,
                            winreg.KEY_WRITE) as hdl:
            if environment:
                winreg.SetValueEx(hdl, "Environment", 0, winreg.REG_MULTI_SZ,
                                  environment)
            winreg.SetValueEx(hdl, "Type", 0, winreg.REG_DWORD,
                              0x110)  # interactive
            with winreg.CreateKey(hdl, "Parameters") as par:
                winreg.SetValueEx(par, "AppDirectory", 0, winreg.REG_SZ,
                                  marcheroot)
                winreg.SetValueEx(par, "Application", 0, winreg.REG_SZ,
                                  sys.executable + ' ' + marched)


if __name__ == "__main__":
    main(sys.argv)
