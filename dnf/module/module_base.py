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

from collections import OrderedDict

import hawkey
import libdnf.smartcols
import libdnf.module
import dnf.selector
import dnf.exceptions

from dnf.module.exceptions import EnableMultipleStreamsException
from dnf.util import logger
from dnf.i18n import _, P_, ucd

import functools

STATE_DEFAULT = libdnf.module.ModulePackageContainer.ModuleState_DEFAULT
STATE_ENABLED = libdnf.module.ModulePackageContainer.ModuleState_ENABLED
STATE_DISABLED = libdnf.module.ModulePackageContainer.ModuleState_DISABLED
STATE_UNKNOWN = libdnf.module.ModulePackageContainer.ModuleState_UNKNOWN
MODULE_TABLE_HINT = _("\n\nHint: [d]efault, [e]nabled, [x]disabled, [i]nstalled")
MODULE_INFO_TABLE_HINT = _("\n\nHint: [d]efault, [e]nabled, [x]disabled, [i]nstalled, [a]ctive")


def _profile_comparison_key(profile):
    return profile.getName()


class ModuleBase(object):
    # :api

    def __init__(self, base):
        # :api
        self.base = base

    def enable(self, module_specs):
        # :api
        no_match_specs, error_specs, solver_errors, module_dicts = \
            self._resolve_specs_enable_update_sack(module_specs)
        for spec, (nsvcap, module_dict) in module_dicts.items():
            if nsvcap.profile:
                logger.info(_("Ignoring unnecessary profile: '{}/{}'").format(
                    nsvcap.name, nsvcap.profile))
        if no_match_specs or error_specs or solver_errors:
            raise dnf.exceptions.MarkingErrors(no_match_group_specs=no_match_specs,
                                               error_group_specs=error_specs,
                                               module_depsolv_errors=solver_errors)

    def disable(self, module_specs):
        # :api
        no_match_specs, solver_errors = self._modules_reset_or_disable(module_specs, STATE_DISABLED)
        if no_match_specs or solver_errors:
            raise dnf.exceptions.MarkingErrors(no_match_group_specs=no_match_specs,
                                               module_depsolv_errors=solver_errors)

    def install(self, module_specs, strict=True):
        # :api
        no_match_specs, error_specs, solver_errors, module_dicts = \
            self._resolve_specs_enable_update_sack(module_specs)

        # <package_name, set_of_spec>
        fail_safe_repo = hawkey.MODULE_FAIL_SAFE_REPO_NAME
        install_dict = {}
        install_set_artifacts = set()
        fail_safe_repo_used = False
        for spec, (nsvcap, moduledict) in module_dicts.items():
            for name, streamdict in moduledict.items():
                for stream, module_list in streamdict.items():
                    install_module_list = [x for x in module_list
                                           if self.base._moduleContainer.isModuleActive(x.getId())]
                    if not install_module_list:
                        logger.error(_("All matches for argument '{0}' in module '{1}:{2}' are not "
                                       "active").format(spec, name, stream))
                        error_specs.append(spec)
                        continue
                    profiles = []
                    latest_module = self._get_latest(install_module_list)
                    if latest_module.getRepoID() == fail_safe_repo:
                        msg = _(
                            "Installing module '{0}' from Fail-Safe repository {1} is not allowed")
                        logger.critical(msg.format(latest_module.getNameStream(), fail_safe_repo))
                        fail_safe_repo_used = True
                    if nsvcap.profile:
                        profiles.extend(latest_module.getProfiles(nsvcap.profile))
                        if not profiles:
                            available_profiles = latest_module.getProfiles()
                            if available_profiles:
                                profile_names = ", ".join(sorted(
                                    [profile.getName() for profile in available_profiles]))
                                msg = _("Unable to match profile for argument {}. Available "
                                        "profiles for '{}:{}': {}").format(
                                    spec, name, stream, profile_names)
                            else:
                                msg = _("Unable to match profile for argument {}").format(spec)
                            logger.error(msg)
                            no_match_specs.append(spec)
                            continue
                    else:
                        profiles_strings = self.base._moduleContainer.getDefaultProfiles(
                            name, stream)
                        if not profiles_strings:
                            available_profiles = latest_module.getProfiles()
                            if available_profiles:
                                profile_names = ", ".join(sorted(
                                    [profile.getName() for profile in available_profiles]))
                                msg = _("No default profiles for module {}:{}. Available profiles"
                                        ": {}").format(
                                    name, stream, profile_names)
                            else:
                                msg = _("No profiles for module {}:{}").format(name, stream)
                            logger.error(msg)
                            error_specs.append(spec)
                        for profile in set(profiles_strings):
                            module_profiles = latest_module.getProfiles(profile)
                            if not module_profiles:
                                logger.error(
                                    _("Default profile {} not available in module {}:{}").format(
                                        profile, name, stream))
                                error_specs.append(spec)

                            profiles.extend(module_profiles)
                    for profile in profiles:
                        self.base._moduleContainer.install(latest_module ,profile.getName())
                        for pkg_name in profile.getContent():
                            install_dict.setdefault(pkg_name, set()).add(spec)
                    for module in install_module_list:
                        install_set_artifacts.update(module.getArtifacts())
        if fail_safe_repo_used:
            raise dnf.exceptions.Error(_(
                "Installing module from Fail-Safe repository is not allowed"))
        __, profiles_errors = self._install_profiles_internal(
            install_set_artifacts, install_dict, strict)
        if profiles_errors:
            error_specs.extend(profiles_errors)

        if no_match_specs or error_specs or solver_errors:
            raise dnf.exceptions.MarkingErrors(no_match_group_specs=no_match_specs,
                                               error_group_specs=error_specs,
                                               module_depsolv_errors=solver_errors)

    def switch_to(self, module_specs, strict=True):
        # :api
        no_match_specs, error_specs, module_dicts = self._resolve_specs_enable(module_specs)
        # collect name of artifacts from new modules for distrosync
        new_artifacts_names = set()
        # collect name of artifacts from active modules for distrosync before sack update
        active_artifacts_names = set()
        src_arches = {"nosrc", "src"}
        for spec, (nsvcap, moduledict) in module_dicts.items():
            for name in moduledict.keys():
                for module in self.base._moduleContainer.query(name, "", "", "", ""):
                    if self.base._moduleContainer.isModuleActive(module):
                        for artifact in module.getArtifacts():
                            arch = artifact.rsplit(".", 1)[1]
                            if arch in src_arches:
                                continue
                            pkg_name = artifact.rsplit("-", 2)[0]
                            active_artifacts_names.add(pkg_name)

        solver_errors = self._update_sack()

        dependency_error_spec = self._enable_dependencies(module_dicts)
        if dependency_error_spec:
            error_specs.extend(dependency_error_spec)

        # <package_name, set_of_spec>
        fail_safe_repo = hawkey.MODULE_FAIL_SAFE_REPO_NAME
        install_dict = {}
        install_set_artifacts = set()
        fail_safe_repo_used = False

        # list of name: [profiles] for module profiles being removed
        removed_profiles = self.base._moduleContainer.getRemovedProfiles()

        for spec, (nsvcap, moduledict) in module_dicts.items():
            for name, streamdict in moduledict.items():
                for stream, module_list in streamdict.items():
                    install_module_list = [x for x in module_list
                                           if self.base._moduleContainer.isModuleActive(x.getId())]
                    if not install_module_list:
                        "No active matches for argument '{0}' in module '{1}:{2}'"
                        logger.error(_("No active matches for argument '{0}' in module "
                                       "'{1}:{2}'").format(spec, name, stream))
                        error_specs.append(spec)
                        continue
                    profiles = []
                    latest_module = self._get_latest(install_module_list)
                    if latest_module.getRepoID() == fail_safe_repo:
                        msg = _(
                            "Installing module '{0}' from Fail-Safe repository {1} is not allowed")
                        logger.critical(msg.format(latest_module.getNameStream(), fail_safe_repo))
                        fail_safe_repo_used = True
                    if nsvcap.profile:
                        profiles.extend(latest_module.getProfiles(nsvcap.profile))
                        if not profiles:
                            available_profiles = latest_module.getProfiles()
                            if available_profiles:
                                profile_names = ", ".join(sorted(
                                    [profile.getName() for profile in available_profiles]))
                                msg = _("Unable to match profile for argument {}. Available "
                                        "profiles for '{}:{}': {}").format(
                                    spec, name, stream, profile_names)
                            else:
                                msg = _("Unable to match profile for argument {}").format(spec)
                            logger.error(msg)
                            no_match_specs.append(spec)
                            continue
                    elif name in removed_profiles:

                        for profile in removed_profiles[name]:
                            module_profiles = latest_module.getProfiles(profile)
                            if not module_profiles:
                                logger.warning(
                                    _("Installed profile '{0}' is not available in module "
                                      "'{1}' stream '{2}'").format(profile, name, stream))
                                continue
                            profiles.extend(module_profiles)
                    for profile in profiles:
                        self.base._moduleContainer.install(latest_module, profile.getName())
                        for pkg_name in profile.getContent():
                            install_dict.setdefault(pkg_name, set()).add(spec)
                    for module in install_module_list:
                        artifacts = module.getArtifacts()
                        install_set_artifacts.update(artifacts)
                        for artifact in artifacts:
                            arch = artifact.rsplit(".", 1)[1]
                            if arch in src_arches:
                                continue
                            pkg_name = artifact.rsplit("-", 2)[0]
                            new_artifacts_names.add(pkg_name)
        if fail_safe_repo_used:
            raise dnf.exceptions.Error(_(
                "Installing module from Fail-Safe repository is not allowed"))
        install_base_query, profiles_errors = self._install_profiles_internal(
            install_set_artifacts, install_dict, strict)
        if profiles_errors:
            error_specs.extend(profiles_errors)

        # distrosync module name
        all_names = set()
        all_names.update(new_artifacts_names)
        all_names.update(active_artifacts_names)
        remove_query = self.base.sack.query().filterm(empty=True)
        base_no_source_query = self.base.sack.query().filterm(arch__neq=['src', 'nosrc']).apply()

        for pkg_name in all_names:
            query = base_no_source_query.filter(name=pkg_name)
            installed = query.installed()
            if not installed:
                continue
            available = query.available()
            if not available:
                logger.warning(_("No packages available to distrosync for package name "
                                 "'{}'").format(pkg_name))
                if pkg_name not in new_artifacts_names:
                    remove_query = remove_query.union(query)
                continue

            only_new_module = query.intersection(install_base_query)
            if only_new_module:
                query = only_new_module
            sltr = dnf.selector.Selector(self.base.sack)
            sltr.set(pkg=query)
            self.base._goal.distupgrade(select=sltr)
        self.base._remove_if_unneeded(remove_query)

        if no_match_specs or error_specs or solver_errors:
            raise dnf.exceptions.MarkingErrors(no_match_group_specs=no_match_specs,
                                               error_group_specs=error_specs,
                                               module_depsolv_errors=solver_errors)

    def reset(self, module_specs):
        # :api
        no_match_specs, solver_errors = self._modules_reset_or_disable(module_specs, STATE_UNKNOWN)
        if no_match_specs:
            raise dnf.exceptions.MarkingErrors(no_match_group_specs=no_match_specs,
                                               module_depsolv_errors=solver_errors)

    def upgrade(self, module_specs):
        # :api
        no_match_specs = []
        fail_safe_repo = hawkey.MODULE_FAIL_SAFE_REPO_NAME
        fail_safe_repo_used = False

        #  Remove source packages because they cannot be installed or upgraded
        base_no_source_query = self.base.sack.query().filterm(arch__neq=['src', 'nosrc']).apply()

        for spec in module_specs:
            module_list, nsvcap = self._get_modules(spec)
            if not module_list:
                no_match_specs.append(spec)
                continue
            update_module_list = [x for x in module_list
                                  if self.base._moduleContainer.isModuleActive(x.getId())]
            if not update_module_list:
                logger.error(_("Unable to resolve argument {}").format(spec))
                continue
            module_dict = self._create_module_dict_and_enable(update_module_list, spec, False)
            upgrade_package_set = set()
            for name, streamdict in module_dict.items():
                for stream, module_list_from_dict in streamdict.items():
                    upgrade_package_set.update(self._get_package_name_set_and_remove_profiles(
                        module_list_from_dict, nsvcap))
                    latest_module = self._get_latest(module_list_from_dict)
                    if latest_module.getRepoID() == fail_safe_repo:
                        msg = _(
                            "Upgrading module '{0}' from Fail-Safe repository {1} is not allowed")
                        logger.critical(msg.format(latest_module.getNameStream(), fail_safe_repo))
                        fail_safe_repo_used = True
                    if nsvcap.profile:
                        profiles_set = latest_module.getProfiles(nsvcap.profile)
                        if not profiles_set:
                            continue
                        for profile in profiles_set:
                            upgrade_package_set.update(profile.getContent())
                    else:
                        for profile in latest_module.getProfiles():
                            upgrade_package_set.update(profile.getContent())
                        for artifact in latest_module.getArtifacts():
                            subj = hawkey.Subject(artifact)
                            for nevra_obj in subj.get_nevra_possibilities(
                                    forms=[hawkey.FORM_NEVRA]):
                                upgrade_package_set.add(nevra_obj.name)

            if not upgrade_package_set:
                logger.error(_("Unable to match profile in argument {}").format(spec))
            query = base_no_source_query.filter(name=upgrade_package_set)
            if query:
                sltr = dnf.selector.Selector(self.base.sack)
                sltr.set(pkg=query)
                self.base._goal.upgrade(select=sltr)
        if fail_safe_repo_used:
            raise dnf.exceptions.Error(_(
                "Upgrading module from Fail-Safe repository is not allowed"))
        return no_match_specs

    def remove(self, module_specs):
        # :api
        no_match_specs = []
        remove_package_set = set()

        for spec in module_specs:
            module_list, nsvcap = self._get_modules(spec)
            if not module_list:
                no_match_specs.append(spec)
                continue
            module_dict = self._create_module_dict_and_enable(module_list, spec, False)
            remove_packages_names = []
            for name, streamdict in module_dict.items():
                for stream, module_list_from_dict in streamdict.items():
                    remove_packages_names.extend(self._get_package_name_set_and_remove_profiles(
                        module_list_from_dict, nsvcap, True))
            if not remove_packages_names:
                logger.error(_("Unable to match profile in argument {}").format(spec))
            remove_package_set.update(remove_packages_names)

        if remove_package_set:
            keep_pkg_names = self.base._moduleContainer.getInstalledPkgNames()
            remove_package_set = remove_package_set.difference(keep_pkg_names)
            if remove_package_set:
                query = self.base.sack.query().installed().filterm(name=remove_package_set)
                if query:
                    self.base._remove_if_unneeded(query)
        return no_match_specs

    def get_modules(self, module_spec):
        # :api
        return self._get_modules(module_spec)

    def _get_modules(self, module_spec):
        # used by ansible (lib/ansible/modules/packaging/os/dnf.py)
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
        return (), None

    def _get_latest(self, module_list):
        latest = None
        if module_list:
            latest = module_list[0]
            for module in module_list[1:]:
                if module.getVersionNum() > latest.getVersionNum():
                    latest = module
        return latest

    def _create_module_dict_and_enable(self, module_list, spec, enable=True):
        moduleDict = {}
        for module in module_list:
            moduleDict.setdefault(
                module.getName(), {}).setdefault(module.getStream(), []).append(module)

        for moduleName, streamDict in moduleDict.items():
            moduleState = self.base._moduleContainer.getModuleState(moduleName)
            if len(streamDict) > 1:
                if moduleState != STATE_DEFAULT and moduleState != STATE_ENABLED \
                        and moduleState != STATE_DISABLED:
                    streams_str = "', '".join(
                        sorted(streamDict.keys(), key=functools.cmp_to_key(self.base.sack.evr_cmp)))
                    msg = _("Argument '{argument}' matches {stream_count} streams ('{streams}') of "
                            "module '{module}', but none of the streams are enabled or "
                            "default").format(
                        argument=spec, stream_count=len(streamDict), streams=streams_str,
                        module=moduleName)
                    raise EnableMultipleStreamsException(moduleName, msg)
                if moduleState == STATE_ENABLED:
                    stream = self.base._moduleContainer.getEnabledStream(moduleName)
                else:
                    stream = self.base._moduleContainer.getDefaultStream(moduleName)
                if not stream or stream not in streamDict:
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

    def _resolve_specs_enable(self, module_specs):
        no_match_specs = []
        error_spec = []
        module_dicts = {}
        for spec in module_specs:
            module_list, nsvcap = self._get_modules(spec)
            if not module_list:
                no_match_specs.append(spec)
                continue
            try:
                module_dict = self._create_module_dict_and_enable(module_list, spec, True)
                module_dicts[spec] = (nsvcap, module_dict)
            except (RuntimeError, EnableMultipleStreamsException) as e:
                error_spec.append(spec)
                logger.error(ucd(e))
                logger.error(_("Unable to resolve argument {}").format(spec))
        return no_match_specs, error_spec, module_dicts

    def _update_sack(self):
        hot_fix_repos = [i.id for i in self.base.repos.iter_enabled() if i.module_hotfixes]
        try:
            solver_errors = self.base.sack.filter_modules(
                self.base._moduleContainer, hot_fix_repos, self.base.conf.installroot,
                self.base.conf.module_platform_id, update_only=True,
                debugsolver=self.base.conf.debug_solver)
        except hawkey.Exception as e:
            raise dnf.exceptions.Error(ucd(e))
        return solver_errors

    def _enable_dependencies(self, module_dicts):
        error_spec = []
        for spec, (nsvcap, moduleDict) in module_dicts.items():
            for streamDict in moduleDict.values():
                for modules in streamDict.values():
                    try:
                        self.base._moduleContainer.enableDependencyTree(
                            libdnf.module.VectorModulePackagePtr(modules))
                    except RuntimeError as e:
                        error_spec.append(spec)
                        logger.error(ucd(e))
                        logger.error(_("Unable to resolve argument {}").format(spec))
        return error_spec

    def _resolve_specs_enable_update_sack(self, module_specs):
        no_match_specs, error_spec, module_dicts = self._resolve_specs_enable(module_specs)

        solver_errors = self._update_sack()

        dependency_error_spec = self._enable_dependencies(module_dicts)
        if dependency_error_spec:
            error_spec.extend(dependency_error_spec)

        return no_match_specs, error_spec, solver_errors, module_dicts

    def _modules_reset_or_disable(self, module_specs, to_state):
        no_match_specs = []
        for spec in module_specs:
            module_list, nsvcap = self._get_modules(spec)
            if not module_list:
                logger.error(_("Unable to resolve argument {}").format(spec))
                no_match_specs.append(spec)
                continue
            if nsvcap.stream or nsvcap.version or nsvcap.context or nsvcap.arch or nsvcap.profile:
                logger.info(_("Only module name is required. "
                              "Ignoring unneeded information in argument: '{}'").format(spec))
            module_names = set()
            for module in module_list:
                module_names.add(module.getName())
            for name in module_names:
                if to_state == STATE_UNKNOWN:
                    self.base._moduleContainer.reset(name)
                if to_state == STATE_DISABLED:
                    self.base._moduleContainer.disable(name)

        solver_errors = self._update_sack()
        return no_match_specs, solver_errors

    def _get_package_name_set_and_remove_profiles(self, module_list, nsvcap, remove=False):
        package_name_set = set()
        latest_module = self._get_latest(module_list)
        installed_profiles_strings = set(self.base._moduleContainer.getInstalledProfiles(
            latest_module.getName()))
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

    def _get_info_profiles(self, module_specs):
        output = set()
        for module_spec in module_specs:
            module_list, nsvcap = self._get_modules(module_spec)
            if not module_list:
                logger.info(_("Unable to resolve argument {}").format(module_spec))
                continue

            if nsvcap.profile:
                logger.info(_("Ignoring unnecessary profile: '{}/{}'").format(
                    nsvcap.name, nsvcap.profile))
            for module in module_list:

                lines = OrderedDict()
                lines["Name"] = module.getFullIdentifier()

                for profile in sorted(module.getProfiles(), key=_profile_comparison_key):
                    lines[profile.getName()] = "\n".join(
                        [pkgName for pkgName in profile.getContent()])

                output.add(self._create_simple_table(lines).toString())
        return "\n\n".join(sorted(output))

    def _profile_report_formatter(self, modulePackage, default_profiles, enabled_str):
        installed_profiles = self.base._moduleContainer.getInstalledProfiles(
            modulePackage.getName())
        available_profiles = modulePackage.getProfiles()
        profiles_str = ""
        for profile in sorted(available_profiles, key=_profile_comparison_key):
            profiles_str += "{}{}".format(
                profile.getName(), " [d]" if profile.getName() in default_profiles else "")
            profiles_str += " [i], " if profile.getName() in installed_profiles and enabled_str \
                else ", "
        return profiles_str[:-2]

    def _summary_report_formatter(self, summary):
        return summary.strip().replace("\n", " ")

    def _module_strs_formatter(self, modulePackage, markActive=False):
        default_str = ""
        enabled_str = ""
        disabled_str = ""
        if modulePackage.getStream() == self.base._moduleContainer.getDefaultStream(
                modulePackage.getName()):
            default_str = " [d]"
        if self.base._moduleContainer.isEnabled(modulePackage):
            if not default_str:
                enabled_str = " "
            enabled_str += "[e]"
        elif self.base._moduleContainer.isDisabled(modulePackage):
            if not default_str:
                disabled_str = " "
            disabled_str += "[x]"
        if markActive and self.base._moduleContainer.isModuleActive(modulePackage):
            if not default_str:
                disabled_str = " "
            disabled_str += "[a]"
        return default_str, enabled_str, disabled_str

    def _get_info(self, module_specs):
        output = set()
        for module_spec in module_specs:
            module_list, nsvcap = self._get_modules(module_spec)
            if not module_list:
                logger.info(_("Unable to resolve argument {}").format(module_spec))
                continue

            if nsvcap.profile:
                logger.info(_("Ignoring unnecessary profile: '{}/{}'").format(
                    nsvcap.name, nsvcap.profile))
            for modulePackage in module_list:
                default_str, enabled_str, disabled_str = self._module_strs_formatter(
                    modulePackage, markActive=True)
                default_profiles = self.base._moduleContainer.getDefaultProfiles(
                    modulePackage.getName(), modulePackage.getStream())

                profiles_str = self._profile_report_formatter(
                    modulePackage, default_profiles, enabled_str)

                lines = OrderedDict()
                lines["Name"] = modulePackage.getName()
                lines["Stream"] = modulePackage.getStream() + default_str + enabled_str + \
                                  disabled_str
                lines["Version"] = modulePackage.getVersion()
                lines["Context"] = modulePackage.getContext()
                lines["Architecture"] = modulePackage.getArch()
                lines["Profiles"] = profiles_str
                lines["Default profiles"] = " ".join(default_profiles)
                lines["Repo"] = modulePackage.getRepoID()
                lines["Summary"] = modulePackage.getSummary()
                lines["Description"] = modulePackage.getDescription()
                req_set = set()
                for req in modulePackage.getModuleDependencies():
                    for require_dict in req.getRequires():
                        for mod_require, stream in require_dict.items():
                            req_set.add("{}:[{}]".format(mod_require, ",".join(stream)))
                lines["Requires"] = "\n".join(sorted(req_set))
                demodularized = modulePackage.getDemodularizedRpms()
                if demodularized:
                    lines["Demodularized rpms"] = "\n".join(demodularized)
                lines["Artifacts"] = "\n".join(sorted(modulePackage.getArtifacts()))
                output.add(self._create_simple_table(lines).toString())
        str_table = "\n\n".join(sorted(output))
        if str_table:
            str_table += MODULE_INFO_TABLE_HINT
        return str_table

    @staticmethod
    def _create_simple_table(lines):
        table = libdnf.smartcols.Table()
        table.enableNoheadings(True)
        table.setColumnSeparator(" : ")

        column_name = table.newColumn("Name")
        column_value = table.newColumn("Value")
        column_value.setWrap(True)
        column_value.setSafechars("\n")
        column_value.setNewlineWrapFunction()

        for line_name, value in lines.items():
            if value is None:
                value = ""
            line = table.newLine()
            line.getColumnCell(column_name).setData(line_name)
            line.getColumnCell(column_value).setData(str(value))

        return table

    def _get_full_info(self, module_specs):
        output = set()
        for module_spec in module_specs:
            module_list, nsvcap = self._get_modules(module_spec)
            if not module_list:
                logger.info(_("Unable to resolve argument {}").format(module_spec))
                continue

            if nsvcap.profile:
                logger.info(_("Ignoring unnecessary profile: '{}/{}'").format(
                    nsvcap.name, nsvcap.profile))
            for modulePackage in module_list:
                info = modulePackage.getYaml()
                if info:
                    output.add(info)
        output_string = "\n\n".join(sorted(output))
        return output_string

    def _what_provides(self, rpm_specs):
        output = set()
        modulePackages = self.base._moduleContainer.getModulePackages()
        baseQuery = self.base.sack.query().filterm(empty=True).apply()
        getBestInitQuery = self.base.sack.query(flags=hawkey.IGNORE_MODULAR_EXCLUDES)

        for spec in rpm_specs:
            subj = dnf.subject.Subject(spec)
            baseQuery = baseQuery.union(subj.get_best_query(
                self.base.sack, with_nevra=True, with_provides=False, with_filenames=False,
                query=getBestInitQuery))

        baseQuery.apply()

        for modulePackage in modulePackages:
            artifacts = modulePackage.getArtifacts()
            if not artifacts:
                continue
            query = baseQuery.filter(nevra_strict=artifacts)
            if query:
                for pkg in query:
                    string_output = ""
                    profiles = []
                    for profile in sorted(modulePackage.getProfiles(), key=_profile_comparison_key):
                        if pkg.name in profile.getContent():
                            profiles.append(profile.getName())
                    lines = OrderedDict()
                    lines["Module"] = modulePackage.getFullIdentifier()
                    lines["Profiles"] = " ".join(sorted(profiles))
                    lines["Repo"] = modulePackage.getRepoID()
                    lines["Summary"] = modulePackage.getSummary()

                    table = self._create_simple_table(lines)

                    string_output += "{}\n".format(self.base.output.term.bold(str(pkg)))
                    string_output += "{}".format(table.toString())
                    output.add(string_output)

        return "\n\n".join(sorted(output))

    def _create_and_fill_table(self, latest):
        table = libdnf.smartcols.Table()
        table.setTermforce(libdnf.smartcols.Table.TermForce_AUTO)
        table.enableMaxout(True)
        column_name = table.newColumn("Name")
        column_stream = table.newColumn("Stream")
        column_profiles = table.newColumn("Profiles")
        column_profiles.setWrap(True)
        column_info = table.newColumn("Summary")
        column_info.setWrap(True)

        if not self.base.conf.verbose:
            column_info.hidden = True

        for latest_per_repo in latest:
            for nameStreamArch in latest_per_repo:
                if len(nameStreamArch) == 1:
                    modulePackage = nameStreamArch[0]
                else:
                    active = [module for module in nameStreamArch
                              if self.base._moduleContainer.isModuleActive(module)]
                    if active:
                        modulePackage = active[0]
                    else:
                        modulePackage = nameStreamArch[0]
                line = table.newLine()
                default_str, enabled_str, disabled_str = self._module_strs_formatter(
                    modulePackage, markActive=False)
                default_profiles = self.base._moduleContainer.getDefaultProfiles(
                    modulePackage.getName(), modulePackage.getStream())
                profiles_str = self._profile_report_formatter(modulePackage, default_profiles,
                                                             enabled_str)
                line.getColumnCell(column_name).setData(modulePackage.getName())
                line.getColumnCell(
                    column_stream).setData(
                    modulePackage.getStream() + default_str + enabled_str + disabled_str)
                line.getColumnCell(column_profiles).setData(profiles_str)
                summary_str = self._summary_report_formatter(modulePackage.getSummary())
                line.getColumnCell(column_info).setData(summary_str)

        return table

    def _get_brief_description(self, module_specs, module_state):
        modules = []
        if module_specs:
            for spec in module_specs:
                module_list, nsvcap = self._get_modules(spec)
                modules.extend(module_list)
        else:
            modules = self.base._moduleContainer.getModulePackages()
        latest = self.base._moduleContainer.getLatestModulesPerRepo(module_state, modules)
        if not latest:
            return ""

        table = self._create_and_fill_table(latest)
        current_repo_id_index = 0
        already_printed_lines = 0
        try:
            repo_name = self.base.repos[latest[0][0][0].getRepoID()].name
        except KeyError:
            repo_name = latest[0][0][0].getRepoID()
        versions = len(latest[0])
        header = self._format_header(table)
        str_table = self._format_repoid(repo_name)
        str_table += header
        for i in range(0, table.getNumberOfLines()):
            if versions + already_printed_lines <= i:
                already_printed_lines += versions
                current_repo_id_index += 1
                # Fail-Safe repository is not in self.base.repos
                try:
                    repo_name = self.base.repos[
                        latest[current_repo_id_index][0][0].getRepoID()].name
                except KeyError:
                    repo_name = latest[current_repo_id_index][0][0].getRepoID()
                versions = len(latest[current_repo_id_index])
                str_table += "\n"
                str_table += self._format_repoid(repo_name)
                str_table += header

            line = table.getLine(i)
            str_table += table.toString(line, line)
        return str_table + MODULE_TABLE_HINT

    def _format_header(self, table):
        line = table.getLine(0)
        return table.toString(line, line).split('\n', 1)[0] + '\n'

    def _format_repoid(self, repo_name):
        return "{}\n".format(self.base.output.term.bold(repo_name))

    def _install_profiles_internal(self, install_set_artifacts, install_dict, strict):
        #  Remove source packages because they cannot be installed or upgraded
        base_no_source_query = self.base.sack.query().filterm(arch__neq=['src', 'nosrc']).apply()
        install_base_query = base_no_source_query.filter(nevra_strict=install_set_artifacts)
        error_specs = []

        # add hot-fix packages
        hot_fix_repos = [i.id for i in self.base.repos.iter_enabled() if i.module_hotfixes]
        hotfix_packages = base_no_source_query.filter(
            reponame=hot_fix_repos, name=install_dict.keys())
        install_base_query = install_base_query.union(hotfix_packages)

        for pkg_name, set_specs in install_dict.items():
            query = install_base_query.filter(name=pkg_name)
            if not query:
                # package can also be non-modular or part of another stream
                query = base_no_source_query.filter(name=pkg_name)
                if not query:
                    for spec in set_specs:
                        logger.error(_("Unable to resolve argument {}").format(spec))
                    logger.error(_("No match for package {}").format(pkg_name))
                    error_specs.extend(set_specs)
                    continue
            self.base._goal.group_members.add(pkg_name)
            sltr = dnf.selector.Selector(self.base.sack)
            sltr.set(pkg=query)
            self.base._goal.install(select=sltr, optional=(not strict))
        return install_base_query, error_specs


def format_modular_solver_errors(errors):
    msg = dnf.util._format_resolve_problems(errors)
    return "\n".join(
        [P_('Modular dependency problem:', 'Modular dependency problems:', len(errors)), msg])
