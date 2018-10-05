# Copyright (C) 2018 Red Hat, Inc.
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

import unittest

import dnf


class AppendListOptionTest(unittest.TestCase):

    def setUp(self):
        self.conf = dnf.conf.MainConf()

    def test_delitem(self):
        self.conf.tsflags = ["a", "b", "c"]
        self.assertEqual(list(self.conf.tsflags), ["a", "b", "c"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a", "b", "c"])

        del var[0]
        self.assertEqual(list(self.conf.tsflags), ["b", "c"])
        self.assertEqual(var, ["b", "c"])

    def test_iadd(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a"])

        var += ["b", "c"]
        self.assertEqual(list(self.conf.tsflags), ["a", "b", "c"])
        self.assertEqual(var, ["a", "b", "c"])

    def test_iadd_tuple(self):
        self.conf.tsflags = ("a", )
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a"])

        var += ("b", "c")
        self.assertEqual(list(self.conf.tsflags), ["a", "b", "c"])
        self.assertEqual(var, ["a", "b", "c"])

    def test_imul(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a"])

        var *= 3
        self.assertEqual(list(self.conf.tsflags), ["a", "a", "a"])
        self.assertEqual(var, ["a", "a", "a"])

    def test_setitem(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a"])

        var[0] = "b"
        self.assertEqual(list(self.conf.tsflags), ["b"])
        self.assertEqual(var, ["b"])

    def test_append(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a"])

        var.append("b")
        self.assertEqual(list(self.conf.tsflags), ["a", "b"])
        self.assertEqual(var, ["a", "b"])

    def test_clear(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a"])

        var.clear()
        self.assertEqual(list(self.conf.tsflags), [])
        self.assertEqual(var, [])

    def test_extend(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a"])

        var.extend(["b", "c"])
        self.assertEqual(list(self.conf.tsflags), ["a", "b", "c"])
        self.assertEqual(var, ["a", "b", "c"])

    def test_insert(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a"])

        var.insert(0, "b")
        self.assertEqual(list(self.conf.tsflags), ["b", "a"])
        self.assertEqual(var, ["b", "a"])

    def test_pop(self):
        self.conf.tsflags = ["a", "b", "c"]
        self.assertEqual(list(self.conf.tsflags), ["a", "b", "c"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a", "b", "c"])

        var.pop()
        self.assertEqual(list(self.conf.tsflags), ["a", "b"])
        self.assertEqual(var, ["a", "b"])

    def test_remove(self):
        self.conf.tsflags = ["a", "b", "c"]
        self.assertEqual(list(self.conf.tsflags), ["a", "b", "c"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a", "b", "c"])

        var.remove("b")
        self.assertEqual(list(self.conf.tsflags), ["a", "c"])
        self.assertEqual(var, ["a", "c"])

    def test_reverse(self):
        self.conf.tsflags = ["a", "b", "c"]
        self.assertEqual(list(self.conf.tsflags), ["a", "b", "c"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a", "b", "c"])

        var.reverse()
        self.assertEqual(list(self.conf.tsflags), ["c", "b", "a"])
        self.assertEqual(var, ["c", "b", "a"])

    def test_reversed(self):
        self.conf.tsflags = ["a", "b", "c"]
        self.assertEqual(list(self.conf.tsflags), ["a", "b", "c"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a", "b", "c"])

        var = list(reversed(var))
        self.assertEqual(list(self.conf.tsflags), ["a", "b", "c"])
        self.assertEqual(var, ["c", "b", "a"])

    def test_sort(self):
        self.conf.tsflags = ["a", "c", "b"]
        self.assertEqual(list(self.conf.tsflags), ["a", "c", "b"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a", "c", "b"])

        var.sort()
        self.assertEqual(list(self.conf.tsflags), ["a", "b", "c"])
        self.assertEqual(var, ["a", "b", "c"])

    def test_priority(self):
        self.conf._set_value("tsflags", ["a"], dnf.conf.config.PRIO_PLUGINDEFAULT)
        self.assertEqual(list(self.conf.tsflags), ["a"])

        self.conf._set_value("tsflags", ["b"], dnf.conf.config.PRIO_PLUGINDEFAULT)
        self.assertEqual(list(self.conf.tsflags), ["a", "b"])

        # appending with lower priority is allowed
        self.conf._set_value("tsflags", ["c"], dnf.conf.config.PRIO_DEFAULT)
        self.assertEqual(list(self.conf.tsflags), ["a", "b", "c"])

        # resetting with lower priority is NOT allowed
        self.conf._set_value("tsflags", [], dnf.conf.config.PRIO_DEFAULT)
        self.assertEqual(list(self.conf.tsflags), ["a", "b", "c"])

        self.conf.tsflags = ["d"]
        self.assertEqual(list(self.conf.tsflags), ["a", "b", "c", "d"])

        self.conf.tsflags.append("e")
        self.assertEqual(list(self.conf.tsflags), ["a", "b", "c", "d", "e"])

        self.conf.tsflags = []
        self.assertEqual(list(self.conf.tsflags), [])

    def test_references(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var1 = self.conf.tsflags
        var2 = self.conf.tsflags
        self.assertEqual(var1, ["a"])
        self.assertEqual(var2, ["a"])

        var1 += ["b", "c"]
        self.assertEqual(list(self.conf.tsflags), ["a", "b", "c"])
        self.assertEqual(var1, ["a", "b", "c"])
        self.assertEqual(var2, ["a", "b", "c"])

    def test_add(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.conf._set_value("tsflags", ["b"])
        var = var + ["c"]
        self.assertEqual(list(self.conf.tsflags), ["a", "b"])
        self.assertEqual(var, ["a", "b", "c"])

    def test_contains(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.conf._set_value("tsflags", ["b"])
        self.assertIn("b", var)

    def test_eq(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.conf._set_value("tsflags", ["b"])
        self.assertEqual(var, ["a", "b"])

    def test_ge(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.conf._set_value("tsflags", ["b"])
        self.assertTrue(var >= ["a", "b"])

    def test_gt(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.conf._set_value("tsflags", ["b"])
        self.assertTrue(var > ["a", "a"])

    def test_le(self):
        self.conf.tsflags = ["a", "b"]
        self.assertEqual(list(self.conf.tsflags), ["a", "b"])

        var = self.conf.tsflags
        self.conf._set_value("tsflags", [])
        self.conf._set_value("tsflags", ["a"])
        self.assertTrue(var <= ["a"])

    def test_lt(self):
        self.conf.tsflags = ["a", "b"]
        self.assertEqual(list(self.conf.tsflags), ["a", "b"])

        var = self.conf.tsflags
        self.conf._set_value("tsflags", [])
        self.conf._set_value("tsflags", ["a"])
        self.assertTrue(var < ["b"])

    def test_ne(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.conf._set_value("tsflags", ["b"])
        self.assertNotEqual(var, ["a"])

    def test_mul(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a"])

        var = var * 3
        self.assertEqual(list(self.conf.tsflags), ["a"])
        self.assertEqual(var, ["a", "a", "a"])

    def test_rmul(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.assertEqual(var, ["a"])

        var = 3 * var
        self.assertEqual(list(self.conf.tsflags), ["a"])
        self.assertEqual(var, ["a", "a", "a"])

    def test_getitem(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.conf._set_value("tsflags", ["b"])
        self.assertEqual(var[1], "b")

    def test_iter(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.conf._set_value("tsflags", ["b"])

        length = 0
        for i in iter(var):
            length += 1
            if length == 1:
                self.assertEqual(i, "a")
            elif length == 2:
                self.assertEqual(i, "b")
        self.assertEqual(length, 2)

    def test_len(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.conf._set_value("tsflags", ["b"])
        self.assertEqual(len(var), 2)

    def test_copy(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.conf._set_value("tsflags", ["b"])
        var2 = var.copy()
        self.assertEqual(var2, ["a", "b"])

    def test_count(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.conf._set_value("tsflags", ["a"])
        self.assertEqual(var.count("a"), 2)

    def test_index(self):
        self.conf.tsflags = ["a"]
        self.assertEqual(list(self.conf.tsflags), ["a"])

        var = self.conf.tsflags
        self.conf._set_value("tsflags", ["b"])
        self.assertEqual(var.index("b"), 1)
