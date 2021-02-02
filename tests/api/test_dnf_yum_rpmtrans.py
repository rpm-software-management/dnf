# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf

from .common import TestCase


class DnfTransactionDisplayApiTest(TestCase):
    def setUp(self):
        self.td = dnf.yum.rpmtrans.TransactionDisplay()

    def test_init(self):
        td = dnf.yum.rpmtrans.TransactionDisplay()
        self.assertHasType(td, dnf.yum.rpmtrans.TransactionDisplay)

    def test_progress(self):
        # TransactionDisplay.progress
        self.assertHasAttr(self.td, "progress")
        self.td.progress(
            package=None,
            action=None,
            ti_done=None,
            ti_total=None,
            ts_done=None,
            ts_total=None
        )

    def test_error(self):
        # RPMTransaction.error
        self.assertHasAttr(self.td, "error")
        self.td.error(message="")
