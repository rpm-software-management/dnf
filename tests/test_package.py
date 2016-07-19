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
from dnf.pycomp import long
from tests import support
from tests.support import mock

import binascii
import hawkey
import rpm

TOUR_MD5 = binascii.unhexlify("68e9ded8ea25137c964a638f12e9987c")
TOUR_SHA256 = binascii.unhexlify("ce77c1e5694b037b6687cf0ab812ca60431ec0b65116abbb7b82684f0b092d62")
TOUR_WRONG_MD5 = binascii.unhexlify("ffe9ded8ea25137c964a638f12e9987c")
TOUR_SIZE = 2317

class PackageTest(support.TestCase):
    def setUp(self):
        base = support.MockBase("main")
        self.sack = base.sack
        self.pkg = self.sack.query().available().filter(name="pepper")[1]

    def test_from_cmdline(self):
        self.sack.create_cmdline_repo()
        local_pkg = self.sack.add_cmdline_package(support.TOUR_44_PKG_PATH)
        self.assertTrue(local_pkg._from_cmdline)
        self.assertFalse(self.pkg._from_cmdline)

    def test_from_system(self):
        pkg = self.sack.query().installed().filter(name="pepper")[0]
        self.assertTrue(pkg._from_system)
        self.assertFalse(self.pkg._from_system)

    def test_header(self):
        self.sack.create_cmdline_repo()
        pkg = self.sack.add_cmdline_package(support.TOUR_44_PKG_PATH)
        header = pkg._header
        self.assertIsInstance(header, rpm.hdr)
        fn_getter = lambda: support.NONEXISTENT_FILE
        with mock.patch.object(pkg, 'localPkg', fn_getter):
            with self.assertRaises(IOError):
                pkg._header

    @mock.patch("dnf.package.Package.rpmdbid", long(3))
    def test_idx(self):
        """ pkg.idx is an int. """
        pkg = self.sack.query().installed().filter(name="pepper")[0]
        self.assertEqual(type(pkg.idx), int)

    def test_pkgtup(self):
        self.assertEqual(self.pkg.pkgtup, ('pepper', 'x86_64', '0', '20', '0'))

    @mock.patch("dnf.package.Package.location", 'f/foo.rpm')
    def test_localPkg(self):
        self.pkg.repo.basecachedir = '/cachedir'
        self.pkg.repo.baseurl = ['file:///mnt/cd']
        self.assertTrue(self.pkg.repo._local)
        self.assertEqual(self.pkg.localPkg(), '/mnt/cd/f/foo.rpm')
        self.pkg.repo.baseurl = ['http://remote']
        self.assertFalse(self.pkg.repo._local)
        self.assertEqual(self.pkg.localPkg(),
                         self.pkg.repo._cachedir + '/packages/foo.rpm')

    def test_verify(self):
        with mock.patch.object(self.pkg, 'localPkg',
                               return_value=support.TOUR_44_PKG_PATH):
            self.pkg._chksum = (hawkey.CHKSUM_MD5, TOUR_MD5)
            self.pkg._size = TOUR_SIZE
            self.assertTrue(self.pkg.verifyLocalPkg())
            self.pkg._chksum = (hawkey.CHKSUM_MD5, TOUR_WRONG_MD5)
            self.assertFalse(self.pkg.verifyLocalPkg())

    def test_return_id_sum(self):
        self.pkg._chksum = (hawkey.CHKSUM_MD5, TOUR_MD5)
        self.assertEqual(self.pkg.returnIdSum(),
                         ('md5', '68e9ded8ea25137c964a638f12e9987c'))

    def test_verify_local(self):
        self.sack.create_cmdline_repo()
        local_pkg = self.sack.add_cmdline_package(support.TOUR_44_PKG_PATH)
        self.assertEqual(local_pkg.reponame, hawkey.CMDLINE_REPO_NAME)
        self.assertTrue(local_pkg.verifyLocalPkg())

    def test_chksum_local(self):
        self.sack.create_cmdline_repo()
        local_pkg = self.sack.add_cmdline_package(support.TOUR_44_PKG_PATH)
        chksum = local_pkg._chksum
        self.assertEqual(chksum[0], hawkey.CHKSUM_SHA256)
        self.assertEqual(chksum[1], TOUR_SHA256)

    def test_verify_installed(self):
        pkg = self.sack.query().installed().filter(name="pepper")[0]
        self.assertRaises(ValueError, pkg.verifyLocalPkg)
