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
from dnf.yum.i18n import _

import operator

DOWNGRADE = 1
ERASE     = 2
INSTALL   = 3
UPGRADE   = 4

class TransactionItem(object):
    __slots__ = ('op_type', 'installed', 'erased', 'obsoleted', 'reason')

    def __init__(self, op_type, installed=None, erased=None, obsoleted=None,
                 reason=None):
        self.op_type = op_type
        self.installed = installed
        self.erased = erased
        self.obsoleted = list() if obsoleted is None else obsoleted

        if reason is None:
            reason = 'unknown'
        self.reason = reason # reason for it to be in the transaction set

    @property
    def active(self):
        return self.installed if self.installed is not None else self.erased

    def installs(self):
        return [] if self.installed is None else [self.installed]

    def propagated_reason(self, yumdb):
        if self.reason == 'user':
            return self.reason
        if self.op_type in [DOWNGRADE, UPGRADE]:
            previously = yumdb.get_package(self.erased).get('reason')
            if previously:
                return previously
        return self.reason

    def removes(self):
        l =  [] if self.erased is None else [self.erased]
        return l + self.obsoleted

class Transaction(object):
    def __init__(self):
        self._tsis = []

    def __iter__(self):
        return iter(self._tsis)

    def __len__(self):
        return len(self._tsis)

    def _items2set(self, extracting_fn):
        lists = map(extracting_fn, self._tsis)
        sets = map(set, lists)
        return reduce(operator.or_, sets, set())

    def add_downgrade(self, downgrade, downgraded, obsoleted):
        tsi = TransactionItem(DOWNGRADE, downgrade, downgraded, obsoleted)
        self._tsis.append(tsi)

    def add_erase(self, erased):
        tsi = TransactionItem(ERASE, erased=erased)
        self._tsis.append(tsi)

    def add_install(self, installed, obsoleted, reason=None):
        tsi = TransactionItem(INSTALL, installed, obsoleted=obsoleted,
                              reason=reason)
        self._tsis.append(tsi)

    def add_upgrade(self, upgrade, upgraded, obsoleted):
        tsi = TransactionItem(UPGRADE, upgrade, upgraded, obsoleted)
        self._tsis.append(tsi)

    def get_items(self, op_type):
        return [tsi for tsi in self._tsis if tsi.op_type == op_type]

    @property
    def install_set(self):
        fn = operator.methodcaller('installs')
        return self._items2set(fn)

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
            return _("DNF will not install a source rpm package (%s).") % \
                src_installs[0]
        return None

    def total_package_count(self):
        return len(self.install_set | self.remove_set)
