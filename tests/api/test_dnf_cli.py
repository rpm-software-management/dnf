# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf
import dnf.cli
import dnf.exceptions

from .common import TestCase


class DnfCliInitApiTest(TestCase):
    def test_cli_error(self):
        # dnf.cli.CliError
        self.assertHasAttr(dnf.cli, "CliError")
        ex = dnf.cli.CliError(value=None)
        self.assertHasType(ex, dnf.exceptions.Error)

    def test_cli(self):
        # dnf.cli.Cli
        self.assertHasAttr(dnf.cli, "Cli")
        self.assertHasType(dnf.cli.Cli, object)

    def test_command(self):
        # dnf.cli.Command
        self.assertHasAttr(dnf.cli, "Command")
        self.assertHasType(dnf.cli.Command, object)
