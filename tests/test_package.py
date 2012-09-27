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
import dnf.package
import dnf.queries
import hawkey
import mock
import os.path
import unittest
import binascii

TOUR_MD5 = binascii.unhexlify("68e9ded8ea25137c964a638f12e9987c")
TOUR_SHA256 = binascii.unhexlify("ce77c1e5694b037b6687cf0ab812ca60431ec0b65116abbb7b82684f0b092d62")
TOUR_WRONG_MD5 = binascii.unhexlify("ffe9ded8ea25137c964a638f12e9987c")
TOUR_SIZE = 2317

class PackageTest(unittest.TestCase):
    def setUp(self):
        yumbase = base.MockYumBase("main")
        self.sack = yumbase.sack
        self.pkg = dnf.queries.available_by_name(self.sack, "pepper")[0]

    def test_from_cmdline(self):
        self.sack.create_cmdline_repo()
        local_pkg = self.sack.add_cmdline_package(base.TOUR_44_PKG_PATH)
        self.assertTrue(local_pkg.from_cmdline)
        self.assertFalse(self.pkg.from_cmdline)

    def test_from_system(self):
        pkg = dnf.queries.installed_by_name(self.sack, "pepper")[0]
        self.assertTrue(pkg.from_system)
        self.assertFalse(self.pkg.from_system)

    @mock.patch("dnf.package.Package.rpmdbid", 3l)
    def test_idx(self):
        """ pkg.idx is an int. """
        pkg = dnf.queries.installed_by_name(self.sack, "pepper")[0]
        self.assertEqual(type(pkg.idx), int)

    def test_pkgtup(self):
        self.assertEqual(self.pkg.pkgtup, ('pepper', 'x86_64', '0', '20', '0'))

    def test_verify(self):
        self.pkg.localpath = base.TOUR_44_PKG_PATH
        self.pkg.chksum = (hawkey.CHKSUM_MD5, TOUR_MD5)
        self.pkg.size = TOUR_SIZE
        self.assertTrue(self.pkg.verifyLocalPkg())
        self.pkg.chksum = (hawkey.CHKSUM_MD5, TOUR_WRONG_MD5)
        self.assertFalse(self.pkg.verifyLocalPkg())

    def test_return_id_sum(self):
        self.pkg.chksum = (hawkey.CHKSUM_MD5, TOUR_MD5)
        self.assertEqual(self.pkg.returnIdSum(),
                         ('md5', '68e9ded8ea25137c964a638f12e9987c'))

    def test_verify_local(self):
        self.sack.create_cmdline_repo()
        local_pkg = self.sack.add_cmdline_package(base.TOUR_44_PKG_PATH)
        self.assertEqual(local_pkg.reponame, hawkey.CMDLINE_REPO_NAME)
        self.assertTrue(local_pkg.verifyLocalPkg())

    def test_chksum_local(self):
        self.sack.create_cmdline_repo()
        local_pkg = self.sack.add_cmdline_package(base.TOUR_44_PKG_PATH)
        chksum = local_pkg.chksum
        self.assertEqual(chksum[0], hawkey.CHKSUM_SHA256)
        self.assertEqual(chksum[1], TOUR_SHA256)

    def test_verify_installed(self):
        pkg = dnf.queries.installed_by_name(self.sack, "pepper")[0]
        self.assertRaises(ValueError, pkg.verifyLocalPkg)
