# search.py
# Search CLI command.
#
# Copyright (C) 2012-2014  Red Hat, Inc.
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


class SearchCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    search command.
    """

    aliases = ('search',)
    summary = _('Search package details for the given string')
    usage = _('QUERY_STRING')

    def configure(self, _):
        demands = self.cli.demands
        demands.available_repos = True
        demands.sack_activation = True

    def doCheck(self, basecmd, extcmds):
        commands.checkItemArg(self.cli, basecmd, extcmds)

    def run(self, extcmds):
        self.base.logger.debug(_('Searching Packages: '))
        return self.cli.search(extcmds)
