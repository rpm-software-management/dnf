# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf

from .common import TestCase


class DnfRPMTransactionApiTest(TestCase):
    def setUp(self):
        self.base = dnf.Base()
        self.base.fill_sack(False, False)
        self.base.resolve()
        self.rpmTrans = self.base.transaction

    def tearDown(self):
        self.base.close()

    def test_iterator(self):
        # RPMTransaction.__iter__
        self.assertHasAttr(self.rpmTrans, "__iter__")
        for i in self.rpmTrans:
            pass

    def test_install_set(self):
        # RPMTransaction.install_set
        self.assertHasAttr(self.rpmTrans, "install_set")
        self.assertHasType(self.rpmTrans.install_set, set)

    def test_remove_set(self):
        # RPMTransaction.remove_set
        self.assertHasAttr(self.rpmTrans, "remove_set")
        self.assertHasType(self.rpmTrans.remove_set, set)
