# -*- coding: utf-8 -*-

# Copyright (C) 2014-2018 Red Hat, Inc.
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

import dnf.cli.commands.search as search
import dnf.match_counter
import dnf.pycomp

import tests.support
from tests import mock


class SearchCountedTest(tests.support.DnfBaseTestCase):

    REPOS = ["main"]
    CLI = "mock"

    def setUp(self):
        super(SearchCountedTest, self).setUp()
        self.cmd = search.SearchCommand(self.cli)

    def test_search_counted(self):
        counter = dnf.match_counter.MatchCounter()
        self.cmd._search_counted(counter, 'summary', 'ation')
        self.assertEqual(len(counter), 2)
        haystacks = set()
        for pkg in counter:
            haystacks.update(counter.matched_haystacks(pkg))
        self.assertCountEqual(haystacks, ["It's an invitation.",
                                          "Make a reservation."])

    def test_search_counted_glob(self):
        counter = dnf.match_counter.MatchCounter()
        self.cmd._search_counted(counter, 'summary', '*invit*')
        self.assertEqual(len(counter), 1)


class SearchTest(tests.support.DnfBaseTestCase):

    REPOS = ["search"]
    CLI = "mock"

    def setUp(self):
        super(SearchTest, self).setUp()
        self.base.output = mock.MagicMock()
        self.base.output.fmtSection = lambda str: str
        self.cmd = search.SearchCommand(self.cli)

    def patched_search(self, *args):
        with tests.support.patch_std_streams() as (stdout, _):
            tests.support.command_run(self.cmd, *args)
            call_args = self.base.output.matchcallback.call_args_list
            pkgs = [c[0][0] for c in call_args]
            return (stdout.getvalue(), pkgs)

    def test_search(self):
        (_, pkgs) = self.patched_search(['lotus'])
        pkg_names = list(map(str, pkgs))
        self.assertIn('lotus-3-16.i686', pkg_names)
        self.assertIn('lotus-3-16.x86_64', pkg_names)

    @mock.patch('dnf.cli.commands.search._',
                dnf.pycomp.NullTranslations().ugettext)
    def test_search_caseness(self):
        (stdout, pkgs) = self.patched_search(['LOTUS'])
        self.assertEqual(stdout, 'Name Matched: LOTUS\n')
        pkg_names = map(str, pkgs)
        self.assertIn('lotus-3-16.i686', pkg_names)
        self.assertIn('lotus-3-16.x86_64', pkg_names)
