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

import rpm

import dnf.goal

import tests.support


class DistroSyncAll(tests.support.ResultTestCase):
    def setUp(self):
        self.base = tests.support.MockBase("distro")
        self.sack = self.base.sack

    def test_distro_sync_all(self):
        self.base.distro_sync()
        self.assertIn(rpm.RPMPROB_FILTER_OLDPACKAGE, self.base._rpm_probfilter)
        packages = tests.support.installed_but(self.sack, "pepper", "librita").run()
        q = self.sack.query().available().filter(name=["pepper", "librita"])
        packages.extend(q)
        self.assertResult(self.base, packages)


class DistroSync(tests.support.ResultTestCase):
    def setUp(self):
        self._base = tests.support.BaseCliStub()
        self._base._sack = tests.support.mock_sack('main', 'updates')
        self._base._goal = dnf.goal.Goal(self._base.sack)

    def test_distro_sync(self):
        installed = self._get_installed(self._base)
        original_pkg = list(filter(lambda p: p.name == "hole", installed))
        self._base.distro_sync_userlist(('bla', 'hole'))
        obsolete_pkg = list(filter(lambda p: p.name == "tour", installed))

        installed2 = self._get_installed(self._base)
        updated_pkg = list(filter(lambda p: p.name == "hole", installed2))
        self.assertLength(updated_pkg, 1)
        self.assertLength(original_pkg, 1)
        self.assertLength(updated_pkg, 1)

        # holy pkg upgraded from version 1 to 2 and obsoletes tour
        self.assertEqual(original_pkg[0].version, "1")
        self.assertEqual(updated_pkg[0].version, "2")
        installed.remove(original_pkg[0])
        installed.remove(obsolete_pkg[0])
        installed2.remove(updated_pkg[0])
        self.assertEqual(installed, installed2)
