# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf

from .common import TestCase


class DnfTransactionApiTest(TestCase):
    def test_pkg_action_constants(self):
        self.assertHasAttr(dnf.transaction, "PKG_DOWNGRADE")
        self.assertHasType(dnf.transaction.PKG_DOWNGRADE, int)

        self.assertHasAttr(dnf.transaction, "PKG_DOWNGRADED")
        self.assertHasType(dnf.transaction.PKG_DOWNGRADED, int)

        self.assertHasAttr(dnf.transaction, "PKG_INSTALL")
        self.assertHasType(dnf.transaction.PKG_INSTALL, int)

        self.assertHasAttr(dnf.transaction, "PKG_OBSOLETE")
        self.assertHasType(dnf.transaction.PKG_OBSOLETE, int)

        self.assertHasAttr(dnf.transaction, "PKG_OBSOLETED")
        self.assertHasType(dnf.transaction.PKG_OBSOLETED, int)

        self.assertHasAttr(dnf.transaction, "PKG_REINSTALL")
        self.assertHasType(dnf.transaction.PKG_REINSTALL, int)

        self.assertHasAttr(dnf.transaction, "PKG_REINSTALLED")
        self.assertHasType(dnf.transaction.PKG_REINSTALLED, int)

        self.assertHasAttr(dnf.transaction, "PKG_REMOVE")
        self.assertHasType(dnf.transaction.PKG_REMOVE, int)

        self.assertHasAttr(dnf.transaction, "PKG_UPGRADE")
        self.assertHasType(dnf.transaction.PKG_UPGRADE, int)

        self.assertHasAttr(dnf.transaction, "PKG_UPGRADED")
        self.assertHasType(dnf.transaction.PKG_UPGRADED, int)

        self.assertHasAttr(dnf.transaction, "PKG_ERASE")
        self.assertHasType(dnf.transaction.PKG_ERASE, int)

        self.assertHasAttr(dnf.transaction, "PKG_CLEANUP")
        self.assertHasType(dnf.transaction.PKG_CLEANUP, int)

        self.assertHasAttr(dnf.transaction, "PKG_VERIFY")
        self.assertHasType(dnf.transaction.PKG_VERIFY, int)

        self.assertHasAttr(dnf.transaction, "PKG_SCRIPTLET")
        self.assertHasType(dnf.transaction.PKG_SCRIPTLET, int)

    def test_trans_action_constants(self):
        self.assertHasAttr(dnf.transaction, "TRANS_PREPARATION")
        self.assertHasType(dnf.transaction.TRANS_PREPARATION, int)

        self.assertHasAttr(dnf.transaction, "TRANS_POST")
        self.assertHasType(dnf.transaction.TRANS_POST, int)

    def test_forward_action_constants(self):
        self.assertHasAttr(dnf.transaction, "FORWARD_ACTIONS")
        self.assertHasType(dnf.transaction.FORWARD_ACTIONS, list)

    def test_backward_action_constants(self):
        self.assertHasAttr(dnf.transaction, "BACKWARD_ACTIONS")
        self.assertHasType(dnf.transaction.BACKWARD_ACTIONS, list)

    def test_action_constants(self):
        self.assertHasAttr(dnf.transaction, "ACTIONS")
        self.assertHasType(dnf.transaction.ACTIONS, dict)

    def test_file_action_constants(self):
        self.assertHasAttr(dnf.transaction, "FILE_ACTIONS")
        self.assertHasType(dnf.transaction.FILE_ACTIONS, dict)
