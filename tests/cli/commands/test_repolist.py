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
# GNU General Public License along with this program; if not, see
# <https://www.gnu.org/licenses/>.  Any Red Hat trademarks that are
# incorporated in the source code or documentation are not subject to the GNU
# General Public License and may only be used or replicated with the express
# permission of Red Hat, Inc.
#

from __future__ import absolute_import

import dnf.cli.commands.repolist as repolist
import dnf.repo

import tests.support


class TestRepolist(tests.support.TestCase):

    @tests.support.mock.patch('dnf.cli.commands.repolist._',
                              dnf.pycomp.NullTranslations().ugettext)
    def test_expire_str(self):
        repo = dnf.repo.Repo('rollup', tests.support.FakeConf())
        expire = repolist._expire_str(repo, None)
        self.assertEqual(expire, '172800 second(s) (last: unknown)')
