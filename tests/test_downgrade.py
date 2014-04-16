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
from __future__ import unicode_literals
from tests import support
from tests.support import mock

import dnf
import hawkey
import rpm

class DowngradeTest(support.ResultTestCase):

    @mock.patch('dnf.rpmUtils.transaction.TransactionWrapper')
    def test_package_downgrade(self, ts):
        base = support.MockBase()

        pkg = base.add_remote_rpm(support.TOUR_44_PKG_PATH)
        cnt = base.package_downgrade(pkg)
        base.ts.setProbFilter.assert_called_with(
            rpm.RPMPROB_FILTER_OLDPACKAGE)
        self.assertGreater(cnt, 0)
        (installed, removed) = self.installed_removed(base)
        self.assertItemsEqual(map(str, installed), ("tour-4-4.noarch", ))
        self.assertItemsEqual(map(str, removed), ("tour-5-0.noarch", ))

    def test_downgrade(self):
        base = support.MockBase("main")
        sack = base.sack
        cnt = base.downgrade("tour")
        self.assertGreater(cnt, 0)

        new_pkg = sack.query().available().filter(name="tour")[0]
        self.assertEqual(new_pkg.evr, "4.6-1")
        new_set = support.installed_but(sack, "tour") + [new_pkg]
        self.assertResult(base, new_set)

    def test_downgrade2(self):
        b = support.MockBase("old_versions")
        ret = b.downgrade("tour")
        installed, removed = self.installed_removed(b)
        self.assertItemsEqual(map(str, installed), ['tour-4.9-1.noarch'])
        self.assertItemsEqual(map(str, removed), ['tour-5-0.noarch'])

class DowngradeTest2(support.TestCase):

    def setUp(self):
        self._base = dnf.Base()
        self._base._sack = support.mock_sack('main')
        self._base._goal = self._goal = mock.create_autospec(hawkey.Goal)

    def test_downgrade_pkgnevra(self):
        """ Downgrade should handle full NEVRAs. """
        pkg = support.ObjectMatcher(dnf.package.Package, {'name': 'tour'})

        downgraded_count = self._base.downgrade('tour-0:5-0.noarch')

        self.assertEqual(self._goal.mock_calls, [mock.call.install(pkg)])
        self.assertEqual(downgraded_count, 1)

    def test_downgrade_notinstalled(self):
        pkg = support.ObjectMatcher(dnf.package.Package, {'name': 'lotus'})

        with self.assertRaises(dnf.exceptions.PackagesNotInstalledError) as context:
            self._base.downgrade('lotus')
        self.assertEqual(context.exception.pkg_spec, 'lotus')
        self.assertEqual(tuple(context.exception.packages), (pkg,) * 2)
        self.assertEqual(self._goal.mock_calls, [])

    def test_downgrade_notfound(self):
        with self.assertRaises(dnf.exceptions.PackageNotFoundError) as context:
            self._base.downgrade('non-existent')
        self.assertEqual(context.exception.pkg_spec, 'non-existent')
        self.assertEqual(self._goal.mock_calls, [])

    def test_downgrade_nodowngrade(self):
        downgraded_count = self._base.downgrade('pepper')

        self.assertEqual(self._goal.mock_calls, [])
        self.assertEqual(downgraded_count, 0)
