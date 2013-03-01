# Copyright (C) 2013  Red Hat, Inc.
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

import dnf.repodict
from dnf.repo import Repo
import unittest

class TestMultiCall(unittest.TestCase):
    def test_multi_call(self):
        l = dnf.repodict.MultiCallList(["one", "two", "three"])
        self.assertEqual(l.upper(), ["ONE", "TWO", "THREE"])
        self.assertEqual(l.pop(), "three")

class TestRepoDict(unittest.TestCase):
    def setUp(self):
        self.x  = Repo('x')
        self.xx = Repo('xx')
        self.y  = Repo('y')
        self.z  = Repo('z')

        self.repos = dnf.repodict.RepoDict()
        self.repos.add(self.x)
        self.repos.add(self.xx)
        self.repos.add(self.y)
        self.repos.add(self.z)
        self.full_set = {self.x, self.xx, self.y, self.z}

    def test_getmultiple(self):
        self.assertEqual(self.repos['x'], self.x)
        self.assertItemsEqual(self.repos.get_multiple('*'), self.full_set)
        self.assertItemsEqual(self.repos.get_multiple('y'), {self.y})
        self.assertItemsEqual(self.repos.get_multiple('x*'), {self.x, self.xx})

    def test_iter_enabled(self):
        self.assertItemsEqual(self.repos.iter_enabled(), self.full_set)
        self.repos.get_multiple("x*").disable()
        self.assertItemsEqual(self.repos.iter_enabled(), {self.y, self.z})

    def test_all(self):
        self.assertItemsEqual(self.repos.all, self.full_set)
