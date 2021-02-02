# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf
import dnf.module.module_base

import os
import shutil
import tempfile

from .common import TestCase


class DnfModuleBaseApiTest(TestCase):
    def setUp(self):
        self.base = dnf.Base(dnf.conf.Conf())
        self._installroot = tempfile.mkdtemp(prefix="dnf_test_installroot_")
        self.base.conf.installroot = self._installroot
        self.base.conf.cachedir = os.path.join(self._installroot, "var/cache/dnf")
        self.base._sack = dnf.sack._build_sack(self.base)
        self.moduleBase = dnf.module.module_base.ModuleBase(self.base)

    def tearDown(self):
        self.base.close()
        if self._installroot.startswith("/tmp/"):
            shutil.rmtree(self._installroot)

    def test_init(self):
        moduleBase = dnf.module.module_base.ModuleBase(self.base)

    def test_enable(self):
        # ModuleBase.enable()
        self.assertHasAttr(self.moduleBase, "enable")
        self.assertRaises(
            dnf.exceptions.Error,
            self.moduleBase.enable,
            module_specs=["nodejs:8"],
        )

    def test_disable(self):
        # ModuleBase.disable()
        self.assertHasAttr(self.moduleBase, "disable")
        self.assertRaises(
            dnf.exceptions.Error,
            self.moduleBase.disable,
            module_specs=["nodejs"],
        )

    def test_reset(self):
        # ModuleBase.reset()
        self.assertHasAttr(self.moduleBase, "reset")
        self.assertRaises(
            dnf.exceptions.Error,
            self.moduleBase.reset,
            module_specs=["nodejs:8"],
        )

    def test_install(self):
        # ModuleBase.install()
        self.assertHasAttr(self.moduleBase, "install")
        self.moduleBase.install(module_specs=[], strict=False)

    def test_remove(self):
        # ModuleBase.remove()
        self.assertHasAttr(self.moduleBase, "remove")
        self.moduleBase.remove(module_specs=[])

    def test_upgrade(self):
        # ModuleBase.upgrade()
        self.assertHasAttr(self.moduleBase, "upgrade")
        self.moduleBase.upgrade(module_specs=[])

    def test_get_modules(self):
        # ModuleBase.get_modules()
        self.assertHasAttr(self.moduleBase, "get_modules")
        self.moduleBase.get_modules(module_spec="")
