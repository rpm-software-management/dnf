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

import os

from ConfigParser import ConfigParser
from collections import OrderedDict

from dnf.conf import ModuleConf
from dnf.exceptions import Error
from dnf.module import module_errors, NO_STREAM_ERR, DIFFERENT_STREAM_INFO, STREAM_NOT_ENABLED_ERR
from dnf.module.repo_module_stream import RepoModuleStream
from dnf.util import logger, ensure_dir


class RepoModule(OrderedDict):
    def __init__(self):
        super(RepoModule, self).__init__()

        self._conf = None
        self.defaults = None
        self.name = None
        self.parent = None

    @property
    def conf(self):
        if self._conf is None:
            self._conf = ModuleConf(section=self.name, parser=ConfigParser())
            self._conf.name = self.name
            self._conf.enabled = False
            self._conf.locked = False
            self._conf.version = -1

        return self._conf

    @conf.setter
    def conf(self, value):
        self._conf = value

    def add(self, repo_module_version):
        module_stream = self.setdefault(repo_module_version.stream, RepoModuleStream())
        module_stream.add(repo_module_version)
        module_stream.parent = self

        self.name = repo_module_version.name
        repo_module_version.repo_module = self

    def enable(self, stream, assumeyes, assumeno):
        if stream not in self:
            raise Error(module_errors[NO_STREAM_ERR].format(stream, self.name))

        if self.conf.stream is not None and str(self.conf.stream) != str(stream) and not assumeyes:
            logger.info(module_errors[DIFFERENT_STREAM_INFO].format(self.name))
            if not assumeno and self.parent.base.output.userconfirm():
                self.enable(stream, True, assumeno)
            else:
                logger.info(module_errors[STREAM_NOT_ENABLED_ERR].format(stream))

        self.conf.stream = stream
        self.conf.enabled = True
        self.write_conf_to_file()

    def disable(self):
        self.conf.enabled = False
        self.write_conf_to_file()

    def lock(self, version):
        self.conf.locked = True
        self.conf.version = version
        self.write_conf_to_file()

    def unlock(self):
        self.conf.locked = False
        self.write_conf_to_file()

    def write_conf_to_file(self):
        output_file = os.path.join(self.parent.get_modules_dir(), "%s.module" % self.conf.name)
        ensure_dir(self.parent.get_modules_dir())

        with open(output_file, "w") as config_file:
            self.conf._write(config_file)
