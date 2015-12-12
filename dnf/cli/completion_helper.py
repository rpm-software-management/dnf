#!/usr/bin/env python
#
# This file is part of dnf.
#
# Copyright 2015 (C) Igor Gnatenko <i.gnatenko.brain@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301  USA

import dnf.exceptions
import dnf.cli
import sys


def filter_list_by_kw(kw, lst):
    return filter(lambda k: str(k).startswith(kw), lst)

def listpkg_to_setstr(pkgs):
    return set([str(x) for x in pkgs])

class RemoveCompletionCommand(dnf.cli.commands.remove.RemoveCommand):
    def __init__(self, args):
        super(RemoveCompletionCommand, self).__init__(args)

    def configure(self, args):
        self.cli.demands.root_user = False
        self.cli.demands.sack_activation = True

    def run(self, args):
        for pkg in ListCompletionCommand.installed(self.base, args[0]):
            print(str(pkg))


class InstallCompletionCommand(dnf.cli.commands.install.InstallCommand):
    def __init__(self, args):
        super(InstallCompletionCommand, self).__init__(args)

    def configure(self, args):
        self.cli.demands.root_user = False
        self.cli.demands.available_repos = True
        self.cli.demands.sack_activation = True

    def run(self, args):
        installed =  listpkg_to_setstr(ListCompletionCommand.installed(self.base, args[0]))
        available = listpkg_to_setstr(ListCompletionCommand.available(self.base, args[0]))
        for pkg in (available - installed):
            print(str(pkg))


class ReinstallCompletionCommand(dnf.cli.commands.reinstall.ReinstallCommand):
    def __init__(self, args):
        super(ReinstallCompletionCommand, self).__init__(args)

    def configure(self, args):
        self.cli.demands.root_user = False
        self.cli.demands.available_repos = True
        self.cli.demands.sack_activation = True

    def run(self, args):
        installed =  listpkg_to_setstr(ListCompletionCommand.installed(self.base, args[0]))
        available = listpkg_to_setstr(ListCompletionCommand.available(self.base, args[0]))
        for pkg in (installed & available):
            print(str(pkg))

class ListCompletionCommand(dnf.cli.commands.ListCommand):
    def __init__(self, args):
        super(ListCompletionCommand, self).__init__(args)

    def run(self, args):
        subcmds = self.__class__.__base__.usage[1:-1].split("|")[1:]
        if args[0] not in subcmds:
            print("\n".join(filter_list_by_kw(args[1], subcmds)))
        else:
            if args[0] == "installed":
                pkgs = self.installed(self.base, args[1])
            elif args[0] == "available":
                pkgs = self.available(self.base, args[1])
            elif args[0] == "updates":
                pkgs = self.updates(self.base, args[1])
            else:
                return
            for pkg in pkgs:
                print(str(pkg))

    @staticmethod
    def installed(base, arg):
        return base.sack.query().installed().filter(name__glob="{}*".format(arg))

    @staticmethod
    def available(base, arg):
        return base.sack.query().available().filter(name__glob="{}*".format(arg))

    @staticmethod
    def updates(base, arg):
        return base.check_updates(["{}*".format(arg)], print_=False)


class RepoListCompletionCommand(dnf.cli.commands.repolist.RepoListCommand):
    def __init__(self, args):
        super(RepoListCompletionCommand, self).__init__(args)

    def run(self, args):
        if args[0] == "enabled":
            print("\n".join(filter_list_by_kw(args[1], [r.id for r in self.base.repos.iter_enabled()])))
        elif args[0] == "disabled":
            print("\n".join(filter_list_by_kw(args[1], [r.id for r in self.base.repos.all() if not r.enabled])))


class UpgradeCompletionCommand(dnf.cli.commands.upgrade.UpgradeCommand):
    def __init__(self, args):
        super(UpgradeCompletionCommand, self).__init__(args)

    def configure(self, args):
        self.cli.demands.root_user = False
        self.cli.demands.available_repos = True
        self.cli.demands.sack_activation = True

    def run(self, args):
        for pkg in ListCompletionCommand.updates(self.base, args[0]):
            print(str(pkg))


class DowngradeCompletionCommand(dnf.cli.commands.downgrade.DowngradeCommand):
    def __init__(self, args):
        super(DowngradeCompletionCommand, self).__init__(args)

    def configure(self, args):
        self.cli.demands.root_user = False
        self.cli.demands.available_repos = True
        self.cli.demands.sack_activation = True

    def run(self, args):
        for pkg in ListCompletionCommand.available(self.base, args[0]).downgrades():
            print(str(pkg))


class CleanCompletionCommand(dnf.cli.commands.clean.CleanCommand):
    def __init__(self, args):
        super(CleanCompletionCommand, self).__init__(args)

    def run(self, args):
        subcmds = self.__class__.__base__.usage[1:-1].split("|")
        print("\n".join(filter_list_by_kw(args[1], subcmds)))


class HistoryCompletionCommand(dnf.cli.commands.HistoryCommand):
    def __init__(self, args):
        super(HistoryCompletionCommand, self).__init__(args)

    def run(self, args):
        subcmds = self.__class__.__base__.usage[1:-1].split("|")[1:]
        if args[0] not in subcmds:
            print("\n".join(filter_list_by_kw(args[1], subcmds)))


def main(args):
    base = dnf.cli.cli.BaseCli()
    cli = dnf.cli.Cli(base)
    if args[0] == "_cmds":
        base.plugins.load(base.conf.pluginpath, [])
        base.plugins.run_init(base, cli)
        print("\n".join(filter_list_by_kw(args[1], cli.cli_commands)))
        return
    cli.cli_commands.clear()
    cli.register_command(RemoveCompletionCommand)
    cli.register_command(InstallCompletionCommand)
    cli.register_command(ReinstallCompletionCommand)
    cli.register_command(ListCompletionCommand)
    cli.register_command(RepoListCompletionCommand)
    cli.register_command(UpgradeCompletionCommand)
    cli.register_command(DowngradeCompletionCommand)
    cli.register_command(CleanCompletionCommand)
    cli.register_command(HistoryCompletionCommand)
    cli.configure(args)
    try:
        cli.run()
    except dnf.exceptions.Error:
        sys.exit(0)

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt:
        sys.exit(1)
