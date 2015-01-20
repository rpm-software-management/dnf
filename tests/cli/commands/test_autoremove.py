# Copyright (C) 2014-2015 Red Hat, Inc.
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
from tests import support

import dnf.cli.commands.autoremove as autoremove


class AutoRemoveCommandTest(support.ResultTestCase):

    def test_run(self):
        base = support.MockBase()
        q = base.sack.query()
        pkgs = list(q.filter(name='librita')) + list(q.filter(name='pepper'))
        yumdb = base.yumdb
        for pkg in pkgs:
            yumdb.get_package(pkg).reason = 'dep'

        cli = base.mock_cli()
        cmd = autoremove.AutoremoveCommand(cli)
        cmd.run([])
        inst, rem = self.installed_removed(base)
        self.assertEmpty(inst)
        removed = ('librita-1-1.i686', 'librita-1-1.x86_64', 'pepper-20-0.x86_64')
        self.assertCountEqual((map(str, rem)), removed)
