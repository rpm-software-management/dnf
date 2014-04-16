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
from tests.support import PycompTestCase
from tests.support import mock

import dnf.history
import dnf.yum.history

class TestedHistory(dnf.yum.history.YumHistory):
    @mock.patch("os.path.exists", return_value=True)
    def __init__(self, unused_exists):
        self._db_date = "1962-07-12"
        super(TestedHistory, self).__init__(support.NONEXISTENT_FILE, mock.Mock())

    def _create_db_file(self):
        return None

class History(PycompTestCase):
    def setUp(self):
        self.base = support.MockBase("main")
        self.sack = self.base.sack
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

class HistoryWrapperTest(support.TestCase):
    """Unit tests of dnf.history._HistoryWrapper."""

    def _create_wrapper(self, yum_history):
        """Create new instance of _HistoryWrapper."""
        wrapper = dnf.history.open_history(yum_history)
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

    def test_transaction_nevra_ops_notransaction(self):
        """Test transaction_nevra_ops without any transaction."""
        with self._create_wrapper(support.HistoryStub()) as history:
            self.assertRaises(ValueError, history.transaction_nevra_ops, 0)

    def test_transaction_nevra_ops_update(self):
        """Test transaction_nevra_ops with a downgrade operation."""
        yum_history = support.HistoryStub()
        yum_history.old_data_pkgs['1'] = (
            dnf.yum.history.YumHistoryPackageState(
                'tour', 'noarch', '0', '4.8', '1', 'Update',
                history=yum_history),
            dnf.yum.history.YumHistoryPackageState(
                'tour', 'noarch', '0', '4.6', '1', 'Updated',
                history=yum_history),
            dnf.yum.history.YumHistoryPackageState(
                'tour', 'noarch', '0', '4.8', '1', 'Obsoleting',
                history=yum_history),
            dnf.yum.history.YumHistoryPackageState(
                'lotus', 'x86_64', '0', '3', '16', 'Obsoleted',
                history=yum_history))
        expected_ops = dnf.history.NEVRAOperations()
        expected_ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch', ('lotus-0:3-16.x86_64',))

        with self._create_wrapper(yum_history) as history:
            result_ops = history.transaction_nevra_ops(1)

        self.assertItemsEqual(result_ops, expected_ops)

class NEVRAOperationsTest(support.TestCase):
    """Unit tests of dnf.history.NEVRAOperations."""

    def test_add_erase_installed(self):
        """Test add with an erasure of NEVRA which was installed before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Install', 'tour-0:4.6-1.noarch', obsoleted_nevras=('lotus-0:3-16.x86_64',))
        ops.add('Erase', 'tour-0:4.6-1.noarch')

        self.assertItemsEqual(
            ops,
            (('Erase', 'lotus-0:3-16.x86_64', None, set()),))

    def test_add_erase_removed(self):
        """Test add with an erasure of NEVRA which was removed before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Erase', 'tour-0:4.6-1.noarch')

        self.assertRaises(
            ValueError,
            ops.add, 'Erase', 'tour-0:4.6-1.noarch')

    def test_add_install_installed(self):
        """Test add with two installs of the same NEVRA."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Install', 'tour-0:4.6-1.noarch')

        self.assertRaises(
            ValueError,
            ops.add, 'Install', 'tour-0:4.6-1.noarch')

    def test_add_install_removed(self):
        """Test add with an install of NEVRA which was removed before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Erase', 'tour-0:4.6-1.noarch')
        ops.add('Install', 'tour-0:4.6-1.noarch')

        self.assertItemsEqual(
            ops,
            (('Reinstall', 'tour-0:4.6-1.noarch', 'tour-0:4.6-1.noarch', set()),))

    def test_add_obsoleted_installed(self):
        """Test add with an obsoleted NEVRA which was installed before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Install', 'lotus-0:3-16.x86_64')
        ops.add('Install', 'tour-0:4.6-1.noarch', obsoleted_nevras=('lotus-0:3-16.x86_64',))

        self.assertItemsEqual(
            ops,
            (('Install', 'tour-0:4.6-1.noarch', None, set()),))

    def test_add_obsoleted_obsoleted(self):
        """Test add with an obsoleted NEVRA which was obsoleted before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Install', 'tour-0:4.6-1.noarch', obsoleted_nevras=('lotus-0:3-16.x86_64', 'mrkite-0:2-0.x86_64'))
        ops.add('Install', 'pepper-0:20-0.x86_64', obsoleted_nevras=('lotus-0:3-16.x86_64', 'librita-0:1-1.x86_64'))

        self.assertItemsEqual(
            ops,
            (('Install', 'tour-0:4.6-1.noarch', None, {'lotus-0:3-16.x86_64', 'mrkite-0:2-0.x86_64'}),
             ('Install', 'pepper-0:20-0.x86_64', None, {'lotus-0:3-16.x86_64', 'librita-0:1-1.x86_64'})))

    def test_add_obsoleted_removed(self):
        """Test add with an obsoleted NEVRA which was removed before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Erase', 'lotus-0:3-16.x86_64')

        self.assertRaises(
            ValueError,
            ops.add, 'Install', 'tour-0:4.6-1.noarch', obsoleted_nevras=('lotus-0:3-16.x86_64',))

    def test_add_reinstall_installed(self):
        """Test add with a reinstall of NEVRA which was installed before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Install', 'tour-0:4.6-1.noarch')
        ops.add('Reinstall', 'tour-0:4.6-1.noarch', 'tour-0:4.6-1.noarch')

        self.assertItemsEqual(
            ops,
            (('Install', 'tour-0:4.6-1.noarch', None, set()),))

    def test_add_replace_installed(self):
        """Test add with a replacing NEVRA which was installed before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Install', 'tour-0:4.8-1.noarch')

        self.assertRaises(
            ValueError,
            ops.add, 'Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

    def test_add_replace_opposite(self):
        """Test add with a replacement which was done before, but swapped."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Downgrade', 'tour-0:4.6-1.noarch', 'tour-0:4.8-1.noarch')
        ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        self.assertItemsEqual(
            ops,
            (('Reinstall', 'tour-0:4.8-1.noarch', 'tour-0:4.8-1.noarch', set()),))

    def test_add_replace_opposite_manual(self):
        """Test add with a manual replacement which was done before, but swapped."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Erase', 'tour-0:4.8-1.noarch')
        ops.add('Install', 'tour-0:4.6-1.noarch')
        ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        self.assertItemsEqual(
            ops,
            (('Reinstall', 'tour-0:4.8-1.noarch', 'tour-0:4.8-1.noarch', set()),))

    def test_add_replace_removed(self):
        """Test add with a replacing NEVRA which was removed before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Erase', 'tour-0:4.8-1.noarch')
        ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        self.assertItemsEqual(
            ops,
            (('Reinstall', 'tour-0:4.8-1.noarch', 'tour-0:4.8-1.noarch', set()),
             ('Erase', 'tour-0:4.6-1.noarch', None, set())))

    def test_add_replaced_opposite(self):
        """Test add with a replaced NEVRA which replaced a NEVRA before in the opposite direction."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Downgrade', 'tour-0:4.6-1.noarch', 'tour-0:4.9-1.noarch')
        ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        self.assertItemsEqual(
            ops,
            (('Erase', 'tour-0:4.9-1.noarch', None, set()),
             ('Install', 'tour-0:4.8-1.noarch', None, set())))

    def test_add_replaced_removed(self):
        """Test add with a replaced NEVRA which was removed before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Erase', 'tour-0:4.6-1.noarch')

        self.assertRaises(
            ValueError,
            ops.add, 'Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

    def test_add_replaced_reinstall(self):
        """Test add with a replaced NEVRA which was reinstalled before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Reinstall', 'tour-0:4.6-1.noarch', 'tour-0:4.6-1.noarch')
        ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        self.assertItemsEqual(
            ops,
            (('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch', set()),))

    def test_add_replaced_replacement(self):
        """Test add with a replaced NEVRA which replaced a NEVRA before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')
        ops.add('Update', 'tour-0:4.9-1.noarch', 'tour-0:4.8-1.noarch')

        self.assertItemsEqual(
            ops,
            (('Update', 'tour-0:4.9-1.noarch', 'tour-0:4.6-1.noarch', set()),))

    def test_addition(self):
        """Test addition of two instances."""
        left_ops = dnf.history.NEVRAOperations()
        left_ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')
        right_ops = dnf.history.NEVRAOperations()
        right_ops.add('Update', 'tour-0:4.9-1.noarch', 'tour-0:4.8-1.noarch')
        expected_ops = dnf.history.NEVRAOperations()
        expected_ops.add('Update', 'tour-0:4.9-1.noarch', 'tour-0:4.6-1.noarch')

        result_ops = left_ops + right_ops

        self.assertEqual(result_ops, expected_ops)

    def test_addition_inplace(self):
        """Test in-place addition of two instances."""
        left_ops = dnf.history.NEVRAOperations()
        left_ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')
        right_ops = dnf.history.NEVRAOperations()
        right_ops.add('Update', 'tour-0:4.9-1.noarch', 'tour-0:4.8-1.noarch')
        expected_ops = dnf.history.NEVRAOperations()
        expected_ops.add('Update', 'tour-0:4.9-1.noarch', 'tour-0:4.6-1.noarch')

        left_ops += right_ops

        self.assertEqual(left_ops, expected_ops)

    def test_equality(self):
        """Test equality of two equal instances."""
        left_ops = dnf.history.NEVRAOperations()
        left_ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')
        right_ops = dnf.history.NEVRAOperations()
        right_ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        is_equal = left_ops == right_ops

        self.assertTrue(is_equal)

    def test_equality_differentcontent(self):
        """Test equality of two instances with different contents."""
        left_ops = dnf.history.NEVRAOperations()
        left_ops.add('Downgrade', 'tour-0:4.6-1.noarch', 'tour-0:4.8-1.noarch')
        right_ops = dnf.history.NEVRAOperations()
        right_ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        is_equal = left_ops == right_ops

        self.assertFalse(is_equal)

    def test_equality_differentlength(self):
        """Test equality of two instances with different lengths."""
        left_ops = dnf.history.NEVRAOperations()
        right_ops = dnf.history.NEVRAOperations()
        right_ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        is_equal = left_ops == right_ops

        self.assertFalse(is_equal)

    def test_equality_differenttype(self):
        """Test equality of an instance and an object of a different type."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        is_equal = ops == 'tour-0:4.8-1.noarch'

        self.assertFalse(is_equal)

    def test_equality_identity(self):
        """Test equality of the same instance."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        is_equal = ops == ops

        self.assertTrue(is_equal)

    def test_inequality(self):
        """Test inequality of two different instances."""
        left_ops = dnf.history.NEVRAOperations()
        left_ops.add('Downgrade', 'tour-0:4.6-1.noarch', 'tour-0:4.8-1.noarch')
        right_ops = dnf.history.NEVRAOperations()
        right_ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        is_inequal = left_ops != right_ops

        self.assertTrue(is_inequal)

    def test_inequality_equal(self):
        """Test inequality of two equal instances."""
        left_ops = dnf.history.NEVRAOperations()
        left_ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')
        right_ops = dnf.history.NEVRAOperations()
        right_ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        is_inequal = left_ops != right_ops

        self.assertFalse(is_inequal)

    def test_iterator(self):
        """Test iterator of an instance."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        iterator = iter(ops)

        self.assertEqual(
            next(iterator),
            ('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch', set()))
        self.assertRaises(StopIteration, next, iterator)

    def test_length(self):
        """Test length of an instance."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        length = len(ops)

        self.assertEqual(length, 1)

    def test_membership(self):
        """Test membership of a contained operation."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Update', 'tour-0:4.9-1.noarch', 'tour-0:4.8-1.noarch')

        is_in = ('Update', 'tour-0:4.9-1.noarch', 'tour-0:4.8-1.noarch', ()) in ops

        self.assertTrue(is_in)

    def test_membership_differentnevra(self):
        """Test membership of an operation with different (replacing) NEVRA."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Update', 'tour-0:4.9-1.noarch', 'tour-0:4.8-1.noarch')

        is_in = ('Update', 'pepper-0:20-0.x86_64', 'tour-0:4.8-1.noarch', ()) in ops

        self.assertFalse(is_in)

    def test_membership_differentobsoleted(self):
        """Test membership of an operation with different obsoleted NEVRAs."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Update', 'tour-0:4.9-1.noarch', 'tour-0:4.8-1.noarch')

        is_in = ('Update', 'tour-0:4.9-1.noarch', 'tour-0:4.8-1.noarch', ('pepper-0:20-0.x86_64',)) in ops

        self.assertFalse(is_in)

    def test_membership_differentreplaced(self):
        """Test membership of an operation with different replaced NEVRA."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Update', 'tour-0:4.9-1.noarch', 'tour-0:4.8-1.noarch')

        is_in = ('Update', 'tour-0:4.9-1.noarch', 'pepper-0:20-0.x86_64', ()) in ops

        self.assertFalse(is_in)

    def test_membership_differentstate(self):
        """Test membership of an operation with different state."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Update', 'tour-0:4.9-1.noarch', 'tour-0:4.8-1.noarch')

        is_in = ('Downgrade', 'tour-0:4.9-1.noarch', 'tour-0:4.8-1.noarch', ()) in ops

        self.assertFalse(is_in)

    def test_membership_differenttype(self):
        """Test membership of an object of a different type."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Update', 'tour-0:4.9-1.noarch', 'tour-0:4.8-1.noarch')

        is_in = 'tour-0:4.9-1.noarch' in ops

        self.assertFalse(is_in)
