import base
import dnf.queries

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
        new_set = dnf.queries.installed_by_name(yumbase.sack, None) + \
            dnf.queries.available_by_name(yumbase.sack, "mrkite")
        self.assertResult(yumbase, new_set)

    def test_install_multilib(self):
        """ Installing a package existing in multiple architectures attempts
            installing all of them.
        """
        yumbase = base.mock_yum_base("main")
        ret = yumbase.install(pattern="lotus")
        arches = [txmbr.po.arch for txmbr in ret]
        self.assertItemsEqual(arches, ['x86_64', 'i686'])
        new_set = dnf.queries.installed_by_name(yumbase.sack, None) + \
            dnf.queries.available_by_name(yumbase.sack, "lotus")
        self.assertResult(yumbase, new_set)
