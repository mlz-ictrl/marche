#  -*- coding: utf-8 -*-
# *****************************************************************************
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
#   Lea Kleesattel <lea.kleesattel@frm2.tum.de>
#
# *****************************************************************************

""" .. index:: web; interface

Webinterface
-----------------------

This interface allows controlling services via a graphical interface.

.. describe:: [interfaces.web]

   The configuration settings that can be set within the **interfaces.web**
   section are:

   .. describe:: port

      **Default:** 8080

      The port to listen for web requests.

   .. describe:: host

      **Default:** 0.0.0.0

      The host to bind to.
"""

from __future__ import print_function

import os
import cherrypy
import json
from cherrypy import log
from jinja2 import Environment, FileSystemLoader
from marche.version import get_version
from marche.iface.base import Interface as BaseInterface
from marche.six import iteritems
from marche.permission import DISPLAY, ClientInfo
from marche.jobs import STATE_STR
from marche.auth import AuthFailed


ENV = Environment(loader=FileSystemLoader(os.path.join(os.path.dirname(
    __file__)) + '/templates'))

CONFIG = {
    '/': {
        'tools.sessions.on': True,
        'tools.staticdir.root': os.path.abspath(os.path.dirname(__file__)),
    },
    '/static': {
        'tools.staticdir.on': True,
        'tools.staticdir.dir': 'static'
    },
    '/favicon.ico': {
        'tools.staticdir.on': True,
        'tools.staticdir.dir': '../../gui/res'
    }
}


class Webinterface(object):
    def __init__(self, jobhandler, authhandler, log):
        self.jobhandler = jobhandler
        self.log = log
        self.auth = authhandler
        self.service_status = {}

    def get_login(self, key):
        if 'logged_in' not in cherrypy.session:
            cherrypy.session['logged_in'] = 'false'
            cherrypy.session['client_info'] = ClientInfo(DISPLAY)
        return cherrypy.session[key]

    def set_login(self, logged_in, client_info):
        cherrypy.session['logged_in'] = logged_in
        cherrypy.session['client_info'] = client_info

    def service_instance_status(self):
        for service, info in iteritems(self.jobhandler.request_service_list(
                self.get_login('client_info')).services):
            for instance in info['instances']:
                if not instance:
                    self.service_status[service] = \
                        STATE_STR[info['instances'][instance]['state']]
                else:
                    self.service_status[service + '_' + instance] = \
                        STATE_STR[info['instances'][instance]['state']]

    def split_service_instance(self, service_instance):
        if '_' in service_instance:
            return service_instance.split('_', 1)
        else:
            return service_instance, ''

    def check_buttons(self, buttons):
        if 'startButton' in buttons:
            self.jobhandler.start_service(self.get_login('client_info'),
                                          *self.split_service_instance(
                                              buttons['startButton']))
        elif 'stopButton' in buttons:
            self.jobhandler.stop_service(self.get_login('client_info'),
                                         *self.split_service_instance(
                                             buttons['stopButton']))
        elif 'restartButton' in buttons:
            self.jobhandler.restart_service(self.get_login('client_info'),
                                            *self.split_service_instance(
                                                buttons['restartButton']))

    @cherrypy.expose
    def button_action(self, **kwargs):
        self.check_buttons(kwargs)

    @cherrypy.expose
    def get_status(self):
        self.service_instance_status()
        return json.dumps(self.service_status)

    @cherrypy.expose
    def get_hostname(self):
        return json.dumps(cherrypy.server.socket_host)

    @cherrypy.expose
    def index(self):
        tmpl = ENV.get_template('index.html')
        self.service_instance_status()
        return tmpl.render(number=get_version(), svc_sts=self.service_status,
                           logged_in=self.get_login('logged_in'))

    @cherrypy.expose
    def login(self, **kwargs):
        tmpl = ENV.get_template('login.html')
        if 'passwd' in kwargs and 'user' in kwargs:
            try:
                self.set_login('true', self.auth.authenticate(kwargs['user'],
                                                              kwargs['passwd']))
                raise cherrypy.HTTPRedirect('index')
            except AuthFailed:
                self.set_login('false', ClientInfo(DISPLAY))
                raise cherrypy.HTTPRedirect('login')
        return tmpl.render(number=get_version(), svc_sts=self.service_status,
                           logged_in=self.get_login('logged_in'))

    @cherrypy.expose
    def logout(self):
        self.set_login('false', ClientInfo(DISPLAY))
        raise cherrypy.HTTPRedirect('login')

    @cherrypy.expose
    def help(self):
        tmpl = ENV.get_template('help.html')
        return tmpl.render(number=get_version(), svc_sts=self.service_status,
                           logged_in=self.get_login('logged_in'))


class Interface(BaseInterface):
    iface_name = 'web'
    needs_events = False
    port = 8080
    host = '0.0.0.0'

    def init(self):
        self._events = []

    def run(self):
        cherrypy.tree.mount(Webinterface(self.jobhandler, self.authhandler,
                                         self.log), config=CONFIG)
        cherrypy.config.update({'server.socket_port': self.port,
                                'server.socket_host': self.host,
                                'log.screen': False,
                                'log.access_file': '',
                                'log.error_file': ''})
        # using marche logger
        log.access_log.addHandler(self.log)
        log.error_log.addHandler(self.log)
        self.log.info('listening on %s:%s' % (cherrypy.server.socket_host,
                                              cherrypy.server.socket_port))
        cherrypy.engine.start()

    def shutdown(self):
        cherrypy.engine.stop()
