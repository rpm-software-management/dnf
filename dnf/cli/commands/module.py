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


class ModuleCommand(commands.Command):
    class SubCommand(commands.Command):

        def __init__(self, cli):
            super(ModuleCommand.SubCommand, self).__init__(cli)

    class ListSubCommand(SubCommand):

        aliases = ('list',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True

        def run_on_module(self):
            mods = self.base.repo_module_dict

            if self.opts.all:
                print(mods.get_brief_description_all(self.opts.module_nsvp))
            elif self.opts.enabled:
                print(mods.get_brief_description_enabled(self.opts.module_nsvp))
            elif self.opts.disabled:
                print(mods.get_brief_description_disabled(self.opts.module_nsvp))
            elif self.opts.installed:
                print(mods.get_brief_description_installed(self.opts.module_nsvp))
            else:
                print(mods.get_brief_description_latest(self.opts.module_nsvp))

            return 0

    class InfoSubCommand(SubCommand):

        aliases = ('info',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True

        def run_on_module(self):
            for spec in self.opts.module_nsvp:
                print()
                if self.opts.verbose:
                    print(self.base.repo_module_dict.get_full_info(spec))
                elif self.opts.profile:
                    print(self.base.repo_module_dict.get_info_profiles(spec))
                else:
                    print(self.base.repo_module_dict.get_info(spec))

    class EnableSubCommand(SubCommand):

        aliases = ('enable',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.root_user = True

        def run_on_module(self):
            for module_ns in self.opts.module_nsvp:
                self.base.repo_module_dict.enable(module_ns, True)
                logger.info("'{}' is enabled".format(module_ns))

    class DisableSubCommand(SubCommand):

        aliases = ('disable',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.root_user = True

        def run_on_module(self):
            for module_n in self.opts.module_nsvp:
                self.base.repo_module_dict.disable(module_n, True)
                logger.info("'{}' is disabled".format(module_n))

    class InstallSubCommand(SubCommand):

        aliases = ('install',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.resolving = True
            demands.root_user = True

        def run_on_module(self):
            module_specs = self.base.repo_module_dict.install(self.opts.module_nsvp)
            if module_specs:
                raise NoModuleException(", ".join(module_specs))

    class UpdateSubCommand(SubCommand):

        aliases = ('update',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.resolving = True
            demands.root_user = True

        def run_on_module(self):
            module_specs, _, _ = self.base.repo_module_dict.upgrade(self.opts.module_nsvp, True)
            if module_specs:
                raise NoModuleException(", ".join(module_specs))

    class RemoveSubCommand(SubCommand):

        aliases = ('remove', 'erase',)

        def configure(self):
            demands = self.cli.demands
            demands.allow_erasing = True
            demands.available_repos = True
            demands.resolving = True
            demands.root_user = True
            demands.sack_activation = True

        def run_on_module(self):
            self.base.repo_module_dict.remove(self.opts.module_nsvp)

    class LockSubCommand(SubCommand):

        aliases = ("lock",)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.root_user = True

        def run_on_module(self):
            for module_n in self.opts.module_nsvp:
                stream, version = self.base.repo_module_dict.lock(module_n, True)
                logger.info("'{}' is locked (stream: {}, version: {})"
                            .format(module_n, stream, version))

    class UnlockSubCommand(SubCommand):

        aliases = ("unlock",)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.root_user = True

        def run_on_module(self):
            for module_n in self.opts.module_nsvp:
                self.base.repo_module_dict.unlock(module_n, True)
                logger.info("'{}' is unlocked".format(module_n))

    class ProfileInfoSubCommand(SubCommand):

        aliases = ("profile", "profile-info")

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True

        def run_on_module(self):
            for spec in self.opts.module_nsvp:
                print()
                logger.info(self.base.repo_module_dict.get_info_profiles(spec))

    class StreamsSubCommand(SubCommand):

        aliases = ("streams", "enabled", "enabled-streams")

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True

        def run_on_module(self):
            logger.info(self.base.repo_module_dict
                        .get_brief_description_enabled(self.opts.module_nsvp))

    class ProvidesSubCommand(SubCommand):

        aliases = ("provides", )

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True

        def run_on_module(self):
            self.base.repo_module_dict.print_what_provides(self.opts.module_nsvp)

    SUBCMDS = {ListSubCommand, InfoSubCommand, EnableSubCommand,
               DisableSubCommand, InstallSubCommand, UpdateSubCommand,
               RemoveSubCommand, LockSubCommand, UnlockSubCommand,
               ProfileInfoSubCommand, StreamsSubCommand, ProvidesSubCommand}

    SUBCMDS_NOT_REQUIRED_ARG = {ListSubCommand, StreamsSubCommand}

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
        parser.add_argument('module_nsvp', nargs='*')

        narrows = parser.add_mutually_exclusive_group()
        narrows.add_argument('--all', dest='all',
                             action='store_true',
                             help=_("show all modules"))
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
        narrows.add_argument('--autoenable', dest='autoenable',
                             action='store_true',
                             help=_("auto enable stream"))

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
            if not self.opts.module_nsvp:
                raise CliError(
                    "dnf {} {}: too few arguments".format(self.opts.command[0],
                                                          self.opts.subcmd[0]))
