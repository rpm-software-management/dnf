# -*- coding: utf-8 -*-

# Copyright (C) 2012-2018 Red Hat, Inc.
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

import binascii
import itertools
import re

import hawkey
import libdnf.transaction
import rpm

import dnf
import dnf.exceptions
import dnf.package
import dnf.subject
import dnf.transaction

import tests.support
from tests.support import mock


class BaseTest(tests.support.TestCase):

    @staticmethod
    def _setup_packages(history):
        pkg = tests.support.MockPackage('pepper-20-0.x86_64')
        pkg._force_swdb_repoid = "main"
        history.rpm.add_install(pkg)
        history.beg("", [], [])
        for tsi in history._swdb.getItems():
            if tsi.getState() == libdnf.transaction.TransactionItemState_UNKNOWN:
                tsi.setState(libdnf.transaction.TransactionItemState_DONE)
        history.end("")
        history.close()

    def test_instance(self):
        base = tests.support.MockBase()
        self.assertIsNotNone(base)
        base.close()

    @mock.patch('dnf.rpm.detect_releasever', lambda x: 'x')
    @mock.patch('dnf.util.am_i_root', lambda: True)
    def test_default_config_root(self):
        base = dnf.Base()
        self.assertIsNotNone(base.conf)
        self.assertIsNotNone(base.conf.cachedir)
        reg = re.compile('/var/cache/dnf')
        self.assertIsNotNone(reg.match(base.conf.cachedir))
        base.close()

    @mock.patch('dnf.rpm.detect_releasever', lambda x: 'x')
    @mock.patch('dnf.util.am_i_root', lambda: False)
    def test_default_config_user(self):
        base = dnf.Base()
        self.assertIsNotNone(base.conf)
        self.assertIsNotNone(base.conf.cachedir)
        reg = re.compile('/var/tmp/dnf-[a-zA-Z0-9_-]+')
        self.assertIsNotNone(reg.match(base.conf.cachedir))
        base.close()

    def test_reset(self):
        base = tests.support.MockBase('main')
        base.reset(sack=True, repos=False)
        self.assertIsNone(base._sack)
        self.assertLength(base.repos, 1)
        base.close()

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
        base.close()

    def test_iter_userinstalled(self):
        """Test iter_userinstalled with a package installed by the user."""
        base = tests.support.MockBase()
        self._setup_packages(base.history)
        base._sack = tests.support.mock_sack('main')
        pkg, = base.sack.query().installed().filter(name='pepper')
        # reason and repo are set in _setup_packages() already
        self.assertEqual(base.history.user_installed(pkg), True)
        self.assertEqual(base.history.repo(pkg), 'main')
        base.close()

    def test_iter_userinstalled_badfromrepo(self):
        """Test iter_userinstalled with a package installed from a bad repository."""
        base = tests.support.MockBase()
        base._sack = tests.support.mock_sack('main')
        self._setup_packages(base.history)

        history = base.history
        pkg = tests.support.MockPackage('pepper-20-0.x86_64')
        pkg._force_swdb_repoid = "anakonda"
        history.rpm.add_install(pkg)
        history.beg("", [], [])
        for tsi in history._swdb.getItems():
            if tsi.getState() == libdnf.transaction.TransactionItemState_UNKNOWN:
                tsi.setState(libdnf.transaction.TransactionItemState_DONE)
        history.end("")
        history.close()

        pkg, = base.sack.query().installed().filter(name='pepper')
        self.assertEqual(base.history.user_installed(pkg), True)
        self.assertEqual(base.history.repo(pkg), 'anakonda')
        base.close()

    def test_iter_userinstalled_badreason(self):
        """Test iter_userinstalled with a package installed for a wrong reason."""
        base = tests.support.MockBase()
        base._sack = tests.support.mock_sack('main')
        self._setup_packages(base.history)

        history = base.history
        pkg = tests.support.MockPackage('pepper-20-0.x86_64')
        pkg._force_swdb_repoid = "main"
        history.rpm.add_install(pkg, reason=libdnf.transaction.TransactionItemReason_DEPENDENCY)
        history.beg("", [], [])
        for tsi in history._swdb.getItems():
            if tsi.getState() == libdnf.transaction.TransactionItemState_UNKNOWN:
                tsi.setState(libdnf.transaction.TransactionItemState_DONE)
        history.end("")
        history.close()

        pkg, = base.sack.query().installed().filter(name='pepper')
        self.assertEqual(base.history.user_installed(pkg), False)
        self.assertEqual(base.history.repo(pkg), 'main')
        base.close()


class MockBaseTest(tests.support.DnfBaseTestCase):
    """Test the Base methods that need a Sack."""

    REPOS = ["main"]
    INIT_SACK = True

    def test_add_remote_rpms(self):
        pkgs = self.base.add_remote_rpms([tests.support.TOUR_50_PKG_PATH])
        self.assertIsInstance(pkgs[0], dnf.package.Package)
        self.assertEqual(pkgs[0].name, 'tour')


class BuildTransactionTest(tests.support.DnfBaseTestCase):

    REPOS = ["updates"]

    def test_resolve(self):
        self.base.upgrade("pepper")
        self.assertTrue(self.base.resolve())
        self.base._ds_callback.assert_has_calls([
            mock.call.start(),
            mock.call.pkg_added(mock.ANY, 'ud'),
            mock.call.pkg_added(mock.ANY, 'u')
        ])
        self.assertLength(self.base.transaction, 2)


# verify transaction test helpers
HASH = "68e9ded8ea25137c964a638f12e9987c"


def mock_sack_fn():
    return (lambda base: tests.support.TestSack(tests.support.REPO_DIR, base))


@property
def ret_pkgid(self):
    return self.name


class VerifyTransactionTest(tests.support.DnfBaseTestCase):

    REPOS = ["main"]
    INIT_TRANSACTION = True

    @mock.patch('dnf.sack._build_sack', new_callable=mock_sack_fn)
    @mock.patch('dnf.package.Package._pkgid', ret_pkgid)  # neutralize @property
    def test_verify_transaction(self, unused_build_sack):
        # we don't simulate the transaction itself here, just "install" what is
        # already there and "remove" what is not.

        tsis = []

        new_pkg = self.base.sack.query().available().filter(name="pepper")[1]
        new_pkg._chksum = (hawkey.CHKSUM_MD5, binascii.unhexlify(HASH))
        new_pkg.repo = mock.Mock()
        new_pkg._force_swdb_repoid = "main"
        self.history.rpm.add_install(new_pkg)

        removed_pkg = self.base.sack.query().available().filter(name="mrkite")[0]
        removed_pkg._force_swdb_repoid = "main"
        self.history.rpm.add_remove(removed_pkg)

        self._swdb_commit(tsis)
        self.base._verify_transaction()

        pkg = self.base.history.package_data(new_pkg)
        self.assertEqual(pkg.ui_from_repo(), '@main')
        self.assertEqual(pkg.action_name, "Install")
        self.assertEqual(pkg.get_reason(), libdnf.transaction.TransactionItemReason_USER)


class InstallReasonTest(tests.support.ResultTestCase):

    REPOS = ["main"]

    def test_reason(self):
        self.base.install("mrkite")
        self.base.resolve()
        new_pkgs = self.base._transaction._get_items(dnf.transaction.PKG_INSTALL)
        pkg_reasons = [(tsi.name, tsi.reason) for tsi in new_pkgs]
        self.assertCountEqual([
            ("mrkite", libdnf.transaction.TransactionItemReason_USER),
            ("trampoline", libdnf.transaction.TransactionItemReason_DEPENDENCY)],
            pkg_reasons
        )


class InstalledMatchingTest(tests.support.ResultTestCase):

    REPOS = ["main"]

    def test_query_matching(self):
        subj = dnf.subject.Subject("pepper")
        query = subj.get_best_query(self.sack)
        inst, avail = self.base._query_matches_installed(query)
        self.assertCountEqual(['pepper-20-0.x86_64'], map(str, inst))
        self.assertCountEqual(['pepper-20-0.src'], map(str, itertools.chain.from_iterable(avail)))

    def test_selector_matching(self):
        subj = dnf.subject.Subject("pepper")
        sltr = subj.get_best_selector(self.sack)
        inst = self.base._sltr_matches_installed(sltr)
        self.assertCountEqual(['pepper-20-0.x86_64'], map(str, inst))


class CompsTest(tests.support.DnfBaseTestCase):
    # Also see test_comps.py

    REPOS = ["main"]
    COMPS = True

    # prevent creating the gen/ directory:
    @mock.patch('dnf.yum.misc.repo_gen_decompress', lambda x, y: x)
    def test_read_comps(self):
        self.assertLength(self.base.comps.groups, tests.support.TOTAL_GROUPS)

    def test_read_comps_disabled(self):
        self.base.repos['main'].enablegroups = False
        self.assertEmpty(self.base.read_comps())


class Goal2TransactionTest(tests.support.DnfBaseTestCase):

    REPOS = ["main", "updates"]

    def test_upgrade(self):
        self.base.upgrade("hole")
        self.assertTrue(self.base._run_hawkey_goal(self.goal, allow_erasing=False))
        ts = self.base._goal2transaction(self.goal)
        self.assertLength(ts, 3)
        tsis = list(ts)

        tsi = tsis[0]
        self.assertEqual(str(tsi.pkg), "hole-2-1.x86_64")
        self.assertEqual(tsi.action, libdnf.transaction.TransactionItemAction_UPGRADE)

        tsi = tsis[1]
        self.assertEqual(str(tsi.pkg), "hole-1-1.x86_64")
        self.assertEqual(tsi.action, libdnf.transaction.TransactionItemAction_UPGRADED)

        tsi = tsis[2]
        self.assertEqual(str(tsi.pkg), "tour-5-0.noarch")
        self.assertEqual(tsi.action, libdnf.transaction.TransactionItemAction_OBSOLETED)
