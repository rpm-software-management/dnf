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

import support
import dnf.queries
import hawkey

class Reinstall(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockYumBase("main")
        self.yumbase.conf.multilib_policy = "all"
        self.sack = self.yumbase.sack

    def test_reinstall(self):
        txmbrs = self.yumbase.reinstall(pattern="pepper")
        self.assertLength(txmbrs, 1)
        new_set = support.installed_but(self.sack, "pepper")
        new_pkg = dnf.queries.available_by_nevra(self.sack, "pepper-20-0.x86_64")
        new_set += list(new_pkg)
        self.assertResult(self.yumbase, new_set)

    def test_reinstall_local(self):
        txmbrs = self.yumbase.reinstall_local(support.TOUR_50_PKG_PATH)
        self.assertLength(txmbrs, 1)
