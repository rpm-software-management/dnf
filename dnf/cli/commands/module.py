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

import sys
import os

import libdnf
import dnf.module.module_base
import dnf.exceptions


def report_module_switch(switchedModules):
    msg1 = _("The operation would result in switching of module '{0}' stream '{1}' to "
             "stream '{2}'")
    for moduleName, streams in switchedModules.items():
        logger.warning(msg1.format(moduleName, streams[0], streams[1]))


class ModuleCommand(commands.Command):
    class SubCommand(commands.Command):

        def __init__(self, cli):
            super(ModuleCommand.SubCommand, self).__init__(cli)
            self.module_base = dnf.module.module_base.ModuleBase(self.base)

    class ListSubCommand(SubCommand):

        aliases = ('list',)

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
                    if e.module_debsolv_errors and e.module_debsolv_errors[1] != \
                            libdnf.module.ModulePackageContainer.ModuleErrorType_ERROR_IN_DEFAULTS:
                        raise e
                logger.error(str(e))
            switchedModules = dict(self.base._moduleContainer.getSwitchedStreams())
            if switchedModules:
                report_module_switch(switchedModules)
                msg = _("It is not possible to switch enabled streams of a module.\n"
                        "It is recommended to remove all installed content from the module, and "
                        "reset the module using 'dnf module reset <module_name>' command. After "
                        "you reset the module, you can enable the other stream.")
                raise dnf.exceptions.Error(msg)

    class DisableSubCommand(SubCommand):

        aliases = ('disable',)

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
                    if e.module_debsolv_errors and e.module_debsolv_errors[1] != \
                            libdnf.module.ModulePackageContainer.ModuleErrorType_ERROR_IN_DEFAULTS:
                        raise e
                logger.error(str(e))

    class ResetSubCommand(SubCommand):

        aliases = ('reset',)

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
            switchedModules = dict(self.base._moduleContainer.getSwitchedStreams())
            if switchedModules:
                report_module_switch(switchedModules)
                msg = _("It is not possible to switch enabled streams of a module.\n"
                        "It is recommended to remove all installed content from the module, and "
                        "reset the module using 'dnf module reset <module_name>' command. After "
                        "you reset the module, you can install the other stream.")
                raise dnf.exceptions.Error(msg)

    class UpdateSubCommand(SubCommand):

        aliases = ('update',)

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
            if not skipped_groups:
                return

            logger.error(dnf.exceptions.MarkingErrors(no_match_group_specs=skipped_groups))

    class ProvidesSubCommand(SubCommand):

        aliases = ("provides", )

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True

        def run_on_module(self):
            output = self.module_base._what_provides(self.opts.module_spec)
            if output:
                print(output)

    SUBCMDS = {ListSubCommand, InfoSubCommand, EnableSubCommand,
               DisableSubCommand, ResetSubCommand, InstallSubCommand, UpdateSubCommand,
               RemoveSubCommand, ProvidesSubCommand}

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
        subcommand_help = [subcmd.aliases[0] for subcmd in self.SUBCMDS]
        parser.add_argument('subcmd', nargs=1, choices=subcommand_help)
        parser.add_argument('module_spec', metavar='module-spec', nargs='*')

        narrows = parser.add_mutually_exclusive_group()
        narrows.add_argument('--enabled', dest='enabled',
                             action='store_true',
                             help=_("show only enabled modules"))
        narrows.add_argument('--disabled', dest='disabled',
                             action='store_true',
                             help=_("show only disabled modules"))
        narrows.add_argument('--installed', dest='installed',
                             action='store_true',
                             help=_("show only installed modules"))
        narrows.add_argument('--profile', dest='profile',
                             action='store_true',
                             help=_("show profile content"))

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
                    "dnf {} {}: too few arguments".format(self.opts.command[0],
                                                          self.opts.subcmd[0]))
