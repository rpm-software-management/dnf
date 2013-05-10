# Copyright (C) 2013  Red Hat, Inc.
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
from tests.mock import call
import dnf.repo
import dnf.transaction
import tests.mock
import tests.support

class TransactionItemTest(tests.support.TestCase):
    def test_creating(self):
        tsi = dnf.transaction.TransactionItem(dnf.transaction.UPGRADE, 'new',
                                              'old', ['o1', 'o2', 'o3'])
        self.assertEqual(tsi.installed, 'new')
        self.assertEqual(tsi.erased, 'old')
        self.assertItemsEqual(tsi.obsoleted, ('o1', 'o2', 'o3'))

        tsi = dnf.transaction.TransactionItem(dnf.transaction.ERASE,
                                              erased='old')
        self.assertEqual(tsi.installed, None)
        self.assertEqual(tsi.erased, 'old')
        self.assertItemsEqual(tsi.obsoleted, ())

    def test_history_iterator(self):
        tsi = dnf.transaction.TransactionItem(dnf.transaction.UPGRADE, 'new',
                                              'old', ['o1', 'o2', 'o3'])
        self.assertItemsEqual(tsi.history_iterator(),
                              [('new', 'Update'), ('old', 'Updated'),
                               ('new', 'Obsoleting'), ('o1', 'Obsoleted'),
                               ('o2', 'Obsoleted'), ('o3', 'Obsoleted')])

    def test_propagated_reason(self):
        TI = dnf.transaction.TransactionItem
        yumdb = tests.mock.Mock()
        yumdb.get_package().get = lambda s: 'dep'

        tsi = TI(dnf.transaction.INSTALL, installed='i1', reason='user')
        self.assertEqual(tsi.propagated_reason(yumdb), 'user')
        tsi = TI(dnf.transaction.UPGRADE, installed='u1', erased='r1')
        self.assertEqual(tsi.propagated_reason(yumdb), 'dep')
        tsi = TI(dnf.transaction.DOWNGRADE, installed='d1', erased='r2')
        self.assertEqual(tsi.propagated_reason(yumdb), 'dep')

        # test the call can survive if no reason is known:
        yumdb = tests.mock.Mock()
        yumdb.get_package().get = lambda s: None
        self.assertEqual(tsi.propagated_reason(yumdb), 'unknown')

    def test_removes(self):
        tsi = dnf.transaction.TransactionItem(dnf.transaction.UPGRADE, 'new',
                                              'old', ['o1', 'o2', 'o3'])
        self.assertItemsEqual(tsi.removes(), ('old', 'o1', 'o2', 'o3'))

class TransactionTest(tests.support.TestCase):
    def setUp(self):
        self.ts = dnf.transaction.Transaction()
        self.ts.add_install('i1', ['o1', 'o2', 'o3'])
        self.ts.add_upgrade('u1', 'r1', ['o4'])
        self.ts.add_upgrade('u2', 'r2', [])
        self.ts.add_downgrade('d1', 'r3', [])

    def test_get_items(self):
        self.assertLength(self.ts.get_items(dnf.transaction.ERASE), 0)
        self.assertLength(self.ts.get_items(dnf.transaction.UPGRADE), 2)

    def test_iter(self):
        self.assertLength(list(self.ts), 4)
        self.assertIsInstance(iter(self.ts).next(),
                              dnf.transaction.TransactionItem)

    def test_length(self):
        self.assertLength(self.ts, 4)

    def test_sets(self):
        self.assertItemsEqual(self.ts.install_set, ('i1', 'u1', 'u2', 'd1'))
        self.assertItemsEqual(self.ts.remove_set,
                              ('o1', 'o2', 'o3', 'o4', 'r1', 'r2', 'r3'))

    def test_total_package_count(self):
        self.assertEqual(self.ts.total_package_count(), 11)

class RPMLimitationsTest(tests.support.TestCase):
    def test_rpm_limitations(self):
        ts = dnf.transaction.Transaction()
        pkg = tests.support.MockPackage('anyway-2-0.src')
        ts.add_install(pkg, [])
        msg = ts.rpm_limitations()
        self.assertIsNot(msg, None)

class PopulateTSTest(tests.support.TestCase):
    def test_populate_rpm_ts(self):
        ts = dnf.transaction.Transaction()
        repo = dnf.repo.Repo('r')
        repo.basecachedir = '/tmp'

        inst = tests.support.MockPackage("ago-20.0-1.x86_64.fc69", repo)
        upg = tests.support.MockPackage("billy-1.2-1.x86_64.fc69", repo)
        old = tests.support.MockPackage("billy-1.1-1.x86_64.fc69", repo)
        ts.add_install(inst, [])
        ts.add_upgrade(upg, old, [])
        rpm_ts = ts.populate_rpm_ts(tests.mock.Mock())
        rpm_ts.assert_has_calls(call.addInstall(None, ts._tsis[0], 'i'))
        rpm_ts.assert_has_calls(call.addInstall(None, ts._tsis[1], 'u'))
