# upgradeto.py
# Upgrade-to CLI command.
#
# Copyright (C) 2014-2016 Red Hat, Inc.
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
from dnf.cli import commands
from dnf.i18n import _
from dnf.cli.option_parser import OptionParser


class UpgradeToCommand(commands.Command):
    aliases = ('upgrade-to', 'update-to')
    summary = _('upgrade a package on your system to the specified version')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('packages', nargs='*', help=_('Package to upgrade'),
                            action=OptionParser.ParseSpecGroupFileCallback,
                            metavar=_('PACKAGE'))

    def configure(self):
        demands = self.cli.demands
        demands.sack_activation = True
        demands.available_repos = True
        demands.resolving = True
        demands.root_user = True
        commands._checkGPGKey(self.base, self.cli)
        commands._checkEnabledRepo(self.base, self.opts.packages)

    def run(self):
        self.opts.pkg_specs += self.opts.filenames
        return self.base.upgrade_userlist_to(self.opts.pkg_specs)
