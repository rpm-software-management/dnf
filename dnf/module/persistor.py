# Copyright (C) 2017  Red Hat, Inc.
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


class ModulePersistor(object):

    def __init__(self):
        self.repo_modules = []

    def set_data(self, repo_module, **kwargs):
        self.repo_modules.append(repo_module)
        for name, value in kwargs.items():
            setattr(repo_module.conf, name, value)

    def save(self):
        for repo_module in self.repo_modules:
            repo_module.write_conf_to_file()

        return True

    def reset(self):
        # read configs from disk
        pass
