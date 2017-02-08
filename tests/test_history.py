# Copyright (C) 2012-2016 Red Hat, Inc.
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
from tests.support import TestCase
from tests.support import mock

import dnf.history
import dnf.yum.history


class TestedHistory(dnf.yum.history.SwdbInterface):
    @mock.patch("os.path.exists", return_value=True)
    def __init__(self, unused_exists):
        self._db_date = "1962-07-12"
        super(TestedHistory, self).__init__(support.NONEXISTENT_FILE, mock.Mock())

    def _create_db_file(self):
        return None


class History(TestCase):
    def setUp(self):
        self.base = support.MockBase("main")
        self.sack = self.base.sack
        self.history = TestedHistory()


class NEVRAOperationsTest(support.TestCase):
    """Unit tests of dnf.history.NEVRAOperations."""

    def test_add_erase_installed(self):
        """Test add with an erasure of NEVRA which was installed before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Install', 'tour-0:4.6-1.noarch', obsoleted_nevras=('lotus-0:3-16.x86_64',))
        ops.add('Erase', 'tour-0:4.6-1.noarch')

        self.assertCountEqual(
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

        self.assertCountEqual(
            ops,
            (('Reinstall', 'tour-0:4.6-1.noarch', 'tour-0:4.6-1.noarch', set()),))

    def test_add_obsoleted_installed(self):
        """Test add with an obsoleted NEVRA which was installed before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Install', 'lotus-0:3-16.x86_64')
        ops.add('Install', 'tour-0:4.6-1.noarch', obsoleted_nevras=('lotus-0:3-16.x86_64',))

        self.assertCountEqual(
            ops,
            (('Install', 'tour-0:4.6-1.noarch', None, set()),))

    def test_add_obsoleted_obsoleted(self):
        """Test add with an obsoleted NEVRA which was obsoleted before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Install', 'tour-0:4.6-1.noarch', obsoleted_nevras=('lotus-0:3-16.x86_64', 'mrkite-0:2-0.x86_64'))
        ops.add('Install', 'pepper-0:20-0.x86_64', obsoleted_nevras=('lotus-0:3-16.x86_64', 'librita-0:1-1.x86_64'))

        self.assertCountEqual(
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

        self.assertCountEqual(
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

        self.assertCountEqual(
            ops,
            (('Reinstall', 'tour-0:4.8-1.noarch', 'tour-0:4.8-1.noarch', set()),))

    def test_add_replace_opposite_manual(self):
        """Test add with a manual replacement which was done before, but swapped."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Erase', 'tour-0:4.8-1.noarch')
        ops.add('Install', 'tour-0:4.6-1.noarch')
        ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        self.assertCountEqual(
            ops,
            (('Reinstall', 'tour-0:4.8-1.noarch', 'tour-0:4.8-1.noarch', set()),))

    def test_add_replace_removed(self):
        """Test add with a replacing NEVRA which was removed before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Erase', 'tour-0:4.8-1.noarch')
        ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        self.assertCountEqual(
            ops,
            (('Reinstall', 'tour-0:4.8-1.noarch', 'tour-0:4.8-1.noarch', set()),
             ('Erase', 'tour-0:4.6-1.noarch', None, set())))

    def test_add_replaced_opposite(self):
        """Test add with a replaced NEVRA which replaced a NEVRA before in the opposite direction."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Downgrade', 'tour-0:4.6-1.noarch', 'tour-0:4.9-1.noarch')
        ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')

        self.assertCountEqual(
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

        self.assertCountEqual(
            ops,
            (('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch', set()),))

    def test_add_replaced_replacement(self):
        """Test add with a replaced NEVRA which replaced a NEVRA before."""
        ops = dnf.history.NEVRAOperations()
        ops.add('Update', 'tour-0:4.8-1.noarch', 'tour-0:4.6-1.noarch')
        ops.add('Update', 'tour-0:4.9-1.noarch', 'tour-0:4.8-1.noarch')

        self.assertCountEqual(
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


class TransactionConverterTest(TestCase):
    """Unit tests of dnf.history.TransactionConverter."""

    def assert_transaction_equal(self, actual, expected):
        """Assert that two transactions are equal."""
        self.assertCountEqual(self.transaction2tuples(actual),
                              self.transaction2tuples(expected))

    def test_find_available_na(self):
        """Test finding with an unavailable NEVRA."""
        sack = support.mock_sack('main')
        converter = dnf.history.TransactionConverter(sack)
        with self.assertRaises(dnf.exceptions.PackagesNotAvailableError) as ctx:
            converter._find_available('none-1-0.noarch')

        self.assertEqual(ctx.exception.pkg_spec, 'none-1-0.noarch')

    def test_find_installed_ni(self):
        """Test finding with an unistalled NEVRA."""
        sack = support.mock_sack('main')
        converter = dnf.history.TransactionConverter(sack)
        with self.assertRaises(dnf.exceptions.PackagesNotInstalledError) as ctx:
            converter._find_installed('none-1-0.noarch')

        self.assertEqual(ctx.exception.pkg_spec, 'none-1-0.noarch')

    def test_convert_downgrade(self):
        """Test conversion with a downgrade."""
        operations = dnf.history.NEVRAOperations()
        operations.add('Downgrade', 'tour-4.6-1.noarch', 'tour-5-0.noarch',
                       ['hole-1-1.x86_64'])

        sack = support.mock_sack('main')
        converter = dnf.history.TransactionConverter(sack)
        actual = converter.convert(operations)

        expected = dnf.transaction.Transaction()
        expected.add_downgrade(
            next(iter(sack.query().available()._nevra('tour-4.6-1.noarch'))),
            next(iter(sack.query().installed()._nevra('tour-5-0.noarch'))),
            [next(iter(sack.query().installed()._nevra('hole-1-1.x86_64')))])
        self.assert_transaction_equal(actual, expected)

    def test_convert_erase(self):
        """Test conversion with an erasure."""
        operations = dnf.history.NEVRAOperations()
        operations.add('Erase', 'pepper-20-0.x86_64')

        sack = support.mock_sack()
        converter = dnf.history.TransactionConverter(sack)
        actual = converter.convert(operations)

        expected = dnf.transaction.Transaction()
        expected.add_erase(
            next(iter(sack.query().installed()._nevra('pepper-20-0.x86_64'))))
        self.assert_transaction_equal(actual, expected)

    def test_convert_install(self):
        """Test conversion with an installation."""
        operations = dnf.history.NEVRAOperations()
        operations.add('Install', 'lotus-3-16.x86_64',
                       obsoleted_nevras=['hole-1-1.x86_64'])

        sack = support.mock_sack('main')
        converter = dnf.history.TransactionConverter(sack)
        actual = converter.convert(operations, 'reason')

        expected = dnf.transaction.Transaction()
        expected.add_install(
            next(iter(sack.query().available()._nevra('lotus-3-16.x86_64'))),
            [next(iter(sack.query().installed()._nevra('hole-1-1.x86_64')))],
            'reason')
        self.assert_transaction_equal(actual, expected)

    def test_convert_reinstall(self):
        """Test conversion with a reinstallation."""
        operations = dnf.history.NEVRAOperations()
        operations.add('Reinstall', 'pepper-20-0.x86_64', 'pepper-20-0.x86_64',
                       ['hole-1-1.x86_64'])

        sack = support.mock_sack('main')
        converter = dnf.history.TransactionConverter(sack)
        actual = converter.convert(operations)

        expected = dnf.transaction.Transaction()
        expected.add_reinstall(
            next(iter(sack.query().available()._nevra('pepper-20-0.x86_64'))),
            next(iter(sack.query().installed()._nevra('pepper-20-0.x86_64'))),
            [next(iter(sack.query().installed()._nevra('hole-1-1.x86_64')))])
        self.assert_transaction_equal(actual, expected)

    def test_upgrade(self):
        """Test repeating with an upgrade."""
        operations = dnf.history.NEVRAOperations()
        operations.add('Update', 'pepper-20-1.x86_64', 'pepper-20-0.x86_64',
                       ['hole-1-1.x86_64'])

        sack = support.mock_sack('updates')
        converter = dnf.history.TransactionConverter(sack)
        actual = converter.convert(operations)

        expected = dnf.transaction.Transaction()
        expected.add_upgrade(
            next(iter(sack.query().available()._nevra('pepper-20-1.x86_64'))),
            next(iter(sack.query().installed()._nevra('pepper-20-0.x86_64'))),
            [next(iter(sack.query().installed()._nevra('hole-1-1.x86_64')))])
        self.assert_transaction_equal(actual, expected)

    @staticmethod
    def transaction2tuples(transaction):
        """Convert a transaction to the iterable of tuples."""
        for item in transaction:
            yield (item.op_type, item.installed, item.erased, item.obsoleted,
                   item.reason)

class ComparisonTests(TestCase):

    def test_transaction(self):
        a = dnf.yum.history.YumHistoryTransaction(None, [1, 5, 0, 5, 0, 0, 0])
        b = dnf.yum.history.YumHistoryTransaction(None, [9, 5, 0, 5, 0, 0, 0])
        self.assertGreater(a, b)
        self.assertLess(b, a)

        a2 = dnf.yum.history.YumHistoryTransaction(None, [0, 1, 0, 0, 0, 0, 0])
        b2 = dnf.yum.history.YumHistoryTransaction(None, [0, 9, 0, 0, 0, 0, 0])
        self.assertGreater(a2, b2)
        self.assertLess(b2, a2)
