# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf
import dnf.conf

from .common import TestCase
from .common import TOUR_4_4


class DnfBaseApiTest(TestCase):
    def setUp(self):
        self.base = dnf.Base(dnf.conf.Conf())
        self.base.conf.persistdir = "/tmp/tests"

    def tearDown(self):
        self.base.close()

    def test_base(self):
        # dnf.base.Base
        self.assertHasAttr(dnf.base, "Base")
        self.assertHasType(dnf.base.Base, object)

    def test_init(self):
        base = dnf.Base(dnf.conf.Conf())

    def test_init_conf(self):
        conf = dnf.conf.Conf()
        base = dnf.base.Base(conf=conf)

    def test_comps(self):
        # Base.comps
        self.assertHasAttr(self.base, "comps")
        self.assertHasType(self.base.comps, dnf.comps.Comps)

        self.base.read_comps()
        self.assertHasType(self.base.comps, dnf.comps.Comps)

    def test_conf(self):
        # Base.conf
        self.assertHasAttr(self.base, "conf")
        self.assertHasType(self.base.conf, dnf.conf.Conf)

    def test_repos(self):
        # Base.repos
        self.assertHasAttr(self.base, "repos")
        self.assertHasType(self.base.repos, dnf.repodict.RepoDict)

        del self.base.repos
        self.assertEqual(self.base.repos, None)

    def test_sack(self):
        # Base.sack
        self.assertHasAttr(self.base, "sack")

        # blank initially
        self.assertEqual(self.base.sack, None)

        self.base.fill_sack(False, False)
        self.assertHasType(self.base.sack, dnf.sack.Sack)

    def test_transaction(self):
        # Base.transaction
        self.assertHasAttr(self.base, "transaction")

        # blank initially
        self.assertEqual(self.base.transaction, None)

        # transaction attribute is set after resolving a transaction
        self.base.fill_sack(False, False)
        self.base.resolve()
        self.assertHasType(self.base.transaction, dnf.db.group.RPMTransaction)

    def test_init_plugins(self):
        # Base.init_plugins(disabled_glob=(), enable_plugins=(), cli=None)
        self.assertHasAttr(self.base, "init_plugins")

        # disable plugins to avoid calling dnf.plugin.Plugins._load() multiple times
        # which causes the tests to crash
        self.base.conf.plugins = False
        self.base.init_plugins(disabled_glob=(), enable_plugins=(), cli=None)

    def test_pre_configure_plugins(self):
        # Base.pre_configure_plugins()
        self.assertHasAttr(self.base, "pre_configure_plugins")

        self.base.pre_configure_plugins()

    def test_configure_plugins(self):
        # Base.configure_plugins()
        self.assertHasAttr(self.base, "configure_plugins")

        self.base.configure_plugins()

    def test_update_cache(self):
        # Base.update_cache(self, timer=False)
        self.assertHasAttr(self.base, "update_cache")

        self.base.update_cache(timer=False)

    def test_fill_sack(self):
        # Base.fill_sack(self, load_system_repo=True, load_available_repos=True):
        self.assertHasAttr(self.base, "fill_sack")

        self.base.fill_sack(load_system_repo=False, load_available_repos=False)

    def test_close(self):
        # Base.close()
        self.assertHasAttr(self.base, "close")

        self.base.close()

    def test_read_all_repos(self):
        # Base.read_all_repos(self, opts=None):
        self.assertHasAttr(self.base, "read_all_repos")

        self.base.read_all_repos(opts=None)

    def test_reset(self):
        # Base.reset(self, sack=False, repos=False, goal=False):cloread_all_repos(self, opts=None)
        self.assertHasAttr(self.base, "reset")

        self.base.reset(sack=False, repos=False, goal=False)

    def test_read_comps(self):
        # Base.read_comps(self, arch_filter=False)
        self.assertHasAttr(self.base, "read_comps")

        self.base.read_comps(arch_filter=False)

    def test_resolve(self):
        # Base.resolve(self, allow_erasing=False)
        self.assertHasAttr(self.base, "resolve")

        self.base.fill_sack(load_system_repo=False, load_available_repos=False)
        self.base.resolve(allow_erasing=False)

    def test_do_transaction(self):
        # Base.do_transaction(self, display=())
        self.assertHasAttr(self.base, "do_transaction")

        self.base.fill_sack(load_system_repo=False, load_available_repos=False)
        self.base.resolve(allow_erasing=False)
        self.base.do_transaction(display=None)

    def test_download_packages(self):
        # Base.download_packages(self, pkglist, progress=None, callback_total=None)
        self.assertHasAttr(self.base, "download_packages")

        self.base.download_packages(pkglist=[], progress=None, callback_total=None)

    def test_add_remote_rpms(self):
        # Base.add_remote_rpms(self, path_list, strict=True, progress=None)
        self.assertHasAttr(self.base, "add_remote_rpms")

        self.base.fill_sack(load_system_repo=False, load_available_repos=False)
        self.base.add_remote_rpms(path_list=[TOUR_4_4], strict=True, progress=None)

    def test_package_signature_check(self):
        # Base.package_signature_check(self, pkg)
        self.assertHasAttr(self.base, "package_signature_check")
        self.base.package_signature_check(pkg=self._get_pkg())

    def test_package_import_key(self):
        # Base.package_import_key(self, pkg, askcb=None, fullaskcb=None)
        self.assertHasAttr(self.base, "package_import_key")
        self.assertRaises(
            ValueError,
            self.base.package_import_key,
            pkg=self._get_pkg(),
            askcb=None,
            fullaskcb=None,
        )

    def test_environment_install(self):
        # Base.environment_install(self, env_id, types, exclude=None, strict=True, exclude_groups=None)
        self.assertHasAttr(self.base, "environment_install")
        self._load_comps()
        self.base.environment_install(
            env_id="sugar-desktop-environment",
            types=["mandatory", "default", "optional"],
            exclude=None,
            strict=True,
            exclude_groups=None
        )

    def test_environment_remove(self):
        # Base.environment_remove(self, env_id):
        self.assertHasAttr(self.base, "environment_remove")

        self.base.read_comps(arch_filter=False)
        self.assertRaises(dnf.exceptions.CompsError, self.base.environment_remove, env_id="base")

    def test_environment_upgrade(self):
        # Base.environment_upgrade(self, env_id):
        self.assertHasAttr(self.base, "environment_upgrade")

        self._load_comps()
        self.assertRaises(dnf.exceptions.CompsError, self.base.environment_upgrade, env_id="sugar-desktop-environment")

    def test_group_install(self):
        # Base.group_install(self, grp_id, pkg_types, exclude=None, strict=True)
        self.assertHasAttr(self.base, "group_install")

        self._load_comps()
        self.base.group_install(
            grp_id="base",
            pkg_types=["mandatory", "default", "optional"],
            exclude=None,
            strict=True
        )

    def test_group_remove(self):
        # Base.group_remove(self, env_id):
        self.assertHasAttr(self.base, "group_remove")

        self._load_comps()
        self.assertRaises(dnf.exceptions.CompsError, self.base.group_remove, grp_id="base")

    def test_group_upgrade(self):
        # Base.group_upgrade(self, env_id):
        self.assertHasAttr(self.base, "group_upgrade")

        self.base.read_comps(arch_filter=False)
        self.assertRaises(dnf.exceptions.CompsError, self.base.group_upgrade, grp_id="base")

    def test_install_specs(self):
        # Base.install_specs(self, install, exclude=None, reponame=None, strict=True, forms=None)
        self.base.fill_sack(load_system_repo=False, load_available_repos=False)
        self.base.install_specs(install=[], exclude=None, reponame=None, strict=True, forms=None)

    def test_install(self):
        # Base.install(self, pkg_spec, reponame=None, strict=True, forms=None)
        self.base.fill_sack(load_system_repo=False, load_available_repos=False)
        self.assertRaises(
            dnf.exceptions.PackageNotFoundError,
            self.base.install,
            pkg_spec="",
            reponame=None,
            strict=True,
            forms=None
        )

    def test_package_downgrade(self):
        # Base.package_downgrade(self, pkg, strict=False)
        pkg = self._get_pkg()
        self.assertRaises(dnf.exceptions.MarkingError, self.base.package_downgrade, pkg=pkg, strict=False)

    def test_package_install(self):
        # Base.package_install(self, pkg, strict=False)
        pkg = self._get_pkg()
        self.base.package_install(pkg=pkg, strict=False)

    def test_package_upgrade(self):
        # Base.package_upgrade(self, pkg)
        pkg = self._get_pkg()
        self.assertRaises(dnf.exceptions.MarkingError, self.base.package_upgrade, pkg=pkg)

    def test_upgrade(self):
        # Base.upgrade(self, pkg_spec, reponame=None)
        self.base.fill_sack(load_system_repo=False, load_available_repos=False)
        self.assertRaises(dnf.exceptions.MarkingError, self.base.upgrade, pkg_spec="", reponame=None)

    def test_upgrade_all(self):
        # Base.upgrade_all(self, reponame=None)
        self.base.fill_sack(load_system_repo=False, load_available_repos=False)
        self.base.upgrade_all(reponame=None)

    def test_autoremove(self):
        # Base.autoremove(self, forms=None, pkg_specs=None, grp_specs=None, filenames=None)
        self.base.fill_sack(load_system_repo=False, load_available_repos=False)
        self.base.autoremove(forms=None, pkg_specs=None, grp_specs=None, filenames=None)

    def test_remove(self):
        # Base.remove(self, pkg_spec, reponame=None, forms=None)
        self.base.fill_sack(load_system_repo=False, load_available_repos=False)
        self.assertRaises(dnf.exceptions.MarkingError, self.base.remove, pkg_spec="", reponame=None, forms=None)

    def test_downgrade(self):
        # Base.downgrade(self, pkg_spec)
        self.base.fill_sack(load_system_repo=False, load_available_repos=False)
        self.assertRaises(dnf.exceptions.MarkingError, self.base.downgrade, pkg_spec="")

    def test_urlopen(self):
        # Base.urlopen(self, url, repo=None, mode='w+b', **kwargs)
        self.base.urlopen(url="file:///dev/null", repo=None, mode='w+b')

    def test_setup_loggers(self):
        # Base.setup_loggers(self)
        self.base.setup_loggers()
