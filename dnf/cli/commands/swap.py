#
# Copyright (C) 2016 Red Hat, Inc.
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

from __future__ import absolute_import
from __future__ import unicode_literals
from dnf.i18n import _
from dnf.cli import commands

import dnf.util
import logging

logger = logging.getLogger("dnf")


class SwapCommand(commands.Command):
    """A class containing methods needed by the cli to execute the swap command.
    """

    aliases = ('swap',)
    summary = _('run an interactive {prog} mod for remove and install one spec').format(
        prog=dnf.util.MAIN_PROG_UPPER)

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('remove_spec', action="store", help=_('The specs that will be removed'))
        parser.add_argument('install_spec', action="store", help=_(
            'The specs that will be installed'))

    def configure(self):
        demands = self.cli.demands
        demands.sack_activation = True
        demands.available_repos = True
        demands.resolving = True
        demands.root_user = True
        commands._checkGPGKey(self.base, self.cli)
        commands._checkEnabledRepo(self.base, [self.opts.install_spec])

    def _perform(self, cmd_str, spec):
        cmd_cls = self.cli.cli_commands.get(cmd_str)
        if cmd_cls is not None:
            cmd = cmd_cls(self.cli)
            self.cli.optparser.parse_command_args(cmd, [cmd_str, spec])
            cmd.run()

    def run(self):
        # The install part must be performed before the remove one because it can
        # operate on local rpm files. Command line packages cannot be added
        # to the sack once the goal is created.
        self._perform('install', self.opts.install_spec)
        self._perform('remove', self.opts.remove_spec)
