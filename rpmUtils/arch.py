#!/usr/bin/python
#

import os

# dict mapping arch -> ( multicompat, best personality, biarch personality )
multilibArches = { "x86_64":  ( "athlon", "x86_64", "athlon" ),
                   "sparc64": ( "sparcv9", "sparcv9", "sparc64" ),
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
    "sparc64": "sparcv9",
    "sparcv9": "sparcv8",
    "sparcv8": "sparc",
    "sparc": "noarch"
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

def bestArchFromList(archlist, myarch=None):
    """ 
        return the best arch for myarch if - myarch is None then return
        the best arch from the list for the canonArch.
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
        raise None

    return thisarch
        
          
def getArchList(thisarch):
    # this returns a list of archs that are compatible with arch given
    archlist = [thisarch]
    while arches.has_key(thisarch):
        thisarch = arches[thisarch]
        archlist.append(thisarch)
    
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

    return arch

# this gets you the "compat" arch of a biarch pair
def getMultiArchInfo(arch = getCanonArch()):
    if multilibArches.has_key(arch):
        return multilibArches[arch]
    if arches.has_key(arch) and arches[arch] != "noarch":
        return getMultiArchInfo(arch = arches[arch])
    return None

# get the best usual userspace arch for the arch we're on.  this is
# out arch unless we're on an arch that uses the secondary as its
# userspace (eg ppc64, sparc64)
def getBaseArch():
    arch = canonArch

    if arch == "sparc64":
        arch = "sparc"

    if arch.startswith("ppc64"):
        arch = "ppc"

    return arch

canonArch = getCanonArch()
