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
#   Georg Brandl <g.brandl@fz-juelich.de>
#
# *****************************************************************************

""" .. index:: web; interface

Webinterface
------------

This interface allows controlling services via a graphical interface.

.. describe:: [interface.web]

   The configuration settings that can be set within the **interfaces.web**
   section are:

   .. describe:: addr

      **Default:** ``"0.0.0.0:8080"``

      The local address and port to listen on for web requests.
"""

import asyncio
import json
import pickle
import random
import socket
import threading
from pathlib import Path

from aiohttp import web
from aiohttp_session import get_session, setup as session_setup
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from jinja2 import Environment, FileSystemLoader

from marche import __version__
from marche.auth import AuthFailed
from marche.iface.base import Interface as BaseInterface
from marche.jobs import STATE_STR
from marche.permission import DISPLAY, ClientInfo

ENV = Environment(loader=FileSystemLoader(Path(__file__).parent / 'templates'))
STATIC = Path(__file__).parent / 'static'


def split_service_instance(service_instance):
    if '_' in service_instance:
        return service_instance.split('_', 1)
    return service_instance, ''


class WebHandler:
    def __init__(self, jobhandler, authhandler, log):
        self.jobhandler = jobhandler
        self.log = log
        self.auth = authhandler

    async def _get_login(self, req, key):
        session = await get_session(req)
        if 'logged_in' not in session:
            session['logged_in'] = False
            session['client_info'] = ClientInfo(DISPLAY)
        return session[key]

    async def _set_login(self, req, logged_in, client_info):
        session = await get_session(req)
        session['logged_in'] = logged_in
        session['client_info'] = client_info

    async def _update_status(self, req):
        result = {}
        for service, info in self.jobhandler.request_service_list(
                await self._get_login(req, 'client_info')).services.items():
            for instance in info['instances']:
                if not instance:
                    result[service] = \
                        STATE_STR[info['instances'][instance]['state']]
                else:
                    result[service + '_' + instance] = \
                        STATE_STR[info['instances'][instance]['state']]
        return result

    async def index(self, req):
        tmpl = ENV.get_template('index.html')
        body = tmpl.render(number=__version__,
                           svc_sts=await self._update_status(req),
                           logged_in=await self._get_login(req, 'logged_in'))
        return web.Response(body=body, content_type='text/html')

    async def control(self, req):
        args = await req.post()
        if 'start' in args:
            self.jobhandler.start_service(
                await self._get_login(req, 'client_info'),
                *split_service_instance(args['start']))
        elif 'stop' in args:
            self.jobhandler.stop_service(
                await self._get_login(req, 'client_info'),
                *split_service_instance(args['stop']))
        elif 'restart' in args:
            self.jobhandler.restart_service(
                await self._get_login(req, 'client_info'),
                *split_service_instance(args['restart']))
        return web.Response()

    async def get_status(self, req):
        return web.Response(body=json.dumps(await self._update_status(req)),
                            content_type='text/json')

    async def get_hostname(self, req):
        return web.Response(body=json.dumps(socket.getfqdn()),
                            content_type='text/json')

    async def help(self, req):
        tmpl = ENV.get_template('help.html')
        body = tmpl.render(version=__version__,
                           logged_in=await self._get_login(req, 'logged_in'))
        return web.Response(body=body, content_type='text/html')

    async def login(self, req):
        args = req.query
        tmpl = ENV.get_template('login.html')
        if 'passwd' in args and 'user' in args:
            try:
                info = self.auth.authenticate(args['user'], args['passwd'])
                await self._set_login(req, True, info)
                raise web.HTTPTemporaryRedirect('/')
            except AuthFailed:
                await self._set_login(req, False, ClientInfo(DISPLAY))
                raise web.HTTPTemporaryRedirect('/login') from None
        body = tmpl.render(logged_in=await self._get_login(req, 'logged_in'))
        return web.Response(body=body, content_type='text/html')

    async def logout(self, req):
        await self._set_login(req, False, ClientInfo(DISPLAY))
        raise web.HTTPTemporaryRedirect('/login')

    async def static(self, req):
        return web.FileResponse(STATIC / req.match_info['file'])


class Interface(BaseInterface):

    iface_name = 'web'
    needs_events = False

    def init(self):
        self._loop = asyncio.get_event_loop()

    def run(self):
        handler = WebHandler(self.jobhandler, self.authhandler, self.log)
        app = web.Application()
        cookies = EncryptedCookieStorage(
            random.randbytes(32),
            encoder=lambda o: pickle.dumps(o).decode('latin1'),
            decoder=lambda s: pickle.loads(s.encode('latin1')))
        session_setup(app, cookies)
        app.router.add_get('/', handler.index)
        app.router.add_get('/index', handler.index)
        app.router.add_post('/control', handler.control)
        app.router.add_get('/get_status', handler.get_status)
        app.router.add_get('/get_hostname', handler.get_hostname)
        app.router.add_get('/help', handler.help)
        app.router.add_get('/login', handler.login)
        app.router.add_get('/logout', handler.logout)
        app.router.add_get('/static/{file:.*}', handler.static)
        threading.Thread(target=self._thread, args=(app,), daemon=True).start()

    def shutdown(self):
        for task in asyncio.all_tasks(self._loop):
            task.cancel()

    def _thread(self, app):
        addr = self.config.get('addr', '0.0.0.0')
        if ':' in addr:
            host, port = addr.rsplit(':', 1)
            port = int(port)
        else:
            host, port = addr, 8080
        try:
            web.run_app(
                app, host=host, port=port, loop=self._loop,
                handle_signals=False, print=self.log.info)
        except asyncio.CancelledError:
            self.log.info('server stopped')
