import base
import dnf.package
import dnf.queries
import hawkey
import os.path
import unittest
import binascii

TOUR_MD5 = binascii.unhexlify("68e9ded8ea25137c964a638f12e9987c")
TOUR_WRONG_MD5 = binascii.unhexlify("ffe9ded8ea25137c964a638f12e9987c")
TOUR_SIZE = 2317

class PackageTest(unittest.TestCase):
    def setUp(self):
        yumbase = base.mock_yum_base("main")
        self.sack = yumbase.sack
        self.pkg = dnf.queries.available_by_name(self.sack, "pepper")[0]

    def test_pkgtup(self):
        self.assertEqual(self.pkg.pkgtup, ('pepper', 'x86_64', '0', '20', '0'))

    def test_verify(self):
        self.pkg.localpath = base.TOUR_PKG_PATH
        self.pkg.chksum = (hawkey.CHKSUM_MD5, TOUR_MD5)
        self.pkg.size = TOUR_SIZE
        self.assertTrue(self.pkg.verifyLocalPkg())
        self.pkg.chksum = (hawkey.CHKSUM_MD5, TOUR_WRONG_MD5)
        self.assertFalse(self.pkg.verifyLocalPkg())

    def test_verify_local(self):
        self.sack.create_cmdline_repo()
        local_pkg = self.sack.add_cmdline_rpm(base.TOUR_PKG_PATH)
        self.assertEqual(local_pkg.reponame, hawkey.CMDLINE_REPO_NAME)
        self.assertTrue(local_pkg.verifyLocalPkg())

    def test_verify_installed(self):
        pkg = dnf.queries.installed_by_name(self.sack, "pepper")[0]
        self.assertRaises(ValueError, pkg.verifyLocalPkg)
