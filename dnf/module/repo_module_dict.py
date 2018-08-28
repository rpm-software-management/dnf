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
import libdnf.module
import dnf.selector

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
from dnf.i18n import _, P_, ucd

STATE_DEFAULT = libdnf.module.ModulePackageContainer.ModuleState_DEFAULT
STATE_ENABLED = libdnf.module.ModulePackageContainer.ModuleState_ENABLED

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

    def _get_modules(self, module_spec):
        subj = hawkey.Subject(module_spec)
        for nsvcap in subj.nsvcap_possibilities():
            name = nsvcap.name if nsvcap.name else ""
            stream = nsvcap.stream if nsvcap.stream else ""
            version = ""
            context = nsvcap.context if nsvcap.context else ""
            arch = nsvcap.arch if nsvcap.arch else ""
            if nsvcap.version and nsvcap.version != -1:
                version = str(nsvcap.version)
            modules = self.base._moduleContainer.query(name, stream, version, context, arch)
            if modules:
                return modules, nsvcap
        return None, None

    def _get_latest(self, module_list):
        latest = None
        if module_list:
            latest = module_list[0]
            for module in module_list[1:]:
                if module.getVersion() > latest.getVersion():
                    latest = module
        return latest

        module_list.sort(reverse=True, key=lambda x: x.getVersion())

    def _create_module_dict_and_enable(self, module_list, enable = True):
        moduleDict = {}
        for module in module_list:
            moduleDict.setdefault(
                module.getName(), {}).setdefault(module.getStream(), []).append(module)

        for moduleName, streamDict in moduleDict.items():
            moduleState = self.base._moduleContainer.getModuleState(moduleName)
            if len(streamDict) > 1:
                if moduleState != STATE_DEFAULT and moduleState != STATE_ENABLED:
                    raise EnableMultipleStreamsException(moduleName)
                if moduleState == STATE_ENABLED:
                    stream = self.base._moduleContainer.getEnabledStream(moduleName)
                else:
                    stream = self.base._moduleContainer.getDefaultStream(moduleName)
                if stream not in streamDict:
                    raise EnableMultipleStreamsException(moduleName)
                for key in sorted(streamDict.keys()):
                    if key == stream:
                        if enable:
                            self.base._moduleContainer.enable(moduleName, key)
                        continue
                    del streamDict[key]
            elif enable:
                for key in streamDict.keys():
                    self.base._moduleContainer.enable(moduleName, key)
            assert len(streamDict) == 1
        return moduleDict

    def install(self, module_specs, strict=True):
        no_match_specs = []
        error_spec = []
        module_dicts = {}
        for spec in set(module_specs):
            module_list, nsvcap = self._get_modules(spec)
            if module_list is None:
                no_match_specs.append(spec)
                continue
            try:
                module_dict = self._create_module_dict_and_enable(module_list)
                module_dicts[spec] = (nsvcap, module_dict)
            except (RuntimeError, EnableMultipleStreamsException) as e:
                error_spec.append(spec)
                logger.error(ucd(e))
                logger.error(_("Unable to resolve argument {}").format(spec))
        hot_fix_repos = [i.id for i in self.base.repos.iter_enabled() if i.module_hotfixes]
        self.base.sack.filter_modules(self.base._moduleContainer, hot_fix_repos,
                                      self.base.conf.installroot, None)

        # <package_name, set_of_spec>
        install_dict = {}
        install_set_artefacts = set()
        for spec, (nsvcap, moduledict) in module_dicts.items():
            for name, streamdict in moduledict.items():
                for stream, module_list in streamdict.items():
                    latest_module = self._get_latest()
                    install_module_list = [x for x in module_list if self.base._moduleContainer.isModuleActive(x.getId())]
                    if not install_module_list:
                        logger.error(_("Unable to resolve argument {}").format(spec))
                        error_spec.append(spec)
                        continue
                    profiles = []
                    latest_module = self._get_latest(install_module_list)
                    if nsvcap.profile:
                        profiles.extend(latest_module.getProfiles(nsvcap.profile))
                        if not profiles:
                            logger.error(_("Unable to match profile in argument {}").format(spec))
                            error_spec.append(spec)
                            continue
                    else:
                        profiles_strings = self.base._moduleContainer.getDefaultProfiles(name, stream)
                        if not profiles_strings:
                            logger.error(_("No default profiles for module {}:{}").format(name, stream))
                            profiles_strings = ['default']
                        for profile in set(profiles_strings):
                            module_profiles = latest_module.getProfiles(profile)
                            if not module_profiles:
                                logger.error(_("Default profile {} not matched for module {}:{}").format(profile, name,
                                                                                                         stream))
                            profiles.extend(module_profiles)
                    for profile in profiles:
                        self.base._moduleContainer.install(latest_module ,profile.getName())
                        for pkg_name in profile.getContent():
                            install_dict.setdefault(pkg_name, set()).add(spec)
                    for module in install_module_list:
                        install_set_artefacts.update(module.getArtifacts())
        install_base_query = self.base.sack.query().filterm(nevra_strict=install_set_artefacts).apply()

        for pkg_name, set_specs in install_dict.items():
            query = install_base_query.filter(name=pkg_name)
            if not query:
                for spec in set_specs:
                    logger.error(_("Unable to resolve argument {}").format(spec))
                logger.error(_("No match for package {}").format(pkg_name))
                error_spec.extend(set_specs)
                continue
            self.base._goal.group_members.add(pkg_name)
            sltr = dnf.selector.Selector(self.base.sack)
            sltr.set(pkg=query)
            self.base._goal.install(select=sltr, optional=(not strict))
        # TODO reise exception and return specks with problem
        return no_match_specs

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

    def _get_package_name_set_and_remove_profiles(self, module_list, nsvcap, remove=False):
        package_name_set = set()
        latest_module = self._get_latest(module_list)
        installed_profiles_strings = set(self.base._moduleContainer.getInstalledProfiles(latest_module.getName()))
        if not installed_profiles_strings:
            return set()
        if nsvcap.profile:
            profiles_set = latest_module.getProfiles(nsvcap.profile)
            if not profiles_set:
                return set()
            for profile in profiles_set:
                if profile.getName() in installed_profiles_strings:
                    if remove:
                        self.base._moduleContainer.uninstall(latest_module, profile.getName())
                    package_name_set.update(profile.getContent())
        else:
            for profile_string in installed_profiles_strings:
                if remove:
                    self.base._moduleContainer.uninstall(latest_module, profile_string)
                for profile in latest_module.getProfiles(profile_string):
                    package_name_set.update(profile.getContent())
        return package_name_set

    def upgrade(self, module_specs):
        no_match_specs = []

        for spec in set(module_specs):
            module_list, nsvcap = self._get_modules(spec)
            if module_list is None:
                no_match_specs.append(spec)
                continue
            update_module_list = [x for x in module_list if self.base._moduleContainer.isModuleActive(x.getId())]
            if not update_module_list:
                logger.error(_("Unable to resolve argument {}").format(spec))
                continue
            module_dict = self._create_module_dict_and_enable(update_module_list, False)
            upgrade_package_set = set()
            for name, streamdict in module_dict.items():
                for stream, module_list_from_dict in streamdict.items():
                    upgrade_package_set.update(self._get_package_name_set_and_remove_profiles(module_list_from_dict, nsvcap))
                    latest_module = self._get_latest(module_list_from_dict)
                    installed_profiles_strings = set(self.base._moduleContainer.getInstalledProfiles(latest_module.getName()))
                    if not installed_profiles_strings:
                        continue
                    if nsvcap.profile:
                        profiles_set = latest_module.getProfiles(nsvcap.profile)
                        if not profiles_set:
                            continue
                        for profile in profiles_set:
                            if profile.getName() in installed_profiles_strings:
                                upgrade_package_set.update(profile.getContent())
                    else:
                        for profile_string in installed_profiles_strings:
                            for profile in latest_module.getProfiles(profile_string):
                                upgrade_package_set.update(profile.getContent())
            if not upgrade_package_set:
                logger.error(_("Unable to match profile in argument {}").format(spec))
            query = self.base.sack.query().available().filterm(name=upgrade_package_set)
            if query:
                sltr = Selector(self.base.sack)
                sltr.set(pkg=query)
                self.base._goal.upgrade(select=sltr)
        return no_match_specs

    def remove(self, module_specs):
        no_match_specs = []
        remove_package_set = set()

        for spec in set(module_specs):
            module_list, nsvcap = self._get_modules(spec)
            if module_list is None:
                no_match_specs.append(spec)
                continue
            module_dict = self._create_module_dict_and_enable(module_list, False)
            remove_packages_names = []
            for name, streamdict in module_dict.items():
                for stream, module_list_from_dict in streamdict.items():
                    remove_packages_names.extend(self._get_package_name_set_and_remove_profiles(module_list_from_dict, nsvcap, True))
            if not remove_packages_names:
                logger.error(_("Unable to match profile in argument {}").format(spec))
            remove_package_set.update(remove_packages_names)

        if remove_package_set:
            keep_pkg_names = self.base._moduleContainer.getInstalledPkgNames()
            remove_package_set.difference(keep_pkg_names)
            if remove_package_set:
                query = self.base.sack.query().installed().filterm(name=remove_package_set)
                if query:
                    self.base._remove_if_unneeded(query)
        return no_match_specs

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
        str_table = self.print_header(table, repo_id)
        for i in range(0, table.getNumberOfLines()):
            if len(versions) + already_printed_lines <= i:
                already_printed_lines += len(versions)
                current_repo_id_index += 1

                repo_id, versions = items[current_repo_id_index]
                str_table += "\n"
                str_table += self.print_header(table, repo_id)

            line = table.getLine(i)
            str_table += table.toString(line, line)

        return str_table + "\n\nHint: [d]efault, [e]nabled, [i]nstalled"

    def print_header(self, table, repo_id):
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
