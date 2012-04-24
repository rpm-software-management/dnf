import base
import dnf.queries
import unittest

class List(unittest.TestCase):
    def test_list_installed(self):
        yumbase = base.mock_yum_base()
        ypl = yumbase.doPackageLists('installed')
        self.assertEqual(len(ypl.installed), base.TOTAL_RPMDB_COUNT)

    def test_list_updates(self):
        yumbase = base.mock_yum_base("updates", "main")
        ypl = yumbase.doPackageLists('updates')
        self.assertEqual(len(ypl.updates), 1)
        pkg = ypl.updates[0]
        self.assertEqual(pkg.name, "pepper")
        ypl = yumbase.doPackageLists('updates', ["pepper"])
        self.assertEqual(len(ypl.updates), 1)
        ypl = yumbase.doPackageLists('updates', ["mrkite"])
        self.assertEqual(len(ypl.updates), 0)

class Queries(unittest.TestCase):
    def test_duplicities(self):
        yumbase = base.mock_yum_base()
        pepper = dnf.queries.installed_by_name(yumbase.sack, "pepper")
        # make sure 'pepper' package exists:
        self.assertEqual(len(pepper), 1)
        # we shouldn't see it more than once with a tricky query below:
        res = dnf.queries.installed_by_name(yumbase.sack, ["pep*", "*per"])
        res_set = set(res)
        self.assertEqual(len(res), len(res_set))
