# Copyright (C) 2017-2018  Red Hat, Inc.
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

import hawkey
import libdnf.smartcols

from dnf.conf.read import ModuleReader
from dnf.module import module_messages, NOTHING_TO_SHOW, \
    INSTALLING_NEWER_VERSION, ENABLED_MODULES
from dnf.module.exceptions import NoStreamSpecifiedException, NoModuleException, \
    ProfileNotInstalledException, NoProfileToRemoveException, \
    DifferentStreamEnabledException, EnableMultipleStreamsException
from dnf.module.repo_module import RepoModule
from dnf.module.subject import ModuleSubject
from dnf.selector import Selector
from dnf.subject import Subject
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
            if repo_module.conf.state._get() == "enabled":
                return repo_module.conf.stream._get()
            return None

        def use_default_stream(repo_module):
            return repo_module.defaults.peek_default_stream()

        try:
            repo_module = self[name]

            stream = first_not_none([stream,
                                     use_enabled_stream(repo_module),
                                     use_default_stream(repo_module)])

            if not stream:
                raise NoStreamSpecifiedException(name)

            repo_module_stream = repo_module[stream]

            if version:
                repo_module_version = repo_module_stream[version]
            else:
                # if version is not specified, pick the latest
                repo_module_version = repo_module_stream.latest()

            # TODO: arch
            # TODO: platform module

        except KeyError:
            return None
        return repo_module_version

    def get_module_dependency_latest(self, name, stream, visited=None):
        visited = visited or set()
        version_dependencies = set()

        try:
            repo_module = self[name]
            repo_module_stream = repo_module[stream]
            repo_module_version = repo_module_stream.latest()
            version_dependencies.add(repo_module_version)

            for requires_name, requires_streams in \
                    repo_module_version.requires().items():
                for requires_stream in requires_streams:
                    if requires_stream[0] == '-':
                        continue
                    requires_ns = "{}:{}".format(requires_name, requires_stream)
                    if requires_ns in visited:
                        continue
                    visited.add(requires_ns)
                    version_dependencies.update(self.get_module_dependency_latest(requires_name,
                                                                                  requires_stream,
                                                                                  visited))
        except KeyError as e:
            logger.debug(e)

        return version_dependencies

    def get_module_dependency(self, name, stream, visited=None):
        visited = visited or set()
        version_dependencies = set()

        try:
            repo_module = self[name]
            repo_module_stream = repo_module[stream]

            versions = repo_module_stream.values()

            for repo_module_version in versions:
                version_dependencies.add(repo_module_version)

                for requires_name, requires_streams in \
                        repo_module_version.requires().items():
                    for requires_stream in requires_streams:
                        if requires_stream[0] == '-':
                            continue
                        requires_ns = "{}:{}".format(requires_name, requires_stream)
                        if requires_ns in visited:
                            continue
                        visited.add(requires_ns)
                        version_dependencies.update(
                            self.get_module_dependency_latest(requires_name,
                                                              requires_stream,
                                                              visited))
        except KeyError as e:
            logger.debug(e)

        return version_dependencies

    def enable_by_version(self, module_version, save_immediately=False):
        self.base._moduleContainer.enable(module_version.name, module_version.stream)
        # re-compute enabled streams and filtered RPMs
        hot_fix_repos = [i.id for i in self.base.repos.iter_enabled() if i.module_hotfixes]
        self.base.sack.filter_modules(self.base._moduleContainer, hot_fix_repos,
                                      self.base.conf.installroot, self.base.conf.module_platform_id,
                                      update_only=True)

        # TODO: remove; temporary workaround for syncing RepoModule.conf with libdnf
        self[module_version.name].conf.stream._set(module_version.stream)
        self[module_version.name].conf.state._set("enabled")

        if save_immediately:
            self.base._moduleContainer.save()

    def enable(self, module_spec, save_immediately=False):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        self.enable_by_version(module_version, save_immediately)

    def disable_by_version(self, module_version, save_immediately=False):
        self.base._moduleContainer.disable(module_version.name, module_version.stream)

        # re-compute enabled streams and filtered RPMs
        hot_fix_repos = [i.id for i in self.base.repos.iter_enabled() if i.module_hotfixes]
        self.base.sack.filter_modules(self.base._moduleContainer, hot_fix_repos,
                                      self.base.conf.installroot, self.base.conf.module_platform_id,
                                      update_only=True)

        # TODO: remove; temporary workaround for syncing RepoModule.conf with libdnf
        self[module_version.name].conf.profiles._set("")
        self[module_version.name].conf.state._set("disabled")

        if save_immediately:
            self.base._moduleContainer.save()

    def disable(self, module_spec, save_immediately=False):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        self.disable_by_version(module_version, save_immediately)

    def reset_by_version(self, module_version, save_immediately=False):
        self.base._moduleContainer.reset(module_version.name)

        # re-compute enabled streams and filtered RPMs
        hot_fix_repos = [i.id for i in self.base.repos.iter_enabled() if i.module_hotfixes]
        self.base.sack.filter_modules(self.base._moduleContainer, hot_fix_repos,
                                      self.base.conf.installroot, self.base.conf.module_platform_id,
                                      update_only=True)

        # TODO: remove; temporary workaround for syncing RepoModule.conf with libdnf
        self[module_version.name].conf.profiles._set("")
        self[module_version.name].conf.state._set("")

        if save_immediately:
            self.base._moduleContainer.save()

    def reset(self, module_spec, save_immediately=False):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        self.reset_by_version(module_version, save_immediately)

    def install(self, module_specs, strict=True):
        versions, module_specs = self.get_best_versions(module_specs)

        result = False
        for module_version, profiles, default_profiles in versions.values():
            self.enable_by_version(module_version)
            self.base._moduleContainer.enable(
                module_version.name, module_version.stream)

        hot_fix_repos = [i.id for i in self.base.repos.iter_enabled() if i.module_hotfixes]
        self.base.sack.filter_modules(self.base._moduleContainer, hot_fix_repos,
                                      self.base.conf.installroot, self.base.conf.module_platform_id,
                                      update_only=True)

        for module_version, profiles, default_profiles in versions.values():
            profiles = sorted(set(profiles))
            default_profiles = sorted(set(default_profiles))

            if profiles or default_profiles:
                result |= module_version.install(profiles, default_profiles, strict)

        if not result and versions:
            module_versions = ["{}:{}".format(module_version.name, module_version.stream)
                               for module_version, profiles, default_profiles in versions.values()]
            logger.info(module_messages[ENABLED_MODULES].format(", ".join(module_versions)))

        return module_specs

    def get_best_versions(self, module_specs):
        best_versions = {}
        skipped = []
        for module_spec in module_specs:
            subj = ModuleSubject(module_spec)

            try:
                module_version, module_form = subj.find_module_version(self)
            except NoModuleException:
                skipped.append(module_spec)
                continue

            key = module_version.name
            if key in best_versions:
                best_version, profiles, default_profiles = best_versions[key]
                if best_version.stream != module_version.stream:
                    raise EnableMultipleStreamsException(module_version.name)

                if module_form.profile:
                    profiles.append(module_form.profile)
                else:
                    stream = module_form.stream or module_version.repo_module.defaults \
                        .peek_default_stream()
                    profile_defaults = module_version.repo_module.defaults.peek_profile_defaults()
                    if stream in profile_defaults:
                        default_profiles.extend(profile_defaults[stream].dup())

                if best_version < module_version:
                    logger.info(module_messages[INSTALLING_NEWER_VERSION].format(best_version,
                                                                                 module_version))
                    best_versions[key] = [module_version, profiles, default_profiles]
                else:
                    best_versions[key] = [best_version, profiles, default_profiles]
            else:
                default_profiles = []
                profiles = []

                stream = module_form.stream or module_version.repo_module.defaults \
                    .peek_default_stream()
                profile_defaults = module_version.repo_module.defaults.peek_profile_defaults()
                if stream in profile_defaults:
                    default_profiles.extend(profile_defaults[stream].dup())

                if module_form.profile:
                    profiles = [module_form.profile]
                elif default_profiles:
                    profiles = []
                else:
                    default_profiles = ['default']

                best_versions[key] = [module_version, profiles, default_profiles]

        return best_versions, skipped

    def upgrade(self, module_specs, create_goal=False):
        skipped = []
        query = None

        module_versions = []
        for module_spec in module_specs:
            subj = ModuleSubject(module_spec)
            try:
                module_version, module_form = subj.find_module_version(self)
                module_versions.append(module_version)

                # in case there is new dependency
                self.enable_by_version(module_version)
            except NoModuleException:
                skipped.append(module_spec)
                continue
            except NoStreamSpecifiedException:
                continue

        hot_fix_repos = [i.id for i in self.base.repos.iter_enabled() if i.module_hotfixes]
        self.base.sack.filter_modules(self.base._moduleContainer, hot_fix_repos,
                                      self.base.conf.installroot, self.base.conf.module_platform_id,
                                      update_only=True)

        for module_version in module_versions:
            if module_version.repo_module.conf.state._get() != "enabled":
                continue

            conf = self[module_form.name].conf
            if conf:
                installed_profiles = list(conf.profiles._get())
            else:
                installed_profiles = []
            if module_form.profile:
                if module_form.profile not in installed_profiles:
                    raise ProfileNotInstalledException(module_version.name)
                profiles = [module_form.profile]
            else:
                profiles = installed_profiles

            if not profiles:
                continue

            returned_query = module_version.upgrade(profiles)
            if query is None and returned_query:
                query = returned_query
            elif returned_query:
                query = query.union(returned_query)

        if create_goal and query:
            sltr = Selector(self.base.sack)
            sltr.set(pkg=query)
            self.base._goal.upgrade(select=sltr)

        return skipped

    def remove(self, module_specs):
        skipped = []
        for module_spec in module_specs:
            subj = ModuleSubject(module_spec)

            try:
                module_version, module_form = subj.find_module_version(self)
            except NoModuleException:
                # TODO: report skipped module specs to the user
                skipped.append(module_spec)
                continue

            conf = self[module_form.name].conf
            if module_version.stream != conf.stream._get():
                raise DifferentStreamEnabledException(module_form.name)

            if list(conf.profiles._get()):
                installed_profiles = list(conf.profiles._get())
            else:
                raise NoProfileToRemoveException(module_spec)
            if module_form.profile:
                if module_form.profile not in installed_profiles:
                    raise ProfileNotInstalledException(module_spec)
                profiles = [module_form.profile]
            else:
                profiles = installed_profiles

            module_version.remove(profiles)
        return skipped

    def read_all_module_confs(self):
        module_reader = ModuleReader(self.get_modules_dir())
        for conf in module_reader:
            repo_module = self.setdefault(conf.name._get(), RepoModule())
            repo_module.conf = conf
            repo_module.name = conf.name._get()
            repo_module.parent = self

    def get_modules_dir(self):
        modules_dir = os.path.join(self.base.conf.installroot,
                                   self.base.conf.modulesdir._get().lstrip("/"))

        ensure_dir(modules_dir)

        return modules_dir

    def get_module_defaults_dir(self):
        return self.base.conf.moduledefaultsdir._get()

    def get_info_profiles(self, module_spec):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        if module_form.profile:
            logger.info("Ignoring unnecessary profile: '{}/{}'".format(module_form.name,
                                                                       module_form.profile))

        lines = OrderedDict()
        lines["Name"] = module_version.full_version

        for profile in module_version.profiles:
            nevra_objects = module_version.profile_nevra_objects(profile)
            lines[profile] = "\n".join(["{}-{}".format(nevra.name, nevra.evr())
                                        for nevra in nevra_objects])

        return self.create_simple_table(lines).toString()

    def get_info(self, module_spec):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        if module_form.profile:
            logger.info("Ignoring unnecessary profile: '{}/{}'".format(module_form.name,
                                                                       module_form.profile))

        conf = module_version.repo_module.conf

        default_stream = module_version.repo_module.defaults.peek_default_stream()
        default_str = " [d]" if module_version.stream == default_stream else ""
        enabled_str = ""
        if module_version.stream == conf.stream._get() and conf.state._get() == "enabled":
            if not default_str:
                enabled_str = " "
            enabled_str += "[e]"

        default_profiles = []
        stream = module_form.stream or module_version.repo_module.defaults.peek_default_stream()
        profile_defaults = module_version.repo_module.defaults.peek_profile_defaults()
        if stream in profile_defaults:
            default_profiles.extend(profile_defaults[stream].dup())

        profiles_str = ""
        available_profiles = module_version.profiles
        installed_profiles = []

        if module_version.stream == conf.stream._get():
            installed_profiles = list(conf.profiles._get())

        for profile in available_profiles:
            profiles_str += "{}{}".format(profile,
                                          " [d]" if profile in default_profiles else "")
            profiles_str += "[i], " if profile in installed_profiles else ", "

        profiles_str = profiles_str[:-2]

        lines = OrderedDict()
        lines["Name"] = module_version.name
        lines["Stream"] = module_version.stream + default_str + enabled_str
        lines["Version"] = module_version.version
        lines["Profiles"] = profiles_str
        lines["Default profiles"] = " ".join(default_profiles)
        lines["Repo"] = module_version.repo.id
        lines["Summary"] = module_version.summary()
        lines["Description"] = module_version.description()
        lines["Artifacts"] = "\n".join(sorted(module_version.artifacts()))

        str_table = self.create_simple_table(lines).toString()

        return str_table + "\n\nHint: [d]efault, [e]nabled, [i]nstalled"

    @staticmethod
    def create_simple_table(lines):
        table = libdnf.smartcols.Table()
        table.enableNoheadings(True)
        table.setColumnSeparator(" : ")

        column_name = table.newColumn("Name")
        column_value = table.newColumn("Value")
        column_value.setWrap(True)
        column_value.setSafechars("\n")
        column_value.setNewlineWrapFunction()

        for line_name, value in lines.items():
            if value:
                line = table.newLine()
                line.getColumnCell(column_name).setData(line_name)
                line.getColumnCell(column_value).setData(str(value))

        return table

    def get_full_info(self, module_spec):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        if module_form.profile:
            logger.info("Ignoring unnecessary profile: '{}/{}'".format(module_form.name,
                                                                       module_form.profile))

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

        for version in self.list_module_version_latest():
            conf = version.repo_module.conf
            if conf.state._get() == "enabled" and conf.stream._get() == version.stream:
                versions.append(version)

        return versions

    def list_module_version_disabled(self):
        versions = []

        for version in self.list_module_version_latest():
            conf = version.repo_module.conf
            if conf.state._get() != "enabled" or version.stream != conf.stream._get():
                versions.append(version)

        return versions

    def list_module_version_installed(self):
        versions = []

        for version in self.list_module_version_latest():
            conf = version.repo_module.conf
            if conf.state._get() == "enabled" and conf.stream._get() == version.stream \
                    and list(conf.profiles._get()):
                versions.append(version)

        return versions

    def print_what_provides(self, rpms):
        output = ""
        versions = self.list_module_version_all()
        for version in versions:
            nevras = version.artifacts()
            for nevra in nevras:
                subj = Subject(nevra)
                nevra_obj = list(subj.get_nevra_possibilities(hawkey.FORM_NEVRA))[0]
                if nevra_obj.name not in rpms:
                    continue

                profiles = []
                for profile in version.profiles:
                    if nevra_obj.name in version.rpms(profile):
                        profiles.append(profile)

                lines = {"Module": version.full_version,
                         "Profiles": " ".join(profiles),
                         "Repo": version.repo.id,
                         "Summary": version.summary()}

                table = self.create_simple_table(lines)

                output += "{}\n".format(self.base.output.term.bold(nevra))
                output += "{}\n\n".format(table.toString())

        logger.info(output[:-2])

    def get_brief_description_latest(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_latest())

    def get_brief_description_enabled(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_enabled())

    def get_brief_description_disabled(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_disabled())

    def get_brief_description_installed(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_installed())

    def get_brief_description_by_name(self, module_n, repo_module_versions):
        if module_n is None or not module_n:
            return self._get_brief_description(repo_module_versions)
        else:
            filtered_versions_by_name = set()
            for name in module_n:
                for version in repo_module_versions:
                    if fnmatch.fnmatch(version.name, name):
                        filtered_versions_by_name.add(version)

            return self._get_brief_description(list(filtered_versions_by_name))

    def _get_brief_description(self, repo_module_versions):
        if not repo_module_versions:
            return module_messages[NOTHING_TO_SHOW]

        versions_by_repo = OrderedDict()
        for version in sorted(repo_module_versions, key=lambda version: version.repo.name):
            default_list = versions_by_repo.setdefault(version.repo.name, [])
            default_list.append(version)

        table = self.create_and_fill_table(versions_by_repo)

        current_repo_id_index = 0
        already_printed_lines = 0
        items = list(versions_by_repo.items())
        repo_id, versions = items[current_repo_id_index]
        header = self.get_header(table, repo_id)
        str_table = header
        for i in range(0, table.getNumberOfLines()):
            if len(versions) + already_printed_lines <= i:
                already_printed_lines += len(versions)
                current_repo_id_index += 1

                repo_id, versions = items[current_repo_id_index]
                str_table += "\n"
                str_table += header

            line = table.getLine(i)
            str_table += table.toString(line, line)

        return str_table + "\n\nHint: [d]efault, [e]nabled, [i]nstalled"

    def get_header(self, table, repo_id):
        line = table.getLine(0)
        header = table.toString(line, line).split('\n', 1)[0]
        out_str = "{}\n".format(self.base.output.term.bold(repo_id))
        out_str += "{}\n".format(header)
        return out_str

    def create_and_fill_table(self, versions_by_repo):
        table = libdnf.smartcols.Table()
        table.setTermforce(libdnf.smartcols.Table.TermForce_ALWAYS)
        table.enableMaxout(True)
        column_name = table.newColumn("Name")
        column_stream = table.newColumn("Stream")
        column_profiles = table.newColumn("Profiles")
        column_profiles.setWrap(True)
        column_info = table.newColumn("Summary")
        column_info.setWrap(True)

        if not self.base.conf.verbose:
            column_info.hidden = True

        for repo_id, versions in versions_by_repo.items():
            for i in sorted(versions):
                line = table.newLine()
                conf = i.repo_module.conf
                defaults_conf = i.repo_module.defaults
                default_str = ""
                enabled_str = ""
                profiles_str = ""
                available_profiles = i.profiles
                installed_profiles = []

                if i.stream == defaults_conf.peek_default_stream():
                    default_str = " [d]"

                if i.stream == conf.stream._get() and conf.state._get() == "enabled":
                    if not default_str:
                        enabled_str = " "
                    enabled_str += "[e]"

                if i.stream == conf.stream._get():
                    installed_profiles = list(conf.profiles._get())

                default_profiles = []
                default_stream = defaults_conf.peek_default_stream()
                profile_defaults = defaults_conf.peek_profile_defaults()
                if default_stream in profile_defaults:
                    default_profiles.extend(profile_defaults[default_stream].dup())
                for profile in available_profiles:
                    profiles_str += "{}{}".format(profile,
                                                  " [d]" if profile in default_profiles else "")
                    profiles_str += "[i], " if profile in installed_profiles else ", "

                line.getColumnCell(column_name).setData(i.name)
                line.getColumnCell(column_stream).setData(i.stream + default_str + enabled_str)
                line.getColumnCell(column_profiles).setData(profiles_str[:-2])
                line.getColumnCell(column_info).setData(i.summary())

        return table
