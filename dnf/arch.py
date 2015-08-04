# arch.py
# Manipulating the machine architecture string.
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

def _invert(dct):
    return {v: k for k in dct for v in dct[k]}

_BASEARCH_MAP = _invert({
    'aarch64' : ('aarch64',),
    'alpha'   : ('alpha', 'alphaev4', 'alphaev45', 'alphaev5', 'alphaev56',
                 'alphaev6', 'alphaev67', 'alphaev68', 'alphaev7', 'alphapca56'),
    'arm'     : ('armv5tejl', 'armv5tel', 'armv6l', 'armv7l'),
    'armhfp'  : ('armv6hl', 'armv7hl', 'armv7hnl'),
    'i386'    : ('i386', 'athlon', 'geode', 'i386', 'i486', 'i586', 'i686'),
    'ia64'    : ('ia64',),
    'mips'    : ('mips',),
    'mipsel'  : ('mipsel',),
    'mips64'  : ('mips64',),
    'mips64el': ('mips64el',),
    'noarch'  : ('noarch',),
    'ppc'     : ('ppc',),
    'ppc64'   : ('ppc64', 'ppc64iseries', 'ppc64p7', 'ppc64pseries'),
    'ppc64le' : ('ppc64le',),
    's390'    : ('s390',),
    's390x'   : ('s390x',),
    'sh3'     : ('sh3',),
    'sh4'     : ('sh4', 'sh4a'),
    'sparc'   : ('sparc', 'sparc64', 'sparc64v', 'sparcv8', 'sparcv9',
                 'sparcv9v'),
    'x86_64'  : ('x86_64', 'amd64', 'ia32e'),
})

def basearch(arch):
    return _BASEARCH_MAP[arch]
