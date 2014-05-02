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
from tests.support import PycompTestCase

import binascii
import dnf
import dnf.const
import dnf.exceptions
import dnf.match_counter
import dnf.package
import dnf.subject
import dnf.transaction
import hawkey
import os
import rpm

class BaseTest(support.TestCase):
    def test_instance(self):
        base = dnf.Base()

    def test_push_userinstalled(self):
        base = support.MockBase()
        # setup:
        base.conf.clean_requirements_on_remove = True
        goal = mock.Mock(spec=["userinstalled"])
        for pkg in base.sack.query().installed():
            base.yumdb.get_package(pkg).reason = 'dep'
        pkg1 = base.sack.query().installed().filter(name="pepper")[0]
        base.yumdb.get_package(pkg1).reason = "user"
        pkg2 = base.sack.query().installed().filter(name="hole")[0]
        base.yumdb.get_package(pkg2).reason = "unknown"

        # test:
        base.push_userinstalled(goal)
        calls = [c[0][0].name for c in goal.userinstalled.call_args_list]
        self.assertItemsEqual(calls, ('hole', 'pepper'))

    def test_reset(self):
        base = support.MockBase('main')
        base.reset(sack=True, repos=False)
        self.assertIsNone(base._sack)
        self.assertLength(base.repos, 1)

    @mock.patch('dnf.rpmUtils.transaction.TransactionWrapper')
    def test_ts(self, mock_ts):
        base = dnf.Base()
        self.assertEqual(base._ts, None)
        ts = base.ts
        # check the setup is correct
        ts.setFlags.call_args.assert_called_with(0)
        flags = ts.setProbFilter.call_args[0][0]
        self.assertFalse(flags & rpm.RPMPROB_FILTER_OLDPACKAGE)
        self.assertFalse(flags & rpm.RPMPROB_FILTER_REPLACEPKG)
        # check file conflicts are reported:
        self.assertFalse(flags & rpm.RPMPROB_FILTER_REPLACENEWFILES)
        # check we can close the connection
        del base.ts
        self.assertEqual(base._ts, None)
        ts.close.assert_called_once_with()

    def test_iter_userinstalled(self):
        """Test iter_userinstalled with a package installed by the user."""
        base = dnf.Base()
        base._sack = support.mock_sack('main')
        base._yumdb = support.MockYumDB()
        pkg, = base.sack.query().installed().filter(name='pepper')
        base.yumdb.get_package(pkg).get = {'reason': 'user', 'from_repo': 'main'}.get

        iterator = base.iter_userinstalled()

        self.assertEqual(next(iterator), pkg)
        self.assertRaises(StopIteration, next, iterator)

    def test_iter_userinstalled_badfromrepo(self):
        """Test iter_userinstalled with a package installed from a bad repository."""
        base = dnf.Base()
        base._sack = support.mock_sack('main')
        base._yumdb = support.MockYumDB()

        pkg, = base.sack.query().installed().filter(name='pepper')
        base.yumdb.get_package(pkg).get = {'reason': 'user', 'from_repo': 'anakonda'}.get

        iterator = base.iter_userinstalled()

        self.assertRaises(StopIteration, next, iterator)

    def test_iter_userinstalled_badreason(self):
        """Test iter_userinstalled with a package installed for a wrong reason."""
        base = dnf.Base()
        base._sack = support.mock_sack('main')
        base._yumdb = support.MockYumDB()

        pkg, = base.sack.query().installed().filter(name='pepper')
        base.yumdb.get_package(pkg).get = {'reason': 'dep', 'from_repo': 'main'}.get

        iterator = base.iter_userinstalled()

        self.assertRaises(StopIteration, next, iterator)

    def test_translate_comps_pkg_types(self):
        base = dnf.Base()
        num = base._translate_comps_pkg_types(('mandatory', 'optional'))
        self.assertEqual(num, 12)

class MockBaseTest(PycompTestCase):
    """Test the Base methods that need a Sack."""

    def setUp(self):
        self.base = support.MockBase("main")

    def test_add_remote_rpm(self):
        pkg = self.base.add_remote_rpm(support.TOUR_50_PKG_PATH)
        self.assertIsInstance(pkg, dnf.package.Package)
        self.assertEqual(pkg.name, 'tour')

    def test_search_counted(self):
        counter = dnf.match_counter.MatchCounter()
        self.base.search_counted(counter, 'summary', 'ation')
        self.assertEqual(len(counter), 2)
        haystacks = set()
        for pkg in counter:
            haystacks.update(counter.matched_haystacks(pkg))
        self.assertItemsEqual(haystacks, ["It's an invitation.",
                                          "Make a reservation."])

    def test_search_counted_glob(self):
        counter = dnf.match_counter.MatchCounter()
        self.base.search_counted(counter, 'summary', '*invit*')
        self.assertEqual(len(counter), 1)

class BuildTransactionTest(support.TestCase):
    def test_resolve(self):
        base = support.MockBase("updates")
        base.upgrade("pepper")
        self.assertTrue(base.resolve())
        base.ds_callback.assert_has_calls(mock.call.start())
        base.ds_callback.assert_has_calls(mock.call.pkg_added(mock.ANY, 'ud'))
        base.ds_callback.assert_has_calls(mock.call.pkg_added(mock.ANY, 'u'))
        self.assertLength(base.transaction, 1)

# verify transaction test helpers
HASH = "68e9ded8ea25137c964a638f12e9987c"
def mock_sack_fn():
    return (lambda base: support.TestSack(support.repo_dir(), base))

@property
def ret_pkgid(self):
    return self.name

class VerifyTransactionTest(PycompTestCase):
    def setUp(self):
        self.base = support.MockBase("main")
        self.base._transaction = dnf.transaction.Transaction()

    @mock.patch('dnf.sack.build_sack', new_callable=mock_sack_fn)
    @mock.patch('dnf.package.Package.pkgid', ret_pkgid) # neutralize @property
    def test_verify_transaction(self, unused_build_sack):
        # we don't simulate the transaction itself here, just "install" what is
        # already there and "remove" what is not.
        new_pkg = self.base.sack.query().available().filter(name="pepper")[1]
        new_pkg.chksum = (hawkey.CHKSUM_MD5, binascii.unhexlify(HASH))
        new_pkg.repo = mock.Mock()
        removed_pkg = self.base.sack.query().available().filter(
            name="mrkite")[0]

        self.base.transaction.add_install(new_pkg, [])
        self.base.transaction.add_erase(removed_pkg)
        self.base.verify_transaction(0)
        # mock is designed so this returns the exact same mock object it did
        # during the method call:
        yumdb_info = self.base.yumdb.get_package(new_pkg)
        self.assertEqual(yumdb_info.from_repo, 'main')
        self.assertEqual(yumdb_info.reason, 'unknown')
        self.assertEqual(yumdb_info.releasever, 'Fedora69')
        self.assertEqual(yumdb_info.checksum_type, 'md5')
        self.assertEqual(yumdb_info.checksum_data, HASH)
        self.base.yumdb.assertLength(2)

class InstallReasonTest(support.ResultTestCase):
    def setUp(self):
        self.base = support.MockBase("main")

    def test_reason(self):
        self.base.install("mrkite")
        self.base.resolve()
        new_pkgs = self.base._transaction.get_items(dnf.transaction.INSTALL)
        pkg_reasons = [(tsi.installed.name, tsi.reason) for tsi in new_pkgs]
        self.assertItemsEqual([("mrkite", "user"), ("trampoline", "dep")],
                              pkg_reasons)

class InstalledMatchingTest(support.ResultTestCase):
    def setUp(self):
        self.base = support.MockBase("main")
        self.sack = self.base.sack

    def test_query_matching(self):
        subj = dnf.subject.Subject("pepper")
        query = subj.get_best_query(self.sack)
        inst, avail = self.base._query_matches_installed(query)
        self.assertItemsEqual(['pepper-20-0.x86_64'], map(str, inst))
        self.assertItemsEqual(['pepper-20-0.src'], map(str, avail))

    def test_selector_matching(self):
        subj = dnf.subject.Subject("pepper")
        sltr = subj.get_best_selector(self.sack)
        inst = self.base._sltr_matches_installed(sltr)
        self.assertItemsEqual(['pepper-20-0.x86_64'], map(str, inst))

class CleanTest(PycompTestCase):
    def test_clean_binary_cache(self):
        base = support.MockBase("main")
        with mock.patch('os.access', return_value=True) as access,\
                mock.patch.object(base, "_cleanFilelist") as _:
            base.clean_binary_cache()
        self.assertEqual(len(access.call_args_list), 3)
        fname = access.call_args_list[0][0][0]
        assert(fname.startswith(dnf.const.TMPDIR))
        assert(fname.endswith(hawkey.SYSTEM_REPO_NAME + '.solv'))
        fname = access.call_args_list[1][0][0]
        assert(fname.endswith('main.solv'))
        fname = access.call_args_list[2][0][0]
        assert(fname.endswith('main-filenames.solvx'))

    def test_clean_files_local(self):
        """Do not delete files from a local repo."""
        base = support.MockBase("main")
        repo = base.repos['main']
        repo.baseurl = ['file:///dnf-bad-test']
        repo.basecachedir = '/tmp/dnf-bad-test'
        with mock.patch.object(base, "_cleanFilelist") as cf_mock,\
             mock.patch('os.path.exists', return_value=True) as exists_mock:
            base._cleanFiles(['rpm'], 'pkgdir', 'package')
        # local repo is not even checked for directory existence:
        self.assertIsNone(exists_mock.call_args)

class CompsTest(support.TestCase):
    # Also see test_comps.py

    # prevent creating the gen/ directory:
    @mock.patch('dnf.yum.misc.repo_gen_decompress', lambda x, y: x)
    def test_read_comps(self):
        base = support.MockBase("main")
        base.repos['main'].metadata = mock.Mock(comps_fn=support.COMPS_PATH)
        base.read_comps()
        groups = base.comps.groups
        self.assertLength(groups, support.TOTAL_GROUPS)

    def test_read_comps_disabled(self):
        base = support.MockBase("main")
        base.repos['main'].enablegroups = False
        self.assertEmpty(base.read_comps())

class Goal2TransactionTest(support.TestCase):
    def test_upgrade(self):
        base = support.MockBase("main", "updates")
        base.upgrade("hole")
        goal = base._goal
        self.assertTrue(base.run_hawkey_goal(goal, allow_erasing=False))
        ts = base._goal2transaction(goal)
        self.assertLength(ts._tsis, 1)
        tsi = ts._tsis[0]
        self.assertItemsEqual(map(str, tsi.installs()), ('hole-2-1.x86_64',))
        self.assertItemsEqual(map(str, tsi.removes()),
                              ('hole-1-1.x86_64', 'tour-5-0.noarch'))
