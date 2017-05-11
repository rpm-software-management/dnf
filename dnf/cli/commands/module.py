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

import argparse

import dnf
from dnf.base import logger
from dnf.i18n import _

from dnf.callback import TransactionProgress, TRANS_POST
from dnf.cli import commands


def parse_module_profile(user_input):
    try:
        name, profile = user_input.rsplit("/", 1)
    except ValueError:
        name = user_input
        profile = ModuleCommand.InstallSubCommand.default_profile

    return name, profile


def perform_on_profiles(perform_fn, repo_module_version, profile):
    try:
        selectors = repo_module_version.profile_selectors(profile)
        for single_selector in selectors:
            perform_fn(select=single_selector, optional=False)
    except KeyError:
        raise dnf.exceptions.Error(_("No such module or profile: {} or {}"
                                     .format(repo_module_version.name, profile)))


class ModuleTransactionProgress(TransactionProgress):

    def __init__(self):
        self.repo_modules = []

    def progress(self, package, action, ti_done, ti_total, ts_done, ts_total):
        if action is TRANS_POST:
            for repo_module in self.repo_modules:
                conf = repo_module.conf
                conf.enabled = True
                conf.version = repo_module.parent.latest(repo_module.name).version

                profiles = repo_module.installed_profiles
                profiles.extend(conf.profiles)
                print (profiles)
                print (sorted(set(profiles)))
                conf.profiles = sorted(set(profiles))

                repo_module.write_conf_to_file()


class ModuleCommand(commands.Command):

    class SubCommand(commands.Command):

        def __init__(self, cli):
            super(ModuleCommand.SubCommand, self).__init__(cli)

        def get_all_modules(self):
            return self.base.repo_module_dict

        def _get_module(self, name, stream):
            return self.get_all_modules()[name][stream]

    class ListSubCommand(SubCommand):

        aliases = ('list',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True

        @staticmethod
        def set_argparser(parser):
            narrows = parser.add_mutually_exclusive_group()
            narrows.add_argument('--enabled', dest='enabled',
                                 action='store_true',
                                 help=_("show only enabled modules"))
            narrows.add_argument('--disabled', dest='disabled',
                                 action='store_true',
                                 help=_("show only disabled modules"))

        def run_on_module(self):
            mods = self.get_all_modules()

            if self.opts.enabled:
                print(mods.get_brief_description_enabled())
            elif self.opts.disabled:
                print(mods.get_brief_description_disabled())
            else:
                print(mods.get_brief_description_all())
            return 0

    class InfoSubCommand(SubCommand):

        aliases = ('info',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True

        @staticmethod
        def set_argparser(parser):
            parser.add_argument('module_nsv', nargs='+')

        def run_on_module(self):
            try:
                name, stream, version = self.opts.module_nsv[0].rsplit("-", 2)
                print(self.base.repo_module_dict.get_full_description(name, stream, version))
            except ValueError:
                raise ValueError(_("You need to specify MODULE-STREAM-VERSION"))

    class EnableSubCommand(SubCommand):

        aliases = ('enable',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.root_user = True

        @staticmethod
        def set_argparser(parser):
            parser.add_argument('module_ns', nargs='+')

        def run_on_module(self):
            try:
                name, stream = self.opts.module_ns[0].rsplit("-", 1)
            except ValueError:
                raise ValueError(_("You need to specify MODULE-STREAM"))

            try:
                self.base.repo_module_dict[name].enable(stream, self.opts.assumeyes)
            except KeyError:
                raise ValueError(_("No such module: {}".format(name)))
            except dnf.exceptions.Error as e:
                logger.info(e)
                if not self.opts.assumeno and self.base.output.userconfirm():
                    self.base.repo_module_dict[name].enable(stream, True)
                else:
                    raise dnf.cli.CliError(_("Operation aborted."))

    class DisableSubCommand(SubCommand):

        aliases = ('disable',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.root_user = True

        @staticmethod
        def set_argparser(parser):
            parser.add_argument('module_n', nargs='+')

        def run_on_module(self):
            try:
                self.base.repo_module_dict[self.opts.module_n[0]].disable()
            except KeyError:
                raise ValueError(_("No such module: {}, try specifying only module name"
                                   .format(self.opts.module_n[0])))

    class InstallSubCommand(SubCommand):

        aliases = ('install',)
        default_profile = "baseimage"

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.resolving = True
            demands.root_user = True
            demands.allow_erasing = True
            demands.transaction_display = ModuleTransactionProgress()

        @staticmethod
        def set_argparser(parser):
            parser.add_argument('module_nsp', nargs='+')

        def run_on_module(self):
            for module in self.opts.module_nsp:
                name, profile = parse_module_profile(module)
                repo_module_version = self.base.repo_module_dict.latest(name)

                repo_module = repo_module_version.parent.parent
                transaction_display = self.cli.demands.transaction_display
                transaction_display.repo_modules.append(repo_module)
                repo_module.installed_profiles.append(profile)

                perform_on_profiles(self.base._goal.install, repo_module_version, profile)

    class UpdateSubCommand(SubCommand):

        aliases = ('update',)

        def configure(self):
            demands = self.cli.demands
            demands.available_repos = True
            demands.sack_activation = True
            demands.resolving = True
            demands.root_user = True
            demands.transaction_display = ModuleTransactionProgress()

        @staticmethod
        def set_argparser(parser):
            parser.add_argument('module_n', nargs='+')

        def run_on_module(self):
            for name in self.opts.module_n:
                repo_module_version = self.base.repo_module_dict.latest(name)
                repo_module = repo_module_version.parent.parent

                transaction_display = self.cli.demands.transaction_display
                transaction_display.repo_modules.append(repo_module)

                for profile in repo_module.conf.profiles:
                    perform_on_profiles(self.base._goal.upgrade, repo_module_version, profile)

    SUBCMDS = {ListSubCommand, InfoSubCommand, EnableSubCommand,
               DisableSubCommand, InstallSubCommand, UpdateSubCommand}

    aliases = ("module",)
    summary = _("Interact with Modules.")

    def __init__(self, cli):
        super(ModuleCommand, self).__init__(cli)
        subcmd_objs = (subcmd(cli) for subcmd in self.SUBCMDS)
        self.subcmd = None
        self._subcmd_name2obj = {
            alias: subcmd for subcmd in subcmd_objs for alias in subcmd.aliases}

    def set_argparser(self, parser):
        subparser = parser.add_subparsers(dest='subcmd',
                                          parser_class=argparse.ArgumentParser)
        for subcommand in self._subcmd_name2obj.keys():
            p = subparser.add_parser(subcommand)
            self._subcmd_name2obj[subcommand].set_argparser(p)

    def configure(self):
        try:
            self.subcmd = self._subcmd_name2obj[self.opts.subcmd]
        except (dnf.cli.CliError, KeyError):
            self.cli.optparser.print_usage()
            raise dnf.cli.CliError
        self.subcmd.opts = self.opts
        self.subcmd.configure()

    def run(self):
        if self.opts.help:
            print(self.cli.optparser.print_usage())
            return 0

        self.subcmd.run_on_module()
