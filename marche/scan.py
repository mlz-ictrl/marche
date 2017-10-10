#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
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
#
# *****************************************************************************

"""Utils for scanning for Marche daemons within the network."""

import socket
import select
import threading
from time import time as currenttime

import netifaces

from marche.iface.udp import UDP_PORT


def scan(my_uid, max_wait=1.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    # send a general broadcast
    s.sendto(b'PING', ('255.255.255.255', UDP_PORT))
    # also send to all interfaces' broadcast addresses
    for iface in netifaces.interfaces():
        addrs = netifaces.ifaddresses(iface)
        if netifaces.AF_INET in addrs and addrs[netifaces.AF_INET]:
            addr = addrs[netifaces.AF_INET][0]
            if 'broadcast' in addr:
                s.sendto(b'PING', (addr['broadcast'], UDP_PORT))
    start = currenttime()
    seen = set()
    while currenttime() < start + max_wait:
        res = select.select([s], [], [], 0.1)
        if res[0]:
            try:
                msg, addr = s.recvfrom(1024)
            except socket.error:  # pragma: no cover
                continue
            msg = msg.decode().split()
            if msg[0] != 'PONG':
                continue
            if len(msg) < 2:
                msg.append(1)
            if len(msg) < 3:
                msg.append('')
            try:
                version = int(msg[1])
                uid = msg[2]
            except Exception:
                continue
            if uid == my_uid:
                continue
            try:
                addr = socket.gethostbyaddr(addr[0])[0]
            except socket.error:  # pragma: no cover
                addr = addr[0]
            if addr in seen:
                continue
            seen.add(addr)
            yield addr, version


def scan_async(callback, my_uid, max_wait=1.0):
    def thread():
        for host, version in scan(my_uid, max_wait):
            callback(host, version)
    thd = threading.Thread(target=thread)
    thd.setDaemon(True)
    thd.start()
