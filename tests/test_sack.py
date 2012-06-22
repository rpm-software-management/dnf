import dnf.sack
import hawkey.test
import base
import mock
import unittest

class Sack(unittest.TestCase):
    def test_ensure_filelists(self):
        sack = dnf.sack.Sack(cachedir=hawkey.test.UNITTEST_DIR)
        sack.load_filelists = mock.Mock()
        sack.write_filelists = mock.Mock()
        # try calling the
        mock_attrs = {"listEnabled.return_value" : []}
        repos = mock.Mock(**mock_attrs)
        sack.ensure_filelists(repos)
        self.assertEqual(sack.load_filelists.call_count, 1)
        self.assertEqual(sack.write_filelists.call_count, 1)

    def test_rpmdb_version(self):
        yumbase = base.mock_yum_base()
        sack = yumbase.sack
        version = yumbase.sack.rpmdb_version()
        self.assertEqual(version._num, 3)
        self.assertEqual(version._chksum.hexdigest(),
                         "6034f87b90f13af4fdf2e8bded72d37e5d00f0ca")
