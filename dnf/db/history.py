# -*- coding: utf-8 -*-

# Copyright (C) 2009, 2012-2018  Red Hat, Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

import calendar
import os
import time

import libdnf.transaction
import libdnf.utils

from dnf.i18n import ucd
from dnf.yum import misc

from .group import GroupPersistor, EnvironmentPersistor, RPMTransaction


class RPMTransactionItemWrapper(object):
    def __init__(self, swdb, item):
        self._swdb = swdb
        self._item = item

    def __str__(self):
        return self._item.getItem().toStr()

    def __lt__(self, other):
        return self._item < other._item

    def __eq__(self, other):
        return self._item == other._item

    def __hash__(self):
        return self._item.__hash__()

    def match(self, pattern):
        return True

    @property
    def name(self):
        return self._item.getRPMItem().getName()

    @property
    def evr(self):
        epoch = self._item.getRPMItem().getEpoch()
        version = self._item.getRPMItem().getVersion()
        release = self._item.getRPMItem().getRelease()
        if epoch:
            return "{}-{}".format(version, release)
        return "{}:{}-{}".format(epoch, version, release)

    @property
    def arch(self):
        return self._item.getRPMItem().getArch()

    @property
    def action(self):
        return self._item.getAction()

    @action.setter
    def action(self, value):
        self._item.setAction(value)

    @property
    def reason(self):
        return self._item.getReason()

    @property
    def action_name(self):
        try:
            return self._item.getActionName()
        except AttributeError:
            return ""

    @property
    def action_short(self):
        try:
            return self._item.getActionShort()
        except AttributeError:
            return ""

    @property
    def state(self):
        return self._item.getState()

    @state.setter
    def state(self, value):
        self._item.setState(value)

    @property
    def from_repo(self):
        return self._item.getRepoid()

    def ui_from_repo(self):
        if not self._item.getRepoid():
            return ""
        return "@" + self._item.getRepoid()

    @property
    def obsoleting(self):
        return None

    def get_reason(self):
        # TODO: get_history_reason
        return self._swdb.rpm.get_reason(self)

    @property
    def pkg(self):
        return self._swdb.rpm._swdb_ti_pkg[self._item]

    @property
    def files(self):
        return self.pkg.files

    @property
    def _active(self):
        return self.pkg


class TransactionWrapper(object):

    altered_lt_rpmdb = False
    altered_gt_rpmdb = False

    def __init__(self, trans):
        self._trans = trans

    @property
    def tid(self):
        return self._trans.getId()

    @property
    def cmdline(self):
        return self._trans.getCmdline()

    @property
    def releasever(self):
        return self._trans.getReleasever()

    @property
    def beg_timestamp(self):
        return self._trans.getDtBegin()

    @property
    def end_timestamp(self):
        return self._trans.getDtEnd()

    @property
    def beg_rpmdb_version(self):
        return self._trans.getRpmdbVersionBegin()

    @property
    def end_rpmdb_version(self):
        return self._trans.getRpmdbVersionEnd()

    @property
    def return_code(self):
        return int(self._trans.getState() != libdnf.transaction.TransactionItemState_DONE)

    @property
    def loginuid(self):
        return self._trans.getUserId()

    @property
    def data(self):
        return self.packages

    @property
    def is_output(self):
        output = self._trans.getConsoleOutput()
        return bool(output)

    def tids(self):
        return [self._trans.getId()]

    def performed_with(self):
        return []

    def packages(self):
        result = self._trans.getItems()
        return [RPMTransactionItemWrapper(self, i) for i in result]

    def output(self):
        return [i[1] for i in self._trans.getConsoleOutput()]

    def error(self):
        return []

    def compare_rpmdbv(self, rpmdbv):
        self.altered_gt_rpmdb = self._trans.getRpmdbVersionEnd() != rpmdbv


class MergedTransactionWrapper(TransactionWrapper):

    def __init__(self, trans):
        self._trans = libdnf.transaction.MergedTransaction(trans._trans)

    def merge(self, trans):
        self._trans.merge(trans._trans)

    @property
    def loginuid(self):
        return self._trans.listUserIds()

    def tids(self):
        return self._trans.listIds()

    @property
    def return_code(self):
        return [int(i != libdnf.transaction.TransactionItemState_DONE) for i in self._trans.listStates()]

    @property
    def cmdline(self):
        return self._trans.listCmdlines()

    @property
    def releasever(self):
        return self._trans.listReleasevers()

    def output(self):
        return [i[1] for i in self._trans.getConsoleOutput()]

class SwdbInterface(object):

    def __init__(self, db_dir, releasever=""):
        # TODO: record all vars
        # TODO: remove relreasever from options
        self.releasever = str(releasever)
        self._rpm = None
        self._group = None
        self._env = None
        self._addon_data = None
        self._swdb = None
        self._db_dir = db_dir

    def __del__(self):
        self.close()

    @property
    def rpm(self):
        if self._rpm is None:
            self._rpm = RPMTransaction(self)
        return self._rpm

    @property
    def group(self):
        if self._group is None:
            self._group = GroupPersistor(self)
        return self._group

    @property
    def env(self):
        if self._env is None:
            self._env = EnvironmentPersistor(self)
        return self._env

    @property
    def dbpath(self):
        return os.path.join(self._db_dir, libdnf.transaction.Swdb.defaultDatabaseName)

    @property
    def swdb(self):
        """ Lazy initialize Swdb object """
        if not self._swdb:
            # _db_dir == persistdir which is prepended with installroot already
            self._swdb = libdnf.transaction.Swdb(self.dbpath)
            # TODO: vars -> libdnf
        return self._swdb

    def transform(self, input_dir):
        transformer = libdnf.transaction.Transformer(input_dir, self.dbpath)
        transformer.transform()

    def close(self):
        self._rpm = None
        self._group = None
        self._env = None
        if self._swdb:
            self._swdb.closeDatabase()
        self._swdb = None

    @property
    def path(self):
        return self.swdb.getPath()

    def reset_db(self):
        return self.swdb.resetDatabase()

    # TODO: rename to get_last_transaction?
    def last(self, complete_transactions_only=True):
        # TODO: complete_transactions_only
        t = self.swdb.getLastTransaction()
        if not t:
            return None
        return TransactionWrapper(t)

    # TODO: rename to: list_transactions?
    def old(self, tids=None, limit=0, complete_transactions_only=False):
        tids = tids or []
        tids = [int(i) for i in tids]
        result = self.swdb.listTransactions()
        result = [TransactionWrapper(i) for i in result]
        # TODO: move to libdnf
        if tids:
            result = [i for i in result if i.tid in tids]

        # populate altered_lt_rpmdb and altered_gt_rpmdb
        for i, trans in enumerate(result):
            if i == 0:
                continue
            prev_trans = result[i-1]
            if trans._trans.getRpmdbVersionBegin() != prev_trans._trans.getRpmdbVersionEnd():
                trans.altered_lt_rpmdb = True
                prev_trans.altered_gt_rpmdb = True
        return result[::-1]

    def set_reason(self, pkg, reason):
        """Set reason for package"""
        rpm_item = self.rpm._pkg_to_swdb_rpm_item(pkg)
        repoid = self.repo(pkg)
        action = libdnf.transaction.TransactionItemAction_REASON_CHANGE
        reason = reason
        replaced_by = None
        ti = self.swdb.addItem(rpm_item, repoid, action, reason)
        ti.setState(libdnf.transaction.TransactionItemState_DONE)
        return ti

    '''
    def package(self, pkg):
        """Get SwdbPackage from package"""
        return self.swdb.package(str(pkg))
    '''

    def repo(self, pkg):
        """Get repository of package"""
        return self.swdb.getRPMRepo(str(pkg))

    def package_data(self, pkg):
        """Get package data for package"""
        # trans item is returned
        result = self.swdb.getRPMTransactionItem(str(pkg))
        result = RPMTransactionItemWrapper(self, result)
        return result

#    def reason(self, pkg):
#        """Get reason for package"""
#        result = self.swdb.resolveRPMTransactionItemReason(pkg.name, pkg.arch, -1)
#        return result

    # TODO: rename to begin_transaction?
    def beg(self, rpmdb_version, using_pkgs, tsis, cmdline=None):
        try:
            self.swdb.initTransaction()
        except:
            pass

        '''
        for pkg in using_pkgs:
            pid = self.pkg2pid(pkg)
            self.swdb.trans_with(tid, pid)
        '''

        # add RPMs to the transaction
        # TODO: _populate_rpm_ts() ?

        if self.group:
            for group_id, group_item in sorted(self.group._installed.items()):
                repoid = ""
                action = libdnf.transaction.TransactionItemAction_INSTALL
                reason = libdnf.transaction.TransactionItemReason_USER
                replaced_by = None
                ti = self.swdb.addItem(group_item, repoid, action, reason)
                ti.setState(libdnf.transaction.TransactionItemState_DONE)

            for group_id, group_item in sorted(self.group._upgraded.items()):
                repoid = ""
                action = libdnf.transaction.TransactionItemAction_UPGRADE
                reason = libdnf.transaction.TransactionItemReason_USER
                replaced_by = None
                ti = self.swdb.addItem(group_item, repoid, action, reason)
                ti.setState(libdnf.transaction.TransactionItemState_DONE)

            for group_id, group_item in sorted(self.group._removed.items()):
                repoid = ""
                action = libdnf.transaction.TransactionItemAction_REMOVE
                reason = libdnf.transaction.TransactionItemReason_USER
                replaced_by = None
                ti = self.swdb.addItem(group_item, repoid, action, reason)
                ti.setState(libdnf.transaction.TransactionItemState_DONE)

        if self.env:
            for env_id, env_item in sorted(self.env._installed.items()):
                repoid = ""
                action = libdnf.transaction.TransactionItemAction_INSTALL
                reason = libdnf.transaction.TransactionItemReason_USER
                replaced_by = None
                ti = self.swdb.addItem(env_item, repoid, action, reason)
                ti.setState(libdnf.transaction.TransactionItemState_DONE)

            for env_id, env_item in sorted(self.env._upgraded.items()):
                repoid = ""
                action = libdnf.transaction.TransactionItemAction_UPGRADE
                reason = libdnf.transaction.TransactionItemReason_USER
                replaced_by = None
                ti = self.swdb.addItem(env_item, repoid, action, reason)
                ti.setState(libdnf.transaction.TransactionItemState_DONE)

            for env_id, env_item in sorted(self.env._removed.items()):
                repoid = ""
                action = libdnf.transaction.TransactionItemAction_REMOVE
                reason = libdnf.transaction.TransactionItemReason_USER
                replaced_by = None
                ti = self.swdb.addItem(env_item, repoid, action, reason)
                ti.setState(libdnf.transaction.TransactionItemState_DONE)


        # save when everything is in memory
        tid = self.swdb.beginTransaction(
            int(calendar.timegm(time.gmtime())),
            str(rpmdb_version),
            cmdline or "",
            int(misc.getloginuid())
            )
        self.swdb.setReleasever(self.releasever)
        self._tid = tid

        return tid

    def pkg_to_swdb_rpm_item(self, po):
        rpm_item = self.swdb.createRPMItem()
        rpm_item.setName(po.name)
        rpm_item.setEpoch(po.epoch or 0)
        rpm_item.setVersion(po.version)
        rpm_item.setRelease(po.release)
        rpm_item.setArch(po.arch)
        return rpm_item

    def log_scriptlet_output(self, msg):
        if not hasattr(self, '_tid'):
            return
        if not msg:
            return
        for line in msg.splitlines():
            line = ucd(line)
            self.swdb.addConsoleOutputLine(1, line)

    '''
    def _log_errors(self, errors):
        for error in errors:
            error = ucd(error)
            self.swdb.log_error(self._tid, error)
    '''

    # TODO: rename to end_transaction?
    def end(self, end_rpmdb_version="", return_code=0, errors=None):
        assert return_code or not errors
        # TODO: fix return_code
        return_code = not bool(return_code)
        if not hasattr(self, '_tid'):
            return  # Failed at beg() time
        self.swdb.endTransaction(
            int(time.time()),
            str(end_rpmdb_version),
            bool(return_code)
        )
        # TODO: consider cleaning individual attributes?
        self.close()
        '''
        if errors is not None:
            self._log_errors(errors)
        '''
        del self._tid
        # TODO: is this a good idea?
        self.swdb.initTransaction()

    # TODO: ignore_case, more patterns
    def search(self, patterns, ignore_case=True):
        """ Search for history transactions which contain specified
            packages al. la. "yum list". Returns transaction ids. """
        return self.swdb.searchTransactionsByRPM(patterns)

    def user_installed(self, pkg):
        """Returns True if package is user installed"""
        reason = self.swdb.resolveRPMTransactionItemReason(pkg.name, pkg.arch, -1)
        if reason == libdnf.transaction.TransactionItemReason_USER:
            return True
        # TODO: return True also for libdnf.transaction.TransactionItemReason_UNKNOWN?
        return False

    def select_user_installed(self, pkgs):
        """Select user installed packages from list of pkgs"""
        result = []
        for po in pkgs:
            reason = self.swdb.resolveRPMTransactionItemReason(po.name, po.arch, -1)
            if reason != libdnf.transaction.TransactionItemReason_USER:
                continue
            result.append(po)
        return result

    def get_erased_reason(self, pkg, first_trans, rollback):
        """Get reason of package before transaction being undone. If package
        is already installed in the system, keep his reason.

        :param pkg: package being installed
        :param first_trans: id of first transaction being undone
        :param rollback: True if transaction is performing a rollback"""
        if rollback:
            # return the reason at the point of rollback; we're setting that reason
            result = self.swdb.resolveRPMTransactionItemReason(pkg.name, pkg.arch, first_trans)
        else:
            result = self.swdb.resolveRPMTransactionItemReason(pkg.name, pkg.arch, -1)

        # consider unknown reason as user-installed
        if result == libdnf.transaction.TransactionItemReason_UNKNOWN:
            result = libdnf.transaction.TransactionItemReason_USER
        return result
