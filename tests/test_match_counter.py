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
import dnf.match_counter
import unittest

class TestCounter(unittest.TestCase):
    def test_canonize_string_set(self):
        a = ['f', 'p']
        b = ['p']
        self.assertLess(dnf.match_counter._canonize_string_set(b, 2),
                        dnf.match_counter._canonize_string_set(a, 2))

    def test_matched(self):
        pkg = base.create_mock_package("humbert", 1)
        pkg.url = url = "http://humbert.com"
        pkg.summary = summary = "Glimpses of an incomparably more poignant bliss."
        counter = dnf.match_counter.MatchCounter()
        counter.add(pkg, 'summary', 'poignant')
        counter.add(pkg, 'url', 'humbert')
        counter.add(pkg, 'summary', 'humbert')
        self.assertItemsEqual(counter.matched_needles(pkg),
                              ['humbert', 'poignant'])
        self.assertItemsEqual(counter.matched_keys(pkg), ['url', 'summary'])
        self.assertItemsEqual(counter.matched_haystacks(pkg), [url, summary])

    def test_sorted(self):
        counter = dnf.match_counter.MatchCounter()
        counter.add(1, 'name', '')
        counter.add(2, 'description', '')
        self.assertEqual(counter.sorted(), [2, 1])

        counter.add(3, 'url', '')
        self.assertEqual(counter.sorted(), [3, 2, 1])

        counter.add(3, 'description', '')
        self.assertEqual(counter.sorted(), [2, 3, 1])
        self.assertEqual(counter.sorted(reverse=True), [1, 3,2])

    def test_sorted_with_needles(self):
        # the same needles should be listed together:
        counter = dnf.match_counter.MatchCounter()
        counter.add(1, 'summary', 'grin')
        counter.add(2, 'summary', 'foolish')
        counter.add(3, 'summary', 'grin')
        counter.add(4, 'summary', 'grin')

        srt = counter.sorted()
        self.assertIn(srt.index(2), [0, 3])

        # more unique needles is more than less unique needles:
        counter = dnf.match_counter.MatchCounter()
        counter.add(1, 'summary', 'a')
        counter.add(1, 'summary', 'b')
        counter.add(2, 'summary', 'b')
        counter.add(2, 'summary', 'b')

        self.assertEqual(counter.sorted(), [2, 1])

    def test_sorted_limit(self):
        counter = dnf.match_counter.MatchCounter()
        counter.add(1, 'name', '')
        counter.add(2, 'url', '')
        counter.add(3, 'description', '')
        self.assertSequenceEqual(counter.sorted(limit_to=[1,2]), [2,1])

    def test_total(self):
        counter = dnf.match_counter.MatchCounter()
        counter.add(3, 'summary', 'humbert')
        counter.add(3, 'url', 'humbert')
        counter.add(20, 'summary', 'humbert')
        self.assertEqual(len(counter), 2)
        self.assertEqual(counter.total(), 3)
