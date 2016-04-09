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
#   Alexander Lenz <alexander.lenz@frm2.tum.de>
#
# *****************************************************************************

"""Job control dispatcher."""

import uuid

from marche.six import iteritems

from marche.protocol import ServiceListEvent, ControlOutputEvent, \
    ConffileEvent, LogfileEvent, StatusEvent, FoundHostEvent
from marche.jobs import Busy, Fault
from marche.scan import scan_async
from marche.permission import ClientInfo, DISPLAY, CONTROL, ADMIN


def command(silent=False):
    def deco(f):
        def new_f(self, *args):
            if silent:
                self.log.debug('running %s%s' % (f.__name__, args))
            else:
                self.log.info('running %s%s' % (f.__name__, args))
            try:
                return f(self, *args)
            except Busy as err:
                self.log.error('%s%s failed: busy (%s)' %
                               (f.__name__, args, err))
                raise
            except Fault as err:
                self.log.error('%s%s failed: fault (%s)' %
                               (f.__name__, args, err))
                raise
            except Exception:
                self.log.exception('unexpected exception occurred')
                raise
        new_f.__name__ = f.__name__
        new_f.__doc__ = f.__doc__
        new_f.is_command = True
        return new_f
    return deco


class JobHandler(object):

    def __init__(self, config, log):
        self.config = config
        self.log = log
        self.uid = uuid.uuid4().hex
        self.jobs = {}
        self.service2job = {}
        self.interfaces = []
        self.unauth_level = config.unauth_level
        self._add_jobs()

    def add_interface(self, iface):
        self.interfaces.append(iface)

    def _add_jobs(self):
        self.log.info('adding jobs...')
        for (name, config) in iteritems(self.config.job_config):
            if 'type' not in config:
                self.log.warning('job %r has no type assigned, '
                                 'ignoring' % name)
                continue
            jobtype = config['type']
            try:
                mod = __import__('marche.jobs.%s' % jobtype, {}, {}, 'Job')
            except Exception as err:
                self.log.exception('could not import module %r for job %s: %s'
                                   % (jobtype, name, err))
                continue
            try:
                job = mod.Job(jobtype, name, config, self.log, self.emit_event)
                if not job.check():
                    job.log.error('feasibility check failed')
                    continue
                job.init()
                self.log.info('job %s initialized' % name)
                for service, instance in job.get_services():
                    other = self.service2job.get(service)
                    if other and other is not job:
                        raise RuntimeError('duplicate service %r, '
                                           'provided by jobs %s and %s' %
                                           (service, name, other.name))
                    self.service2job[service] = job
                    self.log.info('found service: %s.%s' % (service, instance))
                self.jobs[name] = job
            except Exception as err:
                self.log.exception('could not initialize job %s: %s' %
                                   (name, err))

    def _get_job(self, service):
        """Return the job the service belongs to."""
        try:
            return self.service2job[service]
        except KeyError:
            raise Fault('no such service: %s' % service)

    def emit_event(self, event):
        """Emit an event to all connected clients."""
        for iface in self.interfaces:
            iface.emit_event(event)

    @command()
    def trigger_reload(self):
        """Trigger a reload of the jobs and list of their services."""
        for job in list(self.jobs.values()):
            job.shutdown()
        self.config.reload()
        self.jobs = {}
        self.service2job = {}
        self._add_jobs()
        # This will contain all services.  It's up to the interface to filter
        # the list when distributing to individual connected clients.
        self.emit_event(self.request_service_list(ClientInfo(ADMIN)))

    @command(silent=True)
    def scan_network(self):
        """Scan the current network for daemons using UDP broadcast."""
        def callback(host, version):
            self.emit_event(FoundHostEvent(host, version))
        scan_async(callback, self.uid)

    @command(silent=True)
    def request_service_list(self, client):
        """Request a list of all services provided by jobs.

        The service list is sent back as a single ServiceListEvent."""
        svcs = {}
        for job in self.jobs.values():
            with job.lock:
                for service, instance in job.get_services():
                    if not job.has_permission(DISPLAY, client):
                        continue
                    if service not in svcs:
                        svcs[service] = {
                            'instances': {},
                            'permissions': job.determine_permissions(client),
                            'jobtype': job.jobtype,
                        }
                    state, ext = job.polled_service_status(service, instance)
                    svcs[service]['instances'][instance] = {
                        'desc': job.service_description(service, instance),
                        'state': state,
                        'ext_status': ext,
                    }
        return ServiceListEvent(services=svcs)

    def filter_services(self, client, event):
        """Filter a service list event to only jobs that the client can see."""
        if client.level == ADMIN:
            return event
        new_svcs = {}
        for service in event.services:
            if self._get_job(service).has_permission(DISPLAY, client):
                new_svcs[service] = event.services[service]
        return ServiceListEvent(services=new_svcs)

    def can_see_status(self, client, event):
        """Check if the client can see this status event."""
        return self._get_job(event.service).has_permission(DISPLAY, client)

    # Not a command, but needed for XMLRPC.
    def get_service_description(self, client, service, instance):
        job = self._get_job(service)
        job.check_permission(DISPLAY, client)
        with job.lock:
            return job.service_description(service, instance)

    @command()
    def start_service(self, client, service, instance):
        """Start a single service."""
        job = self._get_job(service)
        job.check_permission(CONTROL, client)
        with job.lock:
            job.invalidate(service, instance)
            job.start_service(service, instance)
            job.poll_now()

    @command()
    def stop_service(self, client, service, instance):
        """Stop a single service."""
        job = self._get_job(service)
        job.check_permission(CONTROL, client)
        with job.lock:
            job.invalidate(service, instance)
            job.stop_service(service, instance)
            job.poll_now()

    @command()
    def restart_service(self, client, service, instance):
        """Restart a single service."""
        job = self._get_job(service)
        job.check_permission(CONTROL, client)
        with job.lock:
            job.invalidate(service, instance)
            job.restart_service(service, instance)
            job.poll_now()

    @command(silent=True)
    def request_service_status(self, client, service, instance):
        """Return the status of a single service."""
        job = self._get_job(service)
        job.check_permission(DISPLAY, client)
        with job.lock:
            state, ext = job.polled_service_status(service, instance)
        return StatusEvent(service=service, instance=instance,
                           state=state, ext_status=ext)

    @command(silent=True)
    def request_control_output(self, client, service, instance):
        """Return the last lines of output from starting/stopping."""
        job = self._get_job(service)
        job.check_permission(DISPLAY, client)
        with job.lock:
            output = job.service_output(service, instance)
        return ControlOutputEvent(service=service, instance=instance,
                                  content=output)

    @command()
    def request_logfiles(self, client, service, instance):
        """Return the most recent lines of the service's logfile."""
        job = self._get_job(service)
        job.check_permission(DISPLAY, client)
        with job.lock:
            logfiles = job.service_logs(service, instance)
        return LogfileEvent(service=service, instance=instance, files=logfiles)

    @command()
    def request_conffiles(self, client, service, instance):
        """Retrieve the relevant configuration file(s) for this service.

        Returned list: [filename1, contents1, filename2, contents2, ...]
        """
        job = self._get_job(service)
        job.check_permission(ADMIN, client)
        with job.lock:
            confs = job.receive_config(service, instance)
        return ConffileEvent(service=service, instance=instance, files=confs)

    @command()
    def send_conffile(self, client, service, instance, filename, contents):
        """Send back the relevant configuration file(s) for this service
        and install them.  The service might require a restart afterwards.

        The filename must correspond to one that the ReceiveConfig command
        returned.

        The contents are sent as a latin1-decoded string.
        """
        job = self._get_job(service)
        job.check_permission(ADMIN, client)
        with job.lock:
            job.send_config(service, instance, filename, contents)
