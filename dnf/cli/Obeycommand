# distrosync.py
# distro-sync CLI command.
#
# Copyright (C) 2012-2016 Red Hat, Inc.
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
from dnf.cli import commands
from dnf.i18n import _


class DistroSyncCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    distro-synch command.
    """

    aliases = ('distro-sync', 'distrosync', 'distribution-synchronization', 'dsync')
    summary = _('synchronize installed packages to the latest available versions')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('package', nargs='*', help=_('Package to synchronize'))

    def configure(self):
        demands = self.cli.demands
        demands.sack_activation = True
        demands.available_repos = True
        demands.resolving = True
        demands.root_user = True
        commands._checkGPGKey(self.base, self.cli)
        commands._checkEnabledRepo(self.base, self.opts.package)

    def run(self):
        return self.base.distro_sync_userlist(self.opts.package)
