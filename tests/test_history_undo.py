# test_history_undo.py
# Tests of the history undo command.
#
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

"""Tests of the history undo command."""

from __future__ import absolute_import
from __future__ import unicode_literals
from dnf.exceptions import PackagesNotAvailableError, PackagesNotInstalledError
from dnf.history import NEVRAOperations
from dnf.package import Package
from dnf.transaction import (ERASE, DOWNGRADE, INSTALL, REINSTALL,
                             TransactionItem, UPGRADE)
from hawkey import split_nevra
from tests.support import mock_sack, Base, ObjectMatcher
from unittest import TestCase

class BaseTest(TestCase):
    """Unit tests of dnf.Base."""

    def _create_item_matcher(self, op_type, installed=None, erased=None,
                             obsoleted=[], reason='unknown'):
        """Create a new instance of dnf.transaction.TransactionItem matcher."""
        attrs = {'op_type': op_type,
                 'installed': self._create_package_matcher(installed)
                              if installed else installed,
                 'erased': self._create_package_matcher(erased)
                           if erased else erased,
                 'obsoleted': [self._create_package_matcher(nevra)
                               for nevra in obsoleted],
                 'reason': reason}
        return ObjectMatcher(TransactionItem, attrs)

    def _create_package_matcher(self, nevra_str):
        """Create a new instance of dnf.package.Package matcher."""
        nevra = split_nevra(nevra_str)
        attrs = {'name': nevra.name,
                 'epoch': nevra.epoch,
                 'version': nevra.version,
                 'release': nevra.release,
                 'arch': nevra.arch}
        return ObjectMatcher(Package, attrs)

    def setUp(self):
        """Prepare the test fixture."""
        self._base = Base()
        self._base._sack = mock_sack('main', 'updates')

    def test_history_undo_operations_downgrade(self):
        """Test history_undo_operations with a downgrade."""
        operations = NEVRAOperations()
        operations.add('Downgrade', 'pepper-20-0.x86_64', 'pepper-20-1.x86_64', ('lotus-3-16.x86_64',))

        with self._base:
            self._base._history_undo_operations(operations, 0)

        transaction_it = iter(self._base.transaction)
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             UPGRADE, installed='pepper-20-1.x86_64',
                             erased='pepper-20-0.x86_64'))
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                            INSTALL, installed='lotus-3-16.x86_64',
                            reason='user'))
        self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_operations_downgrade_notavailable(self):
        """Test history_undo_operations with an unavailable downgrade."""
        operations = NEVRAOperations()
        operations.add('Downgrade', 'pepper-20-0.x86_64', 'pepper-20-2.x86_64')

        with self._base, self.assertRaises(PackagesNotAvailableError) as context:
            self._base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'pepper-20-2.x86_64')

    def test_history_undo_operations_downgrade_notinstalled(self):
        """Test history_undo_operations with a not installed downgrade."""
        operations = NEVRAOperations()
        operations.add('Downgrade', 'lotus-3-0.x86_64', 'lotus-3-16.x86_64')

        with self._base, self.assertRaises(PackagesNotInstalledError) as context:
            self._base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'lotus-3-0.x86_64')

    def test_history_undo_operations_erase(self):
        """Test history_undo_operations with an erase."""
        operations = NEVRAOperations()
        operations.add('Erase', 'lotus-3-16.x86_64')

        with self._base:
            self._base._history_undo_operations(operations, 0)

        transaction_it = iter(self._base.transaction)
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             INSTALL, installed='lotus-3-16.x86_64',
                             reason='user'))
        self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_operations_erase_twoavailable(self):
        """Test history_undo_operations with an erase available in two repos."""
        base = Base()
        base._sack = mock_sack('main', 'search')
        operations = NEVRAOperations()
        operations.add('Erase', 'lotus-3-16.x86_64')

        with base:
            base._history_undo_operations(operations, 0)

        transaction_it = iter(base.transaction)
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             INSTALL, installed='lotus-3-16.x86_64',
                             reason='user'))
        self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_operations_erase_notavailable(self):
        """Test history_undo_operations with an unavailable erase."""
        operations = NEVRAOperations()
        operations.add('Erase', 'hole-1-1.x86_64')

        with self._base, self.assertRaises(PackagesNotAvailableError) as context:
            self._base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'hole-1-1.x86_64')

    def test_history_undo_operations_install(self):
        """Test history_undo_operations with an install."""
        operations = NEVRAOperations()
        operations.add('Install', 'pepper-20-0.x86_64', obsoleted_nevras=('lotus-3-16.x86_64',))

        with self._base:
            self._base._history_undo_operations(operations, 0)

        transaction_it = iter(self._base.transaction)
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             ERASE, erased='pepper-20-0.x86_64'))
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             INSTALL, installed='lotus-3-16.x86_64',
                             reason='user'))
        self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_operations_install_notinstalled(self):
        """Test history_undo_operations with a not installed install."""
        operations = NEVRAOperations()
        operations.add('Install', 'mrkite-2-0.x86_64')

        with self._base, self.assertRaises(PackagesNotInstalledError) as context:
            self._base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'mrkite-2-0.x86_64')

    def test_history_undo_operations_reinstall(self):
        """Test history_undo_operations with a reinstall."""
        operations = NEVRAOperations()
        operations.add('Reinstall', 'pepper-20-0.x86_64', 'pepper-20-0.x86_64', ('hole-1-1.x86_64',))

        with self._base:
            self._base._history_undo_operations(operations, 0)

        transaction_it = iter(self._base.transaction)
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             REINSTALL, installed='pepper-20-0.x86_64',
                             erased='pepper-20-0.x86_64',
                             obsoleted=('hole-1-1.x86_64',)))
        self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_operations_reinstall_notavailable(self):
        """Test history_undo_operations with an unvailable reinstall."""
        operations = NEVRAOperations()
        operations.add('Reinstall', 'mrkite-2-0.x86_64', 'mrkite-2-0.x86_64')

        with self._base, self.assertRaises(PackagesNotInstalledError) as context:
            self._base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'mrkite-2-0.x86_64')

    def test_history_undo_operations_reinstall_notinstalled(self):
        """Test history_undo_operations with a not installed reinstall."""
        operations = NEVRAOperations()
        operations.add('Reinstall', 'hole-1-1.x86_64', 'hole-1-1.x86_64')

        with self._base, self.assertRaises(PackagesNotAvailableError) as context:
            self._base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'hole-1-1.x86_64')

    def test_history_undo_operations_reinstall_notinstalled_obsoleted(self):
        """Test history_undo_operations with a not installed obsoleted of a reinstall."""
        operations = NEVRAOperations()
        operations.add('Reinstall', 'pepper-20-0.x86_64', 'pepper-20-0.x86_64', ('lotus-3-16.x86_64',))

        with self._base:
            self._base._history_undo_operations(operations, 0)

        transaction_it = iter(self._base.transaction)
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             REINSTALL, installed='pepper-20-0.x86_64',
                             erased='pepper-20-0.x86_64', obsoleted=()))
        self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_operations_update(self):
        """Test history_undo_operations with an update."""
        operations = NEVRAOperations()
        operations.add('Update', 'tour-5-0.noarch', 'tour-4.6-1.noarch', ('lotus-3-16.x86_64',))

        with self._base:
            self._base._history_undo_operations(operations, 0)

        transaction_it = iter(self._base.transaction)
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             DOWNGRADE, installed='tour-4.6-1.noarch',
                             erased='tour-5-0.noarch'))
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             INSTALL, installed='lotus-3-16.x86_64',
                             reason='user'))
        self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_operations_update_notavailable(self):
        """Test history_undo_operations with an unavailable update."""
        operations = NEVRAOperations()
        operations.add('Update', 'tour-5-0.noarch', 'tour-4.6-2.noarch')

        with self._base, self.assertRaises(PackagesNotAvailableError) as context:
            self._base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'tour-4.6-2.noarch')

    def test_history_undo_operations_update_notinstalled(self):
        """Test history_undo_operations with a not installed update."""
        operations = NEVRAOperations()
        operations.add('Update', 'lotus-4-0.x86_64', 'lotus-3-16.x86_64')

        with self._base, self.assertRaises(PackagesNotInstalledError) as context:
            self._base._history_undo_operations(operations, 0)

        self.assertEqual(context.exception.pkg_spec, 'lotus-4-0.x86_64')
