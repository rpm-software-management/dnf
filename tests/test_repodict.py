# Copyright (C) 2013-2016 Red Hat, Inc.
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

from __future__ import unicode_literals
from tests import support
from tests.support import TestCase
import dnf.repodict


class TestRepoDict(TestCase):
    def setUp(self):
        conf = support.FakeConf()
        self.x  = support.MockRepo('x', conf)
        self.xx = support.MockRepo('xx', conf)
        self.y  = support.MockRepo('y', conf)
        self.z  = support.MockRepo('z', conf)

        self.repos = dnf.repodict.RepoDict()
        self.repos.add(self.x)
        self.repos.add(self.xx)
        self.repos.add(self.y)
        self.repos.add(self.z)
        self.full_set = {self.x, self.xx, self.y, self.z}

    def test_any_enabled(self):
        self.assertTrue(self.repos._any_enabled())
        self.repos.get_matching("*").disable()
        self.assertFalse(self.repos._any_enabled())

    def test_get_matching(self):
        self.assertEqual(self.repos['x'], self.x)
        self.assertCountEqual(self.repos.get_matching('*'), self.full_set)
        self.assertCountEqual(self.repos.get_matching('y'), {self.y})
        self.assertCountEqual(self.repos.get_matching('x*'), {self.x, self.xx})

        self.assertCountEqual(self.repos.get_matching('nope'), [])

    def test_iter_enabled(self):
        self.assertCountEqual(self.repos.iter_enabled(), self.full_set)
        self.repos.get_matching('x*').disable()
        self.assertCountEqual(self.repos.iter_enabled(), {self.y, self.z})

    def test_all(self):
        self.assertCountEqual(self.repos.all(), self.full_set)
