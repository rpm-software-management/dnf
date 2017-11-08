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
from collections import OrderedDict

from dnf.conf import ModuleConf, ModuleDefaultsConf
from dnf.module import module_messages, DIFFERENT_STREAM_INFO
from dnf.module.exceptions import NoStreamException, EnabledStreamException
from dnf.module.repo_module_stream import RepoModuleStream
from dnf.pycomp import ConfigParser
from dnf.util import logger, ensure_dir


class RepoModule(OrderedDict):
    def __init__(self):
        super(RepoModule, self).__init__()

        self._conf = None
        self._defaults = None
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

    @property
    def defaults(self):
        if self._defaults is None:
            self._defaults = ModuleDefaultsConf(section=self.name, parser=ConfigParser())
            self._defaults.name = self.name
            self._defaults.stream = None
            self._defaults.profiles = None

        return self._defaults

    @defaults.setter
    def defaults(self, value):
        self._defaults = value

    def add(self, repo_module_version):
        module_stream = self.setdefault(repo_module_version.stream, RepoModuleStream())
        module_stream.add(repo_module_version)
        module_stream.parent = self

        self.name = repo_module_version.name
        repo_module_version.repo_module = self

    def enable(self, stream, assumeyes=False):
        if stream not in self:
            raise NoStreamException("{}:{}".format(self.name, stream))

        if self.conf.enabled and self.conf.stream == stream:
            return

        if self.conf.stream is not None and \
                str(self.conf.stream) != str(stream) and \
                not assumeyes:
            logger.info(module_messages[DIFFERENT_STREAM_INFO].format(self.name))

            if not self.parent.base.conf.assumeno and \
                    self.parent.base.output.userconfirm():
                self.parent.base._module_persistor.set_data(self, version=-1, profiles=set())
                self.enable(stream, True)
            else:
                raise EnabledStreamException("{}:{}".format(self.name, stream))

        self.parent.base._module_persistor.set_data(self, stream=stream, enabled=True)

    def disable(self):
        self.parent.base._module_persistor.set_data(self, enabled=False, profiles=[])

    def lock(self, version):
        self.parent.base._module_persistor.set_data(self, locked=True, version=version)

    def unlock(self):
        self.parent.base._module_persistor.set_data(self, locked=False)

    def write_conf_to_file(self):
        output_file = os.path.join(self.parent.get_modules_dir(), "%s.module" % self.conf.name)
        ensure_dir(self.parent.get_modules_dir())

        with open(output_file, "w") as config_file:
            self.conf._write(config_file)
