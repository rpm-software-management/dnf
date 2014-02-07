# arch.py
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

import os
import rpm

_ppc64_native_is_best = True

# dict mapping arch -> ( multicompat, best personality, biarch personality )
multilibArches = { "x86_64":  ( "athlon", "x86_64", "athlon" ),
                   "sparc64v": ( "sparcv9v", "sparcv9v", "sparc64v" ),
                   "sparc64": ( "sparcv9", "sparcv9", "sparc64" ),
                   "ppc64":   ( "ppc", "ppc", "ppc64" ),
                   "s390x":   ( "s390", "s390x", "s390" ),
                   }
if _ppc64_native_is_best:
    multilibArches["ppc64"] = ( "ppc", "ppc64", "ppc64" )

arches = {
    # ia32
    "athlon": "i686",
    "i686": "i586",
    "geode": "i586",
    "i586": "i486",
    "i486": "i386",
    "i386": "noarch",

    # amd64
    "x86_64": "athlon",
    "amd64": "x86_64",
    "ia32e": "x86_64",

    # ppc
    "ppc64pseries": "ppc64",
    "ppc64iseries": "ppc64",
    "ppc64": "ppc",
    "ppc": "noarch",

    # s390{,x}
    "s390x": "s390",
    "s390": "noarch",

    # sparc
    "sparc64v": "sparcv9v",
    "sparc64": "sparcv9",
    "sparcv9v": "sparcv9",
    "sparcv9": "sparcv8",
    "sparcv8": "sparc",
    "sparc": "noarch",

    # alpha
    "alphaev7":   "alphaev68",
    "alphaev68":  "alphaev67",
    "alphaev67":  "alphaev6",
    "alphaev6":   "alphapca56",
    "alphapca56": "alphaev56",
    "alphaev56":  "alphaev5",
    "alphaev5":   "alphaev45",
    "alphaev45":  "alphaev4",
    "alphaev4":   "alpha",
    "alpha":      "noarch",

    # arm
    "armv7l": "armv6l",
    "armv6l": "armv5tejl",
    "armv5tejl": "armv5tel",
    "armv5tel": "noarch",

    #arm hardware floating point
    "armv7hnl": "armv7hl",
    "armv7hl": "noarch",

    # super-h
    "sh4a": "sh4",
    "sh4": "noarch",
    "sh3": "noarch",

    #itanium
    "ia64": "noarch",
    }

def _try_read_cpuinfo():
    """ Try to read /proc/cpuinfo ... if we can't ignore errors (ie. proc not
        mounted). """
    try:
        lines = open("/proc/cpuinfo", "r").readlines()
        return lines
    except:
        return []

def isMultiLibArch(arch):
    """returns true if arch is a multilib arch, false if not"""
    if arch not in arches: # or we could check if it is noarch
        return 0

    if arch in multilibArches:
        return 1

    if arches[arch] in multilibArches:
        return 1

    return 0

def getCanonX86Arch(arch):
    #
    if arch == "i586":
        for line in _try_read_cpuinfo():
            if line.startswith("model name") and line.find("Geode(TM)") != -1:
                return "geode"
        return arch
    # only athlon vs i686 isn't handled with uname currently
    if arch != "i686":
        return arch

    # if we're i686 and AuthenticAMD, then we should be an athlon
    for line in _try_read_cpuinfo():
        if line.startswith("vendor") and line.find("AuthenticAMD") != -1:
            return "athlon"
        # i686 doesn't guarantee cmov, but we depend on it
        elif line.startswith("flags") and line.find("cmov") == -1:
            return "i586"

    return arch

def getCanonARMArch(arch):
    # the %{_target_arch} macro in rpm will let us know the abi we are using
    target = rpm.expandMacro('%{_target_cpu}')
    if target.startswith('armv7h'):
        return target
    return arch

def getCanonPPCArch(arch):
    # FIXME: should I do better handling for mac, etc?
    if arch != "ppc64":
        return arch

    machine = None
    for line in _try_read_cpuinfo():
        if line.find("machine") != -1:
            machine = line.split(':')[1]
            break
    if machine is None:
        return arch

    if machine.find("CHRP IBM") != -1:
        return "ppc64pseries"
    if machine.find("iSeries") != -1:
        return "ppc64iseries"
    return arch

def getCanonSPARCArch(arch):
    # Deal with sun4v, sun4u, sun4m cases
    SPARCtype = None
    for line in _try_read_cpuinfo():
        if line.startswith("type"):
            SPARCtype = line.split(':')[1]
            break
    if SPARCtype is None:
        return arch

    if SPARCtype.find("sun4v") != -1:
        if arch.startswith("sparc64"):
            return "sparc64v"
        else:
            return "sparcv9v"
    if SPARCtype.find("sun4u") != -1:
        if arch.startswith("sparc64"):
            return "sparc64"
        else:
            return "sparcv9"
    if SPARCtype.find("sun4m") != -1:
        return "sparcv8"
    return arch

def getCanonX86_64Arch(arch):
    if arch != "x86_64":
        return arch

    vendor = None
    for line in _try_read_cpuinfo():
        if line.startswith("vendor_id"):
            vendor = line.split(':')[1]
            break
    if vendor is None:
        return arch

    if vendor.find("Authentic AMD") != -1 or vendor.find("AuthenticAMD") != -1:
        return "amd64"
    if vendor.find("GenuineIntel") != -1:
        return "ia32e"
    return arch

def getCanonArch():
    if os.access("/etc/rpm/platform", os.R_OK):
        try:
            f = open("/etc/rpm/platform", "r")
            line = f.readline()
            f.close()
            (arch, vendor, opersys) = line.split("-", 2)
            return arch
        except:
            pass

    arch = os.uname()[4]

    if (len(arch) == 4 and arch[0] == "i" and arch[2:4] == "86"):
        return getCanonX86Arch(arch)

    if arch.startswith("arm"):
        return getCanonARMArch(arch)
    if arch.startswith("ppc"):
        return getCanonPPCArch(arch)
    if arch.startswith("sparc"):
        return getCanonSPARCArch(arch)
    if arch == "x86_64":
        return getCanonX86_64Arch(arch)

    return arch

def getBaseArch(myarch):
    """returns 'base' arch for myarch, if specified, or canonArch if not.
       base arch is the arch before noarch in the arches dict if myarch is not
       a key in the multilibArches."""

    if myarch not in arches: # this is dumb, but <shrug>
        return myarch

    if myarch.startswith("sparc64"):
        return "sparc"
    elif myarch.startswith("ppc64") and not _ppc64_native_is_best:
        return "ppc"
    elif myarch.startswith("armv7h"):
        return "armhfp"
    elif myarch.startswith("arm"):
        return "arm"

    if isMultiLibArch(myarch):
        if myarch in multilibArches:
            return myarch
        else:
            return arches[myarch]

    if myarch in arches:
        basearch = myarch
        value = arches[basearch]
        while value != 'noarch':
            basearch = value
            value = arches[basearch]

        return basearch

class Arch(object):
    """Keeping track of what arch we have."""
    def __init__(self):
        self.canonarch = getCanonArch()
        self.basearch = getBaseArch(self.canonarch)
