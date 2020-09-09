# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf
import dnf.cli.cli

from .common import TestCase


class DnfCliCliApiTest(TestCase):
    def setUp(self):
        base = dnf.Base()
        self.cli = dnf.cli.cli.Cli(base=base)

    def test_cli(self):
        # dnf.cli.cli.Cli
        self.assertHasAttr(dnf.cli.cli, "Cli")
        self.assertHasType(dnf.cli.cli.Cli, object)

    def test_init(self):
        base = dnf.Base()
        _ = dnf.cli.cli.Cli(base=base)

    def test_demands(self):
        # dnf.cli.cli.Cli.demands
        self.assertHasAttr(self.cli, "demands")
        self.assertHasType(self.cli.demands, dnf.cli.demand.DemandSheet)

    def test_redirect_logger(self):
        # dnf.cli.cli.Cli.redirect_logger
        self.assertHasAttr(self.cli, "redirect_logger")
        self.cli.redirect_logger(stdout=None, stderr=None)

    def test_register_command(self):
        # dnf.cli.cli.Cli.register_command
        self.assertHasAttr(self.cli, "register_command")
        command_cls = dnf.cli.commands.Command(cli=self.cli)
        self.cli.register_command(command_cls=command_cls)
