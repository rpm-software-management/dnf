# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf

from .common import TestCase


class DnfSackApiTest(TestCase):
    def setUp(self):
        self.base = dnf.Base(dnf.conf.Conf())

    def tearDown(self):
        self.base.close()

    def test_rpmdb_sack(self):
        # dnf.sack.rpmdb_sack
        self.assertHasAttr(dnf.sack, "rpmdb_sack")
        self.assertHasType(dnf.sack.rpmdb_sack(self.base), dnf.sack.Sack)

    def test_query(self):
        # Sack.query
        self.base.fill_sack(False, False)
        self.assertHasAttr(self.base.sack, "query")
        self.assertHasType(self.base.sack.query(flags=0), dnf.query.Query)
