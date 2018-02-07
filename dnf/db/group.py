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


import libdnf.swdb

import dnf.db.history
from dnf.i18n import _


class PersistorBase(object):
    def __init__(self, swdb_interface):
        assert isinstance(swdb_interface, dnf.db.history.SwdbInterface), str(type(swdb_interface))
        self.swdb = swdb_interface
        self.installed = {}
        self.removed = {}
        self.upgraded = {}

    def clean(self):
        self.installed = {}
        self.removed = {}
        self.upgraded = {}

    def install(self, obj):
        raise NotImplementedError

    def remove(self, obj):
        raise NotImplementedError

    def upgrade(self, obj):
        raise NotImplementedError

    def new(self, obj_id, name, translated_name, pkg_types):
        raise NotImplementedError

    def get(self, obj_id):
        raise NotImplementedError

    def search_by_pattern(self, pattern):
        raise NotImplementedError


class GroupPersistor(PersistorBase):

    def install(self, obj):
        self.installed[obj.getGroupId()] = obj

    def remove(self, obj):
        self.removed[obj.getGroupId()] = obj

    def upgrade(self, obj):
        self.upgraded[obj.getGroupId()] = obj

    def new(self, obj_id, name, translated_name, pkg_types):
        swdb_group = libdnf.swdb.CompsGroupItem(self.swdb._conn)
        swdb_group.setGroupId(obj_id)
        swdb_group.setName(name)
        swdb_group.setTranslatedName(translated_name)
        swdb_group.setPackageTypes(pkg_types)
        return swdb_group

    def get(self, obj_id):
        swdb_group = self.swdb.swdb.getCompsGroupItem(obj_id)
        if not swdb_group:
            return None
        swdb_group = swdb_group.getCompsGroupItem()
        return swdb_group

    def search_by_pattern(self, pattern):
        return self.swdb.swdb.getCompsGroupItemsByPattern(pattern)

    def get_package_groups(self, pkg_name):
        return self.swdb.swdb.getPackageCompsGroups(pkg_name)

    def is_removable_pkg(self, pkg_name):
        # for group removal and autoremove
        reason = self.swdb.swdb.resolveRPMTransactionItemReason(pkg_name, "", -2)
        if reason != libdnf.swdb.TransactionItemReason_GROUP:
            return False

        # TODO: implement lastTransId == -2 in libdnf
        package_groups = set(self.get_package_groups(pkg_name))
        for group_id, group in self.removed.items():
            for pkg in group.getPackages():
                if pkg.getName() != pkg_name:
                    continue
                if not pkg.getInstalled():
                    continue
                package_groups.remove(group_id)
        for group_id, group in self.installed.items():
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

    def install(self, obj):
        self.installed[obj.getEnvironmentId()] = obj

    def remove(self, obj):
        self.removed[obj.getEnvironmentId()] = obj

    def upgrade(self, obj):
        self.upgraded[obj.getEnvironmentId()] = obj

    def new(self, obj_id, name, translated_name, pkg_types):
        swdb_env = libdnf.swdb.CompsEnvironmentItem(self.swdb._conn)
        swdb_env.setEnvironmentId(obj_id)
        swdb_env.setName(name)
        swdb_env.setTranslatedName(translated_name)
        swdb_env.setPackageTypes(pkg_types)
        return swdb_env

    def get(self, obj_id):
        swdb_env = self.swdb.swdb.getCompsEnvironmentItem(obj_id)
        if not swdb_env:
            return None
        swdb_env = swdb_env.getCompsEnvironmentItem()
        return swdb_env

    def search_by_pattern(self, pattern):
        return self.swdb.swdb.getCompsEnvironmentItemsByPattern(pattern)

    def get_group_environments(self, group_id):
        return self.swdb.swdb.getCompsGroupEnvironments(group_id)

    def is_removable_group(self, group_id):
        # for environment removal
        swdb_group = self.swdb.group.get(group_id)
        if not swdb_group:
            return False

        # TODO: implement lastTransId == -2 in libdnf
        group_environments = set(self.get_group_environments(group_id))
        for env_id, env in self.removed.items():
            for group in env.getGroups():
                if group.getGroupId() != group_id:
                    continue
                if not group.getInstalled():
                    continue
                group_environments.remove(env_id)
        for env_id, env in self.installed.items():
            for group in env.getGroups():
                if group.getGroupId() != group_id:
                    continue
                if not group.getInstalled():
                    continue
                group_environments.add(env_id)
        if group_environments:
            return False
        return True
