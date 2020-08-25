# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import os

import dnf
import libdnf

from .common import TestCase


class DnfModulePackageApiTest(TestCase):
    def setUp(self):
        self.base = dnf.Base()
        repo = self.base.repos.add_new_repo(
            'api-module-test-repo', self.base.conf,
            baseurl=[os.path.join(os.path.dirname(__file__), "../modules/modules/_all/x86_64/")]
        )
        self.base.fill_sack(load_system_repo=False, load_available_repos=True)
        moduleBase = dnf.module.module_base.ModuleBase(self.base)
        modulePackages, nsvcap = moduleBase.get_modules('*')
        self.modulePackage = modulePackages[0]

    def tearDown(self):
        self.base.close()

    def test_getName(self):
        # ModulePackage.getName()
        self.assertHasAttr(self.modulePackage, "getName")
        self.modulePackage.getName()

    def test_getStream(self):
        # ModulePackage.getStream()
        self.assertHasAttr(self.modulePackage, "getStream")
        self.modulePackage.getStream()

    def test_getVersion(self):
        # ModulePackage.getVersion()
        self.assertHasAttr(self.modulePackage, "getVersion")
        self.modulePackage.getVersion()

    def test_getVersionNum(self):
        # ModulePackage.getVersionNum()
        self.assertHasAttr(self.modulePackage, "getVersionNum")
        self.modulePackage.getVersionNum()

    def test_getContext(self):
        # ModulePackage.getContext()
        self.assertHasAttr(self.modulePackage, "getContext")
        self.modulePackage.getContext()

    def test_getArch(self):
        # ModulePackage.getArch()
        self.assertHasAttr(self.modulePackage, "getArch")
        self.modulePackage.getArch()

    def test_getNameStream(self):
        # ModulePackage.getNameStream()
        self.assertHasAttr(self.modulePackage, "getNameStream")
        self.modulePackage.getNameStream()

    def test_getNameStreamVersion(self):
        # ModulePackage.getNameStreamVersion()
        self.assertHasAttr(self.modulePackage, "getNameStreamVersion")
        self.modulePackage.getNameStreamVersion()

    def test_getFullIdentifier(self):
        # ModulePackage.getFullIdentifier()
        self.assertHasAttr(self.modulePackage, "getFullIdentifier")
        self.modulePackage.getFullIdentifier()

    def test_getProfiles(self):
        # ModulePackage.getProfiles()
        self.assertHasAttr(self.modulePackage, "getProfiles")
        self.modulePackage.getProfiles("test_name_argument")

    def test_getSummary(self):
        # ModulePackage.getSummary()
        self.assertHasAttr(self.modulePackage, "getSummary")
        self.modulePackage.getSummary()

    def test_getDescription(self):
        # ModulePackage.getDescription()
        self.assertHasAttr(self.modulePackage, "getDescription")
        self.modulePackage.getDescription()

    def test_getRepoID(self):
        # ModulePackage.getRepoID()
        self.assertHasAttr(self.modulePackage, "getRepoID")
        self.modulePackage.getRepoID()

    def test_getArtifacts(self):
        # ModulePackage.getArtifacts()
        self.assertHasAttr(self.modulePackage, "getArtifacts")
        self.modulePackage.getArtifacts()

    def test_getModuleDependencies(self):
        # ModulePackage.getModuleDependencies()
        self.assertHasAttr(self.modulePackage, "getModuleDependencies")
        self.modulePackage.getModuleDependencies()

    def test_getYaml(self):
        # ModulePackage.getYaml()
        self.assertHasAttr(self.modulePackage, "getYaml")
        self.modulePackage.getYaml()


class DnfModuleProfileApiTest(TestCase):
    def test_moduleProfile_getName(self):
        # ModuleProfile.getName()
        moduleProfile = libdnf.module.ModuleProfile()
        self.assertHasAttr(moduleProfile, "getName")
        moduleProfile.getName()

    def test_moduleProfile_getDescription(self):
        # ModuleProfile.getDescription()
        moduleProfile = libdnf.module.ModuleProfile()
        self.assertHasAttr(moduleProfile, "getDescription")
        moduleProfile.getDescription()

    def test_moduleProfile_getContent(self):
        # ModuleProfile.getContent()
        moduleProfile = libdnf.module.ModuleProfile()
        self.assertHasAttr(moduleProfile, "getContent")
        moduleProfile.getContent()


class DnfModuleDependenciesApiTest(TestCase):
    def test_moduleDependencies_getRequires(self):
        # ModuleDependencies.getRequires()
        moduleDependecy = libdnf.module.ModuleDependencies()
        self.assertHasAttr(moduleDependecy, "getRequires")
        moduleDependecy.getRequires()
