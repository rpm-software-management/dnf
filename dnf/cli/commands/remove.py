# remove_command.py
# Remove CLI command.
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
from __future__ import unicode_literals
from dnf.cli import commands
from dnf.i18n import _
from dnf.cli.option_parser import OptionParser

import argparse
import dnf.exceptions
import logging

logger = logging.getLogger("dnf")


class RemoveCommand(commands.Command):
    """Remove command."""

    aliases = ('remove', 'erase')
    summary = _('remove a package or packages from your system')

    @staticmethod
    def set_argparser(parser):
        mgroup = parser.add_mutually_exclusive_group()
        mgroup.add_argument('--duplicates', action='store_true',
                            dest='duplicated',
                            help=_('remove duplicated packages'))
        mgroup.add_argument('--duplicated', action='store_true',
                            help=argparse.SUPPRESS)
        mgroup.add_argument('--oldinstallonly', action='store_true',
                            help=_(
                                'remove installonly packages over the limit'))
        parser.add_argument('packages', nargs='*', help=_('Package to remove'),
                            action=OptionParser.ParseSpecGroupFileCallback,
                            metavar=_('PACKAGE'))

    def configure(self):
        demands = self.cli.demands
        demands.allow_erasing = True
        # disable all available repos to delete whole dependency tree
        # instead of replacing removable package with available packages
        demands.available_repos = False
        demands.resolving = True
        demands.root_user = True
        demands.sack_activation = True

    def run(self):
        # local pkgs not supported in erase command
        self.opts.pkg_specs += self.opts.filenames
        done = False

        if self.opts.duplicated:
            q = self.base.sack.query()
            instonly = self.base._get_installonly_query(q.installed())
            dups = q.duplicated().difference(instonly).latest(-1)
            if dups:
                for pkg in dups:
                    self.base.package_remove(pkg)
            else:
                raise dnf.exceptions.Error(
                    _('No duplicated packages found for removal.'))
            return
        if self.opts.oldinstallonly:
            q = self.base.sack.query()
            instonly = self.base._get_installonly_query(q.installed()).latest(
                - self.base.conf.installonly_limit)
            if instonly:
                for pkg in instonly:
                    self.base.package_remove(pkg)
            else:
                raise dnf.exceptions.Error(
                    _('No old installonly packages found for removal.'))
            return

        # Remove groups.
        if self.opts.grp_specs:
            self.base.read_comps(arch_filter=True)
            if self.base.env_group_remove(self.opts.grp_specs):
                done = True

        for pkg_spec in self.opts.pkg_specs:
            try:
                self.base.remove(pkg_spec)
            except dnf.exceptions.MarkingError:
                logger.info(_('No match for argument: %s'),
                                      pkg_spec)
            else:
                done = True

        if not done:
            raise dnf.exceptions.Error(_('No packages marked for removal.'))
