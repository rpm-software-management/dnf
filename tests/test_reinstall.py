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

class Reinstall(support.ResultTestCase):
    def setUp(self):
        self.yumbase = dnf.yum.base.Base()
        self.yumbase.conf.multilib_policy = "all"
        self.yumbase._sack = support.mock_sack('main', 'only_i686')
        self.yumbase._goal = self.goal = mock.create_autospec(hawkey.Goal)

    def test_reinstall_local(self):
        cnt = self.yumbase.reinstall_local(support.TOUR_50_PKG_PATH)
        self.assertEqual(cnt, 1)

    def test_reinstall_pkgname(self):
        pkg = support.PackageMatcher(name='pepper')
        
        reinstalled_count = self.yumbase.reinstall('pepper')
        
        self.assertEqual(reinstalled_count, 1)
        self.assertEqual(self.goal.mock_calls, [mock.call.install(pkg)])

    def test_reinstall_pkgnevra(self):
        pkg = support.PackageMatcher(name='pepper', evr='20-0', arch='x86_64')
        
        reinstalled_count = self.yumbase.reinstall('pepper-0:20-0.x86_64')
        
        self.assertEqual(reinstalled_count, 1)
        self.assertEqual(self.goal.mock_calls, [mock.call.install(pkg)])
    
    def test_reinstall_notfound(self):
        self.assertRaises(dnf.exceptions.PackagesNotInstalledError,
                          self.yumbase.reinstall, 'non-existent')
        self.assertEqual(self.goal.mock_calls, [])
        
    def test_reinstall_notinstalled(self):
        self.assertRaises(dnf.exceptions.PackagesNotInstalledError,
                          self.yumbase.reinstall, 'lotus')
        self.assertEqual(self.goal.mock_calls, [])
        
    def test_reinstall_notavailable(self):
        pkgs = [support.PackageMatcher(name='hole')]
        
        with self.assertRaises(dnf.exceptions.PackagesNotAvailableError) as context:
            self.yumbase.reinstall('hole')
        
        self.assertEquals(context.exception.packages, pkgs)
        self.assertEqual(self.goal.mock_calls, [])
        
    def test_reinstall_notavailable_available(self):
        pkg = support.PackageMatcher(name='librita')
        
        reinstalled_count = self.yumbase.reinstall('librita')
        
        self.assertEqual(reinstalled_count, 1)
        self.assertEqual(self.goal.mock_calls, [mock.call.install(pkg)])

