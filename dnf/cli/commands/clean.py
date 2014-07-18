# clean.py
# Clean CLI command.
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

import dnf.cli

def _check_args(cli, basecmd, extcmds):
    """Verify that extcmds are valid options for clean."""

    valid_args = ('packages', 'metadata', 'dbcache', 'plugins',
                  'expire-cache', 'rpmdb', 'all')

    if len(extcmds) == 0:
        cli.logger.critical(_('Error: clean requires an option: %s') % (
            ", ".join(valid_args)))

    for cmd in extcmds:
        if cmd not in valid_args:
            cli.logger.critical(_('Error: invalid clean argument: %r') % cmd)
            commands.err_mini_usage(cli, basecmd)
            raise dnf.cli.CliError


class CleanCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    clean command.
    """

    aliases = ('clean',)
    summary = _("Remove cached data")
    usage = "[packages|metadata|dbcache|plugins|expire-cache|all]"

    def doCheck(self, basecmd, extcmds):
        """Verify that conditions are met so that this command can run.
        These include that there is at least one enabled repository,
        and that this command is called with appropriate arguments.

        :param basecmd: the name of the command
        :param extcmds: the command line arguments passed to *basecmd*
        """
        _check_args(self.cli, basecmd, extcmds)
        commands.checkEnabledRepo(self.base)

    def run(self, extcmds):
        return self.base.cleanCli(extcmds)
