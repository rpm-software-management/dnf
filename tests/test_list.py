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

import itertools

import libdnf.swdb

import dnf.transaction

import tests.support


class List(tests.support.DnfBaseTestCase):

    REPOS = ["main", "updates"]

    def test_doPackageLists_reponame(self):
        """Test whether packages are filtered by the reponame."""
        reponame = 'main'
        lists = self.base._do_package_lists(reponame=reponame)

        pkgs = itertools.chain.from_iterable(lists.all_lists().values())
        self.assertCountEqual({pkg.reponame for pkg in pkgs}, {reponame})

        assert len(set(pkg.reponame for pkg in self.base.sack.query())) > 1, \
            ('the base must contain packages from multiple repos, '
             'otherwise the test makes no sense')

    def test_list_installed(self):
        ypl = self.base._do_package_lists('installed')
        self.assertEqual(len(ypl.installed), tests.support.TOTAL_RPMDB_COUNT)

    def test_list_installed_reponame(self):
        """Test whether only packages installed from the repository are listed."""
        expected = self.base.sack.query().installed().filter(name={'pepper', 'librita'})
        tsis = []
        for pkg in expected:
            pkg._force_swdb_repoid = "main"
            tsi = dnf.transaction.TransactionItem(
                dnf.transaction.INSTALL,
                installed=pkg,
                reason=libdnf.swdb.TransactionItemReason_USER
            )
            tsis.append(tsi)
        self._swdb_commit(tsis)

        lists = self.base._do_package_lists('installed', reponame='main')

        self.assertCountEqual(lists.installed, expected)

    def test_list_updates(self):
        ypl = self.base._do_package_lists('upgrades')
        self.assertEqual(len(ypl.updates), tests.support.UPDATES_NSOLVABLES - 2)
        pkg = ypl.updates[0]
        self.assertEqual(pkg.name, "hole")
        ypl = self.base._do_package_lists('upgrades', ["pepper"])
        self.assertEqual(len(ypl.updates), 1)
        ypl = self.base._do_package_lists('upgrades', ["mrkite"])
        self.assertEqual(len(ypl.updates), 0)

        ypl = self.base._do_package_lists('upgrades', ["hole"])
        self.assertEqual(len(ypl.updates), 1)

    def test_lists_multiple(self):
        ypl = self.base._do_package_lists('upgrades', ['pepper', 'hole'])
        self.assertLength(ypl.updates, 2)


class TestListAllRepos(tests.support.DnfBaseTestCase):

    REPOS = ["main", "updates"]

    def setUp(self):
        super(TestListAllRepos, self).setUp()
        self.base.conf.multilib_policy = "all"

    def test_list_pattern(self):
        ypl = self.base._do_package_lists('all', ['hole'])
        self.assertLength(ypl.installed, 1)
        self.assertLength(ypl.available, 2)

    def test_list_pattern_arch(self):
        ypl = self.base._do_package_lists('all', ['hole.x86_64'])
        self.assertLength(ypl.installed, 1)
        self.assertLength(ypl.available, 1)

    def test_list_available(self):
        ypl = self.base._do_package_lists('available', ['hole'], showdups=False)
        self.assertCountEqual(map(str, ypl.available), ('hole-2-1.i686',
                                                        'hole-2-1.x86_64'))

        ypl = self.base._do_package_lists('available', ['hole'], showdups=True)
        self.assertCountEqual(map(str, ypl.available), ('hole-2-1.i686',
                                                        'hole-2-1.x86_64',
                                                        'hole-1-2.x86_64'))
