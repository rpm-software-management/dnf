import unittest
import mock
import dnf.util

class Util(unittest.TestCase):
    def test_am_i_root(self):
        with mock.patch('os.geteuid', return_value=1001):
            self.assertFalse(dnf.util.am_i_root())
        with mock.patch('os.geteuid', return_value=0):
            assert(dnf.util.am_i_root())
