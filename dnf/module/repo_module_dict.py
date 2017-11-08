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
import sys
from collections import OrderedDict

import hawkey
import smartcols

from dnf.conf.read import ModuleReader, ModuleDefaultsReader
from dnf.module import module_messages, NOTHING_TO_SHOW, \
    INSTALLING_NEWER_VERSION, NOTHING_TO_INSTALL, VERSION_LOCKED, NO_PROFILE_SPECIFIED
from dnf.module.exceptions import NoStreamSpecifiedException, NoModuleException, \
    EnabledStreamException, ProfileNotInstalledException, NoProfileSpecifiedException, \
    NoProfileToRemoveException, VersionLockedException, CannotLockVersionException
from dnf.module.repo_module import RepoModule
from dnf.module.subject import ModuleSubject
from dnf.selector import Selector
from dnf.subject import Subject
from dnf.util import first_not_none, logger, ensure_dir


def exit_dnf(message):
    logger.info(message)
    sys.exit(0)


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
            return repo_module.defaults.stream

        try:
            repo_module = self[name]

            stream = first_not_none([stream,
                                     use_enabled_stream(repo_module),
                                     use_default_stream(repo_module)])

            if not stream:
                raise NoStreamSpecifiedException(name)

            repo_module_stream = repo_module[stream]

            if repo_module.conf and \
                    repo_module.conf.locked and \
                    repo_module.conf.version is not None:
                if repo_module_stream.latest().version != repo_module.conf.version:
                    logger.info(module_messages[VERSION_LOCKED]
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

    def get_module_dependency_latest(self, name, stream, visited=None):
        visited = visited or set()
        version_dependencies = set()

        try:
            repo_module = self[name]
            repo_module_stream = repo_module[stream]
            repo_module_version = repo_module_stream.latest()
            version_dependencies.add(repo_module_version)

            for requires_name, requires_stream in \
                    repo_module_version.module_metadata.requires.items():
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
            if repo_module.conf.locked:
                versions = [repo_module_stream[repo_module.conf.version]]

            for repo_module_version in versions:
                version_dependencies.add(repo_module_version)

                for requires_name, requires_stream in \
                        repo_module_version.module_metadata.requires.items():
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

    def get_includes(self, name, stream, latest=False):
        includes = set()
        repos = set()

        if latest:
            version_dependencies = self.get_module_dependency_latest(name, stream)
        else:
            version_dependencies = self.get_module_dependency(name, stream)

        for dependency in version_dependencies:
            repos.add(dependency.repo)
            includes.update(dependency.nevra())

        return includes, repos

    def enable_based_on_rpms(self):
        not_in_enabled = set(self.base._goal.list_installs())

        for version in self.base.repo_module_dict.list_module_version_enabled():
            for pkg in self.base._goal.list_installs():
                if version.repo.id != pkg.reponame:
                    continue

                nevra = "{}-{}.{}".format(pkg.name, pkg.evr, pkg.arch)
                if nevra in version.module_metadata.artifacts.rpms and \
                        pkg in not_in_enabled:
                    not_in_enabled.remove(pkg)
                else:
                    not_in_enabled.add(pkg)

        defaults = []
        for version in self.base.repo_module_dict.list_module_version_latest():
            if version.stream == version.repo_module.defaults.stream:
                defaults.append(version)

        for version in defaults:
            for pkg in not_in_enabled:
                nevra = "{}-{}.{}".format(pkg.name, pkg.evr, pkg.arch)
                nevra_epoch_ensured = "{}-{}:{}-{}.{}".format(pkg.name, pkg.epoch, pkg.version,
                                                              pkg.release, pkg.arch)

                if nevra in version.module_metadata.artifacts.rpms or \
                        nevra_epoch_ensured in version.module_metadata.artifacts.rpms:
                    version.repo_module.enable(version.stream, True)

    def enable(self, module_spec, save_immediately=False):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        version_dependencies = self.get_module_dependency_latest(module_version.name,
                                                                 module_version.stream)

        for dependency in version_dependencies:
            self[dependency.name].enable(dependency.stream, self.base.conf.assumeyes)

        if save_immediately:
            self.base._module_persistor.commit()
            self.base._module_persistor.save()

        self.base.use_module_includes()

    def disable(self, module_spec, save_immediately=False):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        repo_module = module_version.repo_module

        if repo_module.conf.locked:
            raise VersionLockedException(module_spec, module_version.version)

        repo_module.disable()

        if save_immediately:
            self.base._module_persistor.commit()
            self.base._module_persistor.save()

    def lock(self, module_spec, save_immediately=False):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        repo_module = module_version.repo_module

        if not repo_module.conf.enabled:
            raise EnabledStreamException(module_spec)
        elif repo_module.conf.locked and \
                (repo_module.conf.stream != module_version.stream or
                 repo_module.conf.version != module_version.version):
            raise VersionLockedException(module_spec, module_version.version)

        version_to_lock = module_version.version
        if repo_module.conf.profiles:
            version_to_lock = module_version.repo_module.conf.version
        repo_module.lock(version_to_lock)

        if module_form.version and version_to_lock != module_form.version:
            raise CannotLockVersionException(module_spec, module_form.version,
                                             "Different version installed.")

        if save_immediately:
            self.base._module_persistor.commit()
            self.base._module_persistor.save()

        return module_version.stream, version_to_lock

    def unlock(self, module_spec, save_immediately=False):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        repo_module = module_version.repo_module

        if not repo_module.conf.enabled:
            raise EnabledStreamException(module_spec)

        repo_module.unlock()

        if save_immediately:
            self.base._module_persistor.commit()
            self.base._module_persistor.save()

        return module_version.stream, module_version.version

    def install(self, module_specs):
        versions, module_specs = self.get_best_versions(module_specs)

        result = False
        for module_version, profiles, default_profiles in versions.values():
            conf = module_version.repo_module.conf
            if conf.locked and conf.version != module_version.version:
                logger.warning(module_messages[VERSION_LOCKED]
                               .format(module_version.name,
                                       module_version.repo_module.conf.version))
                continue

            self.enable("{}:{}".format(module_version.name, module_version.stream))

            if module_version.version > module_version.repo_module.conf.version:
                profiles.extend(module_version.repo_module.conf.profiles)
                profiles = list(set(profiles))

            if profiles or default_profiles:
                result |= module_version.install(profiles, default_profiles)

        if not result and versions and self.base._module_persistor:
            module_versions = ["{}:{}".format(module_version.name, module_version.stream)
                               for module_version, profiles, default_profiles in versions.values()]
            self.base._module_persistor.commit()
            self.base._module_persistor.save()
            exit_dnf(module_messages[NOTHING_TO_INSTALL].format(", ".join(module_versions)))

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

            key = "{}:{}".format(module_version.name, module_version.stream)
            if key in best_versions:
                best_version, profiles, default_profiles = best_versions[key]

                if module_form.profile:
                    profiles.append(module_form.profile)
                else:
                    default_profiles.extend(module_version.repo_module.defaults.profiles)

                if best_version < module_version:
                    logger.info(module_messages[INSTALLING_NEWER_VERSION].format(best_version,
                                                                                 module_version))
                    best_versions[key] = [module_version, profiles, default_profiles]
                else:
                    best_versions[key] = [best_version, profiles, default_profiles]
            else:
                default_profiles = []
                profiles = []

                if module_form.profile:
                    profiles = [module_form.profile]
                elif module_version.repo_module.defaults.profiles:
                    default_profiles = module_version.repo_module.defaults.profiles
                    profiles = []
                else:
                    logger.info(module_messages[NO_PROFILE_SPECIFIED].format(key))

                best_versions[key] = [module_version, profiles, default_profiles]

        return best_versions, skipped

    def upgrade(self, module_specs, create_goal=False):
        skipped = []
        query = None
        query_exclude = None
        for module_spec in module_specs:
            subj = ModuleSubject(module_spec)
            try:
                module_version, module_form = subj.find_module_version(self)
            except NoModuleException:
                skipped.append(module_spec)
                continue
            except NoStreamSpecifiedException:
                continue

            if module_version.repo_module.conf.locked:
                continue
            if not module_version.repo_module.conf.enabled:
                for rpm in module_version.module_metadata.artifacts.rpms:
                    query_for_rpm = self.base.sack.query().filter(nevra=rpm)
                    if query_exclude is None:
                        query_exclude = query_for_rpm
                    else:
                        query_exclude = query_exclude.union(query_for_rpm)
                continue

            conf = self[module_form.name].conf
            if conf:
                installed_profiles = conf.profiles
            else:
                installed_profiles = []
            if module_form.profile:
                if module_form.profile not in installed_profiles:
                    raise ProfileNotInstalledException(module_spec)
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

        return skipped, query, query_exclude

    def upgrade_all(self):
        modules = []
        for module_name, repo_module in self.items():
            if not repo_module.conf:
                continue
            modules.append(module_name)
        modules.sort()
        _, query, query_exclude = self.upgrade(modules)
        return query, query_exclude

    def remove(self, module_specs):
        skipped = []
        for module_spec in module_specs:
            subj = ModuleSubject(module_spec)

            try:
                module_version, module_form = subj.find_module_version(self)
            except NoModuleException:
                skipped.append(module_spec)
                continue

            conf = self[module_form.name].conf
            if conf and conf.profiles:
                installed_profiles = conf.profiles
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

        lines = OrderedDict()
        lines["Name"] = module_version.full_version

        for profile in module_version.profiles:
            nevra_objects = module_version.profile_nevra_objects(profile)
            lines[profile] = "\n".join(["{}-{}".format(nevra.name, nevra.evr())
                                        for nevra in nevra_objects])

        return self.create_simple_table(lines)

    def get_info(self, module_spec):
        subj = ModuleSubject(module_spec)
        module_version, module_form = subj.find_module_version(self)

        default_stream = module_version.repo_module.defaults.stream
        default_str = " (default)" if module_version.stream == default_stream else ""

        default_profiles = []
        if module_version.repo_module.defaults.profiles:
            default_profiles = module_version.repo_module.defaults.profiles

        lines = OrderedDict()
        lines["Name"] = module_version.name
        lines["Stream"] = module_version.stream + default_str
        lines["Version"] = module_version.version
        lines["Profiles"] = " ".join(module_version.profiles)
        lines["Default profiles"] = " ".join(default_profiles)
        lines["Repo"] = module_version.repo.id
        lines["Summary"] = module_version.module_metadata.summary
        lines["Description"] = module_version.module_metadata.description
        lines["Artifacts"] = "\n".join(sorted(module_version.module_metadata.artifacts.rpms))

        table = self.create_simple_table(lines)

        return table

    @staticmethod
    def create_simple_table(lines):
        table = smartcols.Table()
        table.noheadings = True
        table.column_separator = " : "

        column_name = table.new_column("Name")
        column_value = table.new_column("Value")
        column_value.wrap = True
        column_value.safechars = "\n"
        column_value.set_wrapfunc(smartcols.wrapnl_chunksize,
                                  smartcols.wrapnl_nextchunk)

        for line_name, value in lines.items():
            if value:
                line = table.new_line()
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
                    conf.stream == version.stream and conf.profiles:
                versions.append(version)

        return versions

    def print_what_provides(self, rpms):
        output = ""
        versions = self.list_module_version_all()
        for version in versions:
            nevras = version.nevra()
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
                         "Summary": version.module_metadata.summary}

                table = self.create_simple_table(lines)

                output += "{}\n".format(self.base.output.term.bold(nevra))
                output += "{}\n\n".format(table)

        logger.info(output[:-2])

    def get_brief_description_latest(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_latest())

    def get_brief_description_all(self, module_n):
        return self.get_brief_description_by_name(module_n, self.list_module_version_all())

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
        lines = table.lines()

        current_repo_id_index = 0
        already_printed_lines = 0
        items = list(versions_by_repo.items())
        repo_id, versions = items[current_repo_id_index]
        str_table = self.print_header(table, repo_id)
        for i in range(0, len(lines)):
            if len(versions) + already_printed_lines <= i:
                already_printed_lines += len(versions)
                current_repo_id_index += 1

                repo_id, versions = items[current_repo_id_index]
                str_table += "\n"
                str_table += self.print_header(table, repo_id)

            str_table += table.str_line(lines[i], lines[i])

        return str_table + "\n\nHint: [d]efault, [e]nabled, [i]nstalled, [l]ocked"

    def print_header(self, table, repo_id):
        header = str(table).split('\n', 1)[0]
        out_str = "{}\n".format(self.base.output.term.bold(repo_id))
        out_str += "{}\n".format(header)
        return out_str

    def create_and_fill_table(self, versions_by_repo):
        table = smartcols.Table()
        table.termforce = 'always'
        table.maxout = True
        column_name = table.new_column("Name")
        column_stream = table.new_column("Stream")
        column_version = table.new_column("Version")
        column_profiles = table.new_column("Profiles")
        column_profiles.wrap = True
        column_info = table.new_column("Info")
        column_info.wrap = True

        if not self.base.conf.verbose:
            column_info.hidden = True

        for repo_id, versions in sorted(versions_by_repo.items(), key=lambda key: key[0]):
            for i in sorted(versions, key=lambda data: (data.name, data.stream, data.version)):
                line = table.new_line()
                conf = i.repo_module.conf
                defaults_conf = i.repo_module.defaults
                data = i.module_metadata
                default_str = ""
                enabled_str = ""
                locked_str = ""
                profiles_str = ""
                available_profiles = i.profiles
                installed_profiles = []

                if i.stream == defaults_conf.stream:
                    default_str = " [d]"

                if i.stream == conf.stream and conf.enabled:
                    if not default_str:
                        enabled_str = " "
                    enabled_str += "[e]"

                if i.stream == conf.stream and i.version == conf.version:
                    if conf.locked:
                        locked_str = " [l]"
                    installed_profiles = conf.profiles

                for profile in available_profiles[:2]:
                    profiles_str += "{}{}, ".format(profile,
                                                    " [i]" if profile in installed_profiles else "")

                profiles_str = profiles_str[:-2]
                profiles_str += ", ..." if len(available_profiles) > 2 else ""

                line[column_name] = data.name
                line[column_stream] = data.stream + default_str + enabled_str
                line[column_version] = str(data.version) + locked_str
                line[column_profiles] = profiles_str
                line[column_info] = data.summary

        return table
