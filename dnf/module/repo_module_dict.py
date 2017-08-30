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
from dnf.module import module_errors, VERSION_LOCKED, STREAM_NOT_ENABLED_ERR, \
    PROFILE_NOT_INSTALLED, NOTHING_TO_SHOW, \
    NO_DEFAULT_STREAM_ERR, NO_PROFILE_SPECIFIED, INSTALLING_NEWER_VERSION
from dnf.module.repo_module import RepoModule
from dnf.module.subject import ModuleSubject
from dnf.util import first_not_none, logger, ensure_dir


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

            if not stream:
                # TODO change to NoDefaultStreamException
                raise Error(module_errors[NO_DEFAULT_STREAM_ERR].format(name))

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

    def get_includes_latest(self, name, stream):
        includes = set()
        repos = set()
        try:
            repo_module = self[name]
            repo_module_stream = repo_module[stream]
            repo_module_version = repo_module_stream.latest()

            artifacts = repo_module_version.nevra()
            repos.add(repo_module_version.repo)
            includes.update(artifacts)

            for requires_name, requires_stream in \
                    repo_module_version.module_metadata.requires.items():

                # HACK: temporary fix for data issues in F26 Boltron repo
                if requires_name == "bootstrap" and requires_stream == "master":
                    requires_name = "base-runtime"
                    requires_stream = "f26"
                    includes.update(["hostname-0:3.18-2.module_329fd369.x86_64"])

                requires_includes, requires_repos = self.get_includes_latest(requires_name,
                                                                             requires_stream)
                repos.update(requires_repos)
                includes.update(requires_includes)
        except KeyError as e:
            logger.debug(e)

        return includes, repos

    def get_includes(self, name, stream):
        includes = set()
        repos = set()
        try:
            repo_module = self[name]
            repo_module_stream = repo_module[stream]
            for repo_module_version in repo_module_stream.values():
                artifacts = repo_module_version.nevra()
                repos.add(repo_module_version.repo)
                includes.update(artifacts)

                for requires_name, requires_stream in \
                        repo_module_version.module_metadata.requires.items():

                    # HACK: temporary fix for data issues in F26 Boltron repo
                    if requires_name == "bootstrap" and requires_stream == "master":
                        requires_name = "base-runtime"
                        requires_stream = "f26"
                        includes.update(["hostname-0:3.18-2.module_329fd369.x86_64"])

                    requires_includes, requires_repos = self.get_includes(requires_name,
                                                                          requires_stream)
                    repos.update(requires_repos)
                    includes.update(requires_includes)
        except KeyError as e:
            logger.debug(e)

        return includes, repos

    def enable(self, module_spec):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        self[module_version.name].enable(module_version.stream, self.base.conf.assumeyes)

    def disable(self, module_spec):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        repo_module = module_version.repo_module
        repo_module.disable()

    def lock(self, module_spec):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        repo_module = module_version.repo_module

        if not repo_module.conf.enabled:
            raise Error(module_errors[STREAM_NOT_ENABLED_ERR].format(module_spec))

        repo_module.lock(module_version.version)

    def unlock(self, module_spec):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        repo_module = module_version.repo_module

        if not repo_module.conf.enabled:
            raise Error(module_errors[STREAM_NOT_ENABLED_ERR].format(module_spec))

        repo_module.unlock()

    def install(self, module_specs):
        versions, module_specs = self.get_best_versions(module_specs)

        for module_version, profiles, default_profiles in versions.values():
            if module_version.repo_module.conf.locked:
                logger.warning(module_errors[VERSION_LOCKED]
                               .format(module_version.name,
                                       module_version.repo_module.conf.version))
                continue

            self.enable("{}:{}".format(module_version.name, module_version.stream))

            if module_version.version > module_version.repo_module.conf.version:
                profiles.extend(module_version.repo_module.conf.profiles)
                profiles = list(set(profiles))

            module_version.install(profiles, default_profiles)

        return module_specs

    def get_best_versions(self, module_specs):
        best_versions = {}
        skipped = []
        for module_spec in module_specs:
            subj = ModuleSubject(module_spec)

            try:
                module_version, module_form = subj.find_module_version(self)
            except Error:
                skipped.append(module_spec)
                continue

            key = "{}:{}".format(module_version.name, module_version.stream)
            if key in best_versions:
                best_version, profiles, default_profiles = best_versions[key]

                if module_form.profile:
                    profiles.append(module_form.profile)
                else:
                    default_profiles.extend(module_version.repo_module.defaults.profiles)

                if best_version < module_version:
                    logger.info(module_errors[INSTALLING_NEWER_VERSION].format(best_version,
                                                                               module_version))
                    best_versions[key] = [module_version, profiles, default_profiles]
                else:
                    best_versions[key] = [best_version, profiles, default_profiles]
            else:
                default_profiles = []
                profiles = [module_form.profile]
                if not module_form.profile:
                    if not module_version.repo_module.defaults:
                        raise Error(module_errors[NO_PROFILE_SPECIFIED].format(key))
                    default_profiles = module_version.repo_module.defaults.profiles
                    profiles = []

                best_versions[key] = [module_version, profiles, default_profiles]

        return best_versions, skipped

    def upgrade(self, module_specs):
        for module_spec in module_specs:
            subj = ModuleSubject(module_spec)
            module_version, module_form = subj.find_module_version(self)

            if module_version.repo_module.conf.locked:
                continue

            conf = self[module_form.name].conf
            if conf:
                installed_profiles = conf.profiles
            else:
                installed_profiles = []
            if module_form.profile:
                if module_form.profile not in installed_profiles:
                    raise Error(module_errors[PROFILE_NOT_INSTALLED].format(module_spec))
                profiles = [module_form.profile]
            else:
                profiles = installed_profiles

            module_specs.remove(module_spec)
            module_version.upgrade(profiles)

        return module_specs

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

    def remove(self, module_specs):
        for module_spec in module_specs:
            subj = ModuleSubject(module_spec)
            module_version, module_form = subj.find_module_version(self)

            conf = self[module_form.name].conf
            if conf:
                installed_profiles = conf.profiles
            else:
                installed_profiles = []
            if module_form.profile:
                if module_form.profile not in installed_profiles:
                    raise Error(module_errors[PROFILE_NOT_INSTALLED].format(module_spec))
                profiles = [module_form.profile]
            else:
                profiles = installed_profiles

            module_version.remove(profiles)

    def read_all_module_confs(self):
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

    def get_info_profiles(self, module_spec):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        table = smartcols.Table()
        table.noheadings = True
        table.column_separator = " : "

        column_name = table.new_column("Name")
        column_value = table.new_column("Value")
        column_value.wrap = True

        line = table.new_line()
        line[column_name] = "Name"
        line[column_value] = module_version.full_version

        for profile in module_version.profiles:
            line = table.new_line()
            line[column_name] = profile
            line[column_value] = ", ".join(module_version.profile_nevra(profile))

        return table

    def get_info(self, module_spec):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        default_str = ""
        default_profiles = []
        if module_version.repo_module.defaults:
            default_stream = module_version.repo_module.defaults.stream
            default_str = " (default)" if module_version.stream == default_stream else ""

            default_profiles = module_version.repo_module.defaults.profiles

        lines = {"Name": module_version.name,
                 "Stream": module_version.stream + default_str,
                 "Version": module_version.version,
                 "Profiles": ", ".join(module_version.profiles),
                 "Default profiles": ", ".join(default_profiles),
                 "Repo": module_version.repo.id,
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

    def get_full_info(self, module_spec):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

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
            if conf is not None and conf.enabled and conf.stream == version.stream:
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
            if conf is not None and conf.enabled and conf.version == version.version and \
                    conf.stream == version.stream:
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
        column_profiles = table.new_column("Profiles")
        column_profiles.wrap = True
        column_installed = table.new_column("Installed")
        column_installed.wrap = True
        column_info = table.new_column("Info")
        column_info.wrap = True

        for i in sorted(repo_module_versions, key=lambda data: data.name):
            line = table.new_line()
            conf = i.repo_module.conf
            defaults_conf = i.repo_module.defaults
            data = i.module_metadata
            line[column_name] = data.name
            default_str = ""
            if defaults_conf and i.stream == defaults_conf.stream:
                default_str = " (default)"
            line[column_stream] = data.stream + default_str
            line[column_version] = str(data.version)

            available_profiles = i.profiles
            installed_profiles = []
            if conf and conf.version == i.version and conf.stream == i.stream:
                installed_profiles = conf.profiles
                available_profiles = [x for x in available_profiles if x not in installed_profiles]

            number_of_available_profiles = len(available_profiles)
            number_of_installed_profiles = len(installed_profiles)

            trunc_available = ""
            trunc_installed = ""

            if number_of_available_profiles > 2:
                trunc_available = ", ... ({}/{})".format(number_of_available_profiles - 2,
                                                         number_of_available_profiles)
            if number_of_installed_profiles > 2:
                trunc_installed = ", ... ({}/{})".format(number_of_installed_profiles - 2,
                                                         number_of_installed_profiles)

            line[column_profiles] = ", ".join(available_profiles[:2]) + trunc_available
            line[column_installed] = ", ".join(installed_profiles[:2]) + trunc_installed
            line[column_info] = data.summary

        return table
