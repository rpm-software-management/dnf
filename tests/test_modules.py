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
import sys
import tempfile
import unittest

import hawkey
import modulemd

import dnf.conf
from dnf.modules import RepoModuleDict, RepoModule, RepoModuleStream, RepoModuleVersion
from dnf.modules import ModuleSubject, NSVAP


MODULES_DIR = os.path.join(os.path.dirname(__file__), "modules/etc/dnf/modules.d")
REPOS_DIR = os.path.join(os.path.dirname(__file__), "modules/modules")

# with profile
MODULE_NSVAP = "module-name-stream-1.x86_64/profile"
MODULE_NSVP = "module-name-stream-1/profile"
MODULE_NSP = "module-name-stream/profile"
MODULE_NP = "module-name/profile"
MODULE_NAP = "module-name.x86_64/profile"

# without profile
MODULE_NSVA = "module-name-stream-1.x86_64"
MODULE_NSV = "module-name-stream-1"
MODULE_NS = "module-name-stream"
MODULE_N = "module-name"
MODULE_NA = "module-name.x86_64"


class ModuleSubjectTest(unittest.TestCase):

    def test_nsvap(self):
        subj = ModuleSubject(MODULE_NSVAP)
        result = list(subj.get_nsvap_possibilities(forms=hawkey.FORM_NEVRA))
        self.assertEqual(len(result), 1)
        actual = result[0]
        expected = NSVAP(name="module-name", stream="stream", version="1", arch="x86_64", profile="profile")
        self.assertEqual(actual, expected)

    def test_nsva(self):
        subj = ModuleSubject(MODULE_NSVA)
        result = list(subj.get_nsvap_possibilities(forms=hawkey.FORM_NEVRA))
        self.assertEqual(len(result), 1)
        actual = result[0]
        expected = NSVAP(name="module-name", stream="stream", version="1", arch="x86_64", profile=None)
        self.assertEqual(actual, expected)

        # empty profile spec -> no profile
        subj = ModuleSubject(MODULE_NSVA + "/")
        result = list(subj.get_nsvap_possibilities(forms=hawkey.FORM_NEVRA))
        self.assertEqual(len(result), 1)
        actual = result[0]
        expected = NSVAP(name="module-name", stream="stream", version="1", arch="x86_64", profile=None)
        self.assertEqual(actual, expected)

    def test_nsvp(self):
        subj = ModuleSubject(MODULE_NSVAP)
        result = list(subj.get_nsvap_possibilities(forms=hawkey.FORM_NEVR))
        self.assertEqual(len(result), 0)
        # module version "1.x86_64" is not valid (while it is a valid RPM release)

    def test_nsv(self):
        subj = ModuleSubject(MODULE_NSVA)
        result = list(subj.get_nsvap_possibilities(forms=hawkey.FORM_NEVR))
        self.assertEqual(len(result), 0)
        # module version "1.x86_64" is not valid (while it is a valid RPM release)

    def test_nsp(self):
        subj = ModuleSubject(MODULE_NSVAP)
        result = list(subj.get_nsvap_possibilities(forms=hawkey.FORM_NEV))
        self.assertEqual(len(result), 1)
        actual = result[0]
        expected = NSVAP(name="module-name-stream", stream="1.x86_64", version=None, arch=None, profile="profile")
        self.assertEqual(actual, expected)

        subj = ModuleSubject(MODULE_NSP)
        result = list(subj.get_nsvap_possibilities(forms=hawkey.FORM_NEV))
        self.assertEqual(len(result), 1)
        actual = result[0]
        expected = NSVAP(name="module-name", stream="stream", version=None, arch=None, profile="profile")
        self.assertEqual(actual, expected)

    def test_ns(self):
        subj = ModuleSubject(MODULE_NSVA)
        result = list(subj.get_nsvap_possibilities(forms=hawkey.FORM_NEV))
        self.assertEqual(len(result), 1)
        actual = result[0]
        expected = NSVAP(name="module-name-stream", stream="1.x86_64", version=None, arch=None, profile=None)
        self.assertEqual(actual, expected)

        subj = ModuleSubject(MODULE_NS)
        result = list(subj.get_nsvap_possibilities(forms=hawkey.FORM_NEV))
        self.assertEqual(len(result), 1)
        actual = result[0]
        expected = NSVAP(name="module-name", stream="stream", version=None, arch=None, profile=None)
        self.assertEqual(actual, expected)

    def test_nap(self):
        subj = ModuleSubject(MODULE_NAP)
        result = list(subj.get_nsvap_possibilities(forms=hawkey.FORM_NA))
        self.assertEqual(len(result), 1)
        actual = result[0]
        expected = NSVAP(name="module-name", stream=None, version=None, arch="x86_64", profile="profile")
        self.assertEqual(actual, expected)

    def test_na(self):
        subj = ModuleSubject(MODULE_NA)
        result = list(subj.get_nsvap_possibilities(forms=hawkey.FORM_NA))
        self.assertEqual(len(result), 1)
        actual = result[0]
        expected = NSVAP(name="module-name", stream=None, version=None, arch="x86_64", profile=None)
        self.assertEqual(actual, expected)

    def test_np(self):
        subj = ModuleSubject(MODULE_NP)
        result = list(subj.get_nsvap_possibilities(forms=hawkey.FORM_NAME))
        self.assertEqual(len(result), 1)
        actual = result[0]
        expected = NSVAP(name="module-name", stream=None, version=None, arch=None, profile="profile")
        self.assertEqual(actual, expected)

    def test_n(self):
        subj = ModuleSubject(MODULE_N)
        result = list(subj.get_nsvap_possibilities(forms=hawkey.FORM_NAME))
        self.assertEqual(len(result), 1)
        actual = result[0]
        expected = NSVAP(name="module-name", stream=None, version=None, arch=None, profile=None)
        self.assertEqual(actual, expected)

    def test_all(self):
        subj = ModuleSubject(MODULE_NSVAP)
        result = list(subj.get_nsvap_possibilities())
        self.assertEqual(len(result), 4)

        actual = result[0]
        expected = NSVAP(name="module-name", stream="stream", version="1", arch="x86_64", profile="profile")
        self.assertEqual(actual, expected)

        actual = result[1]
        expected = NSVAP(name="module-name-stream", stream="1.x86_64", version=None, arch=None, profile="profile")
        self.assertEqual(actual, expected)

        actual = result[2]
        expected = NSVAP(name="module-name-stream-1", stream=None, version=None, arch="x86_64", profile="profile")
        self.assertEqual(actual, expected)

        actual = result[3]
        expected = NSVAP(name="module-name-stream-1.x86_64", stream=None, version=None, arch=None, profile="profile")
        self.assertEqual(actual, expected)


class RepoModuleDictTest(unittest.TestCase):

    def _create_mmd(self, name, stream, version, rpms=None, profiles=None):
        rpms = rpms or []
        profiles = profiles or {}  # profile_name: {pkg_format: [pkg_names]}

        mmd = modulemd.ModuleMetadata()
        mmd.name = name
        mmd.stream = stream
        mmd.version = version
        mmd.add_module_license("LGPLv2")
        mmd.summary = "Fake module"
        mmd.description = mmd.summary
        for rpm in rpms:
            mmd.components.add_rpm(rpm.rsplit("-", 2)[0], "")
            mmd.artifacts.add_rpm(rpm[:-4])
        for profile_name in profiles:
            profile = modulemd.ModuleProfile()
            profile.rpms.update(profiles[profile_name].get("rpms", []))
            mmd.profiles["default"] = profile
        return mmd

    def test_find_module_version(self):
        rmd = RepoModuleDict(None)

        mmd = self._create_mmd(name="module-name", stream="stream", version=1, profiles={"default": {}})
        rmv = RepoModuleVersion(mmd, None, None)
        rmd.add(rmv)

        mmd = self._create_mmd(name="module-name", stream="stream", version=2, profiles={"default": {}})
        rmv = RepoModuleVersion(mmd, None, None)
        rmd.add(rmv)

        mmd = self._create_mmd(name="module-name", stream="enabled_stream", version=1, profiles={"default": {}})
        rmv = RepoModuleVersion(mmd, None, None)
        rmd.add(rmv)

        mmd = self._create_mmd(name="module-name", stream="default_stream", version=1, profiles={"default": {}})
        rmv = RepoModuleVersion(mmd, None, None)
        rmd.add(rmv)

        # no default, no active -> can't find stream automatically
        rmv = rmd.find_module_version(name="module-name")
        self.assertEqual(rmv, None)

        # set enabled stream
        conf = dnf.conf.ModuleConf()
        conf.enabled = 1
        conf.stream = "enabled_stream"
        rmd["module-name"].conf = conf

        # stream provided by user
        rmv = rmd.find_module_version(name="module-name", stream="stream")
        self.assertEqual(rmv.full_version, "module-name-stream-2")

        # stream and version provided by user
        rmv = rmd.find_module_version(name="module-name", stream="stream", version=1)
        self.assertEqual(rmv.full_version, "module-name-stream-1")

        # stream == active stream
        rmv = rmd.find_module_version(name="module-name")
        self.assertEqual(rmv.full_version, "module-name-enabled_stream-1")

        # stream == default stream
        conf.enabled = 0
        rmv = rmd.find_module_version(name="module-name")
        # TODO: default from system profile
        # self.assertEqual(rmv.full_version, "module-name-default_stream-1")


class ModuleTest(unittest.TestCase):

    def assertInstalls(self, nevras):
        expected = sorted(set(nevras))
        actual = sorted(set([str(i) for i in self.base._goal.list_installs()]))
        self.assertEqual(expected, actual)

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix = "dnf_test_")
        self.conf = dnf.conf.Conf()
        self.conf.cachedir = os.path.join(self.tmpdir, "cache")
        self.conf.installroot = os.path.join(self.tmpdir, "root")
        self.conf.modulesdir = MODULES_DIR
        self.conf.substitutions["arch"] = "x86_64"
        self.conf.substitutions["basearch"] = dnf.rpm.basearch(self.conf.substitutions["arch"])
        self.base = dnf.Base(conf=self.conf)

        self._add_module_repo("_all")
        self.base.fill_sack(load_system_repo=False, load_available_repos=True)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _add_module_repo(self, repo_id, modules=True):
        url = "file://" + os.path.join(REPOS_DIR, repo_id, self.conf.substitutions["arch"])
        repo = self.base.repos.add_new_repo(repo_id, self.base.conf, baseurl=[url], modules=modules)
        return repo

    # dnf module enable

    def test_enable_name(self):
        # use default stream
        self.base.repo_module_dict.enable("httpd", assumeyes=True)

    def test_enable_name_stream(self):
        self.base.repo_module_dict.enable("httpd-2.4", assumeyes=True)
        # TODO: test conf presence and content

    def test_enable_pkgspec(self):
        pass

    def test_enable_invalid(self):
        self.base.repo_module_dict.enable("httpd-invalid", assumeyes=True)
        # TODO: exit code? exception?

    def test_enable_different_stream(self):
        pass

    def test_enable_different_stream_missing_profile(self):
        pass

    # dnf module disable

    def test_disable_name(self):
        pass

    def test_disable_name_stream(self):
        pass

    def test_disable_pkgspec(self):
        pass

    def test_disable_invalid(self):
        pass

    # dnf module lock

    def test_lock_name(self):
        pass

    def test_lock_name_stream(self):
        pass

    def test_lock_pkgspec(self):
        pass

    def test_lock_invalid(self):
        pass

    # dnf module unlock

    def test_unlock_name(self):
        pass

    def test_unlock_name_stream(self):
        pass

    def test_unlock_pkgspec(self):
        pass

    def test_unlock_invalid(self):
        pass

    # dnf module info

    def test_info_name(self):
        pass

    def test_info_name_stream(self):
        pass

    def test_info_pkgspec(self):
        pass

    # dnf module list

    def test_list(self):
        # show latest module versions
        pass

    def test_list_all(self):
        # show all module versions
        pass

    def test_list_enabled(self):
        pass

    def test_list_installed(self):
        pass

    # dnf module install / dnf install @

    def test_install_profile_latest(self):
        self.test_enable_name_stream()
        self.base.repo_module_dict.install(["httpd/default"])
        self.base._goal.run()
        expected = [
            "basesystem-11-3.noarch",
            "filesystem-3.2-40.x86_64",
            "glibc-2.25.90-2.x86_64",
            "glibc-common-2.25.90-2.x86_64",
            "httpd-2.4.25-8.x86_64",
            "libnghttp2-1.21.1-1.x86_64",
        ]
        self.assertInstalls(expected)

    def test_install_profile(self):
        self.test_enable_name_stream()
        self.base.repo_module_dict.install(["httpd-2.4-1/default"])
        self.base._goal.run()
        expected = [
            "basesystem-11-3.noarch",
            "filesystem-3.2-40.x86_64",
            "glibc-2.25.90-2.x86_64",
            "glibc-common-2.25.90-2.x86_64",
            "httpd-2.4.25-7.x86_64",
            "libnghttp2-1.21.1-1.x86_64",
        ]
        self.assertInstalls(expected)

    def test_install_two_profiles(self):
        self.test_enable_name_stream()
        self.base.repo_module_dict.install(["httpd-2.4-1/default", "httpd-2.4-1/doc"])
        self.base._goal.run()
        expected = [
            "basesystem-11-3.noarch",
            "filesystem-3.2-40.x86_64",
            "glibc-2.25.90-2.x86_64",
            "glibc-common-2.25.90-2.x86_64",
            "httpd-2.4.25-7.x86_64",
            "httpd-doc-2.4.25-7.x86_64",
            "libnghttp2-1.21.1-1.x86_64",
        ]
        self.assertInstalls(expected)

    def test_install_two_profiles_different_versions(self):
        self.test_enable_name_stream()
        self.base.repo_module_dict.install(["httpd-2.4-1/default", "httpd-2.4-2/doc"])
        self.base._goal.run()
        expected = [
            "basesystem-11-3.noarch",
            "filesystem-3.2-40.x86_64",
            "glibc-2.25.90-2.x86_64",
            "glibc-common-2.25.90-2.x86_64",
            "httpd-2.4.25-7.x86_64",
            "httpd-doc-2.4.25-8.x86_64",
            "libnghttp2-1.21.1-1.x86_64",
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
        self.base.repo_module_dict.install(["httpd-2.4-2/doc"])
        self.base._goal.run()
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
