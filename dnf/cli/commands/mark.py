# mark.py
# Mark CLI command.
#
# Copyright (C) 2015  Red Hat, Inc.
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
from __future__ import unicode_literals
from dnf.i18n import _
from .. import commands

import dnf
import functools
import logging

logger = logging.getLogger("dnf")


class MarkCommand(commands.Command):

    activate_sack = True
    aliases = ('mark',)
    summary = _("Mark or unmark installed packages as installed by user.")
    usage = "[install|remove [%s]]" % _('PACKAGE')

    @staticmethod
    def _split_cmd(extcmds):
        return extcmds[0], extcmds[1:]

    def __init__(self, cli):
        super(MarkCommand, self).__init__(cli)

    def _mark_install(self, pkg):
        yumdb = self.base.yumdb
        yumdb.get_package(pkg).reason = 'user'
        logger.info(_('%s marked as user installed.'), str(pkg))

    def _mark_remove(self, pkg):
        yumdb = self.base.yumdb
        yumdb.get_package(pkg).reason = 'dep'
        logger.info(_('%s unmarked as user installed.'), str(pkg))

    def configure(self, extcmds):
        demands = self.cli.demands
        demands.sack_activation = True
        demands.root_user = True
        demands.available_repos = False
        demands.resolving = False

    def doCheck(self, basecmd, extcmds):
        if len(extcmds) < 2:
            logger.critical(_('Error: Need a package or list of packages'))
            commands.err_mini_usage(self.cli, basecmd)
            raise dnf.cli.CliError

        cmd, pkgs = self._split_cmd(extcmds)

        if cmd not in ('install', 'remove'):
            commands.err_mini_usage(self.cli, basecmd)
            raise dnf.cli.CliError

    def run(self, extcmds):
        cmd, pkgs = self._split_cmd(extcmds)

        mark_func = functools.partial(getattr(self, '_mark_' + cmd))

        notfound = []
        for pkg in pkgs:
            subj = dnf.subject.Subject(pkg)
            q = subj.get_best_query(self.base.sack)
            for pkg in q:
                mark_func(pkg)
            if len(q) == 0:
                notfound.append(pkg)

        if notfound:
            logger.error(_('Error:'))
            for pkg in notfound:
                logger.error(_('Package %s is not installed.'), pkg)
            raise dnf.cli.CliError
