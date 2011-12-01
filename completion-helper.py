#!/usr/bin/python -t
# -*- coding: utf-8 -*-
#
# Copyright (C) 2011 Ville Skyttä
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
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


import sys

import cli
import yumcommands


class GroupsCompletionCommand(yumcommands.GroupsCommand):
    def doCommand(self, base, basecmd, extcmds):
        cmd, extcmds = self._grp_cmd(basecmd, extcmds)
        # case insensitivity is fine here because groupinstall etc are that too
        installed, available = base.doGroupLists()
        if extcmds[0] in ("installed", "all"):
            for group in installed:
                print group.ui_name
        if extcmds[0] in ("available", "all"):
            for group in available:
                print group.ui_name

class ListCompletionCommand(yumcommands.ListCommand):
    def doCommand(self, base, basecmd, extcmds):
        ypl = base.doPackageLists(pkgnarrow=extcmds[0])
        if extcmds[0] in ("installed", "all"):
            for pkg in ypl.installed:
                print pkg.na
        if extcmds[0] in ("available", "all"):
            for pkg in ypl.available:
                print pkg.na

class RepoListCompletionCommand(yumcommands.RepoListCommand):
    def doCommand(self, base, basecmd, extcmds):
        for repo in base.repos.repos.values():
            if extcmds[0] == "all" \
                    or (extcmds[0] == "enabled" and repo.isEnabled()) \
                    or (extcmds[0] == "disabled" and not repo.isEnabled()):
                print repo.id


def main(args):
    base = cli.YumBaseCli()
    base.yum_cli_commands.clear()
    base.registerCommand(GroupsCompletionCommand())
    base.registerCommand(ListCompletionCommand())
    base.registerCommand(RepoListCompletionCommand())
    base.getOptionsConfig(args)
    base.parseCommands()
    base.doCommands()

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except KeyboardInterrupt, e:
        sys.exit(1)
