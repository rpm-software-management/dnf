# -*- coding: utf-8 -*-

# Copyright (C) 2013-2018 Red Hat, Inc.
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

"""Tests of the history undo command."""

from __future__ import absolute_import
from __future__ import unicode_literals

import libdnf.transaction

from dnf.exceptions import PackagesNotAvailableError, PackagesNotInstalledError
#from dnf.history import NEVRAOperations
#from dnf.transaction import ERASE, DOWNGRADE, INSTALL, REINSTALL, UPGRADE
#from dnf.transaction import TransactionItem

import tests.support

'''
class BaseTest(tests.support.DnfBaseTestCase):
    """Unit tests of dnf.Base."""

    REPOS = ['main', 'updates']

    def assertEqualTransactionItems(self, one, two):
        self.assertEqual(one.op_type, two.op_type)
        self.assertEqual(str(one.installed), str(two.installed))
        self.assertEqual(str(one.erased), str(two.erased))
        self.assertEqual([str(i) for i in one.obsoleted], [str(i) for i in two.obsoleted])
        self.assertEqual(one.reason, two.reason)

    def test_history_undo_operations_downgrade(self):
        """Test history_undo_operations with a downgrade."""
        operations = NEVRAOperations()
        operations.add(
            'Downgrade',
            'pepper-20-0.x86_64',
            'pepper-20-1.x86_64',
            ('lotus-3-16.x86_64',)
        )

        with self.base:
            self.base._history_undo_operations(operations, 0)

            transaction_it = iter(self.base.transaction)

            actual = next(transaction_it)
            expected = TransactionItem(
                UPGRADE,
                installed='pepper-20-1.x86_64',
                erased='pepper-20-0.x86_64'
            )
            self.assertEqualTransactionItems(actual, expected)

            actual = next(transaction_it)
            expected = TransactionItem(
                INSTALL,
                installed='lotus-3-16.x86_64',
                reason=libdnf.transaction.TransactionItemReason_USER
            )
            self.assertEqualTransactionItems(actual, expected)

            self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_operations_downgrade_notavailable(self):
        """Test history_undo_operations with an unavailable downgrade."""
        operations = NEVRAOperations()
        operations.add('Downgrade', 'pepper-20-0.x86_64', 'pepper-20-2.x86_64')

        with self.base, self.assertRaises(PackagesNotAvailableError) as context:
            self.base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'pepper-20-2.x86_64')

    def test_history_undo_operations_downgrade_notinstalled(self):
        """Test history_undo_operations with a not installed downgrade."""
        operations = NEVRAOperations()
        operations.add('Downgrade', 'lotus-3-0.x86_64', 'lotus-3-16.x86_64')

        with self.base, self.assertRaises(PackagesNotInstalledError) as context:
            self.base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'lotus-3-0.x86_64')

    def test_history_undo_operations_erase(self):
        """Test history_undo_operations with an erase."""
        operations = NEVRAOperations()
        operations.add('Erase', 'lotus-3-16.x86_64')

        with self.base:
            self.base._history_undo_operations(operations, 0)

            transaction_it = iter(self.base.transaction)

            actual = next(transaction_it)
            expected = TransactionItem(
                INSTALL,
                installed='lotus-3-16.x86_64',
                reason=libdnf.transaction.TransactionItemReason_USER
            )
            self.assertEqualTransactionItems(actual, expected)

            self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_operations_erase_twoavailable(self):
        """Test history_undo_operations with an erase available in two repos."""
        operations = NEVRAOperations()
        operations.add('Erase', 'lotus-3-16.x86_64')

        with self.base:
            self.base._history_undo_operations(operations, 0)
            transaction_it = iter(self.base.transaction)

            actual = next(transaction_it)
            expected = TransactionItem(
                INSTALL,
                installed='lotus-3-16.x86_64',
                reason=libdnf.transaction.TransactionItemReason_USER
            )
            self.assertEqualTransactionItems(actual, expected)

            self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_operations_erase_notavailable(self):
        """Test history_undo_operations with an unavailable erase."""
        operations = NEVRAOperations()
        operations.add('Erase', 'hole-1-1.x86_64')

        with self.base, self.assertRaises(PackagesNotAvailableError) as context:
            self.base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'hole-1-1.x86_64')

    def test_history_undo_operations_install(self):
        """Test history_undo_operations with an install."""
        operations = NEVRAOperations()
        operations.add('Install', 'pepper-20-0.x86_64', obsoleted_nevras=('lotus-3-16.x86_64',))

        with self.base:
            self.base._history_undo_operations(operations, 0)

            transaction_it = iter(self.base.transaction)

            actual = next(transaction_it)
            expected = TransactionItem(ERASE, erased='pepper-20-0.x86_64')
            self.assertEqualTransactionItems(actual, expected)

            actual = next(transaction_it)
            expected = TransactionItem(
                INSTALL,
                installed='lotus-3-16.x86_64',
                reason=libdnf.transaction.TransactionItemReason_USER
            )
            self.assertEqualTransactionItems(actual, expected)

            self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_operations_install_notinstalled(self):
        """Test history_undo_operations with a not installed install."""
        operations = NEVRAOperations()
        operations.add('Install', 'mrkite-2-0.x86_64')

        with self.base, self.assertRaises(PackagesNotInstalledError) as context:
            self.base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'mrkite-2-0.x86_64')

    def test_history_undo_operations_reinstall(self):
        """Test history_undo_operations with a reinstall."""
        operations = NEVRAOperations()
        operations.add(
            'Reinstall',
            'pepper-20-0.x86_64',
            'pepper-20-0.x86_64',
            ('hole-1-1.x86_64',)
        )

        with self.base:
            self.base._history_undo_operations(operations, 0)

            transaction_it = iter(self.base.transaction)

            actual = next(transaction_it)
            expected = TransactionItem(
                REINSTALL,
                installed='pepper-20-0.x86_64',
                erased='pepper-20-0.x86_64',
                obsoleted=('hole-1-1.x86_64',)
            )
            self.assertEqualTransactionItems(actual, expected)

            self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_operations_reinstall_notavailable(self):
        """Test history_undo_operations with an unvailable reinstall."""
        operations = NEVRAOperations()
        operations.add('Reinstall', 'mrkite-2-0.x86_64', 'mrkite-2-0.x86_64')

        with self.base, self.assertRaises(PackagesNotInstalledError) as context:
            self.base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'mrkite-2-0.x86_64')

    def test_history_undo_operations_reinstall_notinstalled(self):
        """Test history_undo_operations with a not installed reinstall."""
        operations = NEVRAOperations()
        operations.add('Reinstall', 'hole-1-1.x86_64', 'hole-1-1.x86_64')

        with self.base, self.assertRaises(PackagesNotAvailableError) as context:
            self.base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'hole-1-1.x86_64')

    def test_history_undo_operations_reinstall_notinstalled_obsoleted(self):
        """Test history_undo_operations with a not installed obsoleted of a reinstall."""
        operations = NEVRAOperations()
        operations.add(
            'Reinstall',
            'pepper-20-0.x86_64',
            'pepper-20-0.x86_64',
            ('lotus-3-16.x86_64',)
        )

        with self.base:
            self.base._history_undo_operations(operations, 0)

            transaction_it = iter(self.base.transaction)

            actual = next(transaction_it)
            expected = TransactionItem(
                REINSTALL,
                installed='pepper-20-0.x86_64',
                erased='pepper-20-0.x86_64',
                obsoleted=()
            )
            self.assertEqualTransactionItems(actual, expected)

            self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_operations_update(self):
        """Test history_undo_operations with an update."""
        operations = NEVRAOperations()
        operations.add('Update', 'tour-5-0.noarch', 'tour-4.6-1.noarch', ('lotus-3-16.x86_64',))

        with self.base:
            self.base._history_undo_operations(operations, 0)

            transaction_it = iter(self.base.transaction)

            actual = next(transaction_it)
            expected = TransactionItem(
                DOWNGRADE,
                installed='tour-4.6-1.noarch',
                erased='tour-5-0.noarch'
            )
            self.assertEqualTransactionItems(actual, expected)

            actual = next(transaction_it)
            expected = TransactionItem(
                INSTALL,
                installed='lotus-3-16.x86_64',
                reason=libdnf.transaction.TransactionItemReason_USER
            )
            self.assertEqualTransactionItems(actual, expected)

            self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_operations_update_notavailable(self):
        """Test history_undo_operations with an unavailable update."""
        operations = NEVRAOperations()
        operations.add('Update', 'tour-5-0.noarch', 'tour-4.6-2.noarch')

        with self.base, self.assertRaises(PackagesNotAvailableError) as context:
            self.base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'tour-4.6-2.noarch')

    def test_history_undo_operations_update_notinstalled(self):
        """Test history_undo_operations with a not installed update."""
        operations = NEVRAOperations()
        operations.add('Update', 'lotus-4-0.x86_64', 'lotus-3-16.x86_64')

        with self.base, self.assertRaises(PackagesNotInstalledError) as context:
            self.base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'lotus-4-0.x86_64')
'''
