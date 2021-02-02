# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf
import dnf.cli.demand

from .common import TestCase


class DnfCliDemandApiTest(TestCase):
    def setUp(self):
        self.demand_sheet = dnf.cli.demand.DemandSheet()

    def test_demand_sheet(self):
        # dnf.cli.demand.DemandSheet
        self.assertHasAttr(dnf.cli.demand, "DemandSheet")
        self.assertHasType(dnf.cli.demand.DemandSheet, object)

    def test_init(self):
        _ = dnf.cli.demand.DemandSheet()

    def test_allow_erasing(self):
        # dnf.cli.demand.DemandSheet.allow_erasing
        self.assertHasAttr(self.demand_sheet, "allow_erasing")
        self.assertHasType(self.demand_sheet.allow_erasing, bool)

    def test_available_repos(self):
        # dnf.cli.demand.DemandSheet.available_repos
        self.assertHasAttr(self.demand_sheet, "available_repos")
        self.assertHasType(self.demand_sheet.available_repos, bool)

    def test_resolving(self):
        # dnf.cli.demand.DemandSheet.resolving
        self.assertHasAttr(self.demand_sheet, "resolving")
        self.assertHasType(self.demand_sheet.resolving, bool)

    def test_root_user(self):
        # dnf.cli.demand.DemandSheet.root_user
        self.assertHasAttr(self.demand_sheet, "root_user")
        self.assertHasType(self.demand_sheet.root_user, bool)

    def test_sack_activation(self):
        # dnf.cli.demand.DemandSheet.sack_activation
        self.assertHasAttr(self.demand_sheet, "sack_activation")
        self.assertHasType(self.demand_sheet.sack_activation, bool)

    def test_load_system_repo(self):
        # dnf.cli.demand.DemandSheet.load_system_repo
        self.assertHasAttr(self.demand_sheet, "load_system_repo")
        self.assertHasType(self.demand_sheet.load_system_repo, bool)

    def test_success_exit_status(self):
        # dnf.cli.demand.DemandSheet.success_exit_status
        self.assertHasAttr(self.demand_sheet, "success_exit_status")
        self.assertHasType(self.demand_sheet.success_exit_status, int)

    def test_cacheonly(self):
        # dnf.cli.demand.DemandSheet.cacheonly
        self.assertHasAttr(self.demand_sheet, "cacheonly")
        self.assertHasType(self.demand_sheet.cacheonly, bool)

    def test_fresh_metadata(self):
        # dnf.cli.demand.DemandSheet.fresh_metadata
        self.assertHasAttr(self.demand_sheet, "fresh_metadata")
        self.assertHasType(self.demand_sheet.fresh_metadata, bool)

    def test_freshest_metadata(self):
        # dnf.cli.demand.DemandSheet.freshest_metadata
        self.assertHasAttr(self.demand_sheet, "freshest_metadata")
        self.assertHasType(self.demand_sheet.freshest_metadata, bool)

    def test_changelogs(self):
        # dnf.cli.demand.DemandSheet.changelogs
        self.assertHasAttr(self.demand_sheet, "changelogs")
        self.assertHasType(self.demand_sheet.changelogs, bool)

    def test_transaction_display(self):
        # dnf.cli.demand.DemandSheet.transaction_display
        self.assertHasAttr(self.demand_sheet, "transaction_display")
        self.assertHasType(self.demand_sheet.changelogs, object)

    def test_plugin_filtering_enabled(self):
        # dnf.cli.demand.DemandSheet.plugin_filtering_enabled
        self.assertHasAttr(self.demand_sheet, "plugin_filtering_enabled")
        self.assertHasType(self.demand_sheet.plugin_filtering_enabled, object)
