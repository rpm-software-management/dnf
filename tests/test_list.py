# Copyright (C) 2012  Red Hat, Inc.
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
import unittest

class List(unittest.TestCase):
    def test_list_installed(self):
        yumbase = base.mock_yum_base()
        ypl = yumbase.doPackageLists('installed')
        self.assertEqual(len(ypl.installed), base.TOTAL_RPMDB_COUNT)

    def test_list_updates(self):
        yumbase = base.mock_yum_base("updates", "main")
        ypl = yumbase.doPackageLists('updates')
        self.assertEqual(len(ypl.updates), 1)
        pkg = ypl.updates[0]
        self.assertEqual(pkg.name, "pepper")
        ypl = yumbase.doPackageLists('updates', ["pepper"])
        self.assertEqual(len(ypl.updates), 1)
        ypl = yumbase.doPackageLists('updates', ["mrkite"])
        self.assertEqual(len(ypl.updates), 0)
