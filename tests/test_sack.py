import dnf.sack
import hawkey.test
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
