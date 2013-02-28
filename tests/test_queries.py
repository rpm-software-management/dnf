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

import base
import dnf.queries
import dnf.yum.Errors
import hawkey
import unittest

class QueriesTest(base.TestCase):
    def test_duplicities(self):
        sack = base.mock_sack()
        pepper = dnf.queries.installed_by_name(sack, "pepper")
        # make sure 'pepper' package exists:
        self.assertEqual(len(pepper), 1)
        # we shouldn't see it more than once with a tricky query below:
        res = dnf.queries.installed_by_name(sack, ["pep*", "*per"])
        res_set = set(res)
        self.assertEqual(len(res), len(res_set))

    def test_by_file(self):
        # check sanity first:
        sack = base.mock_sack()
        q = sack.query().filter(file__eq="/raised/smile")
        self.assertEqual(len(q.run()), 1)
        pkg = q.result[0]

        # now the query:
        res = dnf.queries.by_file(sack, "/raised/smile")
        self.assertEqual(len(res), 1)
        self.assertEqual(pkg, res[0])

    def test_by_repo(self):
        sack = base.mock_sack("updates", "main")
        pkgs = dnf.queries.by_repo(sack, "updates")
        self.assertEqual(len(pkgs), base.UPDATES_NSOLVABLES)
        pkgs = dnf.queries.by_repo(sack, "main")
        self.assertEqual(len(pkgs), base.MAIN_NSOLVABLES)

    def test_installed_exact(self):
        sack = base.mock_sack()
        pkgs = dnf.queries.installed_exact(sack, "tour", "4.9-0", "noarch")
        self.assertEqual(len(pkgs), 0)
        pkgs = dnf.queries.installed_exact(sack, "tour", "5-0", "x86_64")
        self.assertEqual(len(pkgs), 0)
        pkgs = dnf.queries.installed_exact(sack, "tour", "5-0", "noarch")
        self.assertEqual(len(pkgs), 1)

class SubjectTest(base.TestCase):
    def setUp(self):
        self.sack = base.mock_sack("main", "updates")

    def test_wrong_name(self):
        subj = dnf.queries.Subject("call-his-wife-in")
        self.assertLength(subj.get_best_query(self.sack), 0)

    def test_query_composing(self):
        q = dnf.queries.Subject("librita").get_best_query(self.sack)
        q = q.filter(arch="i686")
        self.assertEqual(str(q[0]), "librita-1-1.i686")

    def test_icase_name(self):
        subj = dnf.queries.Subject("PEpper", ignore_case=True)
        q = subj.get_best_query(self.sack)
        self.assertLength(q, 4)

    def test_get_best_selector(self):
        s = dnf.queries.Subject("pepper-20-0.x86_64").get_best_selector(self.sack)
        self.assertIsNotNone(s)

    def test_best_selector_for_version(self):
        sltr = dnf.queries.Subject("hole-2").get_best_selector(self.sack)
        self.assertItemsEqual(map(str, sltr.matches()),
                              ['hole-2-1.x86_64', 'hole-2-1.i686'])

    def test_with_confusing_dashes(self):
        sltr = dnf.queries.Subject("mrkite-k-h").get_best_selector(self.sack)
        self.assertLength(sltr.matches(), 1)
        sltr = dnf.queries.Subject("mrkite-k-h.x86_64").\
            get_best_selector(self.sack)
        self.assertLength(sltr.matches(), 1)

class DictsTest(unittest.TestCase):
    def test_per_nevra_dict(self):
        sack = base.mock_sack("main")
        pkgs = dnf.queries.by_name(sack, "lotus")
        dct = dnf.queries.per_nevra_dict(pkgs)
        self.assertItemsEqual(dct.iterkeys(),
                              ["lotus-3-16.x86_64", "lotus-3-16.i686"])
        self.assertItemsEqual(dct.itervalues(), pkgs)
