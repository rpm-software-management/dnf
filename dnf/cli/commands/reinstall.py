# reinstall.py
# Reinstall CLI command.
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
from dnf.cli.option_parser import OptionParser
from dnf.i18n import _

import dnf.exceptions
import logging

logger = logging.getLogger('dnf')


class ReinstallCommand(commands.Command):
    """A class containing methods needed by the cli to execute the reinstall command.
    """

    aliases = ('reinstall',)
    summary = _('reinstall a package')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('packages', nargs='+', help=_('Package to reinstall'),
                            action=OptionParser.ParseSpecGroupFileCallback,
                            metavar=_('PACKAGE'))

    def configure(self):
        """Verify that conditions are met so that this command can
        run.  These include that the program is being run by the root
        user, that there are enabled repositories with gpg keys, and
        that this command is called with appropriate arguments.
        """
        demands = self.cli.demands
        demands.sack_activation = True
        demands.available_repos = True
        demands.resolving = True
        demands.root_user = True
        commands._checkGPGKey(self.base, self.cli)
        commands._checkEnabledRepo(self.base, self.opts.filenames)

    def run(self):

        # Reinstall files.
        done = False
        for pkg in self.base.add_remote_rpms(self.opts.filenames, strict=False):
            try:
                self.base.package_reinstall(pkg)
            except dnf.exceptions.MarkingError:
                logger.info(_('No match for argument: %s'),
                            self.base.output.term.bold(pkg.location))
            else:
                done = True

        # Reinstall packages.
        for pkg_spec in self.opts.pkg_specs + ['@' + x for x in self.opts.grp_specs]:
            try:
                self.base.reinstall(pkg_spec)
            except dnf.exceptions.PackagesNotInstalledError as err:
                for pkg in err.packages:
                    logger.info(_('Package %s available, but not installed.'),
                                self.output.term.bold(pkg.name))
                    break
                logger.info(_('No match for argument: %s'),
                            self.base.output.term.bold(pkg_spec))
            except dnf.exceptions.PackagesNotAvailableError as err:
                for pkg in err.packages:
                    xmsg = ''
                    yumdb_info = self.base._yumdb.get_package(pkg)
                    if 'from_repo' in yumdb_info:
                        xmsg = _(' (from %s)') % yumdb_info.from_repo
                    msg = _('Installed package %s%s not available.')
                    logger.info(msg, self.base.output.term.bold(pkg),
                                xmsg)
            except dnf.exceptions.MarkingError:
                assert False, 'Only the above marking errors are expected.'
            else:
                done = True

        if not done:
            raise dnf.exceptions.Error(_('Nothing to do.'))
