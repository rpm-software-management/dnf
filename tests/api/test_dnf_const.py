# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf

from .common import TestCase


class DnfConstApiTest(TestCase):
    def test_filename(self):
        # dnf.const.CONF_FILENAME
        self.assertHasAttr(dnf.const, "CONF_FILENAME")
        self.assertHasType(dnf.const.CONF_FILENAME, str)

    def test_group_package_types(self):
        # dnf.const.GROUP_PACKAGE_TYPES
        self.assertHasAttr(dnf.const, "GROUP_PACKAGE_TYPES")
        self.assertHasType(dnf.const.GROUP_PACKAGE_TYPES, tuple)

    def test_persistdir(self):
        # dnf.const.PERSISTDIR
        self.assertHasAttr(dnf.const, "PERSISTDIR")
        self.assertHasType(dnf.const.PERSISTDIR, str)

    def test_pluginconfpath(self):
        # dnf.const.PLUGINCONFPATH
        self.assertHasAttr(dnf.const, "PLUGINCONFPATH")
        self.assertHasType(dnf.const.PLUGINCONFPATH, str)
