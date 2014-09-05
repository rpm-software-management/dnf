# goal.py
# Customized hawkey.Goal
#
# Copyright (C) 2014  Red Hat, Inc.
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
import hawkey


class Goal(hawkey.Goal):
    def __init__(self, sack):
        super(Goal, self).__init__(sack)
        self.group_members = set()

    def get_reason(self, pkg):
        code = super(Goal, self).get_reason(pkg)
        if code == hawkey.REASON_DEP:
            return 'dep'
        if code == hawkey.REASON_USER:
            if pkg.name in self.group_members:
                return 'group'
            return 'user'
        assert False, 'Unknown reason: %d' % code

    def group_reason(self, pkg, current_reason):
        if current_reason == 'unknown' and pkg.name in self.group_members:
            return 'group'
        return current_reason
