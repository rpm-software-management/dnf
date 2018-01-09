# -*- coding: utf-8 -*-

# Copyright (C) 2012-2018 Red Hat, Inc.
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

import itertools

import dnf

import tests.support


class UpgradeTo(tests.support.ResultTestCase):
    def test_upgrade_to(self):
        base = tests.support.MockBase("main", "updates")
        sack = base.sack
        base.upgrade("pepper-20-1.x86_64")
        new_set = tests.support.installed_but(sack, "pepper").run()
        q = sack.query().available()._nevra("pepper-20-1.x86_64")
        new_set.extend(q)
        self.assertResult(base, new_set)

    def test_upgrade_to_reponame(self):
        """Test whether only packages in selected repo are used."""
        base = tests.support.MockBase('updates', 'third_party')
        base.init_sack()

        base.upgrade('hole-1-2.x86_64', 'updates')

        self.assertResult(base, itertools.chain(
            base.sack.query().installed().filter(name__neq='hole'),
            dnf.subject.Subject('hole-1-2.x86_64').get_best_query(base.sack).filter(reponame='updates')))

    def test_upgrade_to_reponame_not_in_repo(self):
        """Test whether no packages are upgraded if bad repo is selected."""
        base = tests.support.MockBase('main', 'updates')
        base.init_sack()

        base.upgrade('hole-1-2.x86_64', 'main')

        self.assertResult(base, base.sack.query().installed())
