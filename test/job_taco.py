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

"""Test for the TACO job."""

import logging
import sys

from marche.jobs import RUNNING
from marche.jobs.taco import Job
from test.utils import job_call_check

logger = logging.getLogger('testtaco')

SCRIPT = '''\
import sys
print(sys.argv[2])
print(sys.argv[1])
'''

TACO_LOG_CFG = '''
#
# mysrv/inst
#
log4j.category.taco.server.mysrvserver.inst=WARN, mysrvserver_inst

log4j.appender.mysrvserver_inst=org.apache.log4j.RollingFileAppender
log4j.appender.mysrvserver_inst.layout=org.apache.log4j.PatternLayout
log4j.appender.mysrvserver_inst.layout.ConversionPattern=%d %c %-6p : %m%n
log4j.appender.mysrvserver_inst.fileName={tmpdir}/log/mysrvserver_inst.log
log4j.appender.mysrvserver_inst.maxFileSize=100000
log4j.appender.mysrvserver_inst.maxBackupIndex=10
log4j.appender.mysrvserver_inst.append=true

# ignored
log4j.category.taco.server.otherserver=WARN, mysrvserver_inst
log4j.appender.other.fileName=true
'''

DB_DEVLIST = '''\
print('\\tstrange/dev/1')
print('mysrvserver/inst :')
print('\\tmy/dev/1')
print('\\tmy/dev/2')
print('')
print('otherserver/other :')
print('\\tother/dev/1')
'''

DB_DEVRES = '''\
import sys
if sys.argv[1] == 'my/dev/1':
    print('my/dev/1/name: 1')
    print('my/dev/1/iodev: my/dev/2')
    print('')
else:
    print('my/dev/2/name: 2')
'''


def test_job(tmpdir):
    tmpdir.join('taco-server-mysrv').write(SCRIPT)
    tmpdir.join('db_devlist').write(DB_DEVLIST)
    tmpdir.join('db_devres').write(DB_DEVRES)
    tmpdir.join('taco_log.cfg').write(TACO_LOG_CFG.format(tmpdir=tmpdir))
    tmpdir.mkdir('log').join('mysrvserver_inst.log').write('log1\nlog2\n')

    Job.INIT_DIR = 'does/not/exist'
    config = {'envfile': '/does/not/exist', 'logconffile': '/does/not/exist'}
    job = Job('taco', 'name', config, logger, lambda event: None)
    assert not job.check()

    Job.INIT_DIR = str(tmpdir)
    Job.LOG_CONF_FILE = str(tmpdir.join('taco_log.cfg'))
    Job.DB_DEVLIST = '%s -S %s' % (sys.executable, tmpdir.join('db_devlist'))
    Job.DB_DEVRES = '%s -S %s' % (sys.executable, tmpdir.join('db_devres'))

    job = Job('taco', 'name', {}, logger, lambda event: None)
    assert job.check()
    job.init()
    job._initscripts['taco-mysrv'] = '%s -S %s' % \
        (sys.executable, job._initscripts['taco-mysrv'])

    assert job.get_services() == [('taco-mysrv', 'inst')]
    assert job.service_status('taco-mysrv', 'inst') == (RUNNING, '')

    job_call_check(job, 'taco-mysrv', 'inst',
                   'action inst', ['inst', 'action'])

    logs = job.service_logs('taco-mysrv', 'inst')
    assert len(logs) == 1
    for key, value in logs.items():
        if key.endswith('mysrvserver_inst.log'):
            assert value == 'log1\nlog2\n'
        else:
            assert False, 'unknown logfile returned'

    Job.LOG_CONF_FILE = 'does/not/exist'
    job.init()
    assert job.service_logs('taco-mysrv', 'inst') == {}
