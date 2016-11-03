# upgrade.py
# Upgrade CLI command.
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

import dnf.exceptions
import logging

logger = logging.getLogger('dnf')


class UpgradeCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    update command.
    """
    aliases = ('upgrade', 'update')
    summary = _('upgrade a package or packages on your system')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('packages', nargs='*', help=_('Package to upgrade'),
                            action=OptionParser.ParseSpecGroupFileCallback,
                            metavar=_('PACKAGE'))

    def configure(self):
        """Verify that conditions are met so that this command can run.

        These include that there are enabled repositories with gpg
        keys, and that this command is being run by the root user.
        """
        demands = self.cli.demands
        demands.sack_activation = True
        demands.available_repos = True
        demands.resolving = True
        demands.root_user = True
        commands._checkGPGKey(self.base, self.cli)
        commands._checkEnabledRepo(self.base, self.opts.pkg_specs)
        self.upgrade_minimal = None
        self.all_security = None

    def run(self):
        self.cli._populate_update_security_filter(self.opts,
                                                  minimal=self.upgrade_minimal,
                                                  all=self.all_security)
        done = False
        if self.opts.filenames or self.opts.pkg_specs or self.opts.grp_specs:
            # Update files.
            if self.opts.filenames:
                for pkg in self.base.add_remote_rpms(self.opts.filenames, strict=False):
                    try:
                        self.base.package_upgrade(pkg)
                    except dnf.exceptions.MarkingError as e:
                        logger.info(_('No match for argument: %s'),
                                    self.base.output.term.bold(pkg.location))
                    else:
                        done = True

            # Update packages.
            for pkg_spec in self.opts.pkg_specs:
                try:
                    self.base.upgrade(pkg_spec)
                except dnf.exceptions.MarkingError as e:
                    logger.info(_('No match for argument: %s'),
                                 self.base.output.term.bold(pkg_spec))
                else:
                    done = True

            # Update groups.
            if self.opts.grp_specs:
                self.base.read_comps(arch_filter=True)
                self.base.env_group_upgrade(self.opts.grp_specs)
                done = True
        else:
            # Update all packages.
            self.base.upgrade_all()
            done = True
        if not done:
            raise dnf.exceptions.Error(_('No packages marked for upgrade.'))
