# test_history_undo.py
# Tests of the history undo command.
#
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

"""Tests of the history undo command."""

from __future__ import absolute_import
from dnf import Base
from dnf.exceptions import PackagesNotAvailableError, PackagesNotInstalledError
from dnf.package import Package
from dnf.transaction import (ERASE, DOWNGRADE, INSTALL, REINSTALL,
                             TransactionItem, UPGRADE)
from dnf.yum.history import YumHistoryPackageState
from hawkey import split_nevra
from tests.support import mock_sack, ObjectMatcher, YumHistoryStub
from unittest import TestCase

class BaseTest(TestCase):
    """Unit tests of dnf.Base."""

    def _create_item_matcher(self, op_type, installed=None, erased=None,
                             obsoleted=[]):
        """Create a new instance of dnf.transaction.TransactionItem matcher."""
        attrs = {'op_type': op_type,
                 'installed': self._create_package_matcher(installed)
                              if installed else installed,
                 'erased': self._create_package_matcher(erased)
                           if erased else erased,
                 'obsoleted': [self._create_package_matcher(nevra)
                               for nevra in obsoleted]}
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
        self._base.history = YumHistoryStub()

    def test_history_undo_badid(self):
        """Test history_undo with a bad transaction ID."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'hole', 'x86_64', '0', '1', '1', 'Erase',
                history=self._base.history),)

        with self._base:
            self.assertRaises(ValueError, self._base.history_undo, 2)

    def test_history_undo_downgrade(self):
        """Test history_undo with a downgrade."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Downgrade',
                history=self._base.history),
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '1', 'Downgraded',
                history=self._base.history),
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Obsoleting',
                history=self._base.history),
            YumHistoryPackageState(
                'lotus', 'x86_64', '0', '3', '16', 'Obsoleted',
                history=self._base.history))

        with self._base:
            self._base.history_undo(1)

        transaction_it = iter(self._base.transaction)
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             UPGRADE, installed='pepper-20-1.x86_64',
                             erased='pepper-20-0.x86_64'))
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                            INSTALL, installed='lotus-3-16.x86_64'))
        self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_downgrade_notavailable(self):
        """Test history_undo with an unavailable downgrade."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Downgrade',
                history=self._base.history),
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '2', 'Downgraded',
                history=self._base.history))

        with self._base:
            self.assertRaises(PackagesNotAvailableError,
                              self._base.history_undo, 1)

    def test_history_undo_downgrade_notavailable_obsoleted(self):
        """Test history_undo with an unavailable obsoleted of a downgrade."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Downgrade',
                history=self._base.history),
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '1', 'Downgraded',
                history=self._base.history),
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Obsoleting',
                history=self._base.history),
            YumHistoryPackageState(
                'hole', 'x86_64', '0', '1', '1', 'Obsoleted',
                history=self._base.history))

        with self._base:
            self.assertRaises(PackagesNotAvailableError,
                              self._base.history_undo, 1)

    def test_history_undo_downgrade_notinstalled(self):
        """Test history_undo with a not installed downgrade."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'lotus', 'x86_64', '0', '3', '0', 'Downgrade',
                history=self._base.history),
            YumHistoryPackageState(
                'lotus', 'x86_64', '0', '3', '16', 'Downgraded',
                history=self._base.history))

        with self._base:
            self.assertRaises(PackagesNotInstalledError,
                              self._base.history_undo, 1)

    def test_history_undo_empty(self):
        """Test history_undo with an empty transaction."""
        self._base.history.old_data_pkgs['1'] = ()

        with self._base:
            self._base.history_undo(1)

        transaction_it = iter(self._base.transaction)
        self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_erase(self):
        """Test history_undo with an erase."""
        self._base.history.old_data_pkgs['1'] = (YumHistoryPackageState(
            'lotus', 'x86_64', '0', '3', '16', 'Erase',
            history=self._base.history),)

        with self._base:
            self._base.history_undo(1)

        transaction_it = iter(self._base.transaction)
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             INSTALL, installed='lotus-3-16.x86_64'))
        self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_erase_notavailable(self):
        """Test history_undo with an unavailable erase."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'hole', 'x86_64', '0', '1', '1', 'Erase',
                history=self._base.history),)

        with self._base:
            self.assertRaises(PackagesNotAvailableError,
                              self._base.history_undo, 1)

    def test_history_undo_install(self):
        """Test history_undo with an install."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Install',
                history=self._base.history),
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Obsoleting',
                history=self._base.history),
            YumHistoryPackageState(
                'lotus', 'x86_64', '0', '3', '16', 'Obsoleted',
                history=self._base.history))

        with self._base:
            self._base.history_undo(1)

        transaction_it = iter(self._base.transaction)
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             ERASE, erased='pepper-20-0.x86_64'))
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             INSTALL, installed='lotus-3-16.x86_64'))
        self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_install_notavailable_obsoleted(self):
        """Test history_undo with an unvailable obsoleted of an install."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Install',
                history=self._base.history),
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Obsoleting',
                history=self._base.history),
            YumHistoryPackageState(
                'hole', 'x86_64', '0', '1', '1', 'Obsoleted',
                history=self._base.history))

        with self._base:
            self.assertRaises(PackagesNotAvailableError,
                              self._base.history_undo, 1)

    def test_history_undo_install_notinstalled(self):
        """Test history_undo with a not installed install."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'mrkite', 'x86_64', '0', '2', '0', 'Install',
                history=self._base.history),)

        with self._base:
            self.assertRaises(PackagesNotInstalledError,
                              self._base.history_undo, 1)

    def test_history_undo_notransaction(self):
        """Test history_undo without any transaction."""
        with self._base:
            self.assertRaises(ValueError, self._base.history_undo, 1)

    def test_history_undo_offset(self):
        """Test history_undo with a transaction offset from the end."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Install',
                history=self._base.history),)
        self._base.history.old_data_pkgs['2'] = (YumHistoryPackageState(
            'lotus', 'x86_64', '0', '3', '16', 'Erase',
            history=self._base.history),)

        with self._base:
            self._base.history_undo(-1)

        transaction_it = iter(self._base.transaction)
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             INSTALL, installed='lotus-3-16.x86_64'))
        self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_reinstall(self):
        """Test history_undo with a reinstall."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Reinstall',
                history=self._base.history),
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Reinstalled',
                history=self._base.history),
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Obsoleting',
                history=self._base.history),
            YumHistoryPackageState(
                'hole', 'x86_64', '0', '1', '1', 'Obsoleted',
                history=self._base.history))

        with self._base:
            self._base.history_undo(1)

        transaction_it = iter(self._base.transaction)
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             REINSTALL, installed='pepper-20-0.x86_64',
                             erased='pepper-20-0.x86_64',
                             obsoleted=('hole-1-1.x86_64',)))
        self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_reinstall_notavailable(self):
        """Test history_undo with an unvailable reinstall."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'mrkite', 'x86_64', '0', '2', '0', 'Reinstall',
                history=self._base.history),
            YumHistoryPackageState(
                'mrkite', 'x86_64', '0', '2', '0', 'Reinstalled',
                history=self._base.history))

        with self._base:
            self.assertRaises(PackagesNotInstalledError,
                              self._base.history_undo, 1)

    def test_history_undo_reinstall_notinstalled(self):
        """Test history_undo with a not installed reinstall."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'hole', 'x86_64', '0', '1', '1', 'Reinstall',
                history=self._base.history),
            YumHistoryPackageState(
                'hole', 'x86_64', '0', '1', '1', 'Reinstalled',
                history=self._base.history))

        with self._base:
            self.assertRaises(PackagesNotAvailableError,
                              self._base.history_undo, 1)

    def test_history_undo_reinstall_notinstalled_obsoleted(self):
        """Test history_undo with a not installed obsoleted of a reinstall."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Reinstall',
                history=self._base.history),
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Reinstalled',
                history=self._base.history),
            YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Obsoleting',
                history=self._base.history),
            YumHistoryPackageState(
                'lotus', 'x86_64', '0', '3', '16', 'Obsoleted',
                history=self._base.history))

        with self._base:
            self._base.history_undo(1)

        transaction_it = iter(self._base.transaction)
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             REINSTALL, installed='pepper-20-0.x86_64',
                             erased='pepper-20-0.x86_64', obsoleted=()))
        self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_update(self):
        """Test history_undo with an update."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'tour', 'noarch', '0', '5', '0', 'Update',
                history=self._base.history),
            YumHistoryPackageState(
                'tour', 'noarch', '0', '4.6', '1', 'Updated',
                history=self._base.history),
            YumHistoryPackageState(
                'tour', 'noarch', '0', '5', '0', 'Obsoleting',
                history=self._base.history),
            YumHistoryPackageState(
                'lotus', 'x86_64', '0', '3', '16', 'Obsoleted',
                history=self._base.history))

        with self._base:
            self._base.history_undo(1)

        transaction_it = iter(self._base.transaction)
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             DOWNGRADE, installed='tour-4.6-1.noarch',
                             erased='tour-5-0.noarch'))
        self.assertEqual(next(transaction_it),
                         self._create_item_matcher(
                             INSTALL, installed='lotus-3-16.x86_64'))
        self.assertRaises(StopIteration, next, transaction_it)

    def test_history_undo_update_notavailable(self):
        """Test history_undo with an unavailable update."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'tour', 'noarch', '0', '5', '0', 'Update',
                history=self._base.history),
            YumHistoryPackageState(
                'tour', 'noarch', '0', '4.6', '2', 'Updated',
                history=self._base.history))

        with self._base:
            self.assertRaises(PackagesNotAvailableError,
                              self._base.history_undo, 1)

    def test_history_undo_update_notavailable_obsoleted(self):
        """Test history_undo with an unavailable obsoleted of an update."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'tour', 'noarch', '0', '5', '0', 'Update',
                history=self._base.history),
            YumHistoryPackageState(
                'tour', 'noarch', '0', '4.6', '1', 'Updated',
                history=self._base.history),
            YumHistoryPackageState(
                'tour', 'noarch', '0', '5', '0', 'Obsoleting',
                history=self._base.history),
            YumHistoryPackageState(
                'hole', 'x86_64', '0', '1', '1', 'Obsoleted',
                history=self._base.history))

        with self._base:
            self.assertRaises(PackagesNotAvailableError,
                              self._base.history_undo, 1)

    def test_history_undo_update_notinstalled(self):
        """Test history_undo with a not installed update."""
        self._base.history.old_data_pkgs['1'] = (
            YumHistoryPackageState(
                'lotus', 'x86_64', '0', '4', '0', 'Update',
                history=self._base.history),
            YumHistoryPackageState(
                'lotus', 'x86_64', '0', '3', '16', 'Updated',
                history=self._base.history))

        with self._base:
            self.assertRaises(PackagesNotInstalledError,
                              self._base.history_undo, 1)
