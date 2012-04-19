from . import repo
import os.path
import unittest

class Sanity(unittest.TestCase):
    def test_sanity(self):
        assert(os.access(repo("system.repo"), os.R_OK))
        import hawkey
        import hawkey.test
        import dnf
        import dnf.yum
