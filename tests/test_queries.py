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
# GNU General Public License along with this program; if not, see
# <https://www.gnu.org/licenses/>.  Any Red Hat trademarks that are
# incorporated in the source code or documentation are not subject to the GNU
# General Public License and may only be used or replicated with the express
# permission of Red Hat, Inc.
#

from __future__ import absolute_import
from __future__ import unicode_literals

import dnf.query
import dnf.subject

import tests.support


class QueriesTest(tests.support.TestCase):

    def setUp(self):
        self.sack = tests.support.mock_sack('main', 'updates')

    def test_duplicities(self):
        pepper = self.sack.query().installed().filter(name="pepper")
        # make sure 'pepper' package exists:
        self.assertEqual(len(pepper), 1)
        # we shouldn't see it more than once with a tricky query below:
        res = self.sack.query().installed().filter(name=["pep*", "*per"])
        res_set = set(res)
        self.assertEqual(len(res), len(res_set))

    def test_by_file(self):
        # check sanity first:
        q = self.sack.query().filter(file__eq="/raised/smile")
        self.assertEqual(len(q.run()), 1)
        q[0]

    def test_by_repo(self):
        pkgs = self.sack.query().filter(reponame__eq="updates")
        self.assertEqual(len(pkgs), tests.support.UPDATES_NSOLVABLES)
        pkgs = self.sack.query().filter(reponame__eq="main")
        self.assertEqual(len(pkgs), tests.support.MAIN_NSOLVABLES)

    def test_duplicated(self):
        pkgs = self.sack.query().duplicated()
        self.assertEqual(len(pkgs), 3)

    def test_extras(self):
        pkgs = self.sack.query().extras()
        self.assertEqual(len(pkgs), tests.support.TOTAL_RPMDB_COUNT - 4)

    def test_installed_exact(self):
        pkgs = self.sack.query().installed()._nevra("tour-4.9-0.noarch")
        self.assertEqual(len(pkgs), 0)
        pkgs = self.sack.query().installed()._nevra("tour-5-0.x86_64")
        self.assertEqual(len(pkgs), 0)
        pkgs = self.sack.query().installed()._nevra("tour-5-0.noarch")
        self.assertEqual(len(pkgs), 1)

    def test_latest(self):
        tours = self.sack.query().filter(name="tour")
        all_tours = sorted(tours.run(), reverse=True)
        head2 = all_tours[0:2]
        tail2 = all_tours[2:]
        pkgs = tours.latest(2).run()
        self.assertEqual(pkgs, head2)
        pkgs = tours.latest(-2).run()
        self.assertEqual(pkgs, tail2)


class SubjectTest(tests.support.TestCase):

    def setUp(self):
        self.sack = tests.support.mock_sack('main', 'updates')

    def test_wrong_name(self):
        subj = dnf.subject.Subject("call-his-wife-in")
        self.assertLength(subj.get_best_query(self.sack), 0)

    def test_query_composing(self):
        q = dnf.subject.Subject("librita").get_best_query(self.sack)
        q = q.filter(arch="i686")
        self.assertEqual(str(q[0]), "librita-1-1.i686")

    def test_icase_name(self):
        subj = dnf.subject.Subject("PEpper", ignore_case=True)
        q = subj.get_best_query(self.sack)
        self.assertLength(q, 4)

    def test_get_best_selector(self):
        s = dnf.subject.Subject("pepper-20-0.x86_64").get_best_selector(self.sack)
        self.assertIsNotNone(s)

    def test_get_best_selector_for_provides_glob(self):
        s = dnf.subject.Subject("*otus.so*").get_best_selector(self.sack)
        self.assertIsNotNone(s)

    def test_best_selector_for_version(self):
        sltr = dnf.subject.Subject("hole-2").get_best_selector(self.sack)
        self.assertCountEqual(map(str, sltr.matches()),
                              ['hole-2-1.x86_64', 'hole-2-1.i686'])

    def test_with_confusing_dashes(self):
        sltr = dnf.subject.Subject("mrkite-k-h").get_best_selector(self.sack)
        self.assertLength(sltr.matches(), 1)
        sltr = dnf.subject.Subject("mrkite-k-h.x86_64").get_best_selector(self.sack)
        self.assertLength(sltr.matches(), 1)


class DictsTest(tests.support.TestCase):

    def setUp(self):
        self.sack = tests.support.mock_sack('main', 'updates')

    def test_per_nevra_dict(self):
        pkgs = self.sack.query().filter(name="lotus")
        dct = dnf.query._per_nevra_dict(pkgs)
        self.assertCountEqual(dct.keys(),
                              ["lotus-3-16.x86_64", "lotus-3-16.i686"])
        test_list = []
        for list_items in dct.values():
            for item in list_items:
                test_list.append(item)

        self.assertCountEqual(test_list, pkgs)
