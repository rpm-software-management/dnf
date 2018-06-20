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

import os
import gi

from dnf.module.exceptions import LoadCacheException, MissingYamlException
from dnf.pycomp import PY3

gi.require_version('Modulemd', '1.0')
from gi.repository import Modulemd


class ModuleMetadataLoader(object):
    def __init__(self, repo=None):
        self.repo = repo

    @property
    def _metadata_fn(self):
        if self.repo.metadata:
            return self.repo.metadata._repo_dct.get("modules")

    def load(self):
        if self.repo is None:
            raise LoadCacheException(self.repo)

        yaml_file_path = None
        if not self._metadata_fn:
            repodata_dir = self.repo._cachedir + "/repodata/"
            files = os.listdir(repodata_dir)
            for file in files:
                if "modules.yaml" in file:
                    yaml_file_path = repodata_dir + file
                    break

        if not self._metadata_fn and not yaml_file_path:
            raise MissingYamlException(self.repo._cachedir)

        openfunc = open
        if (self._metadata_fn and self._metadata_fn.endswith('.gz')) \
                or (yaml_file_path and yaml_file_path.endswith('.gz')):
            openfunc = gzip.open
        with openfunc(self._metadata_fn or yaml_file_path, "r") as modules_yaml_fd:
            modules_yaml = modules_yaml_fd.read()

        if PY3 and isinstance(modules_yaml, bytes):
            modules_yaml = modules_yaml.decode("utf-8")

        return Modulemd.objects_from_string(modules_yaml)
