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
import dnf.queries
import dnf.yum.Errors
import hawkey
import unittest

class Queries(base.TestCase):
    def test_is_glob_pattern(self):
        assert(dnf.queries.is_glob_pattern("all*.ext"))
        assert(dnf.queries.is_glob_pattern("all?.ext"))
        assert(not dnf.queries.is_glob_pattern("not.ext"))

    def test_pattern(self):
        sack = base.MockYumBase().sack
        split = dnf.queries.Pattern(sack, "all-2.0-1.fc6.x86_64")
        self.assertTrue(split.valid)
        self.assertEqual(split.name, "all")
        self.assertEqual(split.epoch, 0)
        self.assertEqual(split.version, "2.0")
        self.assertEqual(split.release, "1.fc6")
        self.assertEqual(split.arch, "x86_64")

        split = dnf.queries.Pattern(sack, "all-2.0-1.fc6")
        self.assertEqual(split.release, "1.fc6")
        self.assertIsNone(split.arch)
        self.assertEqual(split.version, "2.0")
        self.assertEqual(split.evr, "2.0-1.fc6")

        split = dnf.queries.Pattern(sack, "pepper-20-0.x86_64")
        self.assertLength(split.to_query(), 1)
        split = dnf.queries.Pattern(sack, "pepper-20-0")
        self.assertLength(split.to_query(), 1)

    def test_pattern_fail(self):
        sack = base.MockYumBase().sack
        split = dnf.queries.Pattern(sack, "pepper-2")
        self.assertFalse(split.valid)
        try:
            split.name
        except dnf.yum.Errors.DNFValueError as e:
            pass
        else:
            self.fail("Should throw an erorr.")

    def test_duplicities(self):
        yumbase = base.MockYumBase()
        pepper = dnf.queries.installed_by_name(yumbase.sack, "pepper")
        # make sure 'pepper' package exists:
        self.assertEqual(len(pepper), 1)
        # we shouldn't see it more than once with a tricky query below:
        res = dnf.queries.installed_by_name(yumbase.sack, ["pep*", "*per"])
        res_set = set(res)
        self.assertEqual(len(res), len(res_set))

    def test_by_file(self):
        # check sanity first:
        yumbase = base.MockYumBase()
        q = hawkey.Query(yumbase.sack).filter(file__eq="/raised/smile")
        self.assertEqual(len(q.run()), 1)
        pkg = q.result[0]

        # now the query:
        yumbase = base.MockYumBase()
        res = dnf.queries.by_file(yumbase.sack, "/raised/smile")
        self.assertEqual(len(res), 1)
        self.assertEqual(pkg, res[0])

    def test_by_repo(self):
        yumbase = base.MockYumBase("updates", "main")
        pkgs = dnf.queries.by_repo(yumbase.sack, "updates")
        self.assertEqual(len(pkgs), base.UPDATES_NSOLVABLES)
        pkgs = dnf.queries.by_repo(yumbase.sack, "main")
        self.assertEqual(len(pkgs), base.MAIN_NSOLVABLES)

    def test_installed_exact(self):
        sack = base.MockYumBase().sack
        pkgs = dnf.queries.installed_exact(sack, "tour", "4.9-0", "noarch")
        self.assertEqual(len(pkgs), 0)
        pkgs = dnf.queries.installed_exact(sack, "tour", "5-0", "x86_64")
        self.assertEqual(len(pkgs), 0)
        pkgs = dnf.queries.installed_exact(sack, "tour", "5-0", "noarch")
        self.assertEqual(len(pkgs), 1)

class Dicts(unittest.TestCase):
    def test_per_nevra_dict(self):
        sack = base.MockYumBase("main").sack
        pkgs = dnf.queries.by_name(sack, "lotus")
        dct = dnf.queries.per_nevra_dict(pkgs)
        self.assertItemsEqual(dct.iterkeys(),
                              ["lotus-3-16.x86_64", "lotus-3-16.i686"])
        self.assertItemsEqual(dct.itervalues(), pkgs)
