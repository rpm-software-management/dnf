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

from __future__ import absolute_import
try:
    from unittest import mock
except ImportError:
    from tests import mock
from tests import support
import dnf
import hawkey
import unittest
from tests.support import PycompTestCase

class Reinstall(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockBase("main")
        self.yumbase.conf.multilib_policy = "all"
        self.sack = self.yumbase.sack

    def test_reinstall(self):
        cnt = self.yumbase.reinstall("pepper")
        self.assertEqual(cnt, 1)
        new_set = support.installed_but(self.sack, "pepper")
        available_query = self.sack.query().available()
        new_set += list(available_query.nevra("pepper-20-0.x86_64"))
        self.assertResult(self.yumbase, new_set)

    def test_reinstall_local(self):
        cnt = self.yumbase.reinstall_local(support.TOUR_50_PKG_PATH)
        self.assertEqual(cnt, 1)

class ReinstallTest(PycompTestCase):
    def setUp(self):
        self._base = dnf.Base()
        self._base._sack = support.mock_sack('main')
        self._base._goal = self._goal = mock.create_autospec(hawkey.Goal)

    def test_reinstall_pkgnevra(self):
        pkg = support.ObjectMatcher(
            dnf.package.Package,
            {'name': 'pepper', 'evr': '20-0', 'arch': 'x86_64'})

        reinstalled_count = self._base.reinstall('pepper-0:20-0.x86_64')

        self.assertEqual(reinstalled_count, 1)
        self.assertEqual(self._goal.mock_calls, [mock.call.install(pkg)])

    def test_reinstall_notfound(self):
        with self.assertRaises(dnf.exceptions.PackagesNotInstalledError) as context:
            self._base.reinstall('non-existent')

        self.assertEqual(context.exception.pkg_spec, 'non-existent')
        self.assertEqual(self._goal.mock_calls, [])

    def test_reinstall_notinstalled(self):
        with self.assertRaises(dnf.exceptions.PackagesNotInstalledError) as context:
            self._base.reinstall('lotus')

        self.assertEqual(context.exception.pkg_spec, 'lotus')
        self.assertEqual(self._goal.mock_calls, [])

    def test_reinstall_notavailable(self):
        pkgs = [support.ObjectMatcher(dnf.package.Package, {'name': 'hole'})]

        with self.assertRaises(dnf.exceptions.PackagesNotAvailableError) as context:
            self._base.reinstall('hole')

        self.assertEqual(context.exception.pkg_spec, 'hole')
        self.assertEqual(context.exception.packages, pkgs)
        self.assertEqual(self._goal.mock_calls, [])

    def test_reinstall_notavailable_available(self):
        pkg = support.ObjectMatcher(dnf.package.Package, {'name': 'librita'})

        reinstalled_count = self._base.reinstall('librita')

        self.assertEqual(reinstalled_count, 1)
        self.assertEqual(self._goal.mock_calls, [mock.call.install(pkg)])
