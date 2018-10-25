# showvars.py
# showvars CLI command.
#
# Copyright (C) 2016-2018 Red Hat, Inc.
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

import dnf.conf.substitutions

import logging

logger = logging.getLogger("dnf")

class ShowVarsCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    showvars command.
    """

    aliases = ('showvars',)
    summary = _('show all active dnf variables')

    def run(self):
        logger.debug(_('Getting dnf vars for: ' + self.base.conf.installroot))
        dnfvars = dnf.conf.substitutions.Substitutions()
        dnfvars.update_from_etc(self.base.conf.installroot)

        print("releasever=" + self.base.conf.releasever)
        print("basearch=" + self.base.conf.basearch)
        for var in dnfvars:
            print(var + '=' + dnfvars[var])
