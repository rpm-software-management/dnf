# autoremove.py
# Autoremove CLI command.
#
# Copyright (C) 2014-2015  Red Hat, Inc.
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


class AutoremoveCommand(commands.Command):

    aliases = ('autoremove',)

    def configure(self, _):
        demands = self.cli.demands
        demands.available_repos = True
        demands.fresh_metadata = False
        demands.resolving = True
        demands.root_user = True
        demands.sack_activation = True

    def run(self, extcmds):
        base = self.base
        pkgs = base.sack.query().unneeded(base.sack, base.yumdb,
                                          debug_solver=base.conf.debug_solver)
        for pkg in pkgs:
            base.package_remove(pkg)
