# remove_command.py
# Remove CLI command.
#
# Copyright (C) 2012-2015  Red Hat, Inc.
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
from .. import commands
from dnf.i18n import _

import dnf.exceptions
import logging

logger = logging.getLogger("dnf")


class RemoveCommand(commands.Command):
    """Remove command."""

    aliases = ('remove', 'erase')
    summary = _("Remove a package or packages from your system")
    usage = "%s..." % _('PACKAGE')

    def configure(self, _):
        demands = self.cli.demands
        demands.allow_erasing = True
        # disable all available repos to delete whole dependency tree
        # instead of replacing removable package with available packages
        demands.available_repos = False
        demands.resolving = True
        demands.root_user = True
        demands.sack_activation = True

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run.  These include that the program is being run by the root
        user, and that this command is called with appropriate
        arguments.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        commands.checkPackageArg(self.cli, basecmd, extcmds)

    def run(self, extcmds):
        pkg_specs, grp_specs, filenames = commands.parse_spec_group_file(
            extcmds)
        pkg_specs += filenames  # local pkgs not supported in erase command
        done = False

        # Remove groups.
        if grp_specs:
            self.base.read_comps()
            if self.base.env_group_remove(grp_specs):
                done = True

        for pkg_spec in pkg_specs:
            try:
                self.base.remove(pkg_spec)
            except dnf.exceptions.MarkingError:
                logger.info(_('No match for argument: %s'),
                                      pkg_spec)
            else:
                done = True

        if not done:
            raise dnf.exceptions.Error(_('No packages marked for removal.'))
