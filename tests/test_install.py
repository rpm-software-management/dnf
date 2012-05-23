import base
import dnf.queries
import hawkey

class InstallMultilibAll(base.ResultTestCase):
    def setUp(self):
        self.yumbase = base.mock_yum_base()
        self.yumbase.conf.multilib_policy = "all"

    def test_not_available(self):
        """ Installing a nonexistent package is a void operation. """
        tsinfo = self.yumbase.install(pattern="not-available")
        installed_pkgs = dnf.queries.installed(self.yumbase.sack)
        self.assertEqual(len(tsinfo), 0)
        self.assertResult(self.yumbase, installed_pkgs)

    def test_install(self):
        """ Simple install. """
        self.yumbase.install(pattern="mrkite")
        new_set = dnf.queries.installed(self.yumbase.sack) + \
            dnf.queries.available_by_name(self.yumbase.sack, "mrkite")
        self.assertResult(self.yumbase, new_set)

class MultilibAllMainRepo(base.ResultTestCase):
    def setUp(self):
        self.yumbase = base.mock_yum_base("main")
        self.installed = dnf.queries.installed(self.yumbase.sack)
        self.yumbase.conf.multilib_policy = "all"

    def test_reinstall_existing(self):
        """ Do not try installing an already present package. """
        self.yumbase.install(pattern="pepper")
        self.assertResult(self.yumbase, self.installed)

    def test_install(self):
        """ Installing a package existing in multiple architectures attempts
            installing all of them.
        """
        tsinfo = self.yumbase.install(pattern="lotus")
        arches = [txmbr.po.arch for txmbr in tsinfo]
        self.assertItemsEqual(arches, ['x86_64', 'i686'])
        new_set = self.installed + \
            dnf.queries.available_by_name(self.yumbase.sack, "lotus")
        self.assertResult(self.yumbase, new_set)

class MultilibBestMainRepo(base.ResultTestCase):
    def setUp(self):
        self.yumbase = base.mock_yum_base("main")
        self.installed = dnf.queries.installed(self.yumbase.sack)
        self.assertEqual(self.yumbase.conf.multilib_policy, "best")

    def test_not_available(self):
        """ Installing a nonexistent package is a void operation. """
        tsinfo = self.yumbase.install(pattern="not-available")
        # no query is run and so yumbase can not now it will later yield an
        # empty set:
        self.assertEqual(len(tsinfo), 1)
        self.assertResult(self.yumbase, self.installed)

    def test_install(self):
        """ Installing a package existing in multiple architectures only
            installs the one for our arch.
        """
        tsinfo = self.yumbase.install(pattern="lotus")
        self.assertEqual(len(tsinfo), 1)

        new_package = hawkey.Query(self.yumbase.sack).\
            filter(name="lotus", arch="x86_64", repo="main")[0]
        new_set = self.installed + [new_package]
        self.assertResult(self.yumbase, new_set)
