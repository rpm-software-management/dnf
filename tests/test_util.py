# -*- coding: utf-8 -*-

# Copyright (C) 2012-2018 Red Hat, Inc.
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
from __future__ import unicode_literals

import operator
import os

import dnf.util

import tests.support
from tests.support import mock


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


class Util(tests.support.TestCase):
    def test_am_i_root(self):
        with mock.patch('os.geteuid', return_value=1001):
            self.assertFalse(dnf.util.am_i_root())
        with mock.patch('os.geteuid', return_value=0):
            assert(dnf.util.am_i_root())

    def test_bunch(self):
        b = dnf.util.Bunch()
        self.assertRaises(AttributeError, lambda: b.more)
        b.garden = 'weeds'
        self.assertEqual(b['garden'], 'weeds')
        b['digging'] = 4
        self.assertEqual(b.digging, 4)

    def test_empty(self):
        self.assertTrue(dnf.util.empty(()))
        self.assertFalse(dnf.util.empty([1, 2, 3]))
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

    def test_get_in(self):
        dct = {1: {2: 3},
               5: {8: {9: 10}}}

        self.assertEqual(dnf.util.get_in(dct, (5, 8, 9), -3), 10)
        self.assertEqual(dnf.util.get_in(dct, (5, 8, 8), -3), -3)
        self.assertEqual(dnf.util.get_in(dct, (0, 8, 8), -3), -3)

    def test_group_by_filter(self):
        self.assertEqual(dnf.util.group_by_filter(lambda x: x % 2, range(5)),
                         ([1, 3], [0, 2, 4]))
        self.assertEqual(dnf.util.group_by_filter(lambda x: x, range(5)),
                         ([1, 2, 3, 4], [0]))

    def test_insert_if(self):
        """Test insert_if with sometimes fulfilled condition."""
        item = object()
        iterable = range(4)

        def condition(item):
            return item % 2 == 0

        iterator = dnf.util.insert_if(item, iterable, condition)

        self.assertEqual(next(iterator), item)
        self.assertEqual(next(iterator), 0)
        self.assertEqual(next(iterator), 1)
        self.assertEqual(next(iterator), item)
        self.assertEqual(next(iterator), 2)
        self.assertEqual(next(iterator), 3)
        self.assertRaises(StopIteration, next, iterator)

    def test_is_exhausted_true(self):
        """Test is_exhausted with an iterator which is exhausted."""
        iterator = iter(())

        result = dnf.util.is_exhausted(iterator)

        self.assertTrue(result)

    def test_is_exhausted_false(self):
        """Test is_exhausted with an iterator which is not exhausted."""
        iterator = iter((1,))

        result = dnf.util.is_exhausted(iterator)

        self.assertFalse(result)

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

    def test_mapall(self):
        l = [1, 2, 3]
        out = dnf.util.mapall(lambda n: 2 * n, l)
        self.assertIsInstance(out, list)
        self.assertEqual(out, [2, 4, 6])

    def test_partition(self):
        l = list(range(6))
        smaller, larger = dnf.util.partition(lambda i: i > 4, l)
        self.assertCountEqual(smaller, (0, 1, 2, 3, 4))
        self.assertCountEqual(larger, (5,))

    def test_split_by(self):
        """Test split_by with sometimes fulfilled condition."""
        iterable = range(7)

        def condition(item):
            return item % 3 == 0

        iterator = dnf.util.split_by(iterable, condition)

        self.assertEqual(next(iterator), ())
        self.assertEqual(next(iterator), (0, 1, 2))
        self.assertEqual(next(iterator), (3, 4, 5))
        self.assertEqual(next(iterator), (6,))
        self.assertRaises(StopIteration, next, iterator)

    def test_split_by_empty(self):
        """Test split with empty iterable."""
        iterable = []

        def condition(item):
            return item % 3 == 0

        iterator = dnf.util.split_by(iterable, condition)

        self.assertEqual(next(iterator), ())
        self.assertRaises(StopIteration, next, iterator)

    def test_strip_prefix(self):
        self.assertIsNone(dnf.util.strip_prefix("razorblade", "blade"))
        self.assertEqual(dnf.util.strip_prefix("razorblade", "razor"), "blade")

    def test_touch(self):
        self.assertRaises(OSError, dnf.util.touch,
                          tests.support.NONEXISTENT_FILE, no_create=True)

    def test_split_path(self):
        path_orig = ""
        path_split = dnf.util.split_path(path_orig)
        path_join = os.path.join(*path_split)
        self.assertEqual(path_split, [""])
        self.assertEqual(path_join, path_orig)

        path_orig = "/"
        path_split = dnf.util.split_path(path_orig)
        path_join = os.path.join(*path_split)
        self.assertEqual(path_split, ["/"])
        self.assertEqual(path_join, path_orig)

        path_orig = "abc"
        path_split = dnf.util.split_path(path_orig)
        path_join = os.path.join(*path_split)
        self.assertEqual(path_split, ["abc"])
        self.assertEqual(path_join, path_orig)

        path_orig = "/a/bb/ccc/dddd.conf"
        path_split = dnf.util.split_path(path_orig)
        path_join = os.path.join(*path_split)
        self.assertEqual(path_split, ["/", "a", "bb", "ccc", "dddd.conf"])
        self.assertEqual(path_join, path_orig)


class TestMultiCall(tests.support.TestCase):
    def test_multi_call(self):
        l = dnf.util.MultiCallList(["one", "two", "three"])
        self.assertEqual(l.upper(), ["ONE", "TWO", "THREE"])
        self.assertEqual(l.pop(), "three")

    def test_assignment(self):
        o1 = mock.Mock(x=3)
        o2 = mock.Mock(x=5)
        l = dnf.util.MultiCallList([o1, o2])
        l.x = 5
        self.assertEqual([5, 5], list(map(operator.attrgetter('x'), [o1, o2])))
