# reinstall.py
# Reinstall CLI command.
#
# Copyright (C) 2014  Red Hat, Inc.
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


class ReinstallCommand(commands.Command):
    """A class containing s needed by the cli to execute the
    reinstall command.
    """

    activate_sack = True
    aliases = ('reinstall',)
    resolve = True
    summary = _("reinstall a package")
    usage = "%s..." % _('PACKAGE')
    writes_rpmdb = True

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can
        run.  These include that the program is being run by the root
        user, that there are enabled repositories with gpg keys, and
        that this command is called with appropriate arguments.


        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        commands.checkGPGKey(self.base, self.cli)
        commands.checkPackageArg(self.cli, basecmd, extcmds)
        commands.checkEnabledRepo(self.base, extcmds)

    @staticmethod
    def parse_extcmds(extcmds):
        """Parse command arguments."""
        pkg_specs, filenames = [], []
        for argument in extcmds:
            if argument.endswith('.rpm'):
                filenames.append(argument)
            else:
                pkg_specs.append(argument)
        return pkg_specs, filenames

    def run(self, extcmds):
        pkg_specs, filenames = self.parse_extcmds(extcmds)

        # Reinstall files.
        local_pkgs = map(self.base.add_remote_rpm, filenames)
        results = map(self.base.package_reinstall, local_pkgs)
        done = functools.reduce(operator.or_, results, False)

        # Reinstall packages.
        for pkg_spec in pkg_specs:
            try:
                self.base.reinstall(pkg_spec)
            except dnf.exceptions.PackagesNotInstalledError:
                logger.info(_('No match for argument: %s'), pkg_spec)
            except dnf.exceptions.PackagesNotAvailableError as err:
                for pkg in err.packages:
                    xmsg = ''
                    yumdb_info = self.base.yumdb.get_package(pkg)
                    if 'from_repo' in yumdb_info:
                        xmsg = _(' (from %s)') % yumdb_info.from_repo
                    msg = _('Installed package %s%s%s%s not available.')
                    logger.info(msg, self.base.output.term.MODE['bold'], pkg,
                                self.base.output.term.MODE['normal'], xmsg)
            except dnf.exceptions.MarkingError:
                assert False, 'Only the above marking errors are expected.'
            else:
                done = True

        if not done:
            raise dnf.exceptions.Error(_('Nothing to do.'))
