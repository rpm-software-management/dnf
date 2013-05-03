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
from tests import mock
from tests import support
import dnf.util
import unittest

class Slow(object):
    def __init__(self, val):
        self._val = val
        self.computed = 0

    def new_val(self, val):
        self._val = val
        del self._square1
        del self._square2

    @dnf.util.lazyattr("_square1")
    def square1(self):
        self.computed += 1
        return self._val * self._val

    @property
    @dnf.util.lazyattr("_square2")
    def square2(self):
        self.computed += 1
        return self._val * self._val

class Util(unittest.TestCase):
    def test_am_i_root(self):
        with mock.patch('os.geteuid', return_value=1001):
            self.assertFalse(dnf.util.am_i_root())
        with mock.patch('os.geteuid', return_value=0):
            assert(dnf.util.am_i_root())

    def test_empty(self):
        self.assertTrue(dnf.util.empty(()))
        self.assertFalse(dnf.util.empty([1,2,3]))
        self.assertTrue(dnf.util.empty((x for x in [])))
        self.assertTrue(dnf.util.empty(iter([])))
        self.assertFalse(dnf.util.empty((x for x in [2, 3])))

    def test_file_timestamp(self):
        stat = mock.Mock()
        stat.st_mtime = 123
        with mock.patch('os.stat', return_value=stat):
            self.assertEqual(dnf.util.file_timestamp("/yeah"), 123)
        self.assertRaises(OSError, dnf.util.file_timestamp, "/does/not/ex1st")

    def test_first(self):
        self.assertEqual(dnf.util.first([5, 4, 3]), 5)
        ge = (x for x in range(5, 8))
        self.assertEqual(dnf.util.first(ge), 5)
        self.assertEqual(dnf.util.first([]), None)

        def generator():
            if False:
                yield 10
        self.assertEqual(dnf.util.first(generator()), None)

    def test_group_by_filter(self):
        self.assertEqual(dnf.util.group_by_filter(lambda x: x % 2, xrange(5)),
                         ([1, 3], [0, 2, 4]))
        self.assertEqual(dnf.util.group_by_filter(lambda x: x, xrange(5)),
                         ([1, 2, 3, 4], [0]))

    def test_is_glob_pattern(self):
        assert(dnf.util.is_glob_pattern("all*.ext"))
        assert(dnf.util.is_glob_pattern("all?.ext"))
        assert(not dnf.util.is_glob_pattern("not.ext"))

    def test_lazyattr(self):
        slow = Slow(12)

        self.assertEqual(slow.computed, 0)
        self.assertEqual(slow.square1(), 144)
        self.assertEqual(slow.computed, 1)
        self.assertEqual(slow.square1(), 144)
        self.assertEqual(slow.square1(), 144)
        self.assertEqual(slow.computed, 1)

        self.assertEqual(slow.square2, 144)
        self.assertEqual(slow.computed, 2)
        self.assertEqual(slow.square2, 144)
        self.assertEqual(slow.computed, 2)

        slow.new_val(13)
        self.assertEqual(slow.square1(), 169)
        self.assertEqual(slow.square2, 169)
        self.assertEqual(slow.computed, 4)

    def test_strip_prefix(self):
        self.assertIsNone(dnf.util.strip_prefix("razorblade", "blade"))
        self.assertEqual(dnf.util.strip_prefix("razorblade", "razor"), "blade")

    def test_touch(self):
        self.assertRaises(OSError, dnf.util.touch,
                          support.NONEXISTENT_FILE, no_create=True)
