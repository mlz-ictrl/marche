#  -*- coding: utf-8 -*-
# *****************************************************************************
# Marche - A server control daemon
# Copyright (c) 2015-2022 by the authors, see LICENSE
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

from marche.gui.buttons import JobButtons, MultiJobButtons
from marche.gui.qt import QBrush, QColor, QHeaderView, QIcon, QMessageBox, \
    QSize, Qt, QTreeWidget, QTreeWidgetItem
from marche.jobs import DEAD, INITIALIZING, NOT_AVAILABLE, NOT_RUNNING, \
    RUNNING, STARTING, STATE_STR, STOPPING, WARNING

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

        # cache the used brush objects
        self._brushes = {'': QBrush(), '#ffcccc': QBrush(QColor('#ffcccc')),
                         'gray': QBrush(QColor('gray'))}
        for (fgcolor, bgcolor) in STATE_COLORS.values():
            if fgcolor not in self._brushes:
                self._brushes[fgcolor] = QBrush(QColor(fgcolor))
            if bgcolor not in self._brushes:
                self._brushes[bgcolor] = QBrush(QColor(bgcolor))

        hdr = self.header()
        hdr.setMinimumSectionSize(125)
        if hasattr(hdr, 'setResizeMode'):  # Qt4
            hdr.setResizeMode(QHeaderView.ResizeToContents)
        else:
            hdr.setSectionResizeMode(QHeaderView.ResizeToContents)

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
            QMessageBox.warning(self, 'Error retrieving data', str(err))

        self.expandAll()
        width = sum(self.header().sectionSize(i)
                    for i in range(self.columnCount()))
        width = max(width, self.header().minimumSectionSize()
                    * self.columnCount())

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

        for service, instances in services.items():
            serviceItem = QTreeWidgetItem([service])
            serviceItem.setForeground(1, self._brushes['white'])
            serviceItem.setTextAlignment(1, Qt.AlignCenter)
            serviceItem.setFlags(Qt.ItemIsEnabled)
            serviceItem.setForeground(3, self._brushes['red'])
            self.addTopLevelItem(serviceItem)

            btns = []
            has_empty_instance = None
            for instance in instances:
                if not instance:
                    has_empty_instance = True
                    continue
                instanceItem = QTreeWidgetItem([instance])
                instanceItem.setForeground(1, self._brushes['white'])
                instanceItem.setTextAlignment(1, Qt.AlignCenter)
                instanceItem.setFlags(Qt.ItemIsEnabled)
                instanceItem.setForeground(3, self._brushes['red'])
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

        self._client.startPoller(self.updateStatus, self.updateBulkStatus)
        self.expandAll()

    def updateBulkStatus(self, data):
        model = self.model()
        # block dataChanged signals while updating items; this avoids
        # potentially hundreds of emitted signals and treeview updates
        model.blockSignals(True)
        try:
            if data is None:
                return self.updateStatus(None, None, NOT_AVAILABLE, '')
            for service, svcinfo in data.items():
                for instance, instinfo in svcinfo['instances'].items():
                    self.updateStatus(service, instance, instinfo['state'],
                                      instinfo['ext_status'], parent=False)
            for service in self._virt_items:
                self.updateParentItem(self._virt_items[service])
        finally:
            model.blockSignals(False)
        # finally, emit a signal that *all* data may have changed
        model.dataChanged.emit(model.index(0, 0),
                               model.index(model.rowCount(), 4))

    def updateStatus(self, service, instance, status, info, parent=True):
        if service is instance is None:
            for (svc, inst) in self._items:
                self.updateStatus(svc, inst, status, info)
            return
        if (service, instance) not in self._items:
            return
        item = self._items[service, instance]

        colors = STATE_COLORS.get(status, ('gray', ''))
        item.setForeground(1, self._brushes[colors[0]])
        item.setBackground(1, self._brushes[colors[1]])
        item.setText(1, STATE_STR[status])
        item.setData(1, 32, status)
        if info is not None:
            item.setText(3, info)

        if status in [STARTING, INITIALIZING, STOPPING]:
            item.setIcon(1, QIcon(':/marche/ui-progress-bar.png'))
        else:
            item.setIcon(1, QIcon())

        if parent and service in self._virt_items:
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
            item.setForeground(1, self._brushes['black'])
            item.setBackground(1, self._brushes[''])
        elif len(statuses) == 1:
            status, _ = statuses.popitem()
            colors = STATE_COLORS.get(status, ('gray', ''))
            item.setForeground(1, self._brushes[colors[0]])
            item.setBackground(1, self._brushes[colors[1]])
            item.setText(1, 'ALL %d %s' % (total, STATE_STR[status]))
        else:
            item.setText(1, '%d/%d RUNNING' %
                         (statuses.get(RUNNING, 0), total))
            item.setForeground(1, self._brushes['black'])
            item.setBackground(1, self._brushes['#ffcccc'])

    def reloadJobs(self):
        self._client.reloadJobs()
        self.fill()

    def on_itemClicked(self, item, index):
        # when clicking on the error column, show the whole error in a dialog
        if index == 3:
            if item.text(3):
                QMessageBox.warning(self, 'Error view', item.text(3))
