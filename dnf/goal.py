# goal.py
# Customized hawkey.Goal
#
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
from copy import deepcopy
from dnf.i18n import _
import logging
import hawkey

logger = logging.getLogger('dnf')

class Goal(hawkey.Goal):
    def __init__(self, sack):
        super(Goal, self).__init__(sack)
        self.group_members = set()
        self.module_members = set()
        self._installs = []

    def get_reason(self, pkg):
        code = super(Goal, self).get_reason(pkg)
        if code == hawkey.REASON_DEP:
            return 'dep'
        if code == hawkey.REASON_USER:
            if pkg.name in self.group_members:
                return 'group'
            return 'user'
        if code == hawkey.REASON_CLEAN:
            return 'clean'
        if code == hawkey.REASON_WEAKDEP:
            return 'weak'
        assert False, 'Unknown reason: %d' % code

    def group_reason(self, pkg, current_reason):
        if current_reason == 'unknown' and pkg.name in self.group_members:
            return 'group'
        return current_reason

    def install(self, *args, **kwargs):
        if args:
            self._installs.extend(args)
        if 'select' in kwargs:
            self._installs.extend(kwargs['select'].matches())
        return super(Goal, self).install(*args, **kwargs)

    def push_userinstalled(self, query, yumdb):
        msg = _('--> Finding unneeded leftover dependencies')
        logger.debug(msg)
        for pkg in query.installed():
            yumdb_info = yumdb.get_package(pkg)
            reason = getattr(yumdb_info, 'reason', 'user')
            if reason not in ('dep', 'weak'):
                self.userinstalled(pkg)

    def available_updates_diff(self, query):
        available_updates = set(query.upgrades().filter(arch__neq="src")
                                .latest().run())
        installable_updates = set(self.list_upgrades())
        installs = set(self.list_installs())
        return (available_updates - installable_updates) - installs
