# supplies the 'module' command.
#
# Copyright (C) 2014-2017  Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from __future__ import print_function

from dnf.cli import commands, CliError
from dnf.i18n import _
from dnf.module.exceptions import NoModuleException
from dnf.util import logger
import dnf.util

import sys
import os

import hawkey
import libdnf
import dnf.module.module_base
import dnf.exceptions


class ModuleCommand(commands.Command):
    class SubCommand(commands.Command):

        def __init__(self, cli):
            super(ModuleCommand.SubCommand, self).__init__(cli)
            self.module_base = dnf.module.module_base.ModuleBase(self.base)

        def _get_modules_from_name_stream_specs(self):
            modules_from_specs = set()
            for module_spec in self.opts.module_spec:
                __, nsvcap = self.module_base._get_modules(module_spec)
                # When there is no match, the problem was already reported by module_base.remove()
                if nsvcap is None:
                    continue
                name = nsvcap.name if nsvcap.name else ""
                stream = nsvcap.stream if nsvcap.stream else ""
                if (nsvcap.version and nsvcap.version != -1) or nsvcap.context:
                    logger.info(_("Only module name, stream, architecture or profile is used. "
                                  "Ignoring unneeded information in argument: '{}'").format(
                        module_spec))
                arch = nsvcap.arch if nsvcap.arch else ""
                modules = self.base._moduleContainer.query(name, stream, "", "", arch)
                modules_from_specs.update(modules)
            return modules_from_specs

        def _get_module_artifact_names(self, use_modules, skip_modules):
            artifacts = set()
            pkg_names = set()
            for module in use_modules:
                if module not in skip_modules:
                    if self.base._moduleContainer.isModuleActive(module):
                        artifacts.update(module.getArtifacts())
            for artifact in artifacts:
                subj = hawkey.Subject(artifact)
                for nevra_obj in subj.get_nevra_possibilities(
                        forms=[hawkey.FORM_NEVRA]):
                    if nevra_obj.name:
                        pkg_names.add(nevra_obj.name)
            return pkg_names, artifacts

    class ListSubCommand(SubCommand):

        aliases = ('list',)
        summary = _('list all module streams, profiles and states')

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True

        def run_on_module(self):
            mods = self.module_base

            if self.opts.enabled:
                output = mods._get_brief_description(
                    self.opts.module_spec, libdnf.module.ModulePackageContainer.ModuleState_ENABLED)
            elif self.opts.disabled:
                output = mods._get_brief_description(
                    self.opts.module_spec,
                    libdnf.module.ModulePackageContainer.ModuleState_DISABLED)
            elif self.opts.installed:
                output = mods._get_brief_description(
                    self.opts.module_spec,
                    libdnf.module.ModulePackageContainer.ModuleState_INSTALLED)
            else:
                output = mods._get_brief_description(
                    self.opts.module_spec, libdnf.module.ModulePackageContainer.ModuleState_UNKNOWN)
            if output:
                print(output)
                return
            if self.opts.module_spec:
                msg = _('No matching Modules to list')
                raise dnf.exceptions.Error(msg)

    class InfoSubCommand(SubCommand):

        aliases = ('info',)
        summary = _('print detailed information about a module')

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True

        def run_on_module(self):
            if self.opts.verbose:
                output = self.module_base._get_full_info(self.opts.module_spec)
            elif self.opts.profile:
                output = self.module_base._get_info_profiles(self.opts.module_spec)
            else:
                output = self.module_base._get_info(self.opts.module_spec)
            if output:
                print(output)
            else:
                raise dnf.exceptions.Error(_('No matching Modules to list'))

    class EnableSubCommand(SubCommand):

        aliases = ('enable',)
        summary = _('enable a module stream')

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.resolving = True
            demands.root_user = True

        def run_on_module(self):
            try:
                self.module_base.enable(self.opts.module_spec)
            except dnf.exceptions.MarkingErrors as e:
                if self.base.conf.strict:
                    if e.no_match_group_specs or e.error_group_specs:
                        raise e
                    if e.module_depsolv_errors and e.module_depsolv_errors[1] != \
                            libdnf.module.ModulePackageContainer.ModuleErrorType_ERROR_IN_DEFAULTS:
                        raise e
                logger.error(str(e))

    class DisableSubCommand(SubCommand):

        aliases = ('disable',)
        summary = _('disable a module with all its streams')

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.resolving = True
            demands.root_user = True

        def run_on_module(self):
            try:
                self.module_base.disable(self.opts.module_spec)
            except dnf.exceptions.MarkingErrors as e:
                if self.base.conf.strict:
                    if e.no_match_group_specs or e.error_group_specs:
                        raise e
                    if e.module_depsolv_errors and e.module_depsolv_errors[1] != \
                            libdnf.module.ModulePackageContainer.ModuleErrorType_ERROR_IN_DEFAULTS:
                        raise e
                logger.error(str(e))

    class ResetSubCommand(SubCommand):

        aliases = ('reset',)
        summary = _('reset a module')

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.resolving = True
            demands.root_user = True

        def run_on_module(self):
            try:
                self.module_base.reset(self.opts.module_spec)
            except dnf.exceptions.MarkingErrors as e:
                if self.base.conf.strict:
                    if e.no_match_group_specs:
                        raise e
                logger.error(str(e))

    class InstallSubCommand(SubCommand):

        aliases = ('install',)
        summary = _('install a module profile including its packages')

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.resolving = True
            demands.root_user = True

        def run_on_module(self):
            try:
                self.module_base.install(self.opts.module_spec, self.base.conf.strict)
            except dnf.exceptions.MarkingErrors as e:
                if self.base.conf.strict:
                    if e.no_match_group_specs or e.error_group_specs:
                        raise e
                logger.error(str(e))

    class UpdateSubCommand(SubCommand):

        aliases = ('update',)
        summary = _('update packages associated with an active stream')

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.resolving = True
            demands.root_user = True

        def run_on_module(self):
            module_specs = self.module_base.upgrade(self.opts.module_spec)
            if module_specs:
                raise NoModuleException(", ".join(module_specs))

    class RemoveSubCommand(SubCommand):

        aliases = ('remove', 'erase',)
        summary = _('remove installed module profiles and their packages')

        def configure(self):
            demands = self.cli.demands
            demands.allow_erasing = True
            demands.available_repos = True
            demands.fresh_metadata = False
            demands.resolving = True
            demands.root_user = True
            demands.sack_activation = True

        def run_on_module(self):
            skipped_groups = self.module_base.remove(self.opts.module_spec)
            if self.opts.all:
                modules_from_specs = self._get_modules_from_name_stream_specs()
                remove_names_from_spec, __ = self._get_module_artifact_names(
                    modules_from_specs, set())
                keep_names, __ = self._get_module_artifact_names(
                    self.base._moduleContainer.getModulePackages(), modules_from_specs)
                remove_query = self.base.sack.query().installed().filterm(
                    name=remove_names_from_spec)
                keep_query = self.base.sack.query().installed().filterm(name=keep_names)
                for pkg in remove_query:
                    if pkg in keep_query:
                        msg = _("Package {} belongs to multiple modules, skipping").format(pkg)
                        logger.info(msg)
                    else:
                        self.base.goal.erase(
                            pkg, clean_deps=self.base.conf.clean_requirements_on_remove)
            if not skipped_groups:
                return

            logger.error(dnf.exceptions.MarkingErrors(no_match_group_specs=skipped_groups))

    class SwitchToSubCommand(SubCommand):

        aliases = ('switch-to',)
        summary = _('switch a module to a stream and distrosync rpm packages')

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.resolving = True
            demands.root_user = True
            self.base.conf.module_stream_switch = True

        def run_on_module(self):
            try:
                self.module_base.switch_to(self.opts.module_spec, strict=self.base.conf.strict)
            except dnf.exceptions.MarkingErrors as e:
                if self.base.conf.strict:
                    if e.no_match_group_specs or e.error_group_specs:
                        raise e
                logger.error(str(e))

    class ProvidesSubCommand(SubCommand):

        aliases = ("provides", )
        summary = _('list modular packages')

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True

        def run_on_module(self):
            output = self.module_base._what_provides(self.opts.module_spec)
            if output:
                print(output)

    class RepoquerySubCommand(SubCommand):

        aliases = ("repoquery", )
        summary = _('list packages belonging to a module')

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True

        def run_on_module(self):
            modules_from_specs = set()
            for module_spec in self.opts.module_spec:
                modules, __ = self.module_base._get_modules(module_spec)
                modules_from_specs.update(modules)
            names_from_spec, spec_artifacts = self._get_module_artifact_names(
                modules_from_specs, set())
            package_strings = set()
            if self.opts.available or not self.opts.installed:
                query = self.base.sack.query().available().filterm(nevra_strict=spec_artifacts)
                for pkg in query:
                    package_strings.add(str(pkg))
            if self.opts.installed:
                query = self.base.sack.query().installed().filterm(name=names_from_spec)
                for pkg in query:
                    package_strings.add(str(pkg))

            output = "\n".join(sorted(package_strings))
            print(output)


    SUBCMDS = {ListSubCommand, InfoSubCommand, EnableSubCommand,
               DisableSubCommand, ResetSubCommand, InstallSubCommand, UpdateSubCommand,
               RemoveSubCommand, SwitchToSubCommand, ProvidesSubCommand, RepoquerySubCommand}

    SUBCMDS_NOT_REQUIRED_ARG = {ListSubCommand}

    aliases = ("module",)
    summary = _("Interact with Modules.")

    def __init__(self, cli):
        super(ModuleCommand, self).__init__(cli)
        subcmd_objs = (subcmd(cli) for subcmd in self.SUBCMDS)
        self.subcmd = None
        self._subcmd_name2obj = {
            alias: subcmd for subcmd in subcmd_objs for alias in subcmd.aliases}

    def set_argparser(self, parser):
        narrows = parser.add_mutually_exclusive_group()
        narrows.add_argument('--enabled', dest='enabled',
                             action='store_true',
                             help=_("show only enabled modules"))
        narrows.add_argument('--disabled', dest='disabled',
                             action='store_true',
                             help=_("show only disabled modules"))
        narrows.add_argument('--installed', dest='installed',
                             action='store_true',
                             help=_("show only installed modules or packages"))
        narrows.add_argument('--profile', dest='profile',
                             action='store_true',
                             help=_("show profile content"))
        parser.add_argument('--available', dest='available', action='store_true',
                            help=_("show only available packages"))
        narrows.add_argument('--all', dest='all',
                             action='store_true',
                             help=_("remove all modular packages"))
        subcommand_choices = []
        subcommand_help = []
        for subcmd in sorted(self.SUBCMDS, key=lambda x: x.aliases[0]):
            subcommand_choices.append(subcmd.aliases[0])
            subcommand_help.append('{}: {}'.format(subcmd.aliases[0], subcmd.summary or ''))
        parser.add_argument('subcmd', nargs=1, choices=subcommand_choices,
                            metavar='<modular command>',
                            help='\n'.join(subcommand_help))
        parser.add_argument('module_spec', metavar='module-spec', nargs='*',
                            help=_("Module specification"))

    def configure(self):
        try:
            self.subcmd = self._subcmd_name2obj[self.opts.subcmd[0]]
        except (CliError, KeyError):
            self.cli.optparser.print_usage()
            raise CliError
        self.subcmd.opts = self.opts
        self.subcmd.configure()

    def run(self):
        self.check_required_argument()
        self.subcmd.run_on_module()

    def check_required_argument(self):
        not_required_argument = [alias
                                 for subcmd in self.SUBCMDS_NOT_REQUIRED_ARG
                                 for alias in subcmd.aliases]
        if self.opts.subcmd[0] not in not_required_argument:
            if not self.opts.module_spec:
                raise CliError(
                    _("{} {} {}: too few arguments").format(dnf.util.MAIN_PROG,
                                                            self.opts.command,
                                                            self.opts.subcmd[0]))
