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


from __future__ import print_function

import os

import dnf
from dnf.conf import ModuleConf
from dnf.i18n import _

from collections import OrderedDict
from dnf.modules.metadata_loader import ModuleMetadataLoader


class RepoModuleVersion(object):
    def __init__(self, module_metadata, repo):
        self.module_metadata = module_metadata
        self.repo = repo
        self.parent = None

    def __lt__(self, other):
        # for finding latest
        assert self.full_stream == other.full_stream
        return self.module_metadata.version < other.module_metadata.version

    def nevra(self):
        return self.module_metadata.artifacts.rpms

    def profile_rpms(self, profile):
        return self.module_metadata.profiles[profile].rpms

    def query(self, nevra):
        base = self.parent.parent.parent.base
        query = base.sack.query()
        query = query.filter(nevra=nevra)
        # TODO use later
        # base.sack.add_includes(query, reponame=self.repo.name)
        return query.run()

    def profile_selectors(self, profile):
        sack = self.parent.parent.parent.base.sack
        selectors = []
        for rpm in self.nevra():
            query = dnf.subject.Subject(rpm).get_best_query(sack,
                                                            with_provides=False,
                                                            with_filenames=False)
            if not query:
                raise dnf.exceptions.DepsolveError("Cannot get best query for {}".format(rpm))

            query = query.filter(name=self.profile_rpms(profile))
            selector = dnf.selector.Selector(sack)
            selector.set(pkg=query)
            selectors.append(selector)
        return selectors

    @property
    def version(self):
        return self.module_metadata.version

    @property
    def full_version(self):
        return "%s-%s-%s" % (
            self.module_metadata.name, self.module_metadata.stream, self.module_metadata.version)

    @property
    def stream(self):
        return self.module_metadata.stream

    @property
    def full_stream(self):
        return "%s-%s" % (self.module_metadata.name, self.module_metadata.stream)

    @property
    def name(self):
        return self.module_metadata.name

    def enable(self):
        pass

    def disable(self):
        pass

    @property
    def is_enabled(self):
        pass

    @property
    def is_installed(self):
        pass

    @property
    def profiles(self):
        return sorted(self.module_metadata.profiles)


class RepoModuleStream(OrderedDict):
    def __init__(self):
        super(RepoModuleStream, self).__init__()

        self.stream = None
        self.parent = None

    def add(self, repo_module_version):
        self[repo_module_version.version] = repo_module_version
        repo_module_version.parent = self

        self.stream = repo_module_version.stream


class RepoModule(OrderedDict):
    def __init__(self):
        super(RepoModule, self).__init__()

        self.conf = None
        self.name = None
        self.parent = None

    def add(self, repo_module_version):
        module_stream = self.setdefault(repo_module_version.stream, RepoModuleStream())
        module_stream.add(repo_module_version)
        module_stream.parent = self

        self.name = repo_module_version.name

    def enable(self, stream, assumeyes):
        if self.conf is None:
            self.conf = ModuleConf(section=self.name, parser=dnf.conf.ConfigParser())
            self.conf.name = self.name

        if not assumeyes and self.conf.stream is not None and self.conf.stream is not stream:
            raise dnf.exceptions.Error(_("Enabling different stream"))

        self.conf.stream = stream
        self.conf.enabled = True
        self.write_conf_to_file()

    def disable(self):
        if self.conf is None:
            self.conf = ModuleConf(section=self.name, parser=dnf.conf.ConfigParser())
            self.conf.name = self.name

        self.conf.enabled = False
        self.write_conf_to_file()

    def write_conf_to_file(self):
        modules_dir = self.parent.base.conf.modulesdir[0]
        installroot = self.parent.base.conf.installroot
        # TODO installroot
        output_file = os.path.join(modules_dir, "%s.module" % self.conf.name)
        with open(output_file, "w") as config_file:
            self.conf._write(config_file)


class RepoModuleDict(OrderedDict):

    def __init__(self, base):
        super(RepoModuleDict, self).__init__()

        self.base = base

    def add(self, repo_module_version):
        module = self.setdefault(repo_module_version.name, RepoModule())
        module.add(repo_module_version)
        module.parent = self

    def latest(self, name):
        return max(self[name][self.active_stream(name)].values())

    def active_stream(self, name):
        if self[name].conf is None:
            raise ValueError(_("No active stream for module: {}".format(name)))

        return self[name].conf.stream

    def load_modules(self, repo):
        loader = ModuleMetadataLoader(repo)
        for modulemd in loader.load():
            module_version = RepoModuleVersion()
            module_version.module_metadata = modulemd
            module_version.repo = repo

            self.add(module_version)

    def read_all_modules(self, base_conf):
        module_reader = dnf.conf.read.ModuleReader(base_conf)
        for conf in module_reader:
            repo_module = self.setdefault(conf.name, RepoModule())
            repo_module.conf = conf
            repo_module.name = conf.name
            repo_module.parent = self

    def get_modules_by_name_stream_version(self, name, stream=None, version=None):
        if name not in self:
            return None

        module_metadata = []
        if stream is not None and stream in self[name]:
            if version is not None and version in self[name][stream]:
                module_metadata.append(self[name][stream][version].module_metadata)
            else:
                for module_version in self[name][stream].values():
                    module_metadata.append(module_version.module_metadata)
        else:
            for module_stream in self[name].values():
                for module_version in module_stream.values():
                    module_metadata.append(module_version.module_metadata)

        if len(module_metadata) == 0:
            message = _("No such module: {}".format(name))
            raise NameError(message)

        return module_metadata

    def get_full_description(self, name, stream=None, version=None):
        module_metadata = self.get_modules_by_name_stream_version(name, stream, version)
        module_metadata = sorted(module_metadata, key=lambda data: data.version)

        ret = ""
        for data in module_metadata:
            ret += data.dumps() + "\n"
        return ret[:-1]

    def get_brief_description_all(self):
        return self._get_brief_description(self.values())

    def get_brief_description_enabled(self):
        repo_modules = self.values()
        return self._get_brief_description(
            [module for module in repo_modules if module.conf is not None and module.conf.enabled])

    def get_brief_description_disabled(self):
        repo_modules = self.values()
        return self._get_brief_description(
            [module for module in repo_modules if module.conf is None or not module.conf.enabled])

    @staticmethod
    def _get_brief_description(repo_module_set):
        if len(repo_module_set) == 0:
            return "Nothing to show"

        module_metadata = [repo_module_version.module_metadata
                           for repo_module in repo_module_set
                           for repo_module_stream in repo_module.values()
                           for repo_module_version in repo_module_stream.values()]

        if len(module_metadata) == 0:
            return "Nothing to show"

        space_between_columns = 4
        max_name_width = max(len(data.name) for data in module_metadata) + space_between_columns
        max_stream_width = (max(len(data.stream) for data in module_metadata) +
                            space_between_columns)
        max_vr_width = (max(len(str(data.version)) for data in module_metadata) +
                        space_between_columns)

        ret = "name".ljust(max_name_width)
        ret += "stream".ljust(max_stream_width)
        ret += "version".ljust(max_vr_width)
        ret += "\n"

        for data in module_metadata:
            ret += data.name.ljust(max_name_width)
            ret += data.stream.ljust(max_stream_width)
            ret += str(data.version).ljust(max_vr_width)
            ret += "\n"

        return ret[:-1]
