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

import fnmatch
import os
from collections import OrderedDict

import smartcols

from dnf.conf.read import ModuleReader, ModuleDefaultsReader
from dnf.exceptions import Error
from dnf.module import module_errors, VERSION_LOCKED, NO_MODULE_ERR, STREAM_NOT_ENABLED_ERR, \
    NO_ACTIVE_STREAM_ERR, INSTALLING_NEWER_VERSION, PROFILE_NOT_INSTALLED, NOTHING_TO_SHOW
from dnf.module.metadata_loader import ModuleMetadataLoader
from dnf.module.repo_module import RepoModule
from dnf.module.repo_module_version import RepoModuleVersion
from dnf.module.subject import ModuleSubject
from dnf.util import first_not_none, logger, ensure_dir


class PreferredModuleVersion(object):

    def __init__(self):
        self.moduleversion_nsvcap_pkgspec = []
        self.preferred_version = -1
        self.reason = None


class RepoModuleDict(OrderedDict):

    def __init__(self, base):
        super(RepoModuleDict, self).__init__()

        self.base = base

    def add(self, repo_module_version):
        module = self.setdefault(repo_module_version.name, RepoModule())
        module.add(repo_module_version)
        module.parent = self

    def find_module_version(self, name, stream=None, version=None, context=None, arch=None):
        def use_enabled_stream(repo_module):
            if repo_module.conf and repo_module.conf.enabled:
                return repo_module.conf.stream
            return None

        def use_default_stream(repo_module):
            if repo_module.defaults:
                return repo_module.defaults.stream
            return None

        try:
            repo_module = self[name]

            stream = first_not_none([stream,
                                     use_enabled_stream(repo_module),
                                     use_default_stream(repo_module)])

            repo_module_stream = repo_module[stream]

            if repo_module.conf and \
                    repo_module.conf.locked and \
                    repo_module.conf.version is not None:
                if repo_module_stream.latest().version != repo_module.conf.version:
                    logger.info(module_errors[VERSION_LOCKED]
                                .format("{}:{}".format(repo_module.name, stream),
                                        repo_module.conf.version))

                repo_module_version = repo_module_stream[repo_module.conf.version]
            elif version:
                repo_module_version = repo_module_stream[version]
            else:
                # if version is not specified, pick the latest
                repo_module_version = repo_module_stream.latest()

            # TODO: arch
            # TODO: platform module

        except KeyError:
            return None
        return repo_module_version

    def enable(self, pkg_spec, assumeyes, assumeno=False):
        subj = ModuleSubject(pkg_spec)
        module_version, nsvcap = subj.find_module_version(self)

        if not module_version:
            raise Error(module_errors[NO_MODULE_ERR].format(pkg_spec))

        self[module_version.name].enable(module_version.stream, assumeyes, assumeno)

    def disable(self, pkg_spec):
        subj = ModuleSubject(pkg_spec)
        module_version, nsvcap = subj.find_module_version(self)

        if module_version:
            repo_module = module_version.repo_module
            repo_module.disable()
            return

        # if lookup by pkg_spec failed, try disabling module by name
        try:
            self[pkg_spec].disable()
        except KeyError:
            raise Error(module_errors[NO_MODULE_ERR].format(pkg_spec))

    def lock(self, pkg_spec):
        subj = ModuleSubject(pkg_spec)
        module_version, nsvcap = subj.find_module_version(self)

        if module_version:
            repo_module = module_version.repo_module

            if not repo_module.conf.enabled:
                raise Error(module_errors[STREAM_NOT_ENABLED_ERR].format(pkg_spec))

            repo_module.lock(module_version.version)
            return repo_module.conf.stream, repo_module.conf.version

        raise Error(module_errors[NO_MODULE_ERR].format(pkg_spec))

    def unlock(self, pkg_spec):
        subj = ModuleSubject(pkg_spec)
        module_version, nsvcap = subj.find_module_version(self)

        if module_version:
            repo_module = module_version.repo_module

            if not repo_module.conf.enabled:
                raise Error(module_errors[STREAM_NOT_ENABLED_ERR].format(pkg_spec))

            repo_module.unlock()
            return

        raise Error(module_errors[NO_MODULE_ERR].format(pkg_spec))

    def install(self, pkg_specs, autoenable=False):
        preferred_versions = self.get_preferred_versions(pkg_specs)

        for version in preferred_versions.values():
            for module_version, nsvcap, pkg_spec in version.moduleversion_nsvcap_pkgspec:
                module_version = self.decide_newer_version(module_version, pkg_spec,
                                                           version.preferred_version,
                                                           version.reason)

                if not module_version:
                    raise Error(module_errors[NO_MODULE_ERR].format(pkg_spec))
                elif module_version.repo_module.conf.locked:
                    continue

                if autoenable:
                    self.enable("{}:{}".format(module_version.name, module_version.stream), True)
                elif not self[nsvcap.name].conf.enabled:
                    raise Error(module_errors[NO_ACTIVE_STREAM_ERR].format(module_version.name))

                if nsvcap.profile:
                    profiles = [nsvcap.profile]
                else:
                    profiles = module_version.repo_module.defaults.profiles

                if module_version.version > module_version.repo_module.conf.version:
                    profiles.extend(module_version.repo_module.conf.profiles)
                    profiles = list(set(profiles))

                module_version.install(profiles)

    def decide_newer_version(self, module_version, pkg_spec, preferred_version, reason):
        if int(preferred_version) != module_version.version:
            logger.info(module_errors[INSTALLING_NEWER_VERSION].format(pkg_spec, reason))
            module_version = self.find_module_version(module_version.name, module_version.stream,
                                                      preferred_version)
        return module_version

    def get_preferred_versions(self, pkg_specs):
        preferred_versions = {}
        for pkg_spec in pkg_specs:
            subj = ModuleSubject(pkg_spec)
            module_version, nsvcap = subj.find_module_version(self)

            key = "{}:{}".format(module_version.name, module_version.stream)
            versions = preferred_versions.setdefault(key, PreferredModuleVersion())
            versions.moduleversion_nsvcap_pkgspec.append([module_version, nsvcap, pkg_spec])
            if versions.preferred_version < module_version.version:
                versions.preferred_version = module_version.version
                versions.reason = pkg_spec

        return preferred_versions

    def upgrade(self, pkg_specs):
        for pkg_spec in pkg_specs:
            subj = ModuleSubject(pkg_spec)
            module_version, nsvcap = subj.find_module_version(self)

            if not module_version:
                raise Error(module_errors[NO_MODULE_ERR].format(pkg_spec))
            elif module_version.repo_module.conf.locked:
                continue

            conf = self[nsvcap.name].conf
            if conf:
                installed_profiles = conf.profiles
            else:
                installed_profiles = []
            if nsvcap.profile:
                if nsvcap.profile not in installed_profiles:
                    raise Error(module_errors[PROFILE_NOT_INSTALLED].format(pkg_spec))
                profiles = [nsvcap.profile]
            else:
                profiles = installed_profiles

            module_version.upgrade(profiles)

    def upgrade_all(self):
        modules = []
        for module_name, repo_module in self.items():
            if not repo_module.conf:
                continue
            if not repo_module.conf.enabled:
                continue
            modules.append(module_name)
        modules.sort()
        self.upgrade(modules)

    def remove(self, pkg_specs):
        for pkg_spec in pkg_specs:
            subj = ModuleSubject(pkg_spec)
            module_version, nsvcap = subj.find_module_version(self)

            if not module_version:
                raise Error(module_errors[NO_MODULE_ERR].format(pkg_spec))

            conf = self[nsvcap.name].conf
            if conf:
                installed_profiles = conf.profiles
            else:
                installed_profiles = []
            if nsvcap.profile:
                if nsvcap.profile not in installed_profiles:
                    raise Error(module_errors[PROFILE_NOT_INSTALLED].format(pkg_spec))
                profiles = [nsvcap.profile]
            else:
                profiles = installed_profiles

            module_version.remove(profiles)

    def load_modules(self, repo):
        loader = ModuleMetadataLoader(repo)
        for module_metadata in loader.load():
            module_version = RepoModuleVersion(module_metadata, base=self.base, repo=repo)

            self.add(module_version)

    def read_all_modules(self):
        module_reader = ModuleReader(self.get_modules_dir())
        for conf in module_reader:
            repo_module = self.setdefault(conf.name, RepoModule())
            repo_module.conf = conf
            repo_module.name = conf.name
            repo_module.parent = self

    def read_all_module_defaults(self):
        defaults_reader = ModuleDefaultsReader(self.base.conf.moduledefaultsdir)
        for conf in defaults_reader:
            try:
                self[conf.name].defaults = conf
            except KeyError:
                logger.debug("No module named {}, skipping.".format(conf.name))

    def get_modules_dir(self):
        modules_dir = os.path.join(self.base.conf.installroot,
                                   self.base.conf.modulesdir.lstrip("/"))

        ensure_dir(modules_dir)
        return modules_dir

    def get_module_defaults_dir(self):
        return self.base.conf.moduledefaultsdir

    def get_info(self, pkg_spec):
        subj = ModuleSubject(pkg_spec)
        module_version, nsvcap = subj.find_module_version(self)

        lines = {"Name": module_version.name,
                 "Stream": module_version.stream,
                 "Version": module_version.version,
                 "Profiles": ", ".join(module_version.profiles),
                 "Summary": module_version.module_metadata.summary,
                 "Description": module_version.module_metadata.description,
                 "Artifacts": ", ".join(module_version.module_metadata.artifacts.rpms)}

        table = smartcols.Table()
        table.noheadings = True
        table.column_separator = " : "

        column_name = table.new_column("Name")
        column_value = table.new_column("Value")
        column_value.wrap = True

        for line_name, value in lines.items():
            line = table.new_line()
            if value:
                line[column_name] = line_name
                line[column_value] = str(value)

        return table

    def get_full_info(self, pkg_spec):
        subj = ModuleSubject(pkg_spec)
        module_version, nsvcap = subj.find_module_version(self)
        return module_version.module_metadata.dumps().rstrip("\n")

    def list_module_version_latest(self):
        versions = []

        for module in self.values():
            for stream in module.values():
                versions.append(stream.latest())

        return versions

    def list_module_version_all(self):
        versions = []

        for module in self.values():
            for stream in module.values():
                for version in stream.values():
                    versions.append(version)

        return versions

    def list_module_version_enabled(self):
        versions = []

        for version in self.list_module_version_all():
            conf = version.parent.parent.conf
            if conf is not None and conf.enabled and conf.stream == version.parent.stream:
                versions.append(version)

        return versions

    def list_module_version_disabled(self):
        versions = []

        for version in self.list_module_version_all():
            conf = version.parent.parent.conf
            if conf is None or not conf.enabled or version.stream != conf.stream:
                versions.append(version)

        return versions

    def list_module_version_installed(self):
        versions = []

        for version in self.list_module_version_all():
            conf = version.parent.parent.conf
            if conf is not None and conf.enabled and conf.version:
                versions.append(version)

        return versions

    def get_brief_description_latest(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_latest())

    def get_brief_description_all(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_all())

    def get_brief_description_enabled(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_enabled())

    def get_brief_description_disabled(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_disabled())

    def get_brief_description_installed(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_installed(),
                                                  True)

    def get_brief_description_by_name(self, module_n, repo_module_versions, only_installed=False):
        if module_n is None or not module_n:
            return self._get_brief_description(repo_module_versions, only_installed)
        else:
            filtered_versions_by_name = set()
            for name in module_n:
                for version in repo_module_versions:
                    if fnmatch.fnmatch(version.name, name):
                        filtered_versions_by_name.add(version)

            return self._get_brief_description(list(filtered_versions_by_name), only_installed)

    @staticmethod
    def _get_brief_description(repo_module_versions, only_installed=False):
        if only_installed:
            only_installed_versions = []
            for i in repo_module_versions:
                conf = i.parent.parent.conf
                if int(conf.version) == int(i.version) and conf.stream == i.stream:
                    only_installed_versions.append(i)
            repo_module_versions = only_installed_versions

        if not repo_module_versions:
            return module_errors[NOTHING_TO_SHOW]

        table = smartcols.Table()
        table.maxout = True

        column_name = table.new_column("Name")
        column_stream = table.new_column("Stream")
        column_version = table.new_column("Version")
        column_repo = table.new_column("Repo")
        column_installed = table.new_column("Installed")
        column_info = table.new_column("Info")

        for i in sorted(repo_module_versions, key=lambda data: data.name):
            line = table.new_line()
            conf = i.parent.parent.conf
            data = i.module_metadata
            line[column_name] = data.name
            line[column_stream] = data.stream
            line[column_version] = str(data.version)
            line[column_repo] = i.repo.id
            if conf and conf.version == i.version and conf.stream == i.stream:
                line[column_installed] = ", ".join(conf.profiles)
            line[column_info] = data.summary

        return table
