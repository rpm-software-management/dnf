# -*- coding: utf-8 -*-

# Copyright (C) 2014-2018 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from __future__ import absolute_import
from __future__ import unicode_literals

import libdnf.transaction

import dnf.goal
import dnf.selector

import tests.support


class GoalTest(tests.support.DnfBaseTestCase):

    REPOS = ['main']
    INIT_SACK = True

    def test_get_reason(self):
        sltr = dnf.selector.Selector(self.sack)
        sltr.set(name='mrkite')
        grp_sltr = dnf.selector.Selector(self.sack)
        grp_sltr.set(name='lotus')

        self.goal.install(select=sltr)
        self.goal.install(select=grp_sltr)
        self.goal.group_members.add('lotus')
        self.goal.run()
        installs = self.goal.list_installs()
        mrkite = [pkg for pkg in installs if pkg.name == 'mrkite'][0]
        lotus = [pkg for pkg in installs if pkg.name == 'lotus'][0]
        trampoline = [pkg for pkg in installs if pkg.name == 'trampoline'][0]
        self.assertEqual(self.goal.get_reason(lotus), libdnf.transaction.TransactionItemReason_GROUP)
        self.assertEqual(self.goal.get_reason(mrkite), libdnf.transaction.TransactionItemReason_USER)
        self.assertEqual(self.goal.get_reason(trampoline), libdnf.transaction.TransactionItemReason_DEPENDENCY)

    def test_group_reason(self):
        hole = self.sack.query().filter(name='hole')[0]
        self.goal.group_members.add('hole')
        self.assertEqual(libdnf.transaction.TransactionItemReason_GROUP, self.goal.group_reason(hole, libdnf.transaction.TransactionItemReason_GROUP))
        self.assertEqual(libdnf.transaction.TransactionItemReason_DEPENDENCY, self.goal.group_reason(hole, libdnf.transaction.TransactionItemReason_DEPENDENCY))
