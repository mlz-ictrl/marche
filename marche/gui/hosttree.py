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


from PyQt4.QtGui import QColor, QTreeWidget, QTreeWidgetItem, QBrush,\
    QMessageBox, QIcon, QHeaderView
from PyQt4.QtCore import Qt, QSize

from marche.six import iteritems
from marche.six.moves import range  # pylint: disable=redefined-builtin

from marche.gui.buttons import JobButtons, MultiJobButtons
from marche.jobs import STATE_STR, RUNNING, NOT_RUNNING, WARNING, DEAD, \
    STARTING, STOPPING, INITIALIZING


STATE_COLORS = {
    RUNNING: ('green', ''),
    NOT_RUNNING: ('black', ''),
    DEAD: ('white', 'red'),
    WARNING: ('black', 'yellow'),
    STARTING: ('blue', ''),
    STOPPING: ('blue', ''),
    INITIALIZING: ('blue', ''),
}


class HostTree(QTreeWidget):

    def __init__(self, parent, client):
        QTreeWidget.__init__(self, parent)
        self._client = client

        self.header().setMinimumSectionSize(125)
        self.header().setResizeMode(QHeaderView.ResizeToContents)

        self.setColumnCount(4)
        self.headerItem().setText(0, 'Service')
        self.headerItem().setText(1, 'Status')
        self.headerItem().setText(2, 'Control')
        self.headerItem().setText(3, 'Last error')
        self._items = {}
        self._virt_items = {}
        try:
            self.fill()
        except Exception as err:
            print(err)

        self.expandAll()
        width = sum(self.header().sectionSize(i)
                    for i in range(self.columnCount()))
        width = max(width, self.header().minimumSectionSize()
                    * self.columnCount())
        print(width)
        self.setMinimumWidth(width+50)
        self.itemClicked.connect(self.on_itemClicked)

    def refresh(self):
        self.clear()
        self.fill()

    def clear(self):
        self._client.stopPoller()
        self._items.clear()
        QTreeWidget.clear(self)

    def fill(self):
        self.clear()
        services = self._client.getServices()
        try:
            descrs = self._client.getServiceDescriptions(services)
        except Exception:
            descrs = {}
        self._client.startPoller(self.updateStatus)

        for service, instances in iteritems(services):
            serviceItem = QTreeWidgetItem([service])
            serviceItem.setForeground(1, QBrush(QColor('white')))
            serviceItem.setTextAlignment(1, Qt.AlignCenter)
            serviceItem.setFlags(Qt.ItemIsEnabled)
            serviceItem.setForeground(3, QBrush(QColor('red')))
            self.addTopLevelItem(serviceItem)

            btns = []
            has_empty_instance = None
            for instance in instances:
                if not instance:
                    has_empty_instance = True
                    continue
                instanceItem = QTreeWidgetItem([instance])
                instanceItem.setForeground(1, QBrush(QColor('white')))
                instanceItem.setTextAlignment(1, Qt.AlignCenter)
                instanceItem.setFlags(Qt.ItemIsEnabled)
                instanceItem.setForeground(3, QBrush(QColor('red')))
                if descrs.get((service, instance)):
                    instanceItem.setText(0, descrs[service, instance])
                serviceItem.addChild(instanceItem)

                btn = JobButtons(self._client, service, instance,
                                 instanceItem)
                btns.append(btn)
                self.setItemWidget(instanceItem, 2, btn)
                self._items[service, instance] = instanceItem
            if has_empty_instance:
                btn = JobButtons(self._client, service, '',
                                 serviceItem)
                btn.setMinimumSize(QSize(30, 40))
                self.setItemWidget(serviceItem, 2, btn)
                if descrs.get((service, '')):
                    serviceItem.setText(0, descrs[service, ''])
                self._items[service, ''] = serviceItem
            else:
                # create "virtual" job with buttons that start/stop all
                # instances of the service
                self._virt_items[service] = serviceItem
                multibtn = MultiJobButtons(btns)
                self.setItemWidget(serviceItem, 2, multibtn)

        self.expandAll()

    def updateStatus(self, service, instance, status, info):
        if service is instance is None:
            for (service, instance) in self._items:
                self.updateStatus(service, instance, status, info)
            return
        if (service, instance) not in self._items:
            return
        item = self._items[service, instance]

        colors = STATE_COLORS.get(status, ('gray', ''))
        item.setForeground(1, QBrush(QColor(colors[0]))
                           if colors[0] else QBrush())
        item.setBackground(1, QBrush(QColor(colors[1]))
                           if colors[1] else QBrush())
        item.setText(1, STATE_STR[status])
        item.setData(1, 32, status)
        if info is not None:
            item.setText(3, info)

        if status in [STARTING, INITIALIZING, STOPPING]:
            item.setIcon(1, QIcon(':/marche/ui-progress-bar.png'))
        else:
            item.setIcon(1, QIcon())

        if service in self._virt_items:
            self.updateParentItem(self._virt_items[service])

    def updateParentItem(self, item):
        statuses = {}
        total = item.childCount()
        for i in range(total):
            chst = item.child(i).data(1, 32)
            count = statuses.setdefault(chst, 0)
            statuses[chst] = count + 1
        if not statuses:
            return
        if None in statuses:
            item.setText(1, '')
            item.setForeground(1, QBrush(QColor('black')))
            item.setBackground(1, QBrush())
        elif len(statuses) == 1:
            status, _ = statuses.popitem()
            colors = STATE_COLORS.get(status, ('gray', ''))
            item.setForeground(1, QBrush(QColor(colors[0]))
                               if colors[0] else QBrush())
            item.setBackground(1, QBrush(QColor(colors[1]))
                               if colors[1] else QBrush())
            item.setText(1, 'ALL %d %s' % (total, STATE_STR[status]))
        else:
            item.setText(1, '%d/%d RUNNING' %
                         (statuses.get(RUNNING, 0), total))
            item.setForeground(1, QBrush(QColor('black')))
            item.setBackground(1, QBrush(QColor('#ffcccc')))

    def reloadJobs(self):
        self._client.reloadJobs()
        self.fill()

    def on_itemClicked(self, item, index):
        # when clicking on the error column, show the whole error in a dialog
        if index == 3:
            if item.text(3):
                QMessageBox.warning(self, 'Error view', item.text(3))
