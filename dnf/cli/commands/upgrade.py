# upgrade.py
# Upgrade CLI command.
#
# Copyright (C) 2014 Red Hat, Inc.
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
import functools
import logging
import operator

logger = logging.getLogger('dnf')


class UpgradeCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    update command.
    """
    aliases = ('upgrade', 'update')
    activate_sack = True
    resolve = True
    summary = _("Upgrade a package or packages on your system")
    usage = "[%s...]" % _('PACKAGE')
    writes_rpmdb = True

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can run.

        These include that there are enabled repositories with gpg
        keys, and that this command is being run by the root user.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        commands.checkGPGKey(self.base, self.cli)
        commands.checkEnabledRepo(self.base, extcmds)

    def run(self, extcmds):
        pkg_specs, grp_specs, filenames = commands.parse_spec_group_file(
            extcmds)

        if pkg_specs or grp_specs or filenames:
            # Update files.
            local_pkgs = map(self.base.add_remote_rpm, filenames)
            results = map(self.base.package_upgrade, local_pkgs)
            done = functools.reduce(operator.or_, results, False)

            # Update packages.
            for pkg_spec in pkg_specs:
                try:
                    self.base.upgrade(pkg_spec)
                except dnf.exceptions.MarkingError:
                    logger.info(_('No match for argument: %s'), pkg_spec)
                else:
                    done = True

            # Update groups.
            if grp_specs:
                self.base.read_comps()
                self.base.env_group_upgrade(grp_specs)
                done = True
        else:
            # Update all packages.
            self.base.upgrade_all()
            done = True

        if not done:
            raise dnf.exceptions.Error(_('No packages marked for upgrade.'))
