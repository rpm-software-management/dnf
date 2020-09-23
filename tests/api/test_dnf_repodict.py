# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf

import types
from .common import TestCase


class DnfRepodictApiTest(TestCase):
    def setUp(self):
        self.repodict = dnf.repodict.RepoDict()

    def test_init(self):
        _ = dnf.repodict.RepoDict()

    def test_add(self):
        # RepoDict.add
        self.assertHasAttr(self.repodict, "add")
        self.repodict.add(repo=dnf.repo.Repo())

    def test_all(self):
        # RepoDict.all
        self.assertHasAttr(self.repodict, "all")
        self.assertHasType(self.repodict.all(), list)

    def test_add_new_repo(self):
        # RepoDict.add_new_repo
        self.assertHasAttr(self.repodict, "add_new_repo")
        self.assertHasType(
            self.repodict.add_new_repo(
                repoid="r",
                conf=dnf.conf.Conf(),
                baseurl=(""),
                key1="val1",
                key2="val2"
            ), dnf.repo.Repo)

    def test_enable_debug_repos(self):
        # RepoDict.enable_debug_repos
        self.assertHasAttr(self.repodict, "enable_debug_repos")
        self.repodict.enable_debug_repos()

    def test_enable_source_repos(self):
        # RepoDict.enable_source_repos
        self.assertHasAttr(self.repodict, "enable_source_repos")
        self.repodict.enable_source_repos()

    def test_get_matching(self):
        # RepoDict.get_matching
        self.assertHasAttr(self.repodict, "get_matching")
        self.assertHasType(self.repodict.get_matching(key=""), list)

    def test_iter_enabled(self):
        # RepoDict.iter_enabled
        self.assertHasAttr(self.repodict, "iter_enabled")
        self.assertHasType(self.repodict.iter_enabled(), types.GeneratorType)
