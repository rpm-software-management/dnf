# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf

from .common import TestCase


class DnfRpmApiTest(TestCase):
    def test_detect_releasever(self):
        # dnf.rpm.detect_releasever
        self.assertHasAttr(dnf.rpm, "detect_releasever")

    def test_basearch(self):
        # dnf.rpm.basearch
        self.assertHasAttr(dnf.rpm, "basearch")
        self.assertHasType(dnf.rpm.basearch(arch="x86_64"), str)
