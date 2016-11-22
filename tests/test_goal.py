# Copyright (C) 2014-2016 Red Hat, Inc.
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
import dnf.goal
import dnf.selector
import tests.support


class GoalTest(tests.support.TestCase):
    def setUp(self):
        base = tests.support.MockBase('main')
        self.sack = base.sack
        self.goal = dnf.goal.Goal(self.sack)

    def test_get_reason(self):
        sltr = dnf.selector.Selector(self.sack)
        sltr.set(name='mrkite')
        grp_sltr = dnf.selector.Selector(self.sack)
        grp_sltr.set(name='lotus')

        goal = self.goal
        goal.install(select=sltr)
        goal.install(select=grp_sltr)
        goal.group_members.add('lotus')
        goal.run()
        installs = goal.list_installs()
        mrkite = [pkg for pkg in installs if pkg.name == 'mrkite'][0]
        lotus = [pkg for pkg in installs if pkg.name == 'lotus'][0]
        trampoline = [pkg for pkg in installs if pkg.name == 'trampoline'][0]
        self.assertEqual(goal.get_reason(lotus), 'group')
        self.assertEqual(goal.get_reason(mrkite), 'user')
        self.assertEqual(goal.get_reason(trampoline), 'dep')

    def test_group_reason(self):
        goal = self.goal
        hole = self.sack.query().filter(name='hole')[0]
        goal.group_members.add('hole')
        self.assertEqual('group', goal.group_reason(hole, 'unknown'))
        self.assertEqual('dep', goal.group_reason(hole, 'dep'))

    def test_push_userinstalled(self):
        base = tests.support.MockBase('main')
        base.conf.clean_requirements_on_remove = True
        goal = self.goal
        installed = base.sack.query().installed()
        for pkg in installed:
            base._history.mark_user_installed(pkg, False)
        pkg1 = installed.filter(name="pepper")[0]
        base._history.mark_user_installed(pkg, True)
        pkg2 = installed.filter(name="hole")[0]
        base.set_reason(pkg, 'unknown')
        pkgs = installed.filter(name__neq=["pepper", "hole", "librita"]
                               ).run()

        # test:
        goal.push_userinstalled(installed, base._history)
        goal.run()
        self.assertEqual(goal.list_unneeded(), pkgs)
