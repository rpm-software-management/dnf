# -*- coding: utf-8 -*-

# transaction.py
# Managing the transaction to be passed to RPM.
#
# Copyright (C) 2013-2018 Red Hat, Inc.
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

import functools
import operator

import libdnf.swdb

from dnf.i18n import _


DOWNGRADE = 1
ERASE     = 2
INSTALL   = 3
REINSTALL = 4
UPGRADE   = 5
FAIL      = 6


def convert_reason(reason):
    if isinstance(reason, int):
        return reason

    reason_map = {
        "unknown": libdnf.swdb.TransactionItemReason_UNKNOWN,
        "dep": libdnf.swdb.TransactionItemReason_DEPENDENCY,
        "user": libdnf.swdb.TransactionItemReason_USER,
        "clean": libdnf.swdb.TransactionItemReason_CLEAN,
        "weak": libdnf.swdb.TransactionItemReason_WEAK_DEPENDENCY,
        "group": libdnf.swdb.TransactionItemReason_GROUP,
    }
    return reason_map[reason]


def convert_action(action):
    if isinstance(action, int):
        return action

    # TODO: add more records?
    action_map = {
        "Install": libdnf.swdb.TransactionItemAction_INSTALL,
        "Erase": libdnf.swdb.TransactionItemAction_REMOVE,
        "Reinstall": libdnf.swdb.TransactionItemAction_REINSTALL,
        # TODO: keep OBSOLETE, remove OBSOLETED?
#        "Obsoleted": libdnf.swdb.TransactionItemAction_OBSOLETED,
        "Reinstalled": None,
    }
    return action_map[action]


class TransactionItem(object):
    # :api

    __slots__ = ('op_type', 'installed', 'erased', 'obsoleted', 'reason')

    def __init__(self, op_type, installed=None, erased=None, obsoleted=None, reason=None):
        self.op_type = op_type
        self.installed = installed
        self.erased = erased
        self.obsoleted = list() if obsoleted is None else obsoleted
        reason = reason or libdnf.swdb.TransactionItemReason_UNKNOWN
        self.reason = convert_reason(reason)  # reason for it to be in the transaction set

    @property
    def _active(self):
        return self.installed if self.installed is not None else self.erased

    @property
    def _active_history_state(self):
        return (self._installed_history_state if self.installed is not None
                else self._erased_history_state)

    @property
    def _erased_history_state(self):
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

    _HISTORY_ERASE = [DOWNGRADE, ERASE, REINSTALL, UPGRADE]

    def _history_iterator(self):
        obsoleting = True if self.obsoleted else False
        if self.installed is not None:
            yield (self.installed, self._installed_history_state, obsoleting)
        if self.erased is not None:
            yield (self.erased, self._erased_history_state, False)
        for obs in self.obsoleted:
            yield (obs, self._obsoleted_history_state, False)

    @property
    def _installed_history_state(self):
        return self._HISTORY_INSTALLED_STATES[self.op_type]

    def installs(self):
        # :api
        return [] if self.installed is None else [self.installed]

    @property
    def _obsoleted_history_state(self):
        return 'Obsoleted'

    @property
    def _obsoleting_history_state(self):
        return 'Obsoleting'

    def _propagated_reason(self, history, installonly):
        if self.reason == libdnf.swdb.TransactionItemReason_USER:
            return self.reason
        if self.installed and installonly.filter(name=self.installed.name):
            return libdnf.swdb.TransactionItemReason_USER
        if self.op_type in self._HISTORY_ERASE and self.erased:
            try:
                previously = history.reason(self.erased)
            except:
                previously = None
            if previously:
                return previously
        if self.obsoleted:
            reasons = set()
            for obs in self.obsoleted:
                reasons.add(history.reason(obs))
            if reasons:
                if libdnf.swdb.TransactionItemReason_USER in reasons:
                    return libdnf.swdb.TransactionItemReason_USER
                if libdnf.swdb.TransactionItemReason_GROUP in reasons:
                    return libdnf.swdb.TransactionItemReason_GROUP
                if libdnf.swdb.TransactionItemReason_DEPENDENCY in reasons:
                    return libdnf.swdb.TransactionItemReason_DEPENDENCY
                if libdnf.swdb.TransactionItemReason_WEAK_DEPENDENCY in reasons:
                    return libdnf.swdb.TransactionItemReason_WEAK_DEPENDENCY
        return self.reason

    def _propagate_reason(self, history, installonlypkgs):
        reason = self._propagated_reason(history, installonlypkgs)
        if reason:
            self.reason = reason

    def removes(self):
        # :api
        l =  [] if self.erased is None else [self.erased]
        return l + self.obsoleted


class Transaction(object):
    # :api

    def __init__(self):
        # :api
        self._tsis = []

    def __iter__(self):
        #: api
        return iter(self._tsis)

    def __len__(self):
        return len(self._tsis)

    def _items2set(self, extracting_fn):
        lists = map(extracting_fn, self._tsis)
        sets = map(set, lists)
        return functools.reduce(operator.or_, sets, set())

    def add_downgrade(self, new, downgraded, obsoleted):
        # :api
        tsi = TransactionItem(DOWNGRADE, new, downgraded, obsoleted)
        self._tsis.append(tsi)

    def add_erase(self, erased):
        # :api
        tsi = TransactionItem(ERASE, erased=erased)
        self._tsis.append(tsi)

    def add_install(self, new, obsoleted, reason=None):
        # :api
        reason = reason or libdnf.swdb.TransactionItemReason_UNKNOWN
        reason = convert_reason(reason)  # support for string reasons
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

    def _get_items(self, op_type):
        return [tsi for tsi in self._tsis if tsi.op_type == op_type]

    @property
    def install_set(self):
        # :api
        fn = operator.methodcaller('installs')
        return self._items2set(fn)

    def _populate_rpm_ts(self, ts):
        """Populate the RPM transaction set."""

        for tsi in self._tsis:
            if tsi.op_type == DOWNGRADE:
                ts.addErase(tsi.erased.idx)
                hdr = tsi.installed._header
                ts.addInstall(hdr, tsi, 'u')
            elif tsi.op_type == ERASE:
                ts.addErase(tsi.erased.idx)
            elif tsi.op_type == INSTALL:
                hdr = tsi.installed._header
                if tsi.obsoleted:
                    ts.addInstall(hdr, tsi, 'u')
                else:
                    ts.addInstall(hdr, tsi, 'i')
            elif tsi.op_type == REINSTALL:
                # note: in rpm 4.12 there should not be set
                # rpm.RPMPROB_FILTER_REPLACEPKG to work
                ts.addReinstall(tsi.installed._header, tsi)
                if tsi.obsoleted:
                    for pkg in tsi.obsoleted:
                        ts.addErase(pkg.idx)
            elif tsi.op_type == UPGRADE:
                hdr = tsi.installed._header
                ts.addInstall(hdr, tsi, 'u')
        return ts

    @property
    def remove_set(self):
        # :api
        fn = operator.methodcaller('removes')
        return self._items2set(fn)

    def _rpm_limitations(self):
        """ Ensures all the members can be passed to rpm as they are to perform
            the transaction.
        """
        src_installs = [pkg for pkg in self.install_set if pkg.arch == 'src']
        if len(src_installs):
            return _("Will not install a source rpm package (%s).") % \
                src_installs[0]
        return None

    def _total_package_count(self):
        return len(self.install_set | self.remove_set)
