import base
import os.path
import unittest

class Sanity(unittest.TestCase):
    def test_sanity(self):
        assert(os.access(base.repo("system.repo"), os.R_OK))
        sack = base.mock_yum_base().sack
        assert(sack)
        self.assertEqual(sack.nsolvables, base.SYSTEM_NSOLVABLES)

        sack2 = base.mock_yum_base("main", "updates").sack
        self.assertEqual(sack2.nsolvables, base.TOTAL_NSOLVABLES)
