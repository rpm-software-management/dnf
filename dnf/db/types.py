# Copyright (C) 2017 Red Hat, Inc.
# Unified software database types
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Eduard Cuba <ecuba@redhat.com>

import gi
gi.require_version('Dnf', '1.0')
from gi.repository import Dnf  # noqa


Swdb = Dnf.Swdb
SwdbItem = Dnf.SwdbItem
SwdbReason = Dnf.SwdbReason
SwdbPkg = Dnf.SwdbPkg
SwdbPkgData = Dnf.SwdbPkgData
SwdbTrans = Dnf.SwdbTrans
SwdbGroup = Dnf.SwdbGroup
SwdbEnv = Dnf.SwdbEnv
SwdbRpmData = Dnf.SwdbRpmData

convert_id = Dnf.convert_id_to_reason


def convert_reason(reason):
    if isinstance(reason, Dnf.SwdbReason):
        return reason
    return Dnf.convert_reason_to_id(reason)
