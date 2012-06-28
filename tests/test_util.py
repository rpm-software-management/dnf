import unittest
import mock
import dnf.util

class Slow(object):
    def __init__(self, val):
        self._val = val
        self.computed = 0

    def new_val(self, val):
        self._val = val
        del self._square1
        del self._square2

    @dnf.util.lazyattr("_square1")
    def square1(self):
        self.computed += 1
        return self._val * self._val

    @property
    @dnf.util.lazyattr("_square2")
    def square2(self):
        self.computed += 1
        return self._val * self._val

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

    def test_lazyattr(self):
        slow = Slow(12)

        self.assertEqual(slow.computed, 0)
        self.assertEqual(slow.square1(), 144)
        self.assertEqual(slow.computed, 1)
        self.assertEqual(slow.square1(), 144)
        self.assertEqual(slow.square1(), 144)
        self.assertEqual(slow.computed, 1)

        self.assertEqual(slow.square2, 144)
        self.assertEqual(slow.computed, 2)
        self.assertEqual(slow.square2, 144)
        self.assertEqual(slow.computed, 2)

        slow.new_val(13)
        self.assertEqual(slow.square1(), 169)
        self.assertEqual(slow.square2, 169)
        self.assertEqual(slow.computed, 4)
