# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf
import libcomps

from .common import TestCase


class MockLangs():
    def get(self):
        return []


class DnfCompsApiTest(TestCase):
    def test_conditional(self):
        # dnf.comps.CONDITIONAL
        self.assertHasAttr(dnf.comps, "CONDITIONAL")
        self.assertHasType(dnf.comps.CONDITIONAL, int)

    def test_default(self):
        # dnf.comps.DEFAULT
        self.assertHasAttr(dnf.comps, "DEFAULT")
        self.assertHasType(dnf.comps.DEFAULT, int)

    def test_mandatory(self):
        # dnf.comps.MANDATORY
        self.assertHasAttr(dnf.comps, "MANDATORY")
        self.assertHasType(dnf.comps.MANDATORY, int)

    def test_optional(self):
        # dnf.comps.OPTIONAL
        self.assertHasAttr(dnf.comps, "OPTIONAL")
        self.assertHasType(dnf.comps.OPTIONAL, int)

    def test_category(self):
        # dnf.comps.Category
        self.assertHasAttr(dnf.comps, "Category")
        self.assertHasType(dnf.comps.Category, object)

    def test_category_init(self):
        libcomps_category = libcomps.Category("id", "name", "description")
        _ = dnf.comps.Category(iobj=libcomps_category, langs=None, group_factory=None)

    def test_category_id(self):
        # dnf.comps.Category.id
        libcomps_category = libcomps.Category("id", "name", "description")
        category = dnf.comps.Category(iobj=libcomps_category, langs=None, group_factory=None)

        self.assertHasAttr(category, "id")
        self.assertHasType(category.id, str)

    def test_category_name(self):
        # dnf.comps.Category.name
        libcomps_category = libcomps.Category("id", "name", "description")
        category = dnf.comps.Category(iobj=libcomps_category, langs=None, group_factory=None)

        self.assertHasAttr(category, "name")
        self.assertHasType(category.name, str)

    def test_category_ui_name(self):
        # dnf.comps.Category.ui_name
        libcomps_category = libcomps.Category("id", "name", "description")
        langs = MockLangs()
        category = dnf.comps.Category(iobj=libcomps_category, langs=langs, group_factory=None)

        self.assertHasAttr(category, "ui_name")
        self.assertHasType(category.ui_name, str)

    def test_category_ui_description(self):
        # dnf.comps.Category.ui_description
        libcomps_category = libcomps.Category("id", "name", "description")
        langs = MockLangs()
        category = dnf.comps.Category(iobj=libcomps_category, langs=langs, group_factory=None)

        self.assertHasAttr(category, "ui_description")
        self.assertHasType(category.ui_description, str)

    def test_environment(self):
        # dnf.comps.Environment
        self.assertHasAttr(dnf.comps, "Environment")
        self.assertHasType(dnf.comps.Environment, object)

    def test_environment_init(self):
        libcomps_environment = libcomps.Environment("id", "name", "description")
        _ = dnf.comps.Environment(iobj=libcomps_environment, langs=None, group_factory=None)

    def test_environment_id(self):
        # dnf.comps.Environment.id
        libcomps_environment = libcomps.Environment("id", "name", "description")
        environment = dnf.comps.Environment(iobj=libcomps_environment, langs=None, group_factory=None)

        self.assertHasAttr(environment, "id")
        self.assertHasType(environment.id, str)

    def test_environment_name(self):
        # dnf.comps.Environment.name
        libcomps_environment = libcomps.Environment("id", "name", "description")
        environment = dnf.comps.Environment(iobj=libcomps_environment, langs=None, group_factory=None)

        self.assertHasAttr(environment, "name")
        self.assertHasType(environment.name, str)

    def test_environment_ui_name(self):
        # dnf.comps.Environment.ui_name
        libcomps_environment = libcomps.Environment("id", "name", "description")
        langs = MockLangs()
        environment = dnf.comps.Environment(iobj=libcomps_environment, langs=langs, group_factory=None)

        self.assertHasAttr(environment, "ui_name")
        self.assertHasType(environment.ui_name, str)

    def test_environment_ui_description(self):
        # dnf.comps.Environment.ui_description
        libcomps_environment = libcomps.Environment("id", "name", "description")
        langs = MockLangs()
        environment = dnf.comps.Environment(iobj=libcomps_environment, langs=langs, group_factory=None)

        self.assertHasAttr(environment, "ui_description")
        self.assertHasType(environment.ui_description, str)

    def test_group(self):
        # dnf.comps.Group
        self.assertHasAttr(dnf.comps, "Group")
        self.assertHasType(dnf.comps.Group, object)

    def test_group_init(self):
        libcomps_group = libcomps.Group("id", "name", "description")
        _ = dnf.comps.Group(iobj=libcomps_group, langs=None, pkg_factory=None)

    def test_group_id(self):
        # dnf.comps.Group.id
        libcomps_group = libcomps.Group("id", "name", "description")
        group = dnf.comps.Group(iobj=libcomps_group, langs=None, pkg_factory=None)

        self.assertHasAttr(group, "id")
        self.assertHasType(group.id, str)

    def test_group_name(self):
        # dnf.comps.Group.name
        libcomps_group = libcomps.Group("id", "name", "description")
        group = dnf.comps.Group(iobj=libcomps_group, langs=None, pkg_factory=None)

        self.assertHasAttr(group, "name")
        self.assertHasType(group.name, str)

    def test_group_ui_name(self):
        # dnf.comps.Group.ui_name
        libcomps_group = libcomps.Group("id", "name", "description")
        langs = MockLangs()
        group = dnf.comps.Group(iobj=libcomps_group, langs=langs, pkg_factory=None)

        self.assertHasAttr(group, "ui_name")
        self.assertHasType(group.ui_name, str)

    def test_group_ui_description(self):
        # dnf.comps.Group.ui_description
        libcomps_group = libcomps.Group("id", "name", "description")
        langs = MockLangs()
        group = dnf.comps.Group(iobj=libcomps_group, langs=langs, pkg_factory=None)

        self.assertHasAttr(group, "ui_description")
        self.assertHasType(group.ui_description, str)

    def test_group_packages_iter(self):
        # dnf.comps.Group.packages_iter
        libcomps_group = libcomps.Group("id", "name", "description")
        group = dnf.comps.Group(libcomps_group, None, lambda x: x)
        group.packages_iter()

    def test_package(self):
        # dnf.comps.Package
        self.assertHasAttr(dnf.comps, "Package")
        self.assertHasType(dnf.comps.Package, object)

    def test_package_init(self):
        libcomps_package = libcomps.Package()
        _ = dnf.comps.Package(ipkg=libcomps_package)

    def test_package_name(self):
        # dnf.comps.Package.name
        libcomps_package = libcomps.Package()
        libcomps_package.name = "name"
        package = dnf.comps.Package(libcomps_package)

        self.assertHasAttr(package, "name")
        self.assertHasType(package.name, str)

    def test_package_option_type(self):
        # dnf.comps.Package.option_type
        libcomps_package = libcomps.Package()
        libcomps_package.type = 0
        package = dnf.comps.Package(libcomps_package)

        self.assertHasAttr(package, "option_type")
        self.assertHasType(package.option_type, int)

    def test_comps(self):
        # dnf.comps.Comps
        self.assertHasAttr(dnf.comps, "Comps")
        self.assertHasType(dnf.comps.Comps, object)

    def test_comps_init(self):
        _ = dnf.comps.Comps()

    def test_comps_categories(self):
        # dnf.comps.Comps.categories
        comps = dnf.comps.Comps()

        self.assertHasAttr(comps, "categories")
        self.assertHasType(comps.categories, list)

    def test_comps_category_by_pattern(self):
        # dnf.comps.Comps.category_by_pattern
        comps = dnf.comps.Comps()
        comps.category_by_pattern(pattern="foo", case_sensitive=False)

    def test_comps_categories_by_pattern(self):
        # dnf.comps.Comps.categories_by_pattern
        comps = dnf.comps.Comps()
        comps.categories_by_pattern(pattern="foo", case_sensitive=False)

    def test_comps_categories_iter(self):
        # dnf.comps.Comps.categories_iter
        comps = dnf.comps.Comps()
        comps.categories_iter()

    def test_comps_environments(self):
        # dnf.comps.Comps.environments
        comps = dnf.comps.Comps()

        self.assertHasAttr(comps, "environments")
        self.assertHasType(comps.environments, list)

    def test_comps_environment_by_pattern(self):
        # dnf.comps.Comps.environment_by_pattern
        comps = dnf.comps.Comps()
        comps.environment_by_pattern(pattern="foo", case_sensitive=False)

    def test_comps_environments_by_pattern(self):
        # dnf.comps.Comps.environments_by_pattern
        comps = dnf.comps.Comps()
        comps.environments_by_pattern(pattern="foo", case_sensitive=False)

    def test_comps_environments_iter(self):
        # dnf.comps.Comps.environments_iter
        comps = dnf.comps.Comps()
        comps.environments_iter()

    def test_comps_groups(self):
        # dnf.comps.Comps.groups
        comps = dnf.comps.Comps()

        self.assertHasAttr(comps, "groups")
        self.assertHasType(comps.groups, list)

    def test_comps_group_by_pattern(self):
        # dnf.comps.Comps.group_by_pattern
        comps = dnf.comps.Comps()
        comps.group_by_pattern(pattern="foo", case_sensitive=False)

    def test_comps_groups_by_pattern(self):
        # dnf.comps.Comps.groups_by_pattern
        comps = dnf.comps.Comps()
        comps.groups_by_pattern(pattern="foo", case_sensitive=False)

    def test_comps_groups_iter(self):
        # dnf.comps.Comps.groups_iter
        comps = dnf.comps.Comps()
        comps.groups_iter()
