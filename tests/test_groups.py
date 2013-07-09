# Copyright (C) 2012-2013  Red Hat, Inc.
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
import operator
import dnf.util

class SelectGroupTest(support.ResultTestCase):
    def setUp(self):
        self.base = support.MockYumBase("main")
        self.base.read_mock_comps(support.COMPS_PATH)

    def test_install(self):
        comps = self.base.comps
        grp = dnf.util.first(comps.groups_by_pattern("Solid Ground"))
        self.assertEqual(self.base.select_group(grp), 1)
        inst, removed = self.installed_removed(self.base)
        self.assertItemsEqual([pkg.name for pkg in inst], ("trampoline",))
        self.assertLength(removed, 0)
