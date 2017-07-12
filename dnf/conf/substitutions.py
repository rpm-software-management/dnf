# substitutions.py
# Config file substitutions.
#
# Copyright (C) 2012-2016 Red Hat, Inc.
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

import dnf
import dnf.exceptions
import os


class Substitutions(dict):

    def __init__(self):
        super(Substitutions, self).__init__()
        self._update_from_env()

    def _update_from_env(self):
        for num in range(0, 10):
            env = 'DNF%d' % num
            val = os.environ.get(env, '')
            if val:
                self[env] = val

    def update_from_etc(self, installroot):
        fsvars = []
        try:
            dir_fsvars = installroot + "/etc/dnf/vars/"
            fsvars = os.listdir(dir_fsvars)
        except OSError:
            pass
        for fsvar in fsvars:
            if os.path.islink(dir_fsvars + fsvar):
                continue
            try:
                val = open(dir_fsvars + fsvar).readline()
                if val and val[-1] == '\n':
                    val = val[:-1]
            except (OSError, IOError):
                continue
            self[fsvar] = val
