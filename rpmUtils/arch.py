#!/usr/bin/python
#

import os

# dict mapping arch -> ( multicompat, best personality, biarch personality )
multilibArches = { "x86_64":  ( "athlon", "x86_64", "athlon" ),
                   "sparc64v": ( "sparcv9v", "sparcv9v", "sparc64v" ),
                   "sparc64": ( "sparcv9", "sparcv9", "sparc64" ),
                   "ppc64":   ( "ppc", "ppc", "ppc64" ),
                   "s390x":   ( "s390", "s390x", "s390" ),
                   }

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

    # super-h 
    "sh4a": "sh4",
    "sh4": "noarch",
    "sh3": "noarch",
    
    #itanium
    "ia64": "noarch",
    }

def legitMultiArchesInSameLib(arch=None):
    # this is completely crackrock - if anyone has a better way I
    # am all ears
    
    arch = getBestArch(arch)
    if isMultiLibArch(arch):
        arch = getBaseArch(myarch=arch)
         
    results = [arch]
   
    if arch == 'x86_64' or arch.startswith('sparcv9'):
        for (k, v) in arches.items():
            if v == arch:
                results.append(k)
    return results        


def canCoinstall(arch1, arch2):
    """Take two arches and return True if it is possible that they can be
       installed together with the same nevr. Ex: arch1=i386 and arch2=i686 then
       it will return False. arch1=i386 and arch2=x86_64 will return True.
       It does not determine whether or not the arches make any sense. Just whether
       they could possibly install w/o conflict"""

    # if both are a multlibarch then we can't coinstall  (x86_64, ia32e)
    # if both are not multilibarches then we can't coinstall (i386, i686)
    
    if 'noarch' in [arch1, arch2]: # noarch can never coinstall
        return False

    if isMultiLibArch(arch=arch1) == isMultiLibArch(arch=arch2):
        return False
    # this section keeps arch1=x86_64 arch2=ppc from returning True
    if arch1 in getArchList(arch2) or arch2 in getArchList(arch1):
        return True
    return False

# this computes the difference between myarch and targetarch
def archDifference(myarch, targetarch):
    if myarch == targetarch:
        return 1
    if myarch in arches:
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
        arch = canonArch

    if arch not in arches: # or we could check if it is noarch
        return 0
    
    if arch in multilibArches:
        return 1
        
    if arches[arch] in multilibArches:
        return 1
    
    return 0
    
def getBestArchFromList(archlist, myarch=None):
    """ 
        return the best arch from the list for myarch if - myarch is not given,
        then return the best arch from the list for the canonArch.
    """
    
    if len(archlist) == 0:
        return None

    if myarch is None:
        myarch = canonArch
    
    mybestarch = getBestArch(myarch)
    
    bestarch = getBestArch(myarch)
    if bestarch != myarch:
        bestarchchoice = getBestArchFromList(archlist, bestarch)
        if bestarchchoice != None and bestarchchoice != "noarch":
            return bestarchchoice
            
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
        thisarch = canonArch
    
    archlist = [thisarch]
    while thisarch in arches:
        thisarch = arches[thisarch]
        archlist.append(thisarch)

    # hack hack hack
    # sparc64v is also sparc64 compat
    if archlist[0] == "sparc64v":
        archlist.insert(1,"sparc64")
    
    # if we're a weirdo arch - add noarch on there.
    if len(archlist) == 1 and archlist[0] == thisarch:
        archlist.append('noarch')
    return archlist
    
def _try_read_cpuinfo():
    """ Try to read /proc/cpuinfo ... if we can't ignore errors (ie. proc not
        mounted). """
    try:
        lines = open("/proc/cpuinfo", "r").readlines()
        return lines
    except:
        return []

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

canonArch = getCanonArch()

# this gets you the "compat" arch of a biarch pair
def getMultiArchInfo(arch = canonArch):
    if arch in multilibArches:
        return multilibArches[arch]
    if arch in arches and arches[arch] != "noarch":
        return getMultiArchInfo(arch = arches[arch])
    return None

# get the best usual userspace arch for the arch we're on.  this is
# our arch unless we're on an arch that uses the secondary as its
# userspace (eg ppc64, sparc64)
def getBestArch(myarch=None):
    if myarch:
        arch = myarch
    else:
        arch = canonArch

    if arch.startswith("sparc64"):
        arch = multilibArches[arch][1]

    if arch.startswith("ppc64"):
        arch = 'ppc'

    return arch

def getBaseArch(myarch=None):
    """returns 'base' arch for myarch, if specified, or canonArch if not.
       base arch is the arch before noarch in the arches dict if myarch is not
       a key in the multilibArches."""

    if not myarch:
        myarch = canonArch

    if myarch not in arches: # this is dumb, but <shrug>
        return myarch

    if myarch.startswith("sparc64"):
        return "sparc"
    elif myarch.startswith("ppc64"):
        return "ppc"
    elif myarch.startswith("arm"):
        return "arm"
        
    if isMultiLibArch(arch=myarch):
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
        

class ArchStorage(object):
    """class for keeping track of what arch we have set and doing various 
       permutations based on it"""
    def __init__(self):
        self.canonarch = None 
        self.basearch = None
        self.bestarch = None
        self.compatarches = []
        self.archlist = []
        self.multilib = False
        self.setup_arch()

    def setup_arch(self, arch=None, archlist_includes_compat_arch=True):
        if arch:
            self.canonarch = arch
        else:
            self.canonarch = getCanonArch()
        
        self.basearch = getBaseArch(myarch=self.canonarch)
        self.archlist = getArchList(thisarch=self.canonarch)
        
        if not archlist_includes_compat_arch: # - do we bother including i686 and below on x86_64
            limit_archlist = []
            for a in self.archlist:
                if isMultiLibArch(a) or a == 'noarch':
                    limit_archlist.append(a)
            self.archlist = limit_archlist
            
        self.bestarch = getBestArch(myarch=self.canonarch)
        self.compatarches = getMultiArchInfo(arch=self.canonarch)
        self.multilib = isMultiLibArch(arch=self.canonarch)
        self.legit_multi_arches = legitMultiArchesInSameLib(arch = self.canonarch)

    def get_best_arch_from_list(self, archlist, fromarch=None):
        if not fromarch:
            fromarch = self.canonarch
        return getBestArchFromList(archlist, myarch=fromarch)

    def score(self, arch):
        return archDifference(self.canonarch, arch)

    def get_arch_list(self, arch):
        if not arch:
            return self.archlist
        return getArchList(thisarch=arch)
