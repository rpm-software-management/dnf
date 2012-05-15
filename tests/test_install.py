import base
import dnf.queries

class Install(base.ResultTestCase):
    def setUp(self):
        self.yumbase = base.mock_yum_base()

    def test_not_available(self):
        """ Installing a nonexistent package is a void operation. """
        ret = self.yumbase.install(pattern="not-available")
        installed_pkgs = dnf.queries.installed_by_name(self.yumbase.sack, None)
        self.assertEqual(ret, [])
        self.assertResult(self.yumbase, installed_pkgs)

    def test_install(self):
        """ Simple install. """
        ret = self.yumbase.install(pattern="mrkite")
        new_set = dnf.queries.installed_by_name(self.yumbase.sack, None) + \
            dnf.queries.available_by_name(self.yumbase.sack, "mrkite")
        self.assertResult(self.yumbase, new_set)

class InstallWithMainRepo(base.ResultTestCase):
    def setUp(self):
        self.yumbase = base.mock_yum_base("main")

    def test_reinstall_existing(self):
        """ Do not try installing an already present package. """
        ret = self.yumbase.install(pattern="pepper")
        self.assertResult(self.yumbase,
                          dnf.queries.installed_by_name(self.yumbase.sack, None))

    def test_install_multilib(self):
        """ Installing a package existing in multiple architectures attempts
            installing all of them.
        """
        ret = self.yumbase.install(pattern="lotus")
        arches = [txmbr.po.arch for txmbr in ret]
        self.assertItemsEqual(arches, ['x86_64', 'i686'])
        new_set = dnf.queries.installed_by_name(self.yumbase.sack, None) + \
            dnf.queries.available_by_name(self.yumbase.sack, "lotus")
        self.assertResult(self.yumbase, new_set)
