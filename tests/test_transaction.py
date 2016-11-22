# Copyright (C) 2013-2016 Red Hat, Inc.
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
from tests.support import mock, FakeConf

import dnf.goal
import dnf.repo
import dnf.transaction
import rpm
import tests.support

class TransactionItemTest(tests.support.TestCase):
    @classmethod
    def setUpClass(cls):
        """Prepare the class level fixture."""
        cls.newpkg = tests.support.MockPackage('new-1.0-1.x86_64')
        cls.oldpkg = tests.support.MockPackage('old-4.23-13.x86_64')
        cls.obspkg1 = tests.support.MockPackage('obs1-3.12-12.x86_64')
        cls.obspkg2 = tests.support.MockPackage('obs2-2.1-11.x86_64')
        cls.obspkg3 = tests.support.MockPackage('obs3-1.0-10.x86_64')

    def test_active_hist_state_erase(self):
        """Test active_history_state with the erase op_type."""
        tsi = dnf.transaction.TransactionItem(
            dnf.transaction.ERASE, erased=self.oldpkg)

        history_state = tsi._active_history_state

        self.assertEqual(history_state, 'Erase')

    def test_active_hist_state_install(self):
        """Test active_history_state with the install op_type."""
        tsi = dnf.transaction.TransactionItem(
            dnf.transaction.INSTALL, installed=self.newpkg,
            obsoleted=[self.obspkg1, self.obspkg2])

        history_state = tsi._active_history_state

        self.assertEqual(history_state, 'Install')

    def test_creating(self):
        tsi = dnf.transaction.TransactionItem(
            dnf.transaction.UPGRADE, self.newpkg, self.oldpkg,
            [self.obspkg1, self.obspkg2, self.obspkg3])
        self.assertEqual(tsi.installed, self.newpkg)
        self.assertEqual(tsi.erased, self.oldpkg)
        self.assertCountEqual(
            tsi.obsoleted, [self.obspkg1, self.obspkg2, self.obspkg3])

        tsi = dnf.transaction.TransactionItem(dnf.transaction.ERASE,
                                              erased=self.oldpkg)
        self.assertEqual(tsi.installed, None)
        self.assertEqual(tsi.erased, self.oldpkg)
        self.assertCountEqual(tsi.obsoleted, ())

    def test_history_iterator_reinstall(self):
        """Test history_iterator with the reinstall op_type."""
        tsi = dnf.transaction.TransactionItem(
            dnf.transaction.REINSTALL, self.newpkg, self.oldpkg,
            [self.obspkg1, self.obspkg2, self.obspkg3])
        self.assertCountEqual(
            tsi._history_iterator(),
            [(self.newpkg, 'Reinstall'), (self.oldpkg, 'Reinstalled'),
             (self.newpkg, 'Obsoleting'), (self.obspkg1, 'Obsoleted'),
             (self.obspkg2, 'Obsoleted'), (self.obspkg3, 'Obsoleted')])

    def test_history_iterator_upgrade(self):
        """Test history_iterator with the upgrade op_type."""
        tsi = dnf.transaction.TransactionItem(
            dnf.transaction.UPGRADE, self.newpkg, self.oldpkg,
            [self.obspkg1, self.obspkg2, self.obspkg3])
        self.assertCountEqual(
            tsi._history_iterator(),
            [(self.newpkg, 'Update'), (self.oldpkg, 'Updated'),
             (self.newpkg, 'Obsoleting'), (self.obspkg1, 'Obsoleted'),
             (self.obspkg2, 'Obsoleted'), (self.obspkg3, 'Obsoleted')])

    def test_removes(self):
        tsi = dnf.transaction.TransactionItem(
            dnf.transaction.UPGRADE, self.newpkg, self.oldpkg,
            [self.obspkg1, self.obspkg2, self.obspkg3])
        self.assertCountEqual(
            tsi.removes(),
            [self.oldpkg, self.obspkg1, self.obspkg2, self.obspkg3])

class TransactionTest(tests.support.TestCase):
    def setUp(self):
        self.ipkg = tests.support.MockPackage('inst-1.0-1.x86_64')
        self.upkg1 = tests.support.MockPackage('upg1-2.1-2.x86_64')
        self.upkg2 = tests.support.MockPackage('upg2-3.2-3.x86_64')
        self.dpkg = tests.support.MockPackage('down-4.3-4.x86_64')
        self.rpkg1 = tests.support.MockPackage('rem1-2.1-1.x86_64')
        self.rpkg2 = tests.support.MockPackage('rem2-3.2-2.x86_64')
        self.rpkg3 = tests.support.MockPackage('rem3-4.3-5.x86_64')
        self.opkg1 = tests.support.MockPackage('obs1-4.23-13.x86_64')
        self.opkg2 = tests.support.MockPackage('obs2-3.12-12.x86_64')
        self.opkg3 = tests.support.MockPackage('obs3-2.1-11.x86_64')
        self.opkg4 = tests.support.MockPackage('obs4-1.0-10.x86_64')
        self.trans = dnf.transaction.Transaction()
        self.trans.add_install(self.ipkg, [self.opkg1, self.opkg2, self.opkg3])
        self.trans.add_upgrade(self.upkg1, self.rpkg1, [self.opkg4])
        self.trans.add_upgrade(self.upkg2, self.rpkg2, [])
        self.trans.add_downgrade(self.dpkg, self.rpkg3, [])

    def test_get_items(self):
        self.assertLength(self.trans._get_items(dnf.transaction.ERASE), 0)
        self.assertLength(self.trans._get_items(dnf.transaction.UPGRADE), 2)

    def test_iter(self):
        self.assertLength(list(self.trans), 4)
        self.assertIsInstance(next(iter(self.trans)),
                              dnf.transaction.TransactionItem)

    def test_length(self):
        self.assertLength(self.trans, 4)

    def test_sets(self):
        self.assertCountEqual(
            self.trans.install_set,
            [self.ipkg, self.upkg1, self.upkg2, self.dpkg])
        self.assertCountEqual(
            self.trans.remove_set,
            [self.opkg1, self.opkg2, self.opkg3, self.opkg4,
             self.rpkg1, self.rpkg2, self.rpkg3])

    def test_total_package_count(self):
        self.assertEqual(self.trans._total_package_count(), 11)

class RPMLimitationsTest(tests.support.TestCase):
    def test_rpm_limitations(self):
        ts = dnf.transaction.Transaction()
        pkg = tests.support.MockPackage('anyway-2-0.src')
        ts.add_install(pkg, [])
        msg = ts._rpm_limitations()
        self.assertIsNot(msg, None)

class PopulateTSTest(tests.support.TestCase):
    @staticmethod
    def test_populate_rpm_ts():
        ts = dnf.transaction.Transaction()
        conf = FakeConf(cachedir='/tmp')
        repo = dnf.repo.Repo('r', conf)

        inst = tests.support.MockPackage("ago-20.0-1.x86_64.fc69", repo)
        upg = tests.support.MockPackage("billy-1.2-1.x86_64.fc69", repo)
        old = tests.support.MockPackage("billy-1.1-1.x86_64.fc69", repo)
        ts.add_install(inst, [])
        ts.add_upgrade(upg, old, [])
        rpm_ts = ts._populate_rpm_ts(mock.Mock())
        rpm_ts.assert_has_calls([mock.call.addInstall(None, ts._tsis[0], 'i'),
                                 mock.call.addInstall(None, ts._tsis[1], 'u')])

class RPMProbFilters(tests.support.TestCase):

    @mock.patch('dnf.rpm.transaction.TransactionWrapper')
    def test_filters_install(self, _mock_ts):
        self.base = tests.support.BaseCliStub()
        self.base._sack = tests.support.mock_sack('main', 'search')
        self.base._goal = dnf.goal.Goal(self.base.sack)
        self.base.install("lotus")
        ts = self.base._ts
        ts.setProbFilter.assert_called_with(rpm.RPMPROB_FILTER_OLDPACKAGE)

    @mock.patch('dnf.rpm.transaction.TransactionWrapper')
    def test_filters_downgrade(self, _ts):
        self.base = tests.support.BaseCliStub()
        self.base._sack = tests.support.mock_sack('main', 'old_versions')
        self.base._goal = dnf.goal.Goal(self.base.sack)
        self.base.downgrade("tour")
        ts = self.base._ts
        ts.setProbFilter.assert_called_with(rpm.RPMPROB_FILTER_OLDPACKAGE)

    @mock.patch('dnf.rpm.transaction.TransactionWrapper')
    def test_filters_reinstall(self, _ts):
        self.base = tests.support.BaseCliStub()
        self.base._sack = tests.support.mock_sack('main')
        self.base._goal = dnf.goal.Goal(self.base.sack)
        self.base.reinstall("librita")
        expected = rpm.rpm.RPMPROB_FILTER_OLDPACKAGE
        self.base._ts.setProbFilter.assert_called_with(expected)
