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

import base
import dnf.queries

class UpgradeTo(base.ResultTestCase):
    def test_upgrade_to(self):
        yumbase = base.MockYumBase("main", "updates")
        sack = yumbase.sack
        yumbase.upgrade_to("pepper-20-1.x86_64")
        self.assertLength(yumbase.tsInfo, 1)
        new_set = base.installed_but(sack, "pepper").run()
        new_set.extend(dnf.queries.available_by_nevra(sack, "pepper-20-1.x86_64"))
        self.assertResult(yumbase, new_set)
