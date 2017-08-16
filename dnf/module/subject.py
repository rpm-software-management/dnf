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

import hawkey


class ModuleSubject(object):
    """
    Find matching modules for given user input (pkg_spec).
    """

    def __init__(self, pkg_spec):
        self.pkg_spec = pkg_spec

    def get_nsvcap_possibilities(self, forms=None):
        subj = hawkey.Subject(self.pkg_spec)
        kwargs = {}
        if forms:
            kwargs["form"] = forms
        return subj.nsvcap_possibilities(**kwargs)

    def find_module_version(self, repo_module_dict):
        """
        Find module that matches self.pkg_spec in given repo_module_dict.
        Return (RepoModuleVersion, NSVCAP).
        """

        result = (None, None)
        for nsvcap in self.get_nsvcap_possibilities():
            module_version = repo_module_dict.find_module_version(nsvcap.name, nsvcap.stream,
                                                                  nsvcap.version, nsvcap.context,
                                                                  nsvcap.arch)
            if module_version:
                result = (module_version, nsvcap)
                break
        return result
