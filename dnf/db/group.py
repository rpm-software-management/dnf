# Copyright (C) 2017 Red Hat, Inc.
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
# Eduard Cuba <ecuba@redhat.com>

from hawkey import SwdbGroup, SwdbEnv


class GroupPersistor(object):

    def __init__(self, swdb):
        self.swdb = swdb
        self.groups_installed = []
        self.groups_removed = []

    def commit(self):
        for group in self.groups_removed:
            self.swdb.uninstall_group(group)
        if self.groups_installed:
            self.swdb.groups_commit(self.groups_installed)
        self.groups_installed = []
        self.groups_removed = []

    def install_group(self, group, commit=False):
        self.groups_installed.append(group)
        if commit:
            self.commit()

    def remove_group(self, group, commit=False):
        self.groups_removed.append(group)
        if commit:
            self.commit()

    def new_group(self, name_id, name, ui_name, installed, pkg_types):
        group = SwdbGroup.new(name_id, name, ui_name, installed, pkg_types, self.swdb)
        return group

    def new_env(self, name_id, name, ui_name, pkg_types, grp_types):
        env = SwdbEnv.new(name_id, name, ui_name, pkg_types, grp_types, self.swdb)
        return env

    def environment(self, name_id):
        if isinstance(name_id, SwdbEnv):
            return self.swdb.get_env(name_id.name_id)
        return self.swdb.get_env(name_id)

    def environments(self):
        return self.swdb.environments()

    def environments_by_pattern(self, pattern):
        return self.swdb.env_by_pattern(pattern)

    def group(self, gid):
        if isinstance(gid, SwdbGroup):
            gid = gid.name_id
        return self.swdb.get_group(gid)

    def group_installed(self, group_id):
        # :api
        """Find out whether group is installed"""
        group = self.group(group_id)
        return group.installed if group else False

    def environment_installed(self, env_id):
        # :api
        """Find out whether environment is installed"""
        env = self.environment(env_id)
        return env.installed if env else False

    def groups(self):
        return self.swdb.groups()

    def groups_by_pattern(self, pattern):
        return self.swdb.groups_by_pattern(pattern)

    def add_group(self, group, commit=False):
        self.swdb.add_group(group)
        if commit:
            self.install_group(group, True)

    def add_env(self, env):
        return self.swdb.add_env(env)

    def removable_pkg(self, pkg_name):
        return self.swdb.removable_pkg(pkg_name)
