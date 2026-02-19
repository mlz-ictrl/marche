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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************

"""Utilities for the package."""

import collections
import json
import os
import re
import select
import socket
import sys
from pathlib import Path
from subprocess import PIPE, CalledProcessError, Popen, check_output
from threading import Thread
from time import localtime, monotonic, strftime


class lazy_property:  # noqa: N801
    """A property that calculates its value only once."""

    def __init__(self, func):
        self._func = func
        self.__name__ = func.__name__
        self.__doc__ = func.__doc__

    def __get__(self, obj, obj_class):
        if obj is None:
            return self
        obj.__dict__[self.__name__] = self._func(obj)
        return obj.__dict__[self.__name__]


if os.name == 'nt':  # pragma: no cover
    class Poller:
        """A poor imitation of polling for Windows."""

        def __init__(self):
            self.fds = []

        def register(self, fp, _opt):
            self.fds.append(fp.fileno())

        def poll(self, _timeout):
            return [(fd, None) for fd in self.fds]
    POLLIN = None

else:
    Poller = select.poll
    POLLIN = select.POLLIN


class AsyncProcess(Thread):
    def __init__(self, status, log, cmd, stdout=None, stderr=None, *, sh=True,
                 timeout=5.0):
        Thread.__init__(self, daemon=True)

        self.status = status
        self.log = log
        self.cmd = cmd
        self.use_sh = sh
        self.timeout = timeout

        self.done = False
        self.retcode = None
        self.stdout = stdout if stdout is not None else []
        self.stderr = stderr if stderr is not None else []

    def run(self):
        self.log.debug('call [sh:%s]: %s', self.use_sh, self.cmd)
        proc = None
        poller = None
        started = monotonic()

        def poll_output():
            """Read, log and store output (if any) from processes pipes."""
            # collect fds with new output
            fds = [entry[0] for entry in poller.poll(1000)]

            if proc.stdout.fileno() in fds:
                for line in iter(proc.stdout.readline, b''):
                    line = line.translate(None, b'\r')
                    line = line.decode('utf-8', 'replace')
                    self.log.debug(line.rstrip())
                    self.stdout.append(line)
            if proc.stderr.fileno() in fds:
                for line in iter(proc.stderr.readline, b''):
                    line = line.translate(None, b'\r')
                    line = line.decode('utf-8', 'replace')
                    self.log.warning(line.rstrip())
                    self.stderr.append(line)

        while True:
            if proc is None:
                # create and start process
                proc = Popen(self.cmd, stdin=PIPE, stdout=PIPE, stderr=PIPE,
                             shell=self.use_sh)

                # create poller
                poller = Poller()

                # register pipes to polling
                poller.register(proc.stdout, POLLIN)
                poller.register(proc.stderr, POLLIN)

            poll_output()

            # proc finished?
            if proc.poll() is not None:
                # poll once after the process ended to collect all the
                # missing output
                poll_output()
                # assign return code
                self.retcode = proc.returncode
                self.log.debug('call retcode: %s', self.retcode)
                break

            # timeout occurred?
            if monotonic() > started + self.timeout:
                try:
                    proc.kill()
                except Exception:
                    pass
                self.log.warning('timeout occurred calling %s', self.cmd)
                self.retcode = -1
                break

        self.done = True


nontext_re = re.compile(r'[^\n\t\x20-\x7e]')


def extract_loglines(fpath, n=500):
    def extract(fpath):
        lines = collections.deque(maxlen=n)
        with fpath.open('rb') as fp:
            try:
                # For very long files, skipping over all unneeded lines can
                # take a while.  Set a limit on average line length instead.
                fp.seek(-1000 * n, 2)
            except OSError:
                pass  # the file is too short
            for line in fp:
                line = line.decode('latin1', 'ignore')
                lines.append(nontext_re.sub('', line))
        return ''.join(lines)
    if not fpath.is_file():
        return {}
    fpath = fpath.resolve()
    result = {str(fpath): extract(fpath)}
    # also add rotated logs
    i = 1
    while True:
        new = fpath.with_name(fpath.name + f'.{i}')
        if not new.is_file():
            break
        result[str(new)] = extract(new)
        i += 1
    return result


SYSLOG_PRIO = {
    '0': 'emerg',
    '1': 'alert',
    '2': 'crit ',
    '3': 'error',
    '4': 'warn ',
    '5': 'note ',
    '6': 'info ',
    '7': 'debug',
}


def convert_journalctl_logs(output):
    for line in output:
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:  # noqa: PERF203
            yield line
        else:
            ts = int(entry.get('_SOURCE_REALTIME_TIMESTAMP',
                               entry['__REALTIME_TIMESTAMP']))
            fmt_time = strftime('%Y-%m-%d %H:%M:%S', localtime(ts / 1e6))
            yield (f'[{entry.get("_PID", "?")}] {fmt_time} '
                   f'{SYSLOG_PRIO.get(entry.get("PRIORITY", ""), "?")}: '
                   f'{entry.get("MESSAGE", "?")}\n')
            if 'TRACEBACK' in entry:
                yield entry['TRACEBACK'] + '\n'


def normalize_addr(addr, defport):
    if ':' not in addr:
        addr += ':' + str(defport)
    host, port = addr.split(':')
    try:
        host = socket.getfqdn(host)
    except OSError:  # pragma: no cover
        pass
    return host, port


def read_file(fpath):
    """Read file as latin-1 str."""
    return fpath.read_text('latin1')


def write_file(fpath, contents):
    """Write file from latin-1 string."""
    if not isinstance(contents, bytes):
        contents = contents.encode('latin1')
    fpath.write_bytes(contents)


def get_default_cfgdir():  # pragma: no cover
    """Return the default config dir for the current platform."""
    if os.name == 'nt':
        return Path(sys.prefix) / 'etc' / 'marche'
    return Path('/etc/marche')


INIT_PKG_REQUESTS = [
    'readlink /sbin/init',
    'dpkg -S /sbin/init',
    'rpm -qf /sbin/init',
]


def determine_init_system():
    init_pkg = b''

    for entry in INIT_PKG_REQUESTS:
        try:
            init_pkg = check_output(entry.split()).lower().strip()
            if init_pkg:
                break
        except (CalledProcessError, OSError):
            pass

    if b'systemd' in init_pkg:
        return 'systemd'
    if b'upstart' in init_pkg:
        return 'upstart'
    if b'sysvinit' in init_pkg:
        return 'sysvinit'

    return 'unknown'


# console color utils

_codes = {}

_attrs = {
    'reset':     '39;49;00m',
    'bold':      '01m',
    'faint':     '02m',
    'standout':  '03m',
    'underline': '04m',
    'blink':     '05m',
}

for _name, _value in _attrs.items():
    _codes[_name] = '\x1b[' + _value

_colors = [
    ('black', 'darkgray'),
    ('darkred', 'red'),
    ('darkgreen', 'green'),
    ('brown', 'yellow'),
    ('darkblue', 'blue'),
    ('purple', 'fuchsia'),
    ('turquoise', 'teal'),
    ('lightgray', 'white'),
]

for _i, (_dark, _light) in enumerate(_colors):
    _codes[_dark] = f'\x1b[{_i + 30}m'
    _codes[_light] = f'\x1b[{_i + 30};01m'


def colorize(name, text):
    return _codes.get(name, '') + text + _codes.get('reset', '')
