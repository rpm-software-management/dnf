import dnf.yum
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
        yumbase.conf.cachedir = "/tmp"
        del yumbase.preconf

        self.assertIsNone(yumbase._lockfile)
        yumbase.doLock()
        lockfile = yumbase._lockfile
        self.assertTrue(os.access(lockfile, os.R_OK))
        yumbase.doUnlock()
        self.assertFalse(os.access(lockfile, os.F_OK))
