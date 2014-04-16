# transaction.py
# Managing the transaction to be passed to RPM.
#
# Copyright (C) 2013  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from __future__ import absolute_import
from __future__ import unicode_literals
from dnf.i18n import _
import logging
import operator
from functools import reduce

DOWNGRADE = 1
ERASE     = 2
INSTALL   = 3
REINSTALL = 4
UPGRADE   = 5

class TransactionItem(object):
    __slots__ = ('op_type', 'installed', 'erased', 'obsoleted', 'reason')

    def __init__(self, op_type, installed=None, erased=None, obsoleted=None,
                 reason='unknown'):
        self.op_type = op_type
        self.installed = installed
        self.erased = erased
        self.obsoleted = list() if obsoleted is None else obsoleted
        self.reason = reason # reason for it to be in the transaction set

    @property
    def active(self):
        return self.installed if self.installed is not None else self.erased

    @property
    def active_history_state(self):
        return (self.installed_history_state if self.installed is not None
                else self.erased_history_state)

    @property
    def erased_history_state(self):
        return self._HISTORY_ERASE_STATES[self.op_type]

    _HISTORY_INSTALLED_STATES = {
        DOWNGRADE : 'Downgrade',
        INSTALL   : 'Install',
        REINSTALL : 'Reinstall',
        UPGRADE   : 'Update'
        }

    _HISTORY_ERASE_STATES = {
        DOWNGRADE : 'Downgraded',
        ERASE     : 'Erase',
        REINSTALL : 'Reinstalled',
        UPGRADE   : 'Updated'
        }

    def history_iterator(self):
        if self.installed is not None:
            yield(self.installed, self.installed_history_state)
        if self.erased is not None:
            yield(self.erased, self.erased_history_state)
        if self.obsoleted:
            yield(self.installed, self.obsoleting_history_state)
        for obs in self.obsoleted:
            yield(obs, self.obsoleted_history_state)

    @property
    def installed_history_state(self):
        return self._HISTORY_INSTALLED_STATES[self.op_type]

    def installs(self):
        return [] if self.installed is None else [self.installed]

    @property
    def obsoleted_history_state(self):
        return 'Obsoleted'

    @property
    def obsoleting_history_state(self):
        return 'Obsoleting'

    def propagated_reason(self, yumdb):
        if self.reason == 'user':
            return self.reason
        if self.op_type in [DOWNGRADE, REINSTALL, UPGRADE]:
            previously = yumdb.get_package(self.erased).get('reason')
            if previously:
                return previously
        return self.reason

    def removes(self):
        l =  [] if self.erased is None else [self.erased]
        return l + self.obsoleted

class Transaction(object):
    # :api

    def __init__(self):
        # :api
        self._tsis = []
        self.logger = logging.getLogger("dnf")

    def __iter__(self):
        return iter(self._tsis)

    def __len__(self):
        return len(self._tsis)

    def _items2set(self, extracting_fn):
        lists = map(extracting_fn, self._tsis)
        sets = map(set, lists)
        return reduce(operator.or_, sets, set())

    def add_downgrade(self, new, downgraded, obsoleted):
        # :api
        tsi = TransactionItem(DOWNGRADE, new, downgraded, obsoleted)
        self._tsis.append(tsi)

    def add_erase(self, erased):
        # :api
        tsi = TransactionItem(ERASE, erased=erased)
        self._tsis.append(tsi)

    def add_install(self, new, obsoleted, reason='unknown'):
        # :api
        tsi = TransactionItem(INSTALL, new, obsoleted=obsoleted,
                              reason=reason)
        self._tsis.append(tsi)

    def add_reinstall(self, new, reinstalled, obsoleted):
        # :api
        tsi = TransactionItem(REINSTALL, new, reinstalled, obsoleted)
        self._tsis.append(tsi)

    def add_upgrade(self, upgrade, upgraded, obsoleted):
        # :api
        tsi = TransactionItem(UPGRADE, upgrade, upgraded, obsoleted)
        self._tsis.append(tsi)

    def get_items(self, op_type):
        return [tsi for tsi in self._tsis if tsi.op_type == op_type]

    @property
    def install_set(self):
        fn = operator.methodcaller('installs')
        return self._items2set(fn)

    def populate_rpm_ts(self, ts):
        """Populate the RPM transaction set."""

        for tsi in self._tsis:
            if tsi.op_type == DOWNGRADE:
                ts.addErase(tsi.erased.idx)
                hdr = tsi.installed.header
                ts.addInstall(hdr, tsi, 'i')
                self.logger.debug("populate_rpm_ts: downgrade: %s/%s" %
                                  (tsi.installed, tsi.erased))
            elif tsi.op_type == ERASE:
                ts.addErase(tsi.erased.idx)
                self.logger.debug("populate_rpm_ts: erase: %s" % tsi.erased)
            elif tsi.op_type == INSTALL:
                hdr = tsi.installed.header
                if tsi.obsoleted:
                    ts.addInstall(hdr, tsi, 'u')
                    msg = "populate_rpm_ts: install: %s promoted to upgrade."
                    self.logger.debug(msg % tsi.installed)
                else:
                    ts.addInstall(hdr, tsi, 'i')
                    self.logger.debug("populate_rpm_ts: install: %s" %
                                      tsi.installed)
            elif tsi.op_type == REINSTALL:
                ts.addErase(tsi.erased.idx)
                hdr = tsi.installed.header
                ts.addInstall(hdr, tsi, 'i')
                self.logger.debug("populate_rpm_ts: reinstall: %s" %
                                  tsi.erased)
            elif tsi.op_type == UPGRADE:
                hdr = tsi.installed.header
                ts.addInstall(hdr, tsi, 'u')
                self.logger.debug("populate_rpm_ts: upgrade: %s" % tsi.installed)
        return ts

    @property
    def remove_set(self):
        fn = operator.methodcaller('removes')
        return self._items2set(fn)

    def rpm_limitations(self):
        """ Ensures all the members can be passed to rpm as they are to pefrom
            the transaction.
        """
        src_installs = [pkg for pkg in self.install_set if pkg.arch == 'src']
        if len(src_installs):
            return _("Will not install a source rpm package (%s).") % \
                src_installs[0]
        return None

    def total_package_count(self):
        return len(self.install_set | self.remove_set)
