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
#
# *****************************************************************************

"""Console client."""

import os
import time
import xmlrpc.client

import click

from marche.client import Client, ClientError
from marche.jobs import DEAD, INITIALIZING, NOT_AVAILABLE, NOT_RUNNING, \
    RUNNING, STARTING, STOPPING, WARNING


def try_connect(host, port, user, passwd):
    try:
        client = Client(host, port, user, passwd)
    except ClientError as e:
        if e.code != 401:
            raise
        return
    except xmlrpc.client.ProtocolError as e:
        if e.errcode != 401:
            raise
        return
    return client


def negotiate(host, port, user):
    if not user:
        client = try_connect(host, port, None, None)
        if client:
            return client

    if not user or user == 'marche':
        client = try_connect(host, port, 'marche', 'marche')
        if client:
            return client

    if not user:
        raise RuntimeError('anonymous login failed, need to provide username')

    passwd = click.prompt('Password', hide_input=True)
    client = try_connect(host, port, user, passwd)
    if client:
        return client

    raise RuntimeError('valid login credentials needed')


@click.group(invoke_without_command=True,
             help='Interact with a Marche daemon at HOST (can also be '
             'specified as USER@HOST).')
@click.argument('host')
@click.option('--port', default=8124, help='Specify nonstandard port number.')
@click.option('--user', default='', help='Specify user name for login.')
@click.pass_context
def marchec(ctx, host, port, user):
    if '@' in host:
        host_user, host = host.split('@', 1)
        if user and user != host_user:
            raise RuntimeError('two conflicting user names given')
        user = host_user

    ctx.ensure_object(dict)
    ctx.obj['client'] = negotiate(host, port, user)

    if ctx.invoked_subcommand is None:
        cl = ctx.obj['client']
        all_status(cl)


@marchec.command(help='Check the status of a service.')
@click.argument('service', required=False)
@click.pass_context
def status(ctx, service):
    cl = ctx.obj['client']
    if not service:
        all_status(cl)
    else:
        single_status(cl, service)


@marchec.command(help='Start a service.')
@click.argument('service')
@click.pass_context
def start(ctx, service):
    cl = ctx.obj['client']
    cl.startService(service)
    wait_status(cl, service)


@marchec.command(help='Stop a service.')
@click.argument('service')
@click.pass_context
def stop(ctx, service):
    cl = ctx.obj['client']
    cl.stopService(service)
    wait_status(cl, service)


@marchec.command(help='Restart a service.')
@click.argument('service')
@click.pass_context
def restart(ctx, service):
    cl = ctx.obj['client']
    cl.restartService(service)
    wait_status(cl, service)


@marchec.command(help='Show output of the last service start/stop request.')
@click.argument('service')
@click.pass_context
def output(ctx, service):
    cl = ctx.obj['client']
    out = cl.getServiceOutput(service)
    click.echo(out)


@marchec.command(help='Show the most recent logs produced by a service.')
@click.argument('service')
@click.pass_context
def logs(ctx, service):
    cl = ctx.obj['client']
    logs = cl.getServiceLogs(service)
    for entry in logs:
        click.echo(entry.rstrip())


@marchec.command(help='Reload the job configuration of the Marche daemon.')
@click.pass_context
def reload(ctx):
    cl = ctx.obj['client']
    cl.reloadJobs()
    click.echo('reload done, services now:')
    all_status(cl)


@marchec.command(help='Change the configuration of a service.')
@click.argument('service')
@click.pass_context
def edit(ctx, service):
    cl = ctx.obj['client']
    cfg = cl.receiveServiceConfig(service)
    if not cfg:
        click.echo('No config files found.')
        return
    if len(cfg) % 2 != 0:
        click.echo('Unexpected value returned from server.')
        return

    result = []
    for i in range(0, len(cfg), 2):
        fname, content = (cfg[i], cfg[i + 1])
        _, extension = os.path.splitext(fname)
        if not extension:
            extension = '.txt'  # fall back to txt
        new_cfg = click.edit(content, extension=extension)
        if new_cfg is None:
            click.echo(f'{fname} not modified.')
            continue
        if click.confirm('Use the new config file?'):
            result.append(fname)
            result.append(new_cfg)
    if not result:
        return
    cl.sendServiceConfig(service, data=result)
    n = len(result) // 2
    click.echo(f'Sent {n} new config file{"s" if n > 1 else ""}.')


def all_status(cl):
    svc = cl.getAllServiceInfo()
    for (name, data) in svc.items():
        for (inst, instdata) in data['instances'].items():
            full = f'{name}.{inst}' if inst else name
            single_status(cl, full, instdata['state'])


def single_status(cl, service, sts=None):
    if sts is None:
        sts = cl.getServiceStatus(service)
    click.echo(f'{service:<25} ', nl=False)
    text, color = {
        DEAD: ('dead', 'red'),
        NOT_RUNNING: ('not running', 'red'),
        STARTING: ('starting', 'yellow'),
        INITIALIZING: ('initializing', 'yellow'),
        RUNNING: ('running', 'green'),
        WARNING: ('warning', 'magenta'),
        STOPPING: ('stopping', 'yellow'),
        NOT_AVAILABLE: ('not available', 'white'),
    }.get(sts, ('???', 'white'))
    click.secho(text, fg=color)
    return sts


def wait_status(cl, service):
    for i in range(10):
        sts = single_status(cl, service)
        if sts not in (STARTING, INITIALIZING, STOPPING):
            return
        time.sleep(0.5)


def run():
    try:
        marchec()
    except Exception as err:
        click.secho(f'*** Error: {err}', fg='red', err=True)
