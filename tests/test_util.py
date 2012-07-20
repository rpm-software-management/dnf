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

import unittest
import mock
import dnf.util

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

    def test_file_timestamp(self):
        stat = mock.Mock()
        stat.st_mtime = 123
        with mock.patch('os.stat', return_value=stat):
            self.assertEqual(dnf.util.file_timestamp("/yeah"), 123)
        self.assertRaises(OSError, dnf.util.file_timestamp, "/does/not/ex1st")

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
