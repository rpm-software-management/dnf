# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf
import libdnf

from .common import TestCase
from .common import TOUR_4_4


class DnfPluginApiTest(TestCase):
    def setUp(self):
        self.plugin = dnf.Plugin(base=None, cli=None)

    def test_plugin(self):
        # dnf.Plugin
        self.assertHasAttr(dnf, "Plugin")
        self.assertHasType(dnf.Plugin, object)

    def test_name(self):
        # Plugin.name
        self.assertHasAttr(self.plugin, "name")
        self.plugin.name = "test"
        self.assertHasType(self.plugin.name, str)

    def test_read_config(self):
        # dnf.Plugin.read_config
        self.assertHasAttr(dnf.Plugin, "read_config")
        self.assertHasType(dnf.Plugin.read_config(conf=dnf.conf.Conf()), libdnf.conf.ConfigParser)

    def test_init(self):
        # Plugin.__init__
        _ = dnf.Plugin(base=None, cli=None)

    def test_pre_config(self):
        # Plugin.pre_config
        self.assertHasAttr(self.plugin, "pre_config")
        self.plugin.pre_config()

    def test_config(self):
        # Plugin.config
        self.assertHasAttr(self.plugin, "config")
        self.plugin.config()

    def test_resolved(self):
        # Plugin.resolved
        self.assertHasAttr(self.plugin, "resolved")
        self.plugin.resolved()

    def test_sack(self):
        # Plugin.sack
        self.assertHasAttr(self.plugin, "sack")
        self.plugin.sack()

    def test_pre_transaction(self):
        # Plugin.pre_transaction
        self.assertHasAttr(self.plugin, "pre_transaction")
        self.plugin.pre_transaction()

    def test_transaction(self):
        # Plugin.transaction
        self.assertHasAttr(self.plugin, "transaction")
        self.plugin.transaction()


class Dnfregister_commandApiTest(TestCase):
    def test_register_command(self):
        self.assertHasAttr(dnf.plugin, "register_command")

        @dnf.plugin.register_command
        class TestClassWithDecorator():
            aliases = ('necessary-alias',)

        self.assertHasAttr(TestClassWithDecorator, "_plugin")
