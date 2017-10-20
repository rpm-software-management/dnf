# query.py
# Implements Query.
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

from __future__ import absolute_import
from __future__ import unicode_literals
import hawkey

from hawkey import Query
from dnf.i18n import ucd
from dnf.pycomp import basestring



def _by_provides(sack, patterns, ignore_case=False, get_query=False):
    if isinstance(patterns, basestring):
        patterns = [patterns]

    q = sack.query()
    flags = []
    if ignore_case:
        flags.append(hawkey.ICASE)

    q.filterm(*flags, provides__glob=patterns)
    if get_query:
        return q
    return q.run()

def _per_nevra_dict(pkg_list):
    return {ucd(pkg):pkg for pkg in pkg_list}
