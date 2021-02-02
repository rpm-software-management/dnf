# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import unittest

import dnf

from .common import TestCase


class DnfApiTest(TestCase):
    def test_version(self):
        # dnf.__version__
        self.assertHasAttr(dnf, "__version__")
        self.assertHasType(dnf.__version__, str)

    def test_base(self):
        # dnf.Base
        self.assertHasAttr(dnf, "Base")
        self.assertHasType(dnf.Base, object)

    def test_plugin(self):
        # dnf.Plugin
        self.assertHasAttr(dnf, "Plugin")
        self.assertHasType(dnf.Plugin, object)
