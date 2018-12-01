# -*- coding: utf-8 -*-

# Copyright (C) 2017-2018 Red Hat, Inc.
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


import libdnf.transaction

import dnf.db.history
import dnf.transaction
from dnf.i18n import _


class PersistorBase(object):
    def __init__(self, history):
        assert isinstance(history, dnf.db.history.SwdbInterface), str(type(history))
        self.history = history
        self._installed = {}
        self._removed = {}
        self._upgraded = {}

    def __len__(self):
        return len(self._installed) + len(self._removed) + len(self._upgraded)

    def clean(self):
        self._installed = {}
        self._removed = {}
        self._upgraded = {}

    def _get_obj_id(self, obj):
        raise NotImplementedError

    def install(self, obj):
        self._installed[self._get_obj_id(obj)] = obj

    def remove(self, obj):
        self._removed[self._get_obj_id(obj)] = obj

    def upgrade(self, obj):
        self._upgraded[self._get_obj_id(obj)] = obj

    def new(self, obj_id, name, translated_name, pkg_types):
        raise NotImplementedError

    def get(self, obj_id):
        raise NotImplementedError

    def search_by_pattern(self, pattern):
        raise NotImplementedError


class GroupPersistor(PersistorBase):

    def __iter__(self):
        items = self.history.swdb.getItems()
        items = [i for i in items if i.getCompsGroupItem()]
        return iter(items)

    def _get_obj_id(self, obj):
        return obj.getGroupId()

    def new(self, obj_id, name, translated_name, pkg_types):
        swdb_group = self.history.swdb.createCompsGroupItem()
        swdb_group.setGroupId(obj_id)
        swdb_group.setName(name)
        swdb_group.setTranslatedName(translated_name)
        swdb_group.setPackageTypes(pkg_types)
        return swdb_group

    def get(self, obj_id):
        swdb_group = self.history.swdb.getCompsGroupItem(obj_id)
        if not swdb_group:
            return None
        swdb_group = swdb_group.getCompsGroupItem()
        return swdb_group

    def search_by_pattern(self, pattern):
        return self.history.swdb.getCompsGroupItemsByPattern(pattern)

    def get_package_groups(self, pkg_name):
        return self.history.swdb.getPackageCompsGroups(pkg_name)

    def is_removable_pkg(self, pkg_name):
        # for group removal and autoremove
        reason = self.history.swdb.resolveRPMTransactionItemReason(pkg_name, "", -2)
        if reason != libdnf.transaction.TransactionItemReason_GROUP:
            return False

        # TODO: implement lastTransId == -2 in libdnf
        package_groups = set(self.get_package_groups(pkg_name))
        for group_id, group in self._removed.items():
            for pkg in group.getPackages():
                if pkg.getName() != pkg_name:
                    continue
                if not pkg.getInstalled():
                    continue
                package_groups.remove(group_id)
        for group_id, group in self._installed.items():
            for pkg in group.getPackages():
                if pkg.getName() != pkg_name:
                    continue
                if not pkg.getInstalled():
                    continue
                package_groups.add(group_id)
        if package_groups:
            return False
        return True


class EnvironmentPersistor(PersistorBase):

    def __iter__(self):
        items = self.history.swdb.getItems()
        items = [i for i in items if i.getCompsEnvironmentItem()]
        return iter(items)

    def _get_obj_id(self, obj):
        return obj.getEnvironmentId()

    def new(self, obj_id, name, translated_name, pkg_types):
        swdb_env = self.history.swdb.createCompsEnvironmentItem()
        swdb_env.setEnvironmentId(obj_id)
        swdb_env.setName(name)
        swdb_env.setTranslatedName(translated_name)
        swdb_env.setPackageTypes(pkg_types)
        return swdb_env

    def get(self, obj_id):
        swdb_env = self.history.swdb.getCompsEnvironmentItem(obj_id)
        if not swdb_env:
            return None
        swdb_env = swdb_env.getCompsEnvironmentItem()
        return swdb_env

    def search_by_pattern(self, pattern):
        return self.history.swdb.getCompsEnvironmentItemsByPattern(pattern)

    def get_group_environments(self, group_id):
        return self.history.swdb.getCompsGroupEnvironments(group_id)

    def is_removable_group(self, group_id):
        # for environment removal
        swdb_group = self.history.group.get(group_id)
        if not swdb_group:
            return False

        # TODO: implement lastTransId == -2 in libdnf
        group_environments = set(self.get_group_environments(group_id))
        for env_id, env in self._removed.items():
            for group in env.getGroups():
                if group.getGroupId() != group_id:
                    continue
                if not group.getInstalled():
                    continue
                group_environments.remove(env_id)
        for env_id, env in self._installed.items():
            for group in env.getGroups():
                if group.getGroupId() != group_id:
                    continue
                if not group.getInstalled():
                    continue
                group_environments.add(env_id)
        if group_environments:
            return False
        return True


class RPMTransaction(object):
    def __init__(self, history, transaction=None):
        self.history = history
        self.transaction = transaction
        if not self.transaction:
            try:
                self.history.swdb.initTransaction()
            except:
                pass
        self._swdb_ti_pkg = {}

    # TODO: close trans if needed

    def __iter__(self):
        #: api
        if self.transaction:
            items = self.transaction.getItems()
        else:
            items = self.history.swdb.getItems()
        items = [dnf.db.history.RPMTransactionItemWrapper(self.history, i) for i in items if i.getRPMItem()]
        return iter(items)

    def __len__(self):
        if self.transaction:
            items = self.transaction.getItems()
        else:
            items = self.history.swdb.getItems()
        items = [dnf.db.history.RPMTransactionItemWrapper(self.history, i) for i in items if i.getRPMItem()]
        return len(items)

    def _pkg_to_swdb_rpm_item(self, pkg):
        rpm_item = self.history.swdb.createRPMItem()
        rpm_item.setName(pkg.name)
        rpm_item.setEpoch(pkg.epoch or 0)
        rpm_item.setVersion(pkg.version)
        rpm_item.setRelease(pkg.release)
        rpm_item.setArch(pkg.arch)
        return rpm_item

    def new(self, pkg, action, reason=None, replaced_by=None):
        rpm_item = self._pkg_to_swdb_rpm_item(pkg)
        repoid = self.get_repoid(pkg)
        if reason is None:
            reason = self.get_reason(pkg)
        result = self.history.swdb.addItem(rpm_item, repoid, action, reason)
        if replaced_by:
            result.addReplacedBy(replaced_by)
        self._swdb_ti_pkg[result] = pkg
        return result

    def get_repoid(self, pkg):
        result = getattr(pkg, "_force_swdb_repoid", None)
        if result:
            return result
        return pkg.reponame

    def get_reason(self, pkg):
        """Get reason for package"""
        return self.history.swdb.resolveRPMTransactionItemReason(pkg.name, pkg.arch, -1)

    def _add_obsoleted(self, obsoleted, replaced_by=None):
        obsoleted = obsoleted or []
        for obs in obsoleted:
            ti = self.new(obs, libdnf.transaction.TransactionItemAction_OBSOLETED)
            if replaced_by:
                ti.addReplacedBy(replaced_by)

    def add_downgrade(self, new, old, obsoleted=None):
        ti_new = self.new(new, libdnf.transaction.TransactionItemAction_DOWNGRADE)
        ti_old = self.new(old, libdnf.transaction.TransactionItemAction_DOWNGRADED, replaced_by=ti_new)
        self._add_obsoleted(obsoleted, replaced_by=ti_new)

    def add_erase(self, old, reason=None):
        self.add_remove(old, reason)

    def add_install(self, new, obsoleted=None, reason=None):
        reason = reason or libdnf.transaction.TransactionItemReason_USER
        ti_new = self.new(new, libdnf.transaction.TransactionItemAction_INSTALL, reason)
        self._add_obsoleted(obsoleted, replaced_by=ti_new)

    def add_reinstall(self, new, old, obsoleted=None):
        ti_new = self.new(new, libdnf.transaction.TransactionItemAction_REINSTALL)
        ti_old = self.new(old, libdnf.transaction.TransactionItemAction_REINSTALLED, replaced_by=ti_new)
        self._add_obsoleted(obsoleted, replaced_by=ti_new)

    def add_remove(self, old, reason=None):
        reason = reason or libdnf.transaction.TransactionItemReason_USER
        ti_old = self.new(old, libdnf.transaction.TransactionItemAction_REMOVE, reason)

    def add_upgrade(self, new, old, obsoleted=None):
        ti_new = self.new(new, libdnf.transaction.TransactionItemAction_UPGRADE)
        ti_old = self.new(old, libdnf.transaction.TransactionItemAction_UPGRADED, replaced_by=ti_new)
        self._add_obsoleted(obsoleted, replaced_by=ti_new)

    def _populate_rpm_ts(self, ts):
        """Populate the RPM transaction set."""

        for tsi in self:
            if tsi.action == libdnf.transaction.TransactionItemAction_DOWNGRADE:
                hdr = tsi.pkg._header
                ts.addInstall(hdr, tsi, 'u')
            elif tsi.action == libdnf.transaction.TransactionItemAction_DOWNGRADED:
                ts.addErase(tsi.pkg.idx)
            elif tsi.action == libdnf.transaction.TransactionItemAction_INSTALL:
                hdr = tsi.pkg._header
                ts.addInstall(hdr, tsi, 'i')
            elif tsi.action == libdnf.transaction.TransactionItemAction_OBSOLETE:
                hdr = tsi.pkg._header
                ts.addInstall(hdr, tsi, 'u')
            elif tsi.action == libdnf.transaction.TransactionItemAction_OBSOLETED:
                ts.addErase(tsi.pkg.idx)
            elif tsi.action == libdnf.transaction.TransactionItemAction_REINSTALL:
                # note: in rpm 4.12 there should not be set
                # rpm.RPMPROB_FILTER_REPLACEPKG to work
                hdr = tsi.pkg._header
                ts.addReinstall(hdr, tsi)
            elif tsi.action == libdnf.transaction.TransactionItemAction_REINSTALLED:
                pass
            elif tsi.action == libdnf.transaction.TransactionItemAction_REMOVE:
                ts.addErase(tsi.pkg.idx)
            elif tsi.action == libdnf.transaction.TransactionItemAction_UPGRADE:
                hdr = tsi.pkg._header
                ts.addInstall(hdr, tsi, 'u')
            elif tsi.action == libdnf.transaction.TransactionItemAction_UPGRADED:
                ts.addErase(tsi.pkg.idx)
            elif tsi.action == libdnf.transaction.TransactionItemAction_REASON_CHANGE:
                pass
            else:
                raise RuntimeError("TransactionItemAction not handled: %s" % tsi.action)

        return ts

    @property
    def install_set(self):
        # :api
        result = set()
        for tsi in self:
            if tsi.action in dnf.transaction.FORWARD_ACTIONS:
                try:
                    result.add(tsi.pkg)
                except KeyError:
                    raise RuntimeError("TransactionItem is has no RPM attached: %s" % tsi)
        return result

    @property
    def remove_set(self):
        # :api
        result = set()
        for tsi in self:
            if tsi.action in dnf.transaction.BACKWARD_ACTIONS + [libdnf.transaction.TransactionItemAction_REINSTALLED]:
                try:
                    result.add(tsi.pkg)
                except KeyError:
                    raise RuntimeError("TransactionItem is has no RPM attached: %s" % tsi)
        return result

    def _rpm_limitations(self):
        """ Ensures all the members can be passed to rpm as they are to perform
            the transaction.
        """
        src_installs = [pkg for pkg in self.install_set if pkg.arch == 'src']
        if len(src_installs):
            return _("Will not install a source rpm package (%s).") % \
                src_installs[0]
        return None

    def _get_items(self, action):
        return [tsi for tsi in self if tsi.action == action]
