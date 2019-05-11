#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2018 by the authors, see LICENSE
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

"""Polling loop for jobs."""

import time
import threading

from six.moves import queue

from marche.protocol import StatusEvent


class Poller(object):
    """The poller object; each job instantiates a poller and can start it."""

    def __init__(self, job, interval, event_callback):
        self.job = job
        self.interval = interval
        self.queue = queue.Queue()
        self.event_callback = event_callback
        self._thread = None
        self._stoprequest = False
        self._cache = {}

    def start(self):
        self._stoprequest = False
        self._thread = threading.Thread(target=self._entry)
        self._thread.setDaemon(True)
        self._thread.start()

    def stop(self):
        if self._thread and self._thread.isAlive():
            self._stoprequest = True
            self.queue.put(None)
            self._thread.join()

    def get(self, service, instance):
        cached = self._cache.get((service, instance), [0, None])
        if time.time() > cached[0] + 1.5 * self.interval:
            return None
        return cached[1]

    def invalidate(self, service, instance):
        self._cache.pop((service, instance), None)

    def _entry(self):
        errors = 0
        while not self._stoprequest:
            try:
                # Wait interval or until something arrives in the queue.
                # XXX: diff to next interval instead
                req = self.queue.get(True, self.interval)
                if req is None:
                    continue
            except queue.Empty:
                pass
            try:
                with self.job.lock:
                    states = self.job.all_service_status()
            except Exception:
                if errors < 3:
                    self.job.log.exception('error while polling')
                errors += 1
                continue
            errors = 0
            for key, result in states.items():
                if result != self._cache.get(key, [0, None])[1]:
                    self._cache[key] = [time.time(), result]
                    self.event_callback(StatusEvent(
                        service=key[0],
                        instance=key[1],
                        state=result[0],
                        ext_status=result[1],
                    ))
                else:
                    self._cache[key][0] = time.time()
