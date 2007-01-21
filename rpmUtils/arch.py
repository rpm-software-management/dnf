#!/usr/bin/python
#

import os

# dict mapping arch -> ( multicompat, best personality, biarch personality )
multilibArches = { "x86_64":  ( "athlon", "x86_64", "athlon" ),
                   "sparc64v": ( "sparc", "sparcv9v", "sparc64v" ),
                   "sparc64": ( "sparc", "sparcv9", "sparc64" ),
                   "ppc64":   ( "ppc", "ppc", "ppc64" ),
                   "s390x":   ( "s390", "s390x", "s390" ),
                   "ia64":    ( "i686", "ia64", "i686" )
                   }

arches = {
    # ia32
    "athlon": "i686",
    "i686": "i586",
    "i586": "i486",
    "i486": "i386",
    "i386": "noarch",
    
    # amd64
    "x86_64": "athlon",
    "amd64": "x86_64",
    "ia32e": "x86_64",
    
    # itanium
    "ia64": "i686",
    
    # ppc
    "ppc64pseries": "ppc64",
    "ppc64iseries": "ppc64",    
    "ppc64": "ppc",
    "ppc": "noarch",
    
    # s390{,x}
    "s390x": "s390",
    "s390": "noarch",
    
    # sparc
    "sparc64v": "sparc64",
    "sparc64v": "sparcv9v",
    "sparc64": "sparcv9",
    "sparcv9v": "sparcv9",
    "sparcv9": "sparcv8",
    "sparcv8": "sparc",
    "sparc": "noarch",

    # alpha
    "alphaev6": "alphaev56",
    "alphaev56": "alphaev5",
    "alphaev5": "alpha",
    "alpha": "noarch",
    }

# this computes the difference between myarch and targetarch
def archDifference(myarch, targetarch):
    if myarch == targetarch:
        return 1
    if arches.has_key(myarch):
        ret = archDifference(arches[myarch], targetarch)
        if ret != 0:
            return ret + 1
        return 0
    return 0

def score(arch):
    return archDifference(canonArch, arch)

def isMultiLibArch(arch=None):
    """returns true if arch is a multilib arch, false if not"""
    if arch is None:
        arch = getCanonArch()

    if not arches.has_key(arch): # or we could check if it is noarch
        return 0
    
    if multilibArches.has_key(arch):
        return 1
        
    if multilibArches.has_key(arches[arch]):
        return 1
    
    return 0
    
def getBestArchFromList(archlist, myarch=None):
    """ 
        return the best arch from the list for myarch if - myarch is not given,
        then return the best arch from the list for the canonArch.
    """
    
    if myarch is None:
        myarch = getCanonArch()

    if len(archlist) == 0:
        return None
    
    thisarch = archlist[0]
    for arch in archlist[1:]:
        val1 = archDifference(myarch, thisarch)
        val2 = archDifference(myarch, arch)
        if val1 == 0 and val2 == 0:
           continue
        if val1 < val2:
            if val1 == 0:
                thisarch = arch                
        if val2 < val1:
            if val2 != 0:
                thisarch = arch
        if val1 == val2:
            pass
    
    # thisarch should now be our bestarch
    # one final check to make sure we're not returning a bad arch
    val = archDifference(myarch, thisarch)
    if val == 0:
        return None

    return thisarch
        
          
def getArchList(thisarch=None):
    # this returns a list of archs that are compatible with arch given
    if not thisarch:
        thisarch = getCanonArch()
    
    archlist = [thisarch]
    while arches.has_key(thisarch):
        thisarch = arches[thisarch]
        archlist.append(thisarch)

    # hack hack hack
    # sparc64v is also sparc64 compat
    if archlist[0] == "sparc64v":
        archlist.insert(1,"sparc64")
    
    return archlist
    
        

def getCanonX86Arch(arch):
    # only athlon vs i686 isn't handled with uname currently
    if arch != "i686":
        return arch

    # if we're i686 and AuthenticAMD, then we should be an athlon
    f = open("/proc/cpuinfo", "r")
    lines = f.readlines()
    f.close()
    for line in lines:
        if line.startswith("vendor") and line.find("AuthenticAMD") != -1:
            return "athlon"
        # i686 doesn't guarantee cmov, but we depend on it
        elif line.startswith("flags") and line.find("cmov") == -1:
            return "i586"

    return arch

def getCanonPPCArch(arch):
    # FIXME: should I do better handling for mac, etc?
    if arch != "ppc64":
        return arch

    machine = None
    f = open("/proc/cpuinfo", "r")
    lines = f.readlines()
    f.close()
    for line in lines:
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
    f = open("/proc/cpuinfo", "r")
    lines = f.readlines()
    f.close()
    for line in lines:
        if line.startswith("type"):
            SPARCtype = line.split(':')[1]
            break
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
    f = open("/proc/cpuinfo", "r")
    lines = f.readlines()
    f.close()
    for line in lines:
        if line.startswith("vendor_id"):
            vendor = line.split(':')[1]
            break
    if vendor is None:
        return arch

    if vendor.find("Authentic AMD") != -1:
        return "amd64"
    if vendor.find("GenuineIntel") != -1:
        return "ia32e"
    return arch
        
def getCanonArch(skipRpmPlatform = 0):
    if not skipRpmPlatform and os.access("/etc/rpm/platform", os.R_OK):
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

    if arch.startswith("ppc"):
        return getCanonPPCArch(arch)
    if arch.startswith("sparc"):
        return getCanonSPARCArch(arch)
    if arch == "x86_64":
        return getCanonX86_64Arch(arch)

    return arch

# this gets you the "compat" arch of a biarch pair
def getMultiArchInfo(arch = getCanonArch()):
    if multilibArches.has_key(arch):
        return multilibArches[arch]
    if arches.has_key(arch) and arches[arch] != "noarch":
        return getMultiArchInfo(arch = arches[arch])
    return None

# get the best usual userspace arch for the arch we're on.  this is
# our arch unless we're on an arch that uses the secondary as its
# userspace (eg ppc64, sparc64)
def getBestArch():
    arch = canonArch

    if arch.startswith("sparc64"):
        arch = "sparc"

    if arch.startswith("ppc64"):
        arch = "ppc"

    return arch

def getBaseArch(myarch=None):
    """returns 'base' arch for myarch, if specified, or canonArch if not.
       base arch is the arch before noarch in the arches dict if myarch is not
       a key in the multilibArches."""

    if not myarch:
        myarch = getCanonArch()

    if not arches.has_key(myarch): # this is dumb, but <shrug>
        return myarch

    if myarch.startswith("sparc64"):
        return "sparc"
    elif myarch.startswith("ppc64"):
        return "ppc"
        
    if isMultiLibArch(arch=myarch):
        if multilibArches.has_key(myarch):
            return myarch
        else:
            return arches[myarch]
    
    if arches.has_key(myarch):
        basearch = myarch
        value = arches[basearch]
        while value != 'noarch':
            basearch = value
            value = arches[basearch]
    
        return basearch
        
canonArch = getCanonArch()
