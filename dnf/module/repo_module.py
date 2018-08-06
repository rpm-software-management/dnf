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

import gi
gi.require_version('Modulemd', '1.0')
from gi.repository import Modulemd

from dnf.conf import ModuleConf
from dnf.module import module_messages, DIFFERENT_STREAM_INFO
from dnf.module.exceptions import NoStreamException, EnabledStreamException
from dnf.module.repo_module_stream import RepoModuleStream
from dnf.pycomp import ConfigParser
from dnf.util import logger


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
            self._conf.name._set(self.name)
            self._conf.state._set("")

        return self._conf

    @conf.setter
    def conf(self, value):
        self._conf = value

    @property
    def defaults(self):
        if self._defaults is None:
            self._defaults = Modulemd.Defaults()
            self._defaults.set_module_name(self.name)
            # default stream and profiles remain unset
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
