# Copyright (C) 2012-2014  Red Hat, Inc.
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
from tests import support
import itertools
import unittest

class List(support.TestCase):
    def test_doPackageLists_reponame(self):
        """Test whether packages are filtered by the reponame."""
        reponame = 'main'
        base = support.MockBase(reponame)
        lists = base.doPackageLists(reponame=reponame)

        pkgs = itertools.chain.from_iterable(lists.all_lists().values())
        self.assertItemsEqual({pkg.reponame for pkg in pkgs}, {reponame})

        assert len(set(pkg.reponame for pkg in base.sack.query())) > 1, \
               ('the base must contain packages from multiple repos, '
                'otherwise the test makes no sense')

    def test_list_installed(self):
        base = support.MockBase()
        ypl = base.doPackageLists('installed')
        self.assertEqual(len(ypl.installed), support.TOTAL_RPMDB_COUNT)

    def test_list_installed_reponame(self):
        """Test whether only packages installed from the repository are listed."""
        base = support.MockBase()
        expected = base.sack.query().installed().filter(name={'pepper',
                                                              'librita'})
        for pkg in expected:
            base.yumdb.db[str(pkg)] = {'from_repo': 'main'}

        lists = base.doPackageLists('installed', reponame='main')

        self.assertItemsEqual(lists.installed, expected)

    def test_list_updates(self):
        base = support.MockBase("updates", "main")
        ypl = base.doPackageLists('upgrades')
        self.assertEqual(len(ypl.updates), support.UPDATES_NSOLVABLES - 1)
        pkg = ypl.updates[0]
        self.assertEqual(pkg.name, "hole")
        ypl = base.doPackageLists('upgrades', ["pepper"])
        self.assertEqual(len(ypl.updates), 1)
        ypl = base.doPackageLists('upgrades', ["mrkite"])
        self.assertEqual(len(ypl.updates), 0)

        ypl = base.doPackageLists('upgrades', ["hole"])
        self.assertEqual(len(ypl.updates), 2)

    def test_lists_multiple(self):
        base = support.MockBase('updates', "main")
        ypl = base.doPackageLists('upgrades', ['pepper', 'hole'])
        self.assertLength(ypl.updates, 3)

class TestListAllRepos(support.TestCase):
    def setUp(self):
        self.base = support.MockBase("main", "updates")
        self.base.conf.multilib_policy = "all"

    def test_list_pattern(self):
        ypl = self.base.doPackageLists('all', ['hole'])
        self.assertLength(ypl.installed, 1)
        self.assertLength(ypl.available, 2)

    def test_list_pattern_arch(self):
        ypl = self.base.doPackageLists('all', ['hole.x86_64'])
        self.assertLength(ypl.installed, 1)
        self.assertLength(ypl.available, 1)

    def test_list_available(self):
        ypl = self.base.doPackageLists('available', ['hole'], showdups=False)
        self.assertItemsEqual(map(str, ypl.available), ('hole-2-1.i686',
                                                        'hole-2-1.x86_64'))

        ypl = self.base.doPackageLists('available', ['hole'], showdups=True)
        self.assertItemsEqual(map(str, ypl.available), ('hole-2-1.i686',
                                                        'hole-2-1.x86_64',
                                                        'hole-1-2.x86_64'))
