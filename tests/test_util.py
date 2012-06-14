import unittest
import mock
import dnf.util

class Util(unittest.TestCase):
    def test_am_i_root(self):
        with mock.patch('os.geteuid', return_value=1001):
            self.assertFalse(dnf.util.am_i_root())
        with mock.patch('os.geteuid', return_value=0):
            assert(dnf.util.am_i_root())

    def test_file_timestamp(self):
        stat = mock.Mock()
        stat.st_mtime = 123
        with mock.patch('os.stat', return_value=stat):
            self.assertEqual(dnf.util.file_timestamp("/yeah"), 123)
        self.assertRaises(OSError, dnf.util.file_timestamp, "/does/not/ex1st")
