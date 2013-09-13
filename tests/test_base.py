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
import binascii
import dnf.const
import dnf.exceptions
import dnf.match_counter
import dnf.queries
import dnf.transaction
import dnf.yum.base
import dnf.yum.constants
import hawkey
import os
import rpm
import unittest

class BaseTest(support.TestCase):
    def test_instance(self):
        yumbase = dnf.yum.base.Base()

    def test_push_userinstalled(self):
        yumbase = support.MockYumBase()
        # setup:
        yumbase.conf.clean_requirements_on_remove = True
        pkg = dnf.queries.installed_by_name(yumbase.sack, "pepper")[0]
        goal = mock.Mock(spec=["userinstalled"])
        yumbase.yumdb.get_package(pkg).reason = "user"
        # test:
        yumbase._push_userinstalled(goal)
        goal.userinstalled.assert_called_with(pkg)

    def test_reset(self):
        base = support.MockYumBase('main')
        base.reset(sack=True, repos=False)
        self.assertIsNone(base._sack)
        self.assertLength(base.repos, 1)

    @mock.patch('dnf.rpmUtils.transaction.TransactionWrapper')
    def test_ts(self, mock_ts):
        base = dnf.yum.base.Base()
        self.assertEqual(base._ts, None)
        ts = base.ts
        # check the setup is correct
        ts.setFlags.call_args.assert_called_with(0)
        flags = ts.setProbFilter.call_args[0][0]
        self.assertTrue(flags & rpm.RPMPROB_FILTER_OLDPACKAGE)
        self.assertTrue(flags & rpm.RPMPROB_FILTER_REPLACEPKG)
        # check we can close the connection:
        del base.ts
        self.assertEqual(base._ts, None)
        ts.close.assert_called_once_with()

# test Base methods that need the sack
class MockYumBaseTest(unittest.TestCase):
    def setUp(self):
        self.yumbase = support.MockYumBase("main")

    def test_search_counted(self):
        counter = dnf.match_counter.MatchCounter()
        self.yumbase.search_counted(counter, 'summary', 'ation')
        self.assertEqual(len(counter), 2)
        haystacks = set()
        for pkg in counter:
            haystacks.update(counter.matched_haystacks(pkg))
        self.assertItemsEqual(haystacks, ["It's an invitation.",
                                          "Make a reservation."])

    def test_search_counted_glob(self):
        counter = dnf.match_counter.MatchCounter()
        self.yumbase.search_counted(counter, 'summary', '*invit*')
        self.assertEqual(len(counter), 1)

class BuildTransactionTest(support.TestCase):
    def test_build_transaction(self):
        base = support.MockYumBase("updates")
        base.update(pattern="pepper")
        self.assertTrue(base.build_transaction())
        base.ds_callback.assert_has_calls(mock.call.start())
        base.ds_callback.assert_has_calls(mock.call.pkg_added(mock.ANY, 'ud'))
        base.ds_callback.assert_has_calls(mock.call.pkg_added(mock.ANY, 'u'))
        self.assertLength(base.transaction, 1)

# verify transaction test helpers
HASH = "68e9ded8ea25137c964a638f12e9987c"
def mock_sack_fn():
    return (lambda yumbase: support.TestSack(support.repo_dir(), yumbase))

@property
def ret_pkgid(self):
    return self.name

class VerifyTransactionTest(unittest.TestCase):
    def setUp(self):
        self.yumbase = support.MockYumBase("main")
        self.yumbase._transaction = dnf.transaction.Transaction()

    @mock.patch('dnf.sack.build_sack', new_callable=mock_sack_fn)
    @mock.patch('dnf.package.Package.pkgid', ret_pkgid) # neutralize @property
    def test_verify_transaction(self, unused_build_sack):
        # we don't simulate the transaction itself here, just "install" what is
        # already there and "remove" what is not.
        new_pkg = dnf.queries.available_by_name(self.yumbase.sack, "pepper")[0]
        new_pkg.chksum = (hawkey.CHKSUM_MD5, binascii.unhexlify(HASH))
        new_pkg.repo = mock.Mock()
        removed_pkg = dnf.queries.available_by_name(
            self.yumbase.sack, "mrkite")[0]

        self.yumbase.transaction.add_install(new_pkg, [])
        self.yumbase.transaction.add_erase(removed_pkg)
        self.yumbase.verify_transaction(0)
        # mock is designed so this returns the exact same mock object it did
        # during the method call:
        yumdb_info = self.yumbase.yumdb.get_package(new_pkg)
        self.assertEqual(yumdb_info.from_repo, 'main')
        self.assertEqual(yumdb_info.reason, 'unknown')
        self.assertEqual(yumdb_info.releasever, 'Fedora69')
        self.assertEqual(yumdb_info.checksum_type, 'md5')
        self.assertEqual(yumdb_info.checksum_data, HASH)
        self.yumbase.yumdb.assertLength(2)

class InstallReasonTest(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockYumBase("main")

    def test_reason(self):
        self.yumbase.install("mrkite")
        self.yumbase.build_transaction()
        new_pkgs = self.yumbase._transaction.get_items(dnf.transaction.INSTALL)
        pkg_reasons = [(tsi.installed.name, tsi.reason) for tsi in new_pkgs]
        self.assertItemsEqual([("mrkite", "user"), ("trampoline", "dep")],
                              pkg_reasons)

class InstalledMatchingTest(support.ResultTestCase):
    def setUp(self):
        self.yumbase = support.MockYumBase("main")
        self.sack = self.yumbase.sack

    def test_query_matching(self):
        subj = dnf.queries.Subject("pepper")
        query = subj.get_best_query(self.sack)
        inst, avail = self.yumbase._query_matches_installed(query)
        self.assertItemsEqual(['pepper-20-0.x86_64'], map(str, inst))
        self.assertItemsEqual(['pepper-20-0.src'], map(str, avail))

    def test_selector_matching(self):
        subj = dnf.queries.Subject("pepper")
        sltr = subj.get_best_selector(self.sack)
        inst = self.yumbase._sltr_matches_installed(sltr)
        self.assertItemsEqual(['pepper-20-0.x86_64'], map(str, inst))

class CleanTest(unittest.TestCase):
    def test_clean_binary_cache(self):
        yumbase = support.MockYumBase("main")
        with mock.patch('os.access', return_value=True) as access,\
                mock.patch.object(yumbase, "_cleanFilelist") as _:
            yumbase.clean_binary_cache()
        self.assertEqual(len(access.call_args_list), 3)
        fname = access.call_args_list[0][0][0]
        assert(fname.startswith(dnf.const.TMPDIR))
        assert(fname.endswith(hawkey.SYSTEM_REPO_NAME + '.solv'))
        fname = access.call_args_list[1][0][0]
        assert(fname.endswith('main.solv'))
        fname = access.call_args_list[2][0][0]
        assert(fname.endswith('main-filenames.solvx'))

class CompsTest(support.TestCase):
    # Also see test_comps.py

    # prevent creating the gen/ directory:
    @mock.patch('dnf.yum.misc.repo_gen_decompress', lambda x, y: x)
    def test_read_comps(self):
        yumbase = support.MockYumBase("main")
        yumbase.repos['main'].metadata = mock.Mock(comps_fn=support.COMPS_PATH)
        yumbase.read_comps()
        groups = yumbase.comps.groups
        self.assertLength(groups, 2)

    def test_read_comps_disabled(self):
        yumbase = support.MockYumBase("main")
        yumbase.repos['main'].enablegroups = False
        self.assertRaises(dnf.exceptions.CompsError, yumbase.read_comps)
