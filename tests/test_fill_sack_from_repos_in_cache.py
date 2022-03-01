# -*- coding: utf-8 -*-

# Copyright (C) 2012-2021 Red Hat, Inc.
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
import tempfile
import glob
import shutil
import unittest

import dnf.exceptions
import dnf.repo
import dnf.sack

import hawkey

import tests.support
from tests.support import mock

TEST_REPO_NAME = "test-repo"


class FillSackFromReposInCacheTest(unittest.TestCase):
    def _create_cache_for_repo(self, repopath, tmpdir, repo_name=TEST_REPO_NAME):
        conf = dnf.conf.MainConf()
        conf.cachedir = os.path.join(tmpdir, "cache")
        conf.installroot = tmpdir
        conf.persistdir = os.path.join(conf.installroot, conf.persistdir.lstrip("/"))
        conf.substitutions["arch"] = "x86_64"
        conf.substitutions["basearch"] = dnf.rpm.basearch(conf.substitutions["arch"])

        base = dnf.Base(conf=conf)

        repoconf = dnf.repo.Repo(repo_name, base.conf)
        repoconf.baseurl = repopath
        repoconf.enable()

        base.repos.add(repoconf)

        base.fill_sack(load_system_repo=False)
        base.close()

    def _setUp_from_repo_path(self, original_repo_path):
        repo_copy_path = os.path.join(self.tmpdir, "repo")
        shutil.copytree(original_repo_path, repo_copy_path)

        self._create_cache_for_repo(repo_copy_path, self.tmpdir)

        # Just to be sure remove repo (it shouldn't be used)
        shutil.rmtree(repo_copy_path)

        # Prepare base for the actual test
        conf = dnf.conf.MainConf()
        conf.cachedir = os.path.join(self.tmpdir, "cache")
        conf.installroot = self.tmpdir
        conf.persistdir = os.path.join(conf.installroot, conf.persistdir.lstrip("/"))
        conf.substitutions["arch"] = "x86_64"
        conf.substitutions["basearch"] = dnf.rpm.basearch(conf.substitutions["arch"])
        self.test_base = dnf.Base(conf=conf)
        repoconf = dnf.repo.Repo(TEST_REPO_NAME, conf)
        repoconf.baseurl = repo_copy_path
        repoconf.enable()
        self.test_base.repos.add(repoconf)

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="dnf_test_")
        self.test_base = None

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        if self.test_base:
            self.test_base.close()

    def test_with_solv_solvx_repomd(self):
        self._setUp_from_repo_path(os.path.join(os.path.abspath(os.path.dirname(__file__)), "repos/rpm"))

        # Remove xml metadata except repomd
        # repomd.xml is not compressed and doesn't end with .gz
        repodata_without_repomd = glob.glob(os.path.join(self.tmpdir, "cache/test-repo-*/repodata/*.gz"))
        for f in repodata_without_repomd:
            os.remove(f)

        # Now we only have cache with just solv, solvx files and repomd.xml

        self.test_base.fill_sack_from_repos_in_cache(load_system_repo=False)

        q = self.test_base.sack.query()
        packages = q.run()
        self.assertEqual(len(packages), 9)
        self.assertEqual(packages[0].evr, "4-4")

        # Use *-updateinfo.solvx
        adv_pkgs = q.get_advisory_pkgs(hawkey.LT | hawkey.EQ | hawkey.GT)
        adv_titles = set()
        for pkg in adv_pkgs:
            adv_titles.add(pkg.get_advisory(self.test_base.sack).title)
        self.assertEqual(len(adv_titles), 3)

    def test_with_just_solv_repomd(self):
        self._setUp_from_repo_path(os.path.join(os.path.abspath(os.path.dirname(__file__)), "repos/rpm"))

        # Remove xml metadata except repomd
        # repomd.xml is not compressed and doesn't end with .gz
        repodata_without_repomd = glob.glob(os.path.join(self.tmpdir, "cache/test-repo-*/repodata/*.gz"))
        for f in repodata_without_repomd:
            os.remove(f)

        # Remove solvx files
        solvx = glob.glob(os.path.join(self.tmpdir, "cache/*.solvx"))
        for f in solvx:
            os.remove(f)

        # Now we only have cache with just solv files and repomd.xml

        self.test_base.fill_sack_from_repos_in_cache(load_system_repo=False)

        q = self.test_base.sack.query()
        packages = q.run()
        self.assertEqual(len(packages), 9)
        self.assertEqual(packages[0].evr, "4-4")

        # No *-updateinfo.solvx -> we get no advisory packages
        adv_pkgs = q.get_advisory_pkgs(hawkey.LT | hawkey.EQ | hawkey.GT)
        self.assertEqual(len(adv_pkgs), 0)

    def test_with_xml_metadata(self):
        self._setUp_from_repo_path(os.path.join(os.path.abspath(os.path.dirname(__file__)), "repos/rpm"))

        # Remove all solv and solvx files
        solvx = glob.glob(os.path.join(self.tmpdir, "cache/*.solv*"))
        for f in solvx:
            os.remove(f)

        # Now we only have cache with just xml metadata

        self.test_base.fill_sack_from_repos_in_cache(load_system_repo=False)

        q = self.test_base.sack.query()
        packages = q.run()
        self.assertEqual(len(packages), 9)
        self.assertEqual(packages[0].evr, "4-4")

    def test_exception_without_repomd(self):
        self._setUp_from_repo_path(os.path.join(os.path.abspath(os.path.dirname(__file__)), "repos/rpm"))

        # Remove xml metadata
        repodata_without_repomd = glob.glob(os.path.join(self.tmpdir, "cache/test-repo-*/repodata/*"))
        for f in repodata_without_repomd:
            os.remove(f)

        # Now we only have cache with just solv and solvx files
        # Since we don't have repomd we cannot verify checksums -> fail (exception)

        self.assertRaises(dnf.exceptions.RepoError,
                          self.test_base.fill_sack_from_repos_in_cache, load_system_repo=False)

    def test_exception_with_just_repomd(self):
        self._setUp_from_repo_path(os.path.join(os.path.abspath(os.path.dirname(__file__)), "repos/rpm"))

        # Remove xml metadata except repomd
        # repomd.xml is not compressed and doesn't end with .gz
        repodata_without_repomd = glob.glob(os.path.join(self.tmpdir, "cache/test-repo-*/repodata/*.gz"))
        for f in repodata_without_repomd:
            os.remove(f)

        # Remove all solv and solvx files
        solvx = glob.glob(os.path.join(self.tmpdir, "cache/*.solv*"))
        for f in solvx:
            os.remove(f)

        # Now we only have cache with just repomd
        # repomd is not enough, it doesn't contain the metadata it self -> fail (exception)

        self.assertRaises(dnf.exceptions.RepoError,
                          self.test_base.fill_sack_from_repos_in_cache, load_system_repo=False)

    def test_exception_with_checksum_mismatch_and_only_repomd(self):
        self._setUp_from_repo_path(os.path.join(os.path.abspath(os.path.dirname(__file__)), "repos/rpm"))
        self._create_cache_for_repo(os.path.join(os.path.abspath(os.path.dirname(__file__)), "repos/drpm"),
                                    self.tmpdir, "drpm-repo")

        # Remove xml metadata except repomd
        # repomd.xml is not compressed and doesn't end with .gz
        repodata_without_repomd = glob.glob(os.path.join(self.tmpdir, "cache/test-repo-*/repodata/*.gz"))
        for f in repodata_without_repomd:
            os.remove(f)

        # Replace solvfile of test-repo with solvfile from drpm-repo which has different data (different checksum)
        shutil.move(os.path.join(self.tmpdir, "cache/drpm-repo.solv"),
                    os.path.join(self.tmpdir, "cache/test-repo.solv"))

        # Now we only have cache with solvx, mismatching solv file and just repomd
        # Since we don't have original xml metadata we cannot regenerate solv -> fail (exception)

        self.assertRaises(dnf.exceptions.RepoError,
                          self.test_base.fill_sack_from_repos_in_cache, load_system_repo=False)

    def test_checksum_mistmatch_regenerates_solv(self):
        self._setUp_from_repo_path(os.path.join(os.path.abspath(os.path.dirname(__file__)), "repos/rpm"))
        self._create_cache_for_repo(os.path.join(os.path.abspath(os.path.dirname(__file__)), "repos/drpm"),
                                    self.tmpdir, "drpm-repo")

        # Replace solvfile of test-repo with solvfile from drpm-repo which has different data (different checksum)
        shutil.move(os.path.join(self.tmpdir, "cache/drpm-repo.solv"),
                    os.path.join(self.tmpdir, "cache/test-repo.solv"))

        # Now we only have cache with solvx, mismatching solv file and xml metadata.
        # Checksum mistmatch causes regeneration of solv file and repo works.

        self.test_base.fill_sack_from_repos_in_cache(load_system_repo=False)

        q = self.test_base.sack.query()
        packages = q.run()
        self.assertEqual(len(packages), 9)
        self.assertEqual(packages[0].evr, "4-4")

    def test_with_modules_yaml(self):
        self._setUp_from_repo_path(os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                                "modules/modules/_all/x86_64"))

        # Now we have full cache (also with modules.yaml)

        self.test_base.fill_sack_from_repos_in_cache(load_system_repo=False)

        q = self.test_base.sack.query()
        packages = q.run()

        pkg_names = []
        for pkg in packages:
            pkg_names.append(pkg.name)

        self.assertEqual(pkg_names, ['grub2', 'httpd', 'httpd', 'httpd-doc', 'httpd-doc', 'httpd-provides-name-doc',
                                     'httpd-provides-name-version-release-doc', 'libnghttp2'])

        self.module_base = dnf.module.module_base.ModuleBase(self.test_base)
        modules, _ = self.module_base._get_modules("base-runtime*")
        self.assertEqual(len(modules), 3)
        self.assertEqual(modules[0].getFullIdentifier(), "base-runtime:f26:1::")

    def test_with_modular_repo_without_modules_yaml(self):
        self._setUp_from_repo_path(os.path.join(os.path.abspath(os.path.dirname(__file__)),
                                                "modules/modules/_all/x86_64"))

        # Remove xml and yaml metadata except repomd
        # repomd.xml is not compressed and doesn't end with .gz
        repodata_without_repomd = glob.glob(os.path.join(self.tmpdir, "cache/test-repo-*/repodata/*.gz"))
        for f in repodata_without_repomd:
            os.remove(f)

        # Now we have just solv, *-filenames.solvx and repomd.xml (modules.yaml are not processed into *-modules.solvx)

        self.test_base.fill_sack_from_repos_in_cache(load_system_repo=False)

        q = self.test_base.sack.query()
        packages = q.run()
        # We have many more packages because they are not hidden by modules
        self.assertEqual(len(packages), 44)
        self.assertEqual(packages[0].evr, "10.0-7")

        self.module_base = dnf.module.module_base.ModuleBase(self.test_base)
        modules, _ = self.module_base._get_modules("*")
        self.assertEqual(len(modules), 0)
