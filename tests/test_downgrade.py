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
import dnf.queries

class DowngradeTest(support.ResultTestCase):
    def test_downgrade_local(self):
        yumbase = support.MockYumBase()
        sack = yumbase.sack

        cnt = yumbase.downgrade_local(support.TOUR_44_PKG_PATH)
        self.assertGreater(cnt, 0)
        (installed, removed) = self.installed_removed(yumbase)
        self.assertItemsEqual(map(str, installed), ("tour-4-4.noarch", ))
        self.assertItemsEqual(map(str, removed), ("tour-5-0.noarch", ))

    def test_downgrade(self):
        yumbase = support.MockYumBase("main")
        sack = yumbase.sack
        cnt = yumbase.downgrade("tour")
        self.assertGreater(cnt, 0)

        new_pkg = dnf.queries.available_by_name(sack, "tour")[0]
        self.assertEqual(new_pkg.evr, "4.6-1")
        new_set = support.installed_but(sack, "tour") + [new_pkg]
        self.assertResult(yumbase, new_set)

    def test_downgrade2(self):
        b = support.MockYumBase("old_versions")
        ret = b.downgrade("tour")
        installed, removed = self.installed_removed(b)
        self.assertItemsEqual(map(str, installed), ['tour-4.9-1.noarch'])
        self.assertItemsEqual(map(str, removed), ['tour-5-0.noarch'])
