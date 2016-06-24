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
from tests.support import mock
from tests.support import TestCase

import binascii
import dnf
import dnf.exceptions
import dnf.package
import dnf.subject
import dnf.transaction
import hawkey
import re
import rpm

class BaseTest(support.TestCase):
    def test_instance(self):
        base = support.Base()

    @mock.patch('dnf.rpm.detect_releasever', lambda x: 'x')
    @mock.patch('dnf.util.am_i_root', lambda: True)
    def test_default_config_root(self):
        base = dnf.Base()
        self.assertIsNotNone(base.conf)
        self.assertIsNotNone(base.conf.cachedir)
        reg = re.compile('/var/cache/dnf')
        self.assertIsNotNone(reg.match(base.conf.cachedir))

    @mock.patch('dnf.rpm.detect_releasever', lambda x: 'x')
    @mock.patch('dnf.util.am_i_root', lambda: False)
    def test_default_config_user(self):
        base = dnf.Base()
        self.assertIsNotNone(base.conf)
        self.assertIsNotNone(base.conf.cachedir)
        reg = re.compile('/var/tmp/dnf-[a-zA-Z0-9_-]+')
        self.assertIsNotNone(reg.match(base.conf.cachedir))

    def test_reset(self):
        base = support.MockBase('main')
        base.reset(sack=True, repos=False)
        self.assertIsNone(base._sack)
        self.assertLength(base.repos, 1)

    @mock.patch('dnf.rpm.transaction.TransactionWrapper')
    def test_ts(self, mock_ts):
        base = dnf.Base()
        self.assertEqual(base._priv_ts, None)
        ts = base._ts
        # check the setup is correct
        ts.setFlags.call_args.assert_called_with(0)
        flags = ts.setProbFilter.call_args[0][0]
        self.assertTrue(flags & rpm.RPMPROB_FILTER_OLDPACKAGE)
        self.assertFalse(flags & rpm.RPMPROB_FILTER_REPLACEPKG)
        # check file conflicts are reported:
        self.assertFalse(flags & rpm.RPMPROB_FILTER_REPLACENEWFILES)
        # check we can close the connection
        del base._ts
        self.assertEqual(base._priv_ts, None)
        ts.close.assert_called_once_with()

    def test_iter_userinstalled(self):
        """Test iter_userinstalled with a package installed by the user."""
        base = support.Base()
        base._sack = support.mock_sack('main')
        base._priv_yumdb = support.MockYumDB()
        pkg, = base.sack.query().installed().filter(name='pepper')
        base._yumdb.get_package(pkg).get = {'reason': 'user', 'from_repo': 'main'}.get

        iterator = base.iter_userinstalled()

        self.assertEqual(next(iterator), pkg)
        self.assertRaises(StopIteration, next, iterator)

    def test_iter_userinstalled_badfromrepo(self):
        """Test iter_userinstalled with a package installed from a bad repository."""
        base = support.Base()
        base._sack = support.mock_sack('main')
        base._priv_yumdb = support.MockYumDB()

        pkg, = base.sack.query().installed().filter(name='pepper')
        base._yumdb.get_package(pkg).get = {'reason': 'user', 'from_repo': 'anakonda'}.get

        iterator = base.iter_userinstalled()

        self.assertRaises(StopIteration, next, iterator)

    def test_iter_userinstalled_badreason(self):
        """Test iter_userinstalled with a package installed for a wrong reason."""
        base = support.Base()
        base._sack = support.mock_sack('main')
        base._priv_yumdb = support.MockYumDB()

        pkg, = base.sack.query().installed().filter(name='pepper')
        base._yumdb.get_package(pkg).get = {'reason': 'dep', 'from_repo': 'main'}.get

        iterator = base.iter_userinstalled()

        self.assertRaises(StopIteration, next, iterator)

    def test_translate_comps_pkg_types(self):
        base = support.Base()
        num = base._translate_comps_pkg_types(('mandatory', 'optional'))
        self.assertEqual(num, 12)

class MockBaseTest(TestCase):
    """Test the Base methods that need a Sack."""

    def setUp(self):
        self.base = support.MockBase("main")

    def test_add_remote_rpms(self):
        pkgs = self.base.add_remote_rpms([support.TOUR_50_PKG_PATH])
        self.assertIsInstance(pkgs[0], dnf.package.Package)
        self.assertEqual(pkgs[0].name, 'tour')

class BuildTransactionTest(support.TestCase):
    def test_resolve(self):
        base = support.MockBase("updates")
        base.upgrade("pepper")
        self.assertTrue(base.resolve())
        base._ds_callback.assert_has_calls([mock.call.start(),
                                            mock.call.pkg_added(mock.ANY, 'ud'),
                                            mock.call.pkg_added(mock.ANY, 'u')])
        self.assertLength(base.transaction, 1)

# verify transaction test helpers
HASH = "68e9ded8ea25137c964a638f12e9987c"
def mock_sack_fn():
    return (lambda base: support.TestSack(support.REPO_DIR, base))

@property
def ret_pkgid(self):
    return self.name

class VerifyTransactionTest(TestCase):
    def setUp(self):
        self.base = support.MockBase("main")
        self.base._transaction = dnf.transaction.Transaction()

    @mock.patch('dnf.sack._build_sack', new_callable=mock_sack_fn)
    @mock.patch('dnf.package.Package._pkgid', ret_pkgid) # neutralize @property
    def test_verify_transaction(self, unused_build_sack):
        # we don't simulate the transaction itself here, just "install" what is
        # already there and "remove" what is not.
        new_pkg = self.base.sack.query().available().filter(name="pepper")[1]
        new_pkg._chksum = (hawkey.CHKSUM_MD5, binascii.unhexlify(HASH))
        new_pkg.repo = mock.Mock()
        removed_pkg = self.base.sack.query().available().filter(
            name="mrkite")[0]

        self.base.transaction.add_install(new_pkg, [])
        self.base.transaction.add_erase(removed_pkg)
        self.base._verify_transaction()
        # mock is designed so this returns the exact same mock object it did
        # during the method call:
        yumdb_info = self.base._yumdb.get_package(new_pkg)
        self.assertEqual(yumdb_info.from_repo, 'main')
        self.assertEqual(yumdb_info.reason, 'unknown')
        self.assertEqual(yumdb_info.releasever, 'Fedora69')
        self.assertEqual(yumdb_info.checksum_type, 'md5')
        self.assertEqual(yumdb_info.checksum_data, HASH)
        self.base._yumdb.assertLength(2)

class InstallReasonTest(support.ResultTestCase):
    def setUp(self):
        self.base = support.MockBase("main")

    def test_reason(self):
        self.base.install("mrkite")
        self.base.resolve()
        new_pkgs = self.base._transaction._get_items(dnf.transaction.INSTALL)
        pkg_reasons = [(tsi.installed.name, tsi.reason) for tsi in new_pkgs]
        self.assertCountEqual([("mrkite", "user"), ("trampoline", "dep")],
                              pkg_reasons)

class InstalledMatchingTest(support.ResultTestCase):
    def setUp(self):
        self.base = support.MockBase("main")
        self.sack = self.base.sack

    def test_query_matching(self):
        subj = dnf.subject.Subject("pepper")
        query = subj.get_best_query(self.sack)
        inst, avail = self.base._query_matches_installed(query)
        self.assertCountEqual(['pepper-20-0.x86_64'], map(str, inst))
        self.assertCountEqual(['pepper-20-0.src'], map(str, avail))

    def test_selector_matching(self):
        subj = dnf.subject.Subject("pepper")
        sltr = subj.get_best_selector(self.sack)
        inst = self.base._sltr_matches_installed(sltr)
        self.assertCountEqual(['pepper-20-0.x86_64'], map(str, inst))


class CompsTest(support.TestCase):
    # Also see test_comps.py

    # prevent creating the gen/ directory:
    @mock.patch('dnf.yum.misc.repo_gen_decompress', lambda x, y: x)
    def test_read_comps(self):
        base = support.MockBase("main")
        base.repos['main'].metadata = mock.Mock(_comps_fn=support.COMPS_PATH)
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
        self.assertTrue(base._run_hawkey_goal(goal, allow_erasing=False))
        ts = base._goal2transaction(goal)
        self.assertLength(ts._tsis, 1)
        tsi = ts._tsis[0]
        self.assertCountEqual(map(str, tsi.installs()), ('hole-2-1.x86_64',))
        self.assertCountEqual(map(str, tsi.removes()),
                              ('hole-1-1.x86_64', 'tour-5-0.noarch'))
