#  -*- coding: utf-8 -*-
# *****************************************************************************
# MLZ server control daemon
# Copyright (c) 2015-2016 by the authors, see LICENSE
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

"""Utilities for the package."""

from __future__ import print_function

import os
import re
import sys
import socket
import select
import collections
from os import path
from threading import Thread
from subprocess import Popen, PIPE

try:
    import pwd
    import grp
except ImportError:
    pwd = grp = None


def ensure_directory(dirname):
    """Make sure a directory exists."""
    if not path.isdir(dirname):
        os.makedirs(dirname)


def daemonize(user, group):
    """Daemonize the current process."""
    # finish up with the current stdout/stderr
    sys.stdout.flush()
    sys.stderr.flush()

    # do first fork
    try:
        pid = os.fork()
        if pid > 0:
            sys.stdout.close()
            sys.exit(0)
    except OSError as err:
        print('fork #1 failed:', err, file=sys.stderr)
        sys.exit(1)

    # decouple from parent environment
    # os.chdir('/')  <- doesn't work :(
    os.umask(0o002)
    os.setsid()

    # do second fork
    try:
        pid = os.fork()
        if pid > 0:
            sys.stdout.close()
            sys.exit(0)
    except OSError as err:
        print('fork #2 failed:', err, file=sys.stderr)

    # now I am a daemon!

    # switch user
    setuser(user, group, recover=False)

    # close standard fds, so that child processes don't inherit them even
    # though we override Python-level stdio
    os.close(0)
    os.close(1)
    os.close(2)

    # redirect standard file descriptors
    sys.stdin = open('/dev/null', 'rb')
    sys.stdout = sys.stderr = open('/dev/null', 'wb')


def setuser(user, group, recover=True):
    """Do not daemonize, but at least set the current user and group correctly
    to the configured values if started as root.
    """
    if not hasattr(os, 'geteuid') or os.geteuid() != 0:
        return
    # switch user
    if group:
        gid = grp.getgrnam(group).gr_gid
        if recover:
            os.setegid(gid)
        else:
            os.setgid(gid)
    if user:
        uid = pwd.getpwnam(user).pw_uid
        if recover:
            os.seteuid(uid)
        else:
            os.setuid(uid)
        if 'HOME' in os.environ:
            os.environ['HOME'] = pwd.getpwuid(uid).pw_dir


def write_pidfile(pid_dir):
    """Write a file with the PID of the current process."""
    ensure_directory(pid_dir)
    with open(path.join(pid_dir, 'marched.pid'), 'w') as fp:
        fp.write(str(os.getpid()))


def remove_pidfile(pid_dir):
    """Remove a file with the PID of the current process."""
    os.unlink(path.join(pid_dir, 'marched.pid'))


class lazy_property(object):
    """A property that calculates its value only once."""
    def __init__(self, func):
        self._func = func
        self.__name__ = func.__name__
        self.__doc__ = func.__doc__

    def __get__(self, obj, obj_class):
        if obj is None:
            return obj
        obj.__dict__[self.__name__] = self._func(obj)
        return obj.__dict__[self.__name__]


class AsyncProcess(Thread):
    def __init__(self, status, log, cmd, sh=True, stdout=None, stderr=None):
        Thread.__init__(self)
        self.setDaemon(True)

        self.status = status
        self.log = log
        self.cmd = cmd
        self.use_sh = sh

        self.done = False
        self.retcode = None
        self.stdout = stdout if stdout is not None else []
        self.stderr = stderr if stderr is not None else []

    def run(self):
        self.log.debug('call [sh:%s]: %s' % (self.use_sh, self.cmd))
        proc = None
        poller = None

        def pollOutput():
            """
            Read, log and store output (if any) from processes pipes.
            """
            # collect fds with new output
            fds = [entry[0] for entry in poller.poll()]

            if proc.stdout.fileno() in fds:
                for line in iter(proc.stdout.readline, b''):
                    line = line.decode('utf-8', 'replace').strip('\r\n')
                    self.log.debug(line)
                    self.stdout.append(line)
            if proc.stderr.fileno() in fds:
                for line in iter(proc.stderr.readline, b''):
                    line = line.decode('utf-8', 'replace').strip('\r\n')
                    self.log.warning(line)
                    self.stderr.append(line)

        while True:
            if proc is None:
                # create and start process
                proc = Popen(self.cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                             shell=self.use_sh)

                # create poll select
                poller = select.poll()

                # register pipes to polling
                poller.register(proc.stdout, select.POLLIN)
                poller.register(proc.stderr, select.POLLIN)

            pollOutput()

            if proc.poll() is not None:  # proc finished
                break

        # poll once after the process ended to collect all the missing output
        pollOutput()

        # check return code
        self.retcode = proc.returncode
        self.done = True


nontext_re = re.compile('[^\n\t\x20-\x7e]')


def extractLoglines(filename, n=50):
    def extract(filename):
        shortfn = path.basename(filename)
        lines = collections.deque(maxlen=n)
        with open(filename, 'rb') as fp:
            for line in fp:
                line = line.decode('utf-8', 'replace')
                lines.append(shortfn + ':' + nontext_re.sub('', line))
        return list(lines)
    if not path.exists(filename):
        return []
    filename = path.realpath(filename)
    result = extract(filename)
    # also add rotated logs
    i = 1
    while path.exists(filename + '.%d' % i):
        result.extend(extract(filename + '.%d' % i))
        i += 1
    return result


def normalizeAddr(addr, defport):
    if ':' not in addr:
        addr += ':' + str(defport)
    host, port = addr.split(':')
    try:
        host = socket.getfqdn(host)
    except socket.error:
        pass
    return host, port


def readFile(fname):
    """Read file as latin-1 str."""
    with open(fname, 'rb') as fp:
        contents = fp.read()
    if not isinstance(contents, str):
        return contents.decode('latin1')
    return contents


def writeFile(fname, contents):
    """Write file from latin-1 string."""
    if not isinstance(contents, bytes):
        contents = contents.encode('latin1')
    with open(fname, 'wb') as fp:
        fp.write(contents)
