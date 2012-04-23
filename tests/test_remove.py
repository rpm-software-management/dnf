import base
import dnf.queries
import unittest

class Remove(base.ResultTestCase):
    def test_not_installed(self):
        """ Removing a not-installed package is a void operation. """
        yumbase = base.mock_yum_base()
        ret = yumbase.remove(pattern="mrkite")
        self.assertEqual(ret, [])
        installed_pkgs = dnf.queries.installed_by_name(yumbase.sack, None)
        self.assertResult(yumbase, installed_pkgs)

    def test_remove(self):
        """ Simple remove. """
        yumbase = base.mock_yum_base()
        ret = yumbase.remove(pattern="pepper")
        pepper = list(dnf.queries.installed_by_name(yumbase.sack, "pepper"))
        self.assertEqual([txmbr.po for txmbr in ret], pepper)
        self.assertResult(yumbase, [])
