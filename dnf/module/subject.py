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

from dnf.exceptions import Error
from dnf.module import module_errors, NO_MODULE_ERR


class ModuleSubject(object):
    """
    Find matching modules for given user input (module_spec).
    """

    def __init__(self, module_spec):
        self.module_spec = module_spec

    def get_module_form_possibilities(self, forms=None):
        subj = hawkey.Subject(self.module_spec)
        kwargs = {}
        if forms:
            kwargs["form"] = forms
        return subj.module_form_possibilities(**kwargs)

    def find_module_version(self, repo_module_dict):
        """
        Find module that matches self.module_spec in given repo_module_dict.
        Return (RepoModuleVersion, ModuleForm).
        """

        result = (None, None)
        stream_err = None
        for module_form in self.get_module_form_possibilities():
            try:
                module_version = repo_module_dict.find_module_version(module_form.name,
                                                                      module_form.stream,
                                                                      module_form.version,
                                                                      module_form.context,
                                                                      module_form.arch)
                if module_version:
                    result = (module_version, module_form)
                    break
            except Error as e:
                stream_err = e

        if stream_err:
            raise stream_err
        elif not result[0]:
            raise Error(module_errors[NO_MODULE_ERR].format(self.module_spec))

        return result
