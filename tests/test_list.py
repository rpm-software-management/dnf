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
import unittest

class List(support.TestCase):
    def test_list_installed(self):
        yumbase = support.MockBase()
        ypl = yumbase.doPackageLists('installed')
        self.assertEqual(len(ypl.installed), support.TOTAL_RPMDB_COUNT)

    def test_list_updates(self):
        yumbase = support.MockBase("updates", "main")
        ypl = yumbase.doPackageLists('upgrades')
        self.assertEqual(len(ypl.updates), support.UPDATES_NSOLVABLES - 1)
        pkg = ypl.updates[0]
        self.assertEqual(pkg.name, "pepper")
        ypl = yumbase.doPackageLists('upgrades', ["pepper"])
        self.assertEqual(len(ypl.updates), 1)
        ypl = yumbase.doPackageLists('upgrades', ["mrkite"])
        self.assertEqual(len(ypl.updates), 0)

        ypl = yumbase.doPackageLists('upgrades', ["hole"])
        self.assertEqual(len(ypl.updates), 2)

    def test_lists_multiple(self):
        yumbase = support.MockBase('updates', "main")
        ypl = yumbase.doPackageLists('upgrades', ['pepper', 'hole'])
        self.assertLength(ypl.updates, 3)

class TestListAllRepos(support.TestCase):
    def setUp(self):
        self.yumbase = support.MockBase("main", "updates")
        self.yumbase.conf.multilib_policy = "all"

    def test_list_pattern(self):
        ypl = self.yumbase.doPackageLists('all', ['hole'])
        self.assertLength(ypl.installed, 1)
        self.assertLength(ypl.available, 2)

    def test_list_pattern_arch(self):
        ypl = self.yumbase.doPackageLists('all', ['hole.x86_64'])
        self.assertLength(ypl.installed, 1)
        self.assertLength(ypl.available, 1)

    def test_list_available(self):
        ypl = self.yumbase.doPackageLists('available', ['hole'], showdups=False)
        self.assertItemsEqual(map(str, ypl.available), ('hole-2-1.i686',
                                                        'hole-2-1.x86_64'))

        ypl = self.yumbase.doPackageLists('available', ['hole'], showdups=True)
        self.assertItemsEqual(map(str, ypl.available), ('hole-2-1.i686',
                                                        'hole-2-1.x86_64',
                                                        'hole-1-2.x86_64'))
