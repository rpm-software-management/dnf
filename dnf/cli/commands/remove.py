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
import dnf.base
import argparse
import hawkey
import dnf.exceptions
import logging

logger = logging.getLogger("dnf")


class RemoveCommand(commands.Command):
    """Remove command."""

    nevra_forms = {'remove-n': hawkey.FORM_NAME,
                   'remove-na': hawkey.FORM_NA,
                   'remove-nevra': hawkey.FORM_NEVRA,
                   'erase-n': hawkey.FORM_NAME,
                   'erase-na': hawkey.FORM_NA,
                   'erase-nevra': hawkey.FORM_NEVRA}

    aliases = ('remove', 'erase',) + tuple(nevra_forms.keys())
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
        # disable all available repos to delete whole dependency tree
        # instead of replacing removable package with available packages
        demands.resolving = True
        demands.root_user = True
        demands.sack_activation = True
        if self.opts.duplicated:
            demands.available_repos = True
        elif dnf.base.WITH_MODULES and self.opts.grp_specs:
            demands.available_repos = True
            demands.fresh_metadata = False
            demands.allow_erasing = True
        else:
            demands.allow_erasing = True
            demands.available_repos = False

    def run(self):

        forms = [self.nevra_forms[command] for command in self.opts.command
                 if command in list(self.nevra_forms.keys())]

        # local pkgs not supported in erase command
        self.opts.pkg_specs += self.opts.filenames
        done = False

        if self.opts.duplicated:
            q = self.base.sack.query()
            instonly = self.base._get_installonly_query(q.installed())
            dups = q.duplicated().difference(instonly)
            if not dups:
                raise dnf.exceptions.Error(_('No duplicated packages found for removal.'))

            for (name, arch), pkgs_list in dups._na_dict().items():
                if len(pkgs_list) < 2:
                    continue
                pkgs_list.sort(reverse=True)
                try:
                    self.base.reinstall(str(pkgs_list[0]))
                except dnf.exceptions.PackagesNotAvailableError:
                    xmsg = ''
                    msg = _('Installed package %s%s not available.')
                    logger.warning(msg, self.base.output.term.bold(str(pkgs_list[0])), xmsg)

                for pkg in pkgs_list[1:]:
                    self.base.package_remove(pkg)
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
        if self.opts.grp_specs and forms:
            for grp_spec in self.opts.grp_specs:
                msg = _('Not a valid form: %s')
                logger.warning(msg, self.base.output.term.bold(grp_spec))
        elif self.opts.grp_specs:
            if dnf.base.WITH_MODULES:
                module_base = dnf.module.module_base.ModuleBase(self.base)
                skipped_grps = module_base.remove(self.opts.grp_specs)
                if len(self.opts.grp_specs) != len(skipped_grps):
                    done = True
            else:
                skipped_grps = self.opts.grp_specs

            if skipped_grps:
                self.base.read_comps(arch_filter=True)
                for group in skipped_grps:
                    try:
                        if self.base.env_group_remove([group]):
                            done = True
                    except dnf.exceptions.Error:
                        pass

        for pkg_spec in self.opts.pkg_specs:
            try:
                self.base.remove(pkg_spec, forms=forms)
            except dnf.exceptions.MarkingError:
                logger.info(_('No match for argument: %s'),
                                      pkg_spec)
            else:
                done = True

        if not done:
            logger.warning(_('No packages marked for removal.'))
