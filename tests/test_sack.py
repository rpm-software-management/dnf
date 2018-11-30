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

import dnf.exceptions
import dnf.repo
import dnf.sack

import tests.support
from tests.support import mock


class SackTest(tests.support.DnfBaseTestCase):

    REPOS = []

    def test_rpmdb_version(self):
        version = self.sack._rpmdb_version()
        self.assertIsNotNone(version)
        expected = "%s:%s" % (tests.support.TOTAL_RPMDB_COUNT, tests.support.RPMDB_CHECKSUM)
        self.assertEqual(version, expected)

    def test_excludepkgs(self):
        self.base.conf.excludepkgs = ['pepper']
        self.base._setup_excludes_includes()
        peppers = self.base.sack.query().filter(name='pepper').run()
        self.assertLength(peppers, 0)

    def test_exclude(self):
        self.base.conf.exclude = ['pepper']
        self.base._setup_excludes_includes()
        peppers = self.base.sack.query().filter(name='pepper').run()
        self.assertLength(peppers, 0)

    def test_disable_excludes(self):
        self.base.conf.disable_excludes = ['all']
        self.base.conf.excludepkgs = ['pepper']
        self.base._setup_excludes_includes()
        peppers = self.base.sack.query().filter(name='pepper').run()
        self.assertLength(peppers, 1)

    def test_excludepkgs_glob(self):
        # override base with custom repos
        self.base = tests.support.MockBase('main')
        self.base.repos['main'].excludepkgs = ['pepp*']
        self.base._setup_excludes_includes()
        peppers = self.base.sack.query().filter(name='pepper', reponame='main')
        self.assertLength(peppers, 0)

    def test_excludepkgs_includepkgs(self):
        self.base.conf.excludepkgs = ['*.i?86']
        self.base.conf.includepkgs = ['lib*']
        self.base._setup_excludes_includes()
        peppers = self.base.sack.query().filter().run()
        self.assertLength(peppers, 1)
        self.assertEqual(str(peppers[0]), "librita-1-1.x86_64")

    @mock.patch('dnf.sack._build_sack', lambda x: mock.Mock())
    @mock.patch('dnf.goal.Goal', lambda x: mock.Mock())
    def test_fill_sack(self):
        def raiser():
            raise dnf.exceptions.RepoError()

        r = tests.support.MockRepo('bag', self.base.conf)
        r.enable()
        self.base._repos.add(r)
        r.load = mock.Mock(side_effect=raiser)
        r.skip_if_unavailable = False
        self.assertRaises(dnf.exceptions.RepoError,
                          self.base.fill_sack, load_system_repo=False)
        self.assertTrue(r.enabled)
        self.assertTrue(r._check_config_file_age)
