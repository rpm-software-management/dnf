# __init__.py
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
from . import transaction
from dnf.pycomp import is_py3bytes
import dnf.const
import dnf.exceptions
import rpm  # used by ansible (dnf.rpm.rpm.labelCompare in lib/ansible/modules/packaging/os/dnf.py)


def detect_releasever(installroot):
    # :api
    """Calculate the release version for the system."""

    ts = transaction.initReadOnlyTransaction(root=installroot)
    ts.pushVSFlags(~(rpm._RPMVSF_NOSIGNATURES | rpm._RPMVSF_NODIGESTS))
    for distroverpkg in dnf.const.DISTROVERPKG:
        if dnf.pycomp.PY3:
            distroverpkg = bytes(distroverpkg, 'utf-8')
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
        try:
            try:
                # header returns bytes -> look for bytes
                # it may fail because rpm returns a decoded string since 10 Apr 2019
                off = hdr[rpm.RPMTAG_PROVIDENAME].index(distroverpkg)
            except ValueError:
                # header returns a string -> look for a string
                off = hdr[rpm.RPMTAG_PROVIDENAME].index(distroverpkg.decode("utf8"))
            flag = hdr[rpm.RPMTAG_PROVIDEFLAGS][off]
            ver = hdr[rpm.RPMTAG_PROVIDEVERSION][off]
            if flag == rpm.RPMSENSE_EQUAL and ver:
                if hdr['name'] not in (distroverpkg, distroverpkg.decode("utf8")):
                    # override the package version
                    releasever = ver
        except (ValueError, KeyError, IndexError):
            pass

        if is_py3bytes(releasever):
            releasever = str(releasever, "utf-8")
        return releasever
    return None


def _header(path):
    """Return RPM header of the file."""
    ts = transaction.initReadOnlyTransaction()
    with open(path) as package:
        fdno = package.fileno()
        try:
            hdr = ts.hdrFromFdno(fdno)
        except rpm.error as e:
            raise dnf.exceptions.Error("{0}: '{1}'".format(e, path))
        return hdr


def _invert(dct):
    return {v: k for k in dct for v in dct[k]}

_BASEARCH_MAP = _invert({
    'aarch64': ('aarch64',),
    'alpha': ('alpha', 'alphaev4', 'alphaev45', 'alphaev5', 'alphaev56',
              'alphaev6', 'alphaev67', 'alphaev68', 'alphaev7', 'alphapca56'),
    'arm': ('armv5tejl', 'armv5tel', 'armv5tl', 'armv6l', 'armv7l', 'armv8l'),
    'armhfp': ('armv6hl', 'armv7hl', 'armv7hnl', 'armv8hl'),
    'i386': ('i386', 'athlon', 'geode', 'i386', 'i486', 'i586', 'i686'),
    'ia64': ('ia64',),
    'mips': ('mips',),
    'mipsel': ('mipsel',),
    'mips64': ('mips64',),
    'mips64el': ('mips64el',),
    'noarch': ('noarch',),
    'ppc': ('ppc',),
    'ppc64': ('ppc64', 'ppc64iseries', 'ppc64p7', 'ppc64pseries'),
    'ppc64le': ('ppc64le',),
    'riscv32' : ('riscv32',),
    'riscv64' : ('riscv64',),
    'riscv128' : ('riscv128',),
    's390': ('s390',),
    's390x': ('s390x',),
    'sh3': ('sh3',),
    'sh4': ('sh4', 'sh4a'),
    'sparc': ('sparc', 'sparc64', 'sparc64v', 'sparcv8', 'sparcv9',
              'sparcv9v'),
    'x86_64': ('x86_64', 'amd64', 'ia32e'),
})


def basearch(arch):
    # :api
    return _BASEARCH_MAP[arch]


def getheader(rpm_hdr, key):
    '''
    Returns value of rpm_hdr[key] as a string. Rpm has switched from bytes to str
    and we need to handle both properly.
    '''
    value = rpm_hdr[key]
    if is_py3bytes(value):
        value = str(value, "utf-8")
    return value
