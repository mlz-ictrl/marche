#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2019 by the authors, see LICENSE
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

import glob
import os
from os import listdir, path

from setuptools import find_packages, setup

import marche.utils
import marche.version

scripts = ['bin/marched', 'bin/marche-gui']

srcdir = path.dirname(__file__)
uidir = path.join(srcdir, 'marche', 'gui', 'ui')
uis = [path.join('gui', 'ui', entry) for entry in listdir(uidir)]
webdir = path.join(srcdir, 'marche', 'iface', 'web', 'static')
webstuff = [path.join('iface', 'web', 'static', entry)
            for entry in listdir(webdir)]
tmpldir = path.join(srcdir, 'marche', 'iface', 'web', 'templates')
templates = [path.join('iface', 'web', 'templates', entry)
             for entry in listdir(tmpldir)]

configs = glob.glob(path.join(srcdir, 'etc', '*.conf'))
configs += glob.glob(path.join(srcdir, 'etc', 'dist', '*.conf'))
configs.remove(path.join('etc', 'general.conf'))

data_files = [(marche.utils.get_default_cfgdir(), configs)]
if os.name == 'posix':
    data_files.append(('/etc/init.d', ['etc/marched']))
    data_files.append(('/lib/systemd/system', ['etc/marched.service']))

setup(
    name = 'marche',
    version = marche.version.get_version(),
    license = 'GPL',
    author = 'Georg Brandl',
    author_email = 'g.brandl@fz-juelich.de',
    description = 'Server control daemon',
    packages = find_packages(exclude=['test']),
    package_data = {'marche': ['RELEASE-VERSION'] + uis + webstuff + templates},
    data_files = data_files,
    scripts = scripts,
    classifiers = [
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Intended Audience :: Science/Research',
        'Natural Language :: English',
        'License :: OSI Approved :: GPL License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Topic :: Scientific/Engineering',
        'Topic :: Scientific/Engineering :: Human Machine Interfaces',
        'Topic :: Scientific/Engineering :: Physics',
    ],
)
