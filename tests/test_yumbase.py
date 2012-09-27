# Copyright (C) 2012  Red Hat, Inc.
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

import base
import binascii
import dnf.const
import dnf.queries
import dnf.yum
import dnf.yum.constants
import hawkey
import mock
import os
import unittest

class YumBaseTest(unittest.TestCase):
    def test_instance(self):
        yumbase = dnf.yum.YumBase()

    @mock.patch('dnf.const.PID_FILENAME', "/var/run/dnf.unittest.pid")
    def test_locking(self):
        # tricky setup:
        yumbase = dnf.yum.YumBase()
        yumbase.conf = mock.Mock()
        yumbase.conf.cache = None
        yumbase.cache_c.prefix = "/tmp"
        yumbase.cache_c.suffix = ""
        del yumbase.preconf

        self.assertIsNone(yumbase._lockfile)
        yumbase.doLock()
        lockfile = yumbase._lockfile
        self.assertTrue(os.access(lockfile, os.R_OK))
        yumbase.doUnlock()
        self.assertFalse(os.access(lockfile, os.F_OK))

    def test_push_userinstalled(self):
        yumbase = base.mock_yum_base()
        # setup:
        yumbase.conf.clean_requirements_on_remove = True
        pkg = dnf.queries.installed_by_name(yumbase.sack, "pepper")[0]
        goal = mock.Mock(spec=["userinstalled"])
        yumbase.yumdb.get_package(pkg).reason = "user"
        # test:
        yumbase._push_userinstalled(goal)
        goal.userinstalled.assert_called_with(pkg)

# verify transaction test helpers
HASH = "68e9ded8ea25137c964a638f12e9987c"
def mock_sack_fn():
    return (lambda yumbase: base.TestSack(base.repo_dir(), yumbase))

@property
def ret_pkgid(self):
    return self.name

class VerifyTransactionTest(unittest.TestCase):
    def setUp(self):
        self.yumbase = base.mock_yum_base("main")

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

        self.yumbase.tsInfo.addInstall(new_pkg)
        self.yumbase.tsInfo.addErase(removed_pkg)
        self.yumbase.verifyTransaction()
        # mock is designed so this returns the exact same mock object it did
        # during the method call:
        yumdb_info = self.yumbase.yumdb.get_package(new_pkg)
        self.assertEqual(yumdb_info.from_repo, 'main')
        self.assertEqual(yumdb_info.reason, 'unknown')
        self.assertEqual(yumdb_info.releasever, 'Fedora69')
        self.assertEqual(yumdb_info.checksum_type, 'md5')
        self.assertEqual(yumdb_info.checksum_data, HASH)
        self.yumbase.yumdb.assertLength(2)

class InstallReason(base.ResultTestCase):
    def setUp(self):
        self.yumbase = base.mock_yum_base("main")

    def test_reason(self):
        self.yumbase.install(pattern="mrkite")
        self.yumbase.buildTransaction()
        new_pkgs = self.yumbase.tsInfo.getMembersWithState(
            output_states=dnf.yum.constants.TS_INSTALL_STATES)
        pkg_reasons = [(txmbr.po.name, txmbr.reason) for txmbr in new_pkgs]
        self.assertItemsEqual([("mrkite", "user"), ("trampoline", "dep")],
                              pkg_reasons)

class CleanTest(unittest.TestCase):
    def test_clean_binary_cache(self):
        yumbase = base.mock_yum_base("main")
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
