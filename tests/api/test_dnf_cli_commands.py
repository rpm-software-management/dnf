# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf
import dnf.cli.commands

from .common import TestCase


class DnfCliCommandsApiTest(TestCase):
    def setUp(self):
        base = dnf.Base(dnf.conf.Conf())
        cli = dnf.cli.cli.Cli(base=base)
        self.command = dnf.cli.commands.Command(cli=cli)

    def test_command(self):
        # dnf.cli.commands.Command
        self.assertHasAttr(dnf.cli.commands, "Command")
        self.assertHasType(dnf.cli.commands.Command, object)

    def test_init(self):
        base = dnf.Base(dnf.conf.Conf())
        cli = dnf.cli.cli.Cli(base=base)
        _ = dnf.cli.commands.Command(cli=cli)

    def test_aliases(self):
        # dnf.cli.commands.Command.aliases
        self.assertHasAttr(self.command, "aliases")
        self.assertHasType(self.command.aliases, list)

    def test_summary(self):
        # dnf.cli.commands.Command.summary
        self.assertHasAttr(self.command, "summary")
        self.assertHasType(self.command.summary, str)

    def test_base(self):
        # dnf.cli.commands.Command.base
        self.assertHasAttr(self.command, "base")
        self.assertHasType(self.command.base, dnf.Base)

    def test_cli(self):
        # dnf.cli.commands.Command.cli
        self.assertHasAttr(self.command, "cli")
        self.assertHasType(self.command.cli, dnf.cli.cli.Cli)

    def test_pre_configure(self):
        # dnf.cli.commands.Command.pre_configure
        self.assertHasAttr(self.command, "pre_configure")
        self.command.pre_configure()

    def test_configure(self):
        # dnf.cli.commands.Command.configure
        self.assertHasAttr(self.command, "configure")
        self.command.configure()

    def test_run(self):
        # dnf.cli.commands.Command.run
        self.assertHasAttr(self.command, "run")
        self.command.run()
