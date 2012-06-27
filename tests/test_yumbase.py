import base
import binascii
import dnf.queries
import dnf.yum
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
    @mock.patch('dnf.yum.rpmsack.RPMDBAdditionalDataPackage')
    @mock.patch('dnf.package.Package.pkgid', ret_pkgid) # neutralize @property
    def test_verify_transaction(self, datapackageclass, unused_build_sack):
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
        yumdb_info = datapackageclass()
        self.assertEqual(yumdb_info.from_repo, 'main')
        self.assertEqual(yumdb_info.reason, 'user')
        self.assertEqual(yumdb_info.releasever, 'Fedora69')
        self.assertEqual(yumdb_info.checksum_type, 'md5')
        self.assertEqual(yumdb_info.checksum_data, HASH)
        datapackageclass.assert_any_call(mock.ANY,
                                         '/should-not-exist-bad-test!/yumdb/m/mrkite-mrkite-2-0-x86_64',
                                         yumdb_cache=mock.ANY)
        datapackageclass.assert_any_call(mock.ANY,
                                         '/should-not-exist-bad-test!/yumdb/p/pepper-pepper-20-0-x86_64',
                                         yumdb_cache=mock.ANY)
