# __init__.py
#
# Copyright (C) 2012-2014  Red Hat, Inc.
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

from . import transaction
from dnf.pycomp import is_py3bytes
import dnf.const
import dnf.exceptions
import rpm


def detect_releasever(installroot):
    """Calculate the release version for the system. :api"""

    ts = transaction.initReadOnlyTransaction(root=installroot)
    ts.pushVSFlags(~(rpm._RPMVSF_NOSIGNATURES|rpm._RPMVSF_NODIGESTS))
    for distroverpkg in dnf.const.DISTROVERPKG:
        try:
            idx = ts.dbMatch('provides', distroverpkg)
        except (TypeError, rpm.error) as e:
            raise dnf.exceptions.Error('Error: %s' % str(e))
        if not len(idx):
            continue
        try:
            hdr = next(idx)
        except StopIteration:
            msg = 'Error: rpmdb failed to list provides. Try: rpm --rebuilddb'
            raise dnf.exceptions.Error(msg)
        releasever = hdr['version']
        if is_py3bytes(releasever):
            releasever = str(releasever, "utf-8")
        return releasever
    return None

def header(path):
    """Return RPM header of the file."""
    ts = transaction.initReadOnlyTransaction()
    with open(path) as package:
        fdno = package.fileno()
        return ts.hdrFromFdno(fdno)
