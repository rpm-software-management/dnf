import base
import dnf.queries

class Remove(base.ResultTestCase):
    def setUp(self):
        self.yumbase = base.mock_yum_base()

    def test_not_installed(self):
        """ Removing a not-installed package is a void operation. """
        ret = self.yumbase.remove(pattern="mrkite")
        self.assertEqual(ret, [])
        installed_pkgs = dnf.queries.installed_by_name(self.yumbase.sack, None)
        self.assertResult(self.yumbase, installed_pkgs)

    def test_remove(self):
        """ Simple remove. """
        ret = self.yumbase.remove(pattern="pepper")
        pepper = dnf.queries.installed_by_name(self.yumbase.sack, "pepper")
        self.assertEqual([txmbr.po for txmbr in ret], pepper)
        self.assertResult(self.yumbase,
                          dnf.queries.installed_by_name(self.yumbase.sack,
                                                        "librita"))

    def test_remove_depended(self):
        """ Remove a lib that some other package depends on. """
        ret = self.yumbase.remove(pattern="librita")
        # we should end up with nothing in this case:
        self.assertResult(self.yumbase, [])
