import base
import dnf.package
import hawkey
import os.path
import queries
import unittest
import binascii

TOUR_PKG_PATH = os.path.join(base.repo_dir(), "tour-4-4.noarch.rpm")
TOUR_MD5 = binascii.unhexlify("68e9ded8ea25137c964a638f12e9987c")
TOUR_WRONG_MD5 = binascii.unhexlify("ffe9ded8ea25137c964a638f12e9987c")
TOUR_SIZE = 2317

class PackageTest(unittest.TestCase):
    def setUp(self):
        yumbase = base.mock_yum_base()
        self.sack = yumbase.sack
        self.pkg = queries.by_name(yumbase.sack, "pepper")[0]

    def test_pkgtup(self):
        self.assertEqual(self.pkg.pkgtup, ('pepper', 'x86_64', '0', '20', '0'))

    def test_verify(self):
        self.pkg.localpath = TOUR_PKG_PATH
        self.pkg.chksum = (hawkey.CHKSUM_MD5, TOUR_MD5)
        self.pkg.size = TOUR_SIZE
        self.assertTrue(self.pkg.verifyLocalPkg())
        self.pkg.chksum = (hawkey.CHKSUM_MD5, TOUR_WRONG_MD5)
        self.assertFalse(self.pkg.verifyLocalPkg())
