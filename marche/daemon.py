#  -*- coding: utf-8 -*-
# *****************************************************************************
# MLZ server control daemon
# Copyright (c) 2015 by the authors, see LICENSE
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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************

import os
import sys
import time
import logging
import optparse
from os import path

# configure logging library: we don't need process/thread ids and callers
logging.logMultiprocessing = False
logging.logProcesses = False
logging.logThreads = False
logging._srcfile = None

log = logging.getLogger('marche')

from marche import __version__
from marche.config import Config
from marche.utils import daemonize, setuser, write_pidfile, remove_pidfile
from marche.loggers import ColoredConsoleHandler, LogfileHandler
from marche.handler import JobHandler


def main():
    inplace = path.exists(path.join(path.dirname(__file__), '..', '.git'))
    inplaceCfg = path.join(path.dirname(__file__), '..', 'devconfig')

    parser = optparse.OptionParser(
        usage='%prog [options]',
        version='Marche daemon version %s' % __version__)
    parser.add_option('-c',
                      dest='configdir',
                      action='store',
                      default=(inplaceCfg if inplace else '/etc/marche'),
                      help='configuration directory (default /etc/marche)')
    parser.add_option('-d', dest='daemonize', action='store_true',
                      help='daemonize the process')
    parser.add_option('-v', dest='verbose', action='store_true',
                      help='verbose (debug) output')
    opts, args = parser.parse_args()

    if args:
        parser.print_usage()
        return 1

    config = Config(opts.configdir)

    if opts.daemonize:
        daemonize(config.user, config.group)
    else:
        setuser(config.user, config.group)

    log.setLevel(logging.DEBUG if opts.verbose else logging.INFO)
    if not opts.daemonize:
        log.addHandler(ColoredConsoleHandler())
    try:
        log.addHandler(LogfileHandler(config.logdir, 'marche'))
    except Exception, e:
        if opts.daemonize:
            print >>sys.stderr, 'cannot open logfile:', e
        else:
            log.exception('cannot open logfile: %s', e)
            if opts.configdir == '/etc/marche' and os.path.isdir('devconfig'):
                log.info('consider using `-c devconfig` from a checkout')
        return 1

    if not config.interfaces:
        log.error('no interfaces configured, the daemon will not do '
                  'anything useful!')
        return 0

    if not config.job_config:
        log.error('no jobs configured, the daemon will not do '
                  'anything useful!')
        return 0

    if opts.daemonize:
        write_pidfile(config.piddir)

    jobhandler = JobHandler(config, log)

    # put tango at the end: its server loop needs to run in the foreground
    if 'tango' in config.interfaces:
        ifaces = [iface for iface in config.interfaces if iface != 'tango']
        ifaces.append('tango')
        config.interfaces = ifaces

    running_interfaces = []

    for interface in config.interfaces:
        try:
            mod = __import__('marche.iface.%s' % interface, {}, {}, ['Interface'])
        except Exception as err:
            log.exception('could not import interface %r: %s', interface, err)
            continue
        log.info('starting interface: %s', interface)
        try:
            mod.Interface(config, jobhandler, log).run()
        except Exception as err:
            log.exception('could not start interface %r: %s', interface, err)
            continue
        running_interfaces.append(interface)

    if 'tango' not in running_interfaces:
        log.info('startup successful')
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    if opts.daemonize:
        remove_pidfile(config.piddir)
    return 0
