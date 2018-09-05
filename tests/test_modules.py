# Copyright (C) 2017 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from __future__ import absolute_import
from __future__ import unicode_literals

import os
import shutil
import tempfile
import unittest

import libdnf

import dnf.conf
import dnf.base

TOP_DIR = os.path.abspath(os.path.dirname(__file__))
MODULES_DIR = os.path.join(TOP_DIR, "modules/etc/dnf/modules.d")
REPOS_DIR = os.path.join(TOP_DIR, "modules/modules")
DEFAULTS_DIR = os.path.join(TOP_DIR, "modules/etc/dnf/modules.defaults.d")

# with profile
MODULE_NSVAP = "module-name:stream:1::x86_64/profile"
MODULE_NSVP = "module-name:stream:1/profile"
MODULE_NSAP = "module-name:stream::x86_64/profile"
MODULE_NSP = "module-name:stream/profile"
MODULE_NP = "module-name/profile"
MODULE_NAP = "module-name::x86_64/profile"

# without profile
MODULE_NSVA = "module-name:stream:1::x86_64"
MODULE_NSV = "module-name:stream:1"
MODULE_NSA = "module-name:stream::x86_64"
MODULE_NS = "module-name:stream"
MODULE_N = "module-name"
MODULE_NA = "module-name::x86_64"


class ModuleTest(unittest.TestCase):
    def assertInstalls(self, nevras):
        expected = sorted(set(nevras))
        actual = sorted(set([str(i) for i in self.base._goal.list_installs()]))
        self.assertEqual(expected, actual)

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="dnf_test_")
        self.conf = dnf.conf.MainConf()
        self.conf.cachedir = os.path.join(self.tmpdir, "cache")
        self.conf.installroot = os.path.join(TOP_DIR, "modules")
        self.conf.modulesdir._set(MODULES_DIR)
        self.conf.moduledefaultsdir._set(DEFAULTS_DIR)
        self.conf.persistdir = os.path.join(self.conf.installroot, self.conf.persistdir.lstrip("/"))
        self.conf.substitutions["arch"] = "x86_64"
        self.conf.substitutions["basearch"] = dnf.rpm.basearch(self.conf.substitutions["arch"])
        self.conf.assumeyes = True
        self.base = dnf.Base(conf=self.conf)
        self.module_base = dnf.module.module_base.ModuleBase(self.base)

        self._add_module_repo("_all")
        self.base.fill_sack(load_system_repo=False)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _add_module_repo(self, repo_id, modules=True):
        url = "file://" + os.path.join(REPOS_DIR, repo_id, self.conf.substitutions["arch"])
        repo = self.base.repos.add_new_repo(repo_id, self.base.conf, baseurl=[url], modules=modules)
        return repo

    # dnf module enable

    def test_enable_name(self):
        # use default stream
        self.module_base.enable(["httpd"])
        self.assertEqual(self.base._moduleContainer.getModuleState("httpd"),
                         libdnf.module.ModulePackageContainer.ModuleState_ENABLED)
        self.assertEqual(self.base._moduleContainer.getEnabledStream("httpd"), "2.4")

    def test_enable_name_stream(self):
        self.module_base.enable(["httpd:2.4"])
        self.assertEqual(self.base._moduleContainer.getModuleState("httpd"),
                         libdnf.module.ModulePackageContainer.ModuleState_ENABLED)
        self.assertEqual(self.base._moduleContainer.getEnabledStream("httpd"), "2.4")

        # also enable base-runtime; it's a dependency that's used in other tests
        self.module_base.enable(["base-runtime:f26"])

    def test_enable_pkgspec(self):
        self.module_base.enable(["httpd:2.4:1/foo"])
        self.assertEqual(self.base._moduleContainer.getModuleState("httpd"),
                         libdnf.module.ModulePackageContainer.ModuleState_ENABLED)
        self.assertEqual(self.base._moduleContainer.getEnabledStream("httpd"), "2.4")

    def test_enable_invalid(self):
        with self.assertRaises(dnf.exceptions.Error):
            self.module_base.enable(["httpd:invalid"])

    def test_enable_different_stream(self):
        self.module_base.enable(["httpd:2.4"])
        self.assertEqual(self.base._moduleContainer.getModuleState("httpd"),
                         libdnf.module.ModulePackageContainer.ModuleState_ENABLED)
        self.assertEqual(self.base._moduleContainer.getEnabledStream("httpd"), "2.4")

        self.module_base.enable(["httpd:2.2"])
        self.assertEqual(self.base._moduleContainer.getModuleState("httpd"),
                         libdnf.module.ModulePackageContainer.ModuleState_ENABLED)
        self.assertEqual(self.base._moduleContainer.getEnabledStream("httpd"), "2.2")

    def test_enable_different_stream_missing_profile(self):
        pass

    # dnf module disable

    def test_disable_name(self):
        self.module_base.enable(["httpd:2.4"])
        self.assertEqual(self.base._moduleContainer.getModuleState("httpd"),
                         libdnf.module.ModulePackageContainer.ModuleState_ENABLED)
        self.assertEqual(self.base._moduleContainer.getEnabledStream("httpd"), "2.4")

        self.module_base.disable(["httpd"])
        self.assertEqual(self.base._moduleContainer.getModuleState("httpd"),
                         libdnf.module.ModulePackageContainer.ModuleState_DISABLED)
        self.assertEqual(self.base._moduleContainer.getEnabledStream("httpd"), "")

    def test_disable_name_stream(self):
        # It should disable whole module not only stream (strem = "")
        self.module_base.enable(["httpd:2.4"])
        self.assertEqual(self.base._moduleContainer.getModuleState("httpd"),
                         libdnf.module.ModulePackageContainer.ModuleState_ENABLED)
        self.assertEqual(self.base._moduleContainer.getEnabledStream("httpd"), "2.4")

        self.module_base.disable(["httpd:2.4"])
        self.assertEqual(self.base._moduleContainer.getModuleState("httpd"),
                         libdnf.module.ModulePackageContainer.ModuleState_DISABLED)
        self.assertEqual(self.base._moduleContainer.getEnabledStream("httpd"), "")

    def test_disable_pkgspec(self):
        # It should disable whole module not only profile (strem = "")
        self.module_base.enable(["httpd:2.4"])
        self.assertEqual(self.base._moduleContainer.getModuleState("httpd"),
                         libdnf.module.ModulePackageContainer.ModuleState_ENABLED)
        self.assertEqual(self.base._moduleContainer.getEnabledStream("httpd"), "2.4")

        self.module_base.disable(["httpd:2.4:1/foo"])
        self.assertEqual(self.base._moduleContainer.getModuleState("httpd"),
                         libdnf.module.ModulePackageContainer.ModuleState_DISABLED)
        self.assertEqual(self.base._moduleContainer.getEnabledStream("httpd"), "")

    def test_disable_invalid(self):
        self.module_base.enable(["httpd:2.4"])
        self.assertEqual(self.base._moduleContainer.getModuleState("httpd"),
                         libdnf.module.ModulePackageContainer.ModuleState_ENABLED)
        self.assertEqual(self.base._moduleContainer.getEnabledStream("httpd"), "2.4")
        with self.assertRaises(dnf.exceptions.Error):
            self.module_base.disable(["httpd:invalid"])

    def test_info_name(self):
        pass

    def test_info_name_stream(self):
        pass

    def test_info_pkgspec(self):
        pass

    # dnf module list

    def test_list_installed(self):
        # install
        self.module_base.install(["base-runtime"])

        # check module conf
        self.assertEqual(self.base._moduleContainer.getModuleState("base-runtime"),
                         libdnf.module.ModulePackageContainer.ModuleState_ENABLED)
        self.assertEqual(self.base._moduleContainer.getEnabledStream("base-runtime"), "f26")
        self.assertEqual(list(self.base._moduleContainer.getInstalledProfiles("base-runtime")),
                         ["minimal"])

    # dnf module install / dnf install @

    def test_install_profile_latest(self):
        self.test_enable_name_stream()
        self.module_base.install(["httpd/default"])
        self.base.resolve()
        expected = [
            "basesystem-11-3.noarch",
            "filesystem-3.2-40.x86_64",
            "glibc-2.25.90-2.x86_64",
            "glibc-common-2.25.90-2.x86_64",
            "httpd-2.4.25-8.x86_64",
            "libnghttp2-1.21.1-1.x86_64",  # expected behaviour, non-modular rpm pulled in
        ]
        self.assertInstalls(expected)

    def test_install_profile(self):
        self.test_enable_name_stream()
        self.module_base.install(["httpd:2.4:1/default"])
        self.base.resolve()
        expected = [
            "basesystem-11-3.noarch",
            "filesystem-3.2-40.x86_64",
            "glibc-2.25.90-2.x86_64",
            "glibc-common-2.25.90-2.x86_64",
            "httpd-2.4.25-7.x86_64",
            "libnghttp2-1.21.1-1.x86_64",  # expected behaviour, non-modular rpm pulled in
        ]
        self.assertInstalls(expected)

    def test_install_two_profiles(self):
        self.test_enable_name_stream()

        self.module_base.install(["httpd:2.4:1/default", "httpd:2.4:1/doc"])
        self.base.resolve()
        expected = [
            "basesystem-11-3.noarch",
            "filesystem-3.2-40.x86_64",
            "glibc-2.25.90-2.x86_64",
            "glibc-common-2.25.90-2.x86_64",
            "httpd-2.4.25-7.x86_64",
            "httpd-doc-2.4.25-7.x86_64",
            "libnghttp2-1.21.1-1.x86_64",  # expected behaviour, non-modular rpm pulled in
        ]
        self.assertInstalls(expected)

    def test_install_two_profiles_different_versions(self):
        self.test_enable_name_stream()
        self.module_base.install(["httpd:2.4:2/default", "httpd:2.4:1/doc"])
        self.base.resolve()
        expected = [
            "basesystem-11-3.noarch",
            "filesystem-3.2-40.x86_64",
            "glibc-2.25.90-2.x86_64",
            "glibc-common-2.25.90-2.x86_64",
            "httpd-2.4.25-8.x86_64",
            "httpd-doc-2.4.25-8.x86_64",
            "libnghttp2-1.21.1-1.x86_64",  # expected behaviour, non-modular rpm pulled in
        ]
        self.assertInstalls(expected)

    def test_install_profile_updated(self):
        return
        """
        # install profile1 from an old module version
        # then install profile2 from latest module version
        # -> dnf forces upgrade profile1 to the latest module version
        """

        self.test_install_profile()
        self.module_base.install(["httpd:2.4:2/doc"])
        self.base.resolve()
        expected = [
            "basesystem-11-3.noarch",
            "filesystem-3.2-40.x86_64",
            "glibc-2.25.90-2.x86_64",
            "glibc-common-2.25.90-2.x86_64",
            "httpd-2.4.25-8.x86_64",
            "httpd-doc-2.4.25-8.x86_64",
            "libnghttp2-1.21.1-1.x86_64",
        ]
        self.assertInstalls(expected)

    def test_install_deps_same_module_version(self):
        pass

    def test_install_implicit_empty_default_profile(self):
        # install module without a 'default' profile
        # implicit empty 'default' profile is assumed
        # -> no packages should be installed, just module enablement
        self.module_base.install(["m4:1.4.18"])

        self.assertEqual(self.base._moduleContainer.getModuleState("m4"),
                         libdnf.module.ModulePackageContainer.ModuleState_ENABLED)
        self.assertEqual(self.base._moduleContainer.getEnabledStream("m4"), "1.4.18")
        self.assertEqual(list(self.base._moduleContainer.getInstalledProfiles("m4")), ['default'])

        self.base.resolve()
        self.assertInstalls([])

    # dnf module upgrade / dnf upgrade @

    def test_upgrade(self):
        pass

    def test_upgrade_lower_rpm_nevra(self):
        pass

    def test_upgrade_lower_module_nsvap(self):
        pass

    def test_upgrade_missing_profile(self):
        pass

    # dnf module downgrade / dnf downgrade @

    def test_downgrade(self):
        pass

    # dnf module remove / dnf remove @

    def test_remove(self):
        pass

    def test_remove_shared_rpms(self):
        # don't remove RPMs that are part of another installed module / module profile
        # also don't remove RPMs that are required by user-installed RPMs
        pass

    def test_remove_invalid(self):
        pass

    def test_bare_rpms_filtering(self):
        """
        Test hybrid repos where RPMs of the same name (or Provides)
        can be both modular and bare (non-modular).
        """

        # no match with modular RPM $name -> keep
        q = self.base.sack.query().filter(nevra="grub2-2.02-0.40.x86_64")
        self.assertEqual(len(q), 1)

        # $name matches with modular RPM $name -> exclude
        q = self.base.sack.query().filter(nevra="httpd-2.2.10-1.x86_64")
        self.assertEqual(len(q), 0)

        # Provides: $name matches with modular RPM $name -> exclude
        q = self.base.sack.query().filter(nevra="httpd-provides-name-3.0-1.x86_64")
        self.assertEqual(len(q), 0)

        # Provides: $name = ... matches with modular RPM $name -> exclude
        q = self.base.sack.query().filter(nevra="httpd-provides-name-version-release-3.0-1.x86_64")
        self.assertEqual(len(q), 0)
