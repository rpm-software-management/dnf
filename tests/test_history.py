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
import dnf.history
import dnf.yum.history
import hawkey
import unittest
from tests.support import PycompTestCase

class TestedHistory(dnf.yum.history.YumHistory):
    @mock.patch("os.path.exists", return_value=True)
    def __init__(self, unused_exists):
        self._db_date = "1962-07-12"
        super(TestedHistory, self).__init__(support.NONEXISTENT_FILE, mock.Mock())

    def _create_db_file(self):
        return None

class History(PycompTestCase):
    def setUp(self):
        self.yumbase = support.MockBase("main")
        self.sack = self.yumbase.sack
        self.history = TestedHistory()

    def pkgtup2pid_test(self):
        """ Check pkg2pid() correctly delegates to _*2pid()s. """
        hpkg = dnf.yum.history.YumHistoryPackage("n", "a", "e", "v", "r")
        with mock.patch.object(self.history, "_hpkg2pid") as hpkg2pid:
            self.history.pkg2pid(hpkg)
            hpkg2pid.assert_called_with(hpkg, True)

        ipkg = self.sack.query().installed().filter(name="pepper")[0]
        with mock.patch.object(self.history, "_ipkg2pid") as ipkg2pid:
            self.history.pkg2pid(ipkg)
            ipkg2pid.assert_called_with(ipkg, True)

        apkg = self.sack.query().available().filter(name="lotus")[0]
        with mock.patch.object(self.history, "_apkg2pid") as apkg2pid:
            self.history.pkg2pid(apkg)
            apkg2pid.assert_called_with(apkg, True)

class HistoryWrapperTest(unittest.TestCase):
    """Unit tests of dnf.history._HistoryWrapper."""

    def _create_wrapper(self, yum_history):
        """Create new instance of _HistoryWrapper."""
        wrapper = dnf.history.open_history(yum_history, support.mock_sack())
        assert isinstance(wrapper, dnf.history._HistoryWrapper)
        return wrapper

    def test_context_manager(self):
        """Test whether _HistoryWrapper can be used as a context manager."""
        yum_history = mock.create_autospec(dnf.yum.history.YumHistory)
        history = self._create_wrapper(yum_history)

        with history as instance:
            pass

        self.assertIs(instance, history)
        self.assertEqual(yum_history.close.mock_calls, [mock.call()])

    def test_close(self):
        """Test close."""
        yum_history = mock.create_autospec(dnf.yum.history.YumHistory)
        history = self._create_wrapper(yum_history)

        history.close()

        self.assertEqual(yum_history.close.mock_calls, [mock.call()])

    def test_has_transaction_absent(self):
        """Test has_transaction without any transaction."""
        with self._create_wrapper(support.HistoryStub()) as history:
            present = history.has_transaction(1)

        self.assertFalse(present)

    def test_has_transaction_present(self):
        """Test has_transaction with a transaction present."""
        yum_history = support.HistoryStub()
        yum_history.old_data_pkgs['1'] = (
            dnf.yum.history.YumHistoryPackageState(
                'lotus', 'x86_64', '0', '3', '16', 'Erase',
                history=yum_history),)

        with self._create_wrapper(yum_history) as history:
            present = history.has_transaction(1)

        self.assertTrue(present)

    def test_last_transaction_id(self):
        """Test last_transaction_id with some transactions."""
        yum_history = support.HistoryStub()
        yum_history.old_data_pkgs['1'] = (
            dnf.yum.history.YumHistoryPackageState(
                'lotus', 'x86_64', '0', '3', '16', 'Erase',
                history=yum_history),)
        yum_history.old_data_pkgs['2'] = (
            dnf.yum.history.YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Install',
                history=yum_history),)

        with self._create_wrapper(yum_history) as history:
            id_ = history.last_transaction_id()

        self.assertEqual(id_, 2)

    def test_last_transaction_id_notransaction(self):
        """Test last_transaction_id without any transaction."""
        with self._create_wrapper(support.HistoryStub()) as history:
            id_ = history.last_transaction_id()

        self.assertIsNone(id_)

    def test_transaction_items_ops_all(self):
        """Test transaction_items_ops with all states."""
        yum_history = support.HistoryStub()
        yum_history.old_data_pkgs['1'] = (
            dnf.yum.history.YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Install',
                history=yum_history),
            dnf.yum.history.YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Obsoleting',
                history=yum_history),
            dnf.yum.history.YumHistoryPackageState(
                'lotus', 'x86_64', '0', '3', '16', 'Obsoleted',
                history=yum_history))

        with self._create_wrapper(yum_history) as history:
            items_ops = history.transaction_items_ops(1)

        item_ops = next(items_ops)
        self.assertRaises(StopIteration, next, items_ops)
        self.assertEqual(next(item_ops),
                         ('pepper-0:20-0.x86_64', 'Install'))
        self.assertEqual(next(item_ops),
                         ('pepper-0:20-0.x86_64', 'Obsoleting'))
        self.assertEqual(next(item_ops),
                         ('lotus-0:3-16.x86_64', 'Obsoleted'))
        self.assertRaises(StopIteration, next, item_ops)

    def test_transaction_items_ops_badfirst(self):
        """Test transaction_items_ops with an invalid first state."""
        yum_history = support.HistoryStub()
        yum_history.old_data_pkgs['1'] = (
            dnf.yum.history.YumHistoryPackageState(
                'pepper', 'x86_64', '0', '20', '0', 'Obsoleted',
                history=yum_history),)

        with self._create_wrapper(yum_history) as history:
            self.assertRaises(ValueError, history.transaction_items_ops, 1)

    def test_transaction_items_ops_notransaction(self):
        """Test transaction_items_ops without any transaction."""
        with self._create_wrapper(support.HistoryStub()) as history:
            self.assertRaises(ValueError, history.transaction_items_ops, 0)
