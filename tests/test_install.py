import base
import dnf.queries
import unittest

class Install(base.ResultTestCase):
    def test_not_available(self):
        """ Installing a nonexistent package is a void operation. """
        yumbase = base.mock_yum_base()
        ret = yumbase.install(pattern="not-available")
        installed_pkgs = dnf.queries.installed_by_name(yumbase.sack, None)
        self.assertEqual(ret, [])
        self.assertResult(yumbase, installed_pkgs)

    def test_install(self):
        """ Simple install. """
        yumbase = base.mock_yum_base("main")
        ret = yumbase.install(pattern="mrkite")
        new_set = list(dnf.queries.installed_by_name(yumbase.sack, None)) + \
            list(dnf.queries.available_by_name(yumbase.sack, "mrkite"))
        self.assertResult(yumbase, new_set)
