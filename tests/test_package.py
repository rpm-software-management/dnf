import base
import dnf.package
import queries
import unittest

class PackageTest(unittest.TestCase):
    def setUp(self):
        yumbase = base.mock_yum_base()
        self.pkg = queries.by_name(yumbase.sack, "pepper")[0]

    def test_pkgtup(self):
        self.assertEqual(self.pkg.pkgtup, ('pepper', 'x86_64', '0', '20', '0'))
