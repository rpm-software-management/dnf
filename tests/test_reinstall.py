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
from tests import mock
from tests import support
import dnf.yum.base
import hawkey
import unittest

class Reinstall(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockYumBase("main")
        self.yumbase.conf.multilib_policy = "all"
        self.sack = self.yumbase.sack

    def test_reinstall(self):
        cnt = self.yumbase.reinstall("pepper")
        self.assertEqual(cnt, 1)
        new_set = support.installed_but(self.sack, "pepper")
        new_pkg = dnf.queries.available_by_nevra(self.sack, "pepper-20-0.x86_64")
        new_set += list(new_pkg)
        self.assertResult(self.yumbase, new_set)

    def test_reinstall_local(self):
        cnt = self.yumbase.reinstall_local(support.TOUR_50_PKG_PATH)
        self.assertEqual(cnt, 1)

class ReinstallTest(unittest.TestCase):
    def setUp(self):
        self._base = dnf.yum.base.Base()
        self._base._sack = support.mock_sack('main')
        self._base._goal = self._goal = mock.create_autospec(hawkey.Goal)

    def test_reinstall_pkgnevra(self):
        pkg = support.PackageMatcher(name='pepper', evr='20-0', arch='x86_64')
        
        reinstalled_count = self._base.reinstall('pepper-0:20-0.x86_64')
        
        self.assertEqual(reinstalled_count, 1)
        self.assertEqual(self._goal.mock_calls, [mock.call.install(pkg)])
    
    def test_reinstall_notfound(self):
        self.assertRaises(dnf.exceptions.ReinstallRemoveError,
                          self._base.reinstall, 'non-existent')
        self.assertEqual(self._goal.mock_calls, [])
        
    def test_reinstall_notinstalled(self):
        self.assertRaises(dnf.exceptions.ReinstallRemoveError,
                          self._base.reinstall, 'lotus')
        self.assertEqual(self._goal.mock_calls, [])
        
    def test_reinstall_notavailable(self):
        pkgs = [support.PackageMatcher(name='hole')]
        
        with self.assertRaises(dnf.exceptions.ReinstallInstallError) as context:
            self._base.reinstall('hole')
        
        self.assertEquals(context.exception.failed_pkgs, pkgs)
        self.assertEqual(self._goal.mock_calls, [])
        
    def test_reinstall_notavailable_available(self):
        pkg = support.PackageMatcher(name='librita')
        
        reinstalled_count = self._base.reinstall('librita')
        
        self.assertEqual(reinstalled_count, 1)
        self.assertEqual(self._goal.mock_calls, [mock.call.install(pkg)])
