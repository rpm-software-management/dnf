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

import gzip
import modulemd

from dnf.exceptions import Error
from dnf.module import module_errors, LOAD_CACHE_ERR, MISSING_YAML_ERR


class ModuleMetadataLoader(object):
    def __init__(self, repo=None):
        self.repo = repo

    @property
    def _metadata_fn(self):
        return self.repo.metadata._repo_dct.get("modules")

    def load(self):
        if self.repo is None:
            raise Error(module_errors[LOAD_CACHE_ERR].format(self.repo))

        if not self._metadata_fn:
            raise Error(module_errors[MISSING_YAML_ERR].format(self.repo._cachedir))

        with gzip.open(self._metadata_fn, "r") as modules_yaml_gz:
            modules_yaml = modules_yaml_gz.read()

        return modulemd.loads_all(modules_yaml)
