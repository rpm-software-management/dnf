# arch.py
# Manipulating the machine architecture string.
#
# Copyright (C) 2014-2015  Red Hat, Inc.
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


"""
ARCHES
======

Notes
-----
 * more significant architectures must go first
   for example: i686 -> i586 -> i486 -> i386
 * group arches by basearch for better readability

Format
------
{
    "arch": architecture name
    "basearch": base architecture, yum's $basearch
    "multilib_arch": multilib architecture name or None
    "parent": [optional] override ARCHES ordering by direct specification of parent arch
}

Differences to rpmUtils.arch
----------------------------
 * sparc64v and sparc64 basearch changed from 'sparc' to 'sparc64'
"""


ARCHES = [
    # basearch: src
    {
        "arch": "src",
        "basearch": "src",
        "multilib_arch": None,
    },
    {
        "arch": "nosrc",
        "basearch": "src",
        "multilib_arch": None,
    },

    # basearch: noarch
    {
        "arch": "noarch",
        "basearch": "noarch",
        "multilib_arch": None,
    },

    # basearch: aarch64
    {
        "arch": "aarch64",
        "basearch": "aarch64",
        "multilib_arch": None,
    },

    # basearch: alpha
    {
        "arch": "alphaev7",
        "basearch": "alpha",
        "multilib_arch": None,
    },
    {
        "arch": "alphaev68",
        "basearch": "alpha",
        "multilib_arch": None,
    },
    {
        "arch": "alphaev67",
        "basearch": "alpha",
        "multilib_arch": None,
    },
    {
        "arch": "alphaev6",
        "basearch": "alpha",
        "multilib_arch": None,
    },
    {
        "arch": "alphapca56",
        "basearch": "alpha",
        "multilib_arch": None,
    },
    {
        "arch": "alphaev56",
        "basearch": "alpha",
        "multilib_arch": None,
    },
    {
        "arch": "alphaev5",
        "basearch": "alpha",
        "multilib_arch": None,
    },
    {
        "arch": "alphaev45",
        "basearch": "alpha",
        "multilib_arch": None,
    },
    {
        "arch": "alphaev4",
        "basearch": "alpha",
        "multilib_arch": None,
    },
    {
        "arch": "alpha",
        "basearch": "alpha",
        "multilib_arch": None,
    },

    # basearch: arm
    {
        "arch": "armv7l",
        "basearch": "arm",
        "multilib_arch": None,
    },
    {
        "arch": "armv6l",
        "basearch": "arm",
        "multilib_arch": None,
    },
    {
        "arch": "armv5tejl",
        "basearch": "arm",
        "multilib_arch": None,
    },
    {
        "arch": "armv5tel",
        "basearch": "arm",
        "multilib_arch": None,
    },

    # basearch: arm64
    {
        "arch": "arm64",
        "basearch": "arm64",
        "multilib_arch": None,
    },

    # basearch: armhfp
    {
        "arch": "armv7hnl",
        "basearch": "armhfp",
        "multilib_arch": None,
    },
    {
        "arch": "armv7hl",
        "basearch": "armhfp",
        "multilib_arch": None,
    },
    {
        "arch": "armv6hl",
        "basearch": "armhfp",
        "multilib_arch": None,
    },

    # basearch: i386
    {
        "arch": "athlon",
        "basearch": "i386",
        "multilib_arch": None,
        "parent": "i686",  # athlon is not entirely compatible with geode
    },
    {
        "arch": "geode",
        "basearch": "i386",
        "multilib_arch": None,
    },
    {
        "arch": "i686",
        "basearch": "i386",
        "multilib_arch": None,
    },
    {
        "arch": "i586",
        "basearch": "i386",
        "multilib_arch": None,
    },
    {
        "arch": "i486",
        "basearch": "i386",
        "multilib_arch": None,
    },
    {
        "arch": "i386",
        "basearch": "i386",
        "multilib_arch": None,
    },

    # basearch: ia64
    {
        "arch": "ia64",
        "basearch": "ia64",
        "multilib_arch": None,
    },

    # basearch: ppc
    {
        "arch": "ppc",
        "basearch": "ppc",
        "multilib_arch": None,
    },

    # basearch: ppc64
    {
        "arch": "ppc64p7",
        "basearch": "ppc64",
        "multilib_arch": "ppc",
        "parent": "ppc64",  # ppc64p7 is not entirely compatible with ppc64pseries and ppc64iseries
    },
    {
        "arch": "ppc64pseries",
        "basearch": "ppc64",
        "multilib_arch": "ppc",
        "parent": "ppc64",  # ppc64pseries is not entirely compatible with ppc64iseries
    },
    {
        "arch": "ppc64iseries",
        "basearch": "ppc64",
        "multilib_arch": "ppc",
    },
    {
        "arch": "ppc64",
        "basearch": "ppc64",
        "multilib_arch": "ppc",
    },

    # basearch: ppc64le
    {
        "arch": "ppc64le",
        "basearch": "ppc64le",
        "multilib_arch": None,
    },

    # basearch: s390
    {
        "arch": "s390",
        "basearch": "s390",
        "multilib_arch": None,
    },

    # basearch: s390x
    {
        "arch": "s390x",
        "basearch": "s390x",
        "multilib_arch": "s390",
    },

    # basearch: sh3
    {
        "arch": "sh3",
        "basearch": "sh3",
        "multilib_arch": None,
    },

    # basearch: sh4
    {
        "arch": "sh4a",
        "basearch": "sh4",
        "multilib_arch": None,
    },
    {
        "arch": "sh4",
        "basearch": "sh4",
        "multilib_arch": None,
    },

    # basearch: sparc
    {
        "arch": "sparc64v",
        "basearch": "sparc64",
        "multilib_arch": "sparcv9v",
    },
    {
        "arch": "sparc64",
        "basearch": "sparc64",
        "multilib_arch": "sparcv9",
    },
    {
        "arch": "sparcv9v",
        "basearch": "sparc",
        "multilib_arch": None,
    },
    {
        "arch": "sparcv9",
        "basearch": "sparc",
        "multilib_arch": None,
    },
    {
        "arch": "sparcv8",
        "basearch": "sparc",
        "multilib_arch": None,
    },
    {
        "arch": "sparc",
        "basearch": "sparc",
        "multilib_arch": None,
    },

    # basearch: x86_64
    {
        "arch": "amd64",
        "basearch": "x86_64",
        "multilib_arch": "athlon",
        "parent": "x86_64",  # amd64 is not entirely compatible with ia32e
    },
    {
        "arch": "ia32e",
        "basearch": "x86_64",
        "multilib_arch": "athlon",
    },
    {
        "arch": "x86_64",
        "basearch": "x86_64",
        "multilib_arch": "athlon",
    },
]


def _find_arch(arch):
    for i in ARCHES:
        if i["arch"] == arch:
            return i
    raise ValueError("Unknown arch: %s" % arch)


def _find_basearch(arch):
    for i in ARCHES:
        if i["basearch"] == arch:
            return i
    raise ValueError("Unknown basearch: %s" % arch)


def is_valid_arch(arch):
    try:
        _find_arch(arch)
    except ValueError:
        return False
    return True


def is_valid_basearch(arch):
    try:
        _find_basearch(arch)
    except ValueError:
        return False
    return True


def _find_arches(arch, just_compatible=True):
    if arch is None:
        return []
    arch_data = _find_arch(arch)
    result = []
    found = False
    for i in ARCHES:
        if i["basearch"] != arch_data["basearch"]:
            continue
        if just_compatible:
            if i["arch"] == arch:
                found = True
            if found:
                result.append(i)
                parent_arch = i.get("parent", None)
                if parent_arch:
                    return result + _find_arches(parent_arch, just_compatible)
        else:
            result.append(i)
    return result


class Arch(object):

    def __init__(self, arch, basearch=False, just_compatible=True):
        if basearch:
            arch = _find_basearch(arch)["arch"]
            just_compatible = False

        self.arch = arch
        self.just_compatible = just_compatible

        arch_data = _find_arch(self.arch)
        self.basearch = arch_data["basearch"]
        self.multilib_arch = arch_data["multilib_arch"]

        self.native_arches = [i["arch"] for i in _find_arches(self.arch, self.just_compatible)]
        self.multilib_arches = [i["arch"] for i in _find_arches(self.multilib_arch, self.just_compatible)]
        self.noarch_arches = [i["arch"] for i in _find_arches("noarch", just_compatible=False)]
        self.source_arches = [i["arch"] for i in _find_arches("src", just_compatible=False)]

        if self.is_noarch:
            self.arches = self.noarch_arches[:]
        elif self.is_source:
            self.arches = self.source_arches[:]
        else:
            self.arches = self.native_arches + self.multilib_arches + self.noarch_arches

    @property
    def is_multilib(self):
        return bool(self.multilib_arch)

    @property
    def is_noarch(self):
        return bool(self.basearch == "noarch")

    @property
    def is_source(self):
        return bool(self.basearch == "src")

    def __str__(self):
        return self.arch

    def __lt__(self, other):
        if self.is_multilib:
            # multilib arch has complete arch list
            a = Arch(self.basearch, basearch=True, just_compatible=False)
        else:
            a = Arch(other.basearch, basearch=True, just_compatible=False)

        if self.arch not in a.arches or other.arch not in a.arches:
            raise ValueError("Cannot compare incompatible arches: %s, %s" % (self.arch, other.arch))

        return a.arches.index(self.arch) - a.arches.index(other.arch)

    def __gt__(self, other):
        return other < self

    def __eq__(self, other):
        return self.arch == other.arch


# compatibility with previous DNF implementation


_BASEARCH_MAP = dict([(i["arch"], i["basearch"]) for i in ARCHES if i["basearch"] != "src"])


def basearch(arch):
    return Arch(arch).basearch
