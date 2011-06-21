#!/usr/bin/python -tt
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
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
# Copyright 2004 Duke University 
# Written by Seth Vidal <skvidal at phy.duke.edu>

"""
Classes and functions dealing with rpm package representations.
"""

import rpm
import os
import os.path
import misc
import i18n
import re
import fnmatch
import stat
import warnings
from subprocess import Popen, PIPE
from rpmUtils import RpmUtilsError
import rpmUtils.miscutils
from rpmUtils.miscutils import flagToString, stringToVersion, compareVerOnly
import Errors
import errno
import struct
from constants import *
from operator import itemgetter

import urlparse
urlparse.uses_fragment.append("media")
from urlgrabber.grabber import URLGrabber, URLGrabError

try:
    import xattr
    if not hasattr(xattr, 'get'):
        xattr = None # This is a "newer" API.
except ImportError:
    xattr = None

# For verify
import pwd
import grp

def comparePoEVR(po1, po2):
    """
    Compare two Package or PackageEVR objects.
    """
    (e1, v1, r1) = (po1.epoch, po1.version, po1.release)
    (e2, v2, r2) = (po2.epoch, po2.version, po2.release)
    return rpmUtils.miscutils.compareEVR((e1, v1, r1), (e2, v2, r2))
def comparePoEVREQ(po1, po2):
    """
    Compare two Package or PackageEVR objects for equality.
    """
    (e1, v1, r1) = (po1.epoch, po1.version, po1.release)
    (e2, v2, r2) = (po2.epoch, po2.version, po2.release)
    if r1 != r2: return False
    if v1 != v2: return False
    if e1 != e2: return False
    return True

def buildPkgRefDict(pkgs, casematch=True):
    """take a list of pkg objects and return a dict the contains all the possible
       naming conventions for them eg: for (name,i386,0,1,1)
       dict[name] = (name, i386, 0, 1, 1)
       dict[name.i386] = (name, i386, 0, 1, 1)
       dict[name-1-1.i386] = (name, i386, 0, 1, 1)       
       dict[name-1] = (name, i386, 0, 1, 1)       
       dict[name-1-1] = (name, i386, 0, 1, 1)
       dict[0:name-1-1.i386] = (name, i386, 0, 1, 1)
       dict[name-0:1-1.i386] = (name, i386, 0, 1, 1)
       """
    pkgdict = {}
    for pkg in pkgs:
        (n, a, e, v, r) = pkg.pkgtup
        if not casematch:
            n = n.lower()
            a = a.lower()
            e = e.lower()
            v = v.lower()
            r = r.lower()
        name = n
        nameArch = '%s.%s' % (n, a)
        nameVerRelArch = '%s-%s-%s.%s' % (n, v, r, a)
        nameVer = '%s-%s' % (n, v)
        nameVerRel = '%s-%s-%s' % (n, v, r)
        envra = '%s:%s-%s-%s.%s' % (e, n, v, r, a)
        nevra = '%s-%s:%s-%s.%s' % (n, e, v, r, a)
        for item in [name, nameArch, nameVerRelArch, nameVer, nameVerRel, envra, nevra]:
            if item not in pkgdict:
                pkgdict[item] = []
            pkgdict[item].append(pkg)
            
    return pkgdict
       
def parsePackages(pkgs, usercommands, casematch=0,
                  unique='repo-epoch-name-version-release-arch'):
    """matches up the user request versus a pkg list:
       for installs/updates available pkgs should be the 'others list' 
       for removes it should be the installed list of pkgs
       takes an optional casematch option to determine if case should be matched
       exactly. Defaults to not matching."""

    pkgdict = buildPkgRefDict(pkgs, bool(casematch))
    exactmatch = []
    matched = []
    unmatched = []
    for command in usercommands:
        if not casematch:
            command = command.lower()
        if command in pkgdict:
            exactmatch.extend(pkgdict[command])
            del pkgdict[command]
        else:
            # anything we couldn't find a match for
            # could mean it's not there, could mean it's a wildcard
            if misc.re_glob(command):
                trylist = pkgdict.keys()
                # command and pkgdict are already lowered if not casematch
                # so case sensitive is always fine
                restring = fnmatch.translate(command)
                regex = re.compile(restring)
                foundit = 0
                for item in trylist:
                    if regex.match(item):
                        matched.extend(pkgdict[item])
                        del pkgdict[item]
                        foundit = 1
 
                if not foundit:    
                    unmatched.append(command)
                    
            else:
                unmatched.append(command)

    unmatched = misc.unique(unmatched)
    if unique == 'repo-epoch-name-version-release-arch': # pkg.__hash__
        matched    = misc.unique(matched)
        exactmatch = misc.unique(exactmatch)
    elif unique == 'repo-pkgkey': # So we get all pkg entries from a repo
        def pkgunique(pkgs):
            u = {}
            for pkg in pkgs:
                mark = "%s%s" % (pkg.repo.id, pkg.pkgKey)
                u[mark] = pkg
            return u.values()
        matched    = pkgunique(matched)
        exactmatch = pkgunique(exactmatch)
    else:
        raise ValueError, "Bad value for unique: %s" % unique
    return exactmatch, matched, unmatched

class FakeSack:
    """ Fake PackageSack to use with FakeRepository"""
    def __init__(self):
        pass # This is fake, so do nothing
    
    def have_fastReturnFileEntries(self):
        """ Is calling pkg.returnFileEntries(primary_only=True) faster than
            using searchFiles(). """
        return True

    def delPackage(self, obj):
        """delete a pkgobject, do nothing, but make localpackages work with --skip-broken"""
        pass # This is fake, so do nothing
            
class FakeRepository:
    """Fake repository class for use in rpmsack package objects"""

    def _set_cleanup_repoid(self, repoid):
        """ Set the repoid, but because it can be random ... clean it up. """

        #  We don't want repoids to contain random bytes that can be
        # in the FS directories. It's also nice if they aren't "huge". So
        # just chop to the rpm name.
        pathbased = False
        if '/' in repoid:
            repoid = os.path.basename(repoid)
            pathbased = True

        if repoid.endswith(".rpm"):
            repoid = repoid[:-4]
            pathbased = True

        bytes = [] # Just in case someone uses mv to be evil:
        if pathbased:
            bytes.append('/')

        for byte in repoid:
            if ord(byte) >= 128:
                byte = '?'
            bytes.append(byte)
        self.id = "".join(bytes)

    def __init__(self, repoid):
        self._set_cleanup_repoid(repoid)
        self.name = self.id
        self.sack = FakeSack()

    def __cmp__(self, other):
        if self.id > other.id:
            return 1
        elif self.id < other.id:
            return -1
        else:
            return 0
        
    def __hash__(self):
        return hash(self.id)

    def __str__(self):
        return self.id


#  Goal for the below is to have a packageobject that can be used by generic
# functions independent of the type of package - ie: installed or available
#  Note that this is also used to history etc. ... so it's more a nevra+checksum
# holder than a base for things which are actual packages.
class PackageObject(object):
    """Base Package Object - sets up the default storage dicts and the
       most common returns"""
       
    def __init__(self):
        self.name = None
        self.version = None
        self.release = None
        self.epoch = None
        self.arch = None
        # self.pkgtup = (self.name, self.arch, self.epoch, self.version, self.release)
        self._checksums = [] # (type, checksum, id(0,1)
        
    def _ui_envra(self):
        if self.epoch == '0':
            out = '%s-%s-%s.%s' % (self.name, 
                                   self.version,
                                   self.release, 
                                   self.arch)
        else:
            out = '%s:%s-%s-%s.%s' % (self.epoch,
                                      self.name,  
                                      self.version, 
                                      self.release, 
                                      self.arch)
        return out
    ui_envra = property(fget=lambda self: self._ui_envra())

    def _ui_nevra(self):
        if self.epoch == '0':
            out = '%s-%s-%s.%s' % (self.name,
                                   self.version,
                                   self.release,
                                   self.arch)
        else:
            out = '%s-%s:%s-%s.%s' % (self.name,
                                      self.epoch,
                                      self.version,
                                      self.release,
                                      self.arch)
        return out
    ui_nevra = property(fget=lambda self: self._ui_nevra())

    def __str__(self):
        return self.ui_envra

    def printVer(self):
        """returns a printable version string - including epoch, if it's set"""
        if self.epoch != '0':
            ver = '%s:%s-%s' % (self.epoch, self.version, self.release)
        else:
            ver = '%s-%s' % (self.version, self.release)

        return ver

    def verCMP(self, other):
        """ Compare package to another one, only rpm-version ordering. """
        if not other:
            return 1
        ret = cmp(self.name, other.name)
        if ret == 0:
            ret = comparePoEVR(self, other)
        return ret

    def __cmp__(self, other):
        """ Compare packages, this is just for UI/consistency. """
        ret = self.verCMP(other)
        if ret == 0:
            ret = cmp(self.arch, other.arch)
        if ret == 0 and hasattr(self, 'repoid') and hasattr(other, 'repoid'):
            ret = cmp(self.repoid, other.repoid)
            # We want 'installed' to appear over 'abcd' and 'xyz', so boost that
            if ret and self.repoid == 'installed':
                return 1
            if ret and other.repoid == 'installed':
                return -1
        return ret
    def __eq__(self, other):
        """ Compare packages for yes/no equality, includes everything in the
            UI package comparison. """
        if not other:
            return False
        if self.pkgtup != other.pkgtup:
            return False
        if hasattr(self, 'repoid') and hasattr(other, 'repoid'):
            if self.repoid != other.repoid:
                return False
        return True
    def __ne__(self, other):
        if not (self == other):
            return True
        return False

    def __getitem__(self, key):
        return getattr(self, key)

    def verEQ(self, other):
        """ Compare package to another one, only rpm-version equality. """
        if not other:
            return None
        ret = cmp(self.name, other.name)
        if ret != 0:
            return False
        return comparePoEVREQ(self, other)
    def verNE(self, other):
        """ Compare package to another one, only rpm-version inequality. """
        if not other:
            return None
        return not self.verEQ(other)
    def verLT(self, other):
        """ Uses verCMP, tests if the other _rpm-version_ is <  ours. """
        return self.verCMP(other) <  0
    def verLE(self, other):
        """ Uses verCMP, tests if the other _rpm-version_ is <= ours. """
        return self.verCMP(other) <= 0
    def verGT(self, other):
        """ Uses verCMP, tests if the other _rpm-version_ is >  ours. """
        return self.verCMP(other) >  0
    def verGE(self, other):
        """ Uses verCMP, tests if the other _rpm-version_ is >= ours. """
        return self.verCMP(other) >= 0

    def __repr__(self):
        return "<%s : %s (%s)>" % (self.__class__.__name__, str(self),hex(id(self))) 

    def returnSimple(self, varname):
        warnings.warn("returnSimple() will go away in a future version of Yum.\n",
                      Errors.YumFutureDeprecationWarning, stacklevel=2)
        return getattr(self, varname)

    def returnChecksums(self):
        return self._checksums

    checksums = property(fget=lambda self: self.returnChecksums())
    
    def returnIdSum(self):
        for (csumtype, csum, csumid) in self.checksums:
            if csumid:
                return (csumtype, csum)


_not_found_repo = FakeRepository('-')
_not_found_repo.cost = 0
class YumNotFoundPackage(PackageObject):

    def __init__(self, pkgtup):
        self.name    = pkgtup[0]
        self.arch    = pkgtup[1]
        self.epoch   = pkgtup[2]
        self.version = pkgtup[3]
        self.release = pkgtup[4]
        self.pkgtup  = pkgtup

        self.size = 0
        self._checksums = [] # (type, checksum, id(0,1)

        self.repo = _not_found_repo
        self.repoid = _not_found_repo.id

    # Fakeout output.py that it's a real pkg. ...
    def _ui_from_repo(self):
        """ This just returns '-' """
        return self.repoid
    ui_from_repo = property(fget=lambda self: self._ui_from_repo())

    def verifyLocalPkg(self):
        """check the package checksum vs the localPkg
           return True if pkg is good, False if not"""
        return False

#  This is the virtual base class of actual packages, it basically requires a
# repo. even though it doesn't set one up in it's __init__. It also doesn't have
# PackageObject methods ... so is basically unusable on it's own
# see: YumAvailablePackage.
class RpmBase(object):
    """return functions and storage for rpm-specific data"""

    def __init__(self):
        self.prco = {}
        self.prco['obsoletes'] = [] # (name, flag, (e,v,r))
        self.prco['conflicts'] = [] # (name, flag, (e,v,r))
        self.prco['requires'] = [] # (name, flag, (e,v,r))
        self.prco['provides'] = [] # (name, flag, (e,v,r))
        self.files = {}
        self.files['file'] = []
        self.files['dir'] = []
        self.files['ghost'] = []
        self._changelog = [] # (ctime, cname, ctext)
        self.licenses = []
        self._hash = None

    # FIXME: This is identical to PackageObject.__eq__ and __ne__, should be
    #        remove (is .repoid fine here? ... we need it, maybe .repo.id).
    def __eq__(self, other):
        if not other: # check if other not is a package object. 
            return False
        if self.pkgtup != other.pkgtup:
            return False
        if self.repoid != other.repoid:
            return False
        return True
    def __ne__(self, other):
        if not (self == other):
            return True
        return False

    def returnEVR(self):
        return PackageEVR(self.epoch, self.version, self.release)
    
    def __hash__(self):
        if self._hash is None:
            mystr = '%s - %s:%s-%s-%s.%s' % (self.repo.id, self.epoch, self.name,
                                         self.version, self.release, self.arch)
            self._hash = hash(mystr)
        return self._hash
        
    def returnPrco(self, prcotype, printable=False):
        """return list of provides, requires, conflicts or obsoletes"""
        
        prcos = self.prco.get(prcotype, [])

        if printable:
            results = []
            for prco in prcos:
                if not prco[0]: # empty or none or whatever, doesn't matter
                    continue
                results.append(misc.prco_tuple_to_string(prco))
            return results

        return prcos

    def checkPrco(self, prcotype, prcotuple):
        """returns 1 or 0 if the pkg contains the requested tuple/tuple range"""
        # get rid of simple cases - nothing
        if prcotype not in self.prco:
            return 0

        # First try and exact match, then search
        # Make it faster, if it's "big".
        if len(self.prco[prcotype]) <= 8:
            if prcotuple in self.prco[prcotype]:
                return 1
        else:
            if not hasattr(self, '_prco_lookup'):
                self._prco_lookup = {'obsoletes' : None, 'conflicts' : None,
                                     'requires'  : None, 'provides'  : None}

            if self._prco_lookup[prcotype] is None:
                self._prco_lookup[prcotype] = set(self.prco[prcotype])

            if prcotuple in self._prco_lookup[prcotype]:
                return 1

        if True: # Keep indentation for patch smallness...
            # make us look it up and compare
            (reqn, reqf, (reqe, reqv ,reqr)) = prcotuple
            if reqf is not None:
                return self.inPrcoRange(prcotype, prcotuple)
            else:
                for (n, f, (e, v, r)) in self.returnPrco(prcotype):
                    if i18n.str_eq(reqn, n):
                        return 1

        return 0

    def inPrcoRange(self, prcotype, reqtuple):
        """returns true if the package has a the prco that satisfies 
           the reqtuple range, assume false.
           Takes: prcotype, requested prco tuple"""
        return bool(self.matchingPrcos(prcotype, reqtuple))

    def matchingPrcos(self, prcotype, reqtuple):
        (reqn, reqf, (reqe, reqv, reqr)) = reqtuple
        # find the named entry in pkgobj, do the comparsion
        result = []
        for (n, f, (e, v, r)) in self.returnPrco(prcotype):
            if not i18n.str_eq(reqn, n):
                continue

            if f == '=':
                f = 'EQ'
            if f != 'EQ' and prcotype == 'provides':
                # isn't this odd, it's not 'EQ' and it is a provides
                # - it really should be EQ
                # use the pkgobj's evr for the comparison
                if e is None:
                    e = self.epoch
                if v is None:
                    v = self.ver
                if r is None:
                    r = self.rel
                #(e, v, r) = (self.epoch, self.ver, self.rel)

            matched = rpmUtils.miscutils.rangeCompare(
                reqtuple, (n, f, (e, v, r)))
            if matched:
                result.append((n, f, (e, v, r)))

        return result

    def provides_for(self, reqtuple):
        """check to see if the package object provides for the requirement
           passed, including searching filelists if the requirement is a file
           dep"""
        
        if self.checkPrco('provides', reqtuple):
            return True
        
        if reqtuple[0].startswith('/'):
            if misc.re_primary_filename(reqtuple[0]):
                pri_only = True
            else:
                pri_only = False

            for ftype in ('file', 'dir', 'ghost'):
                if reqtuple[0] in self.returnFileEntries(ftype, pri_only):
                    return True
        
        return False
        
    def returnChangelog(self):
        """return changelog entries"""
        return self._changelog
        
    def returnFileEntries(self, ftype='file', primary_only=False):
        """return list of files based on type, you can pass primary_only=True
           to limit to those files in the primary repodata"""
        if self.files:
            if ftype in self.files:
                if primary_only:
                    if ftype == 'dir':
                        match = misc.re_primary_dirname
                    else:
                        match = misc.re_primary_filename
                    return [fn for fn in self.files[ftype] if match(fn)]
                return self.files[ftype]
        return []
            
    def returnFileTypes(self, primary_only=False):
        """return list of types of files in the package, you can pass
           primary_only=True to limit to those files in the primary repodata"""
        if primary_only:
            ret = [] # We only return the types for the primary files.
            for ftype in self.files.keys():
                if ftype == 'dir':
                    match = misc.re_primary_dirname
                else:
                    match = misc.re_primary_filename
                #  As soon as we find a primary file of this type, we can
                # return it.
                for fn in self.files[ftype]:
                    if match(fn):
                        break
                else:
                    continue
                ret.append(ftype)
            return ret

        return self.files.keys()

    def returnPrcoNames(self, prcotype):
        if not hasattr(self, '_cache_prco_names_' + prcotype):
            data = [n for (n, f, v) in self.returnPrco(prcotype)]
            setattr(self, '_cache_prco_names_' + prcotype, data)
        return getattr(self, '_cache_prco_names_' + prcotype)

    def getProvidesNames(self):
        warnings.warn('getProvidesNames() will go away in a future version of Yum.\n',
                      Errors.YumDeprecationWarning, stacklevel=2)
        return self.provides_names

    def simpleFiles(self, ftype='files'):
        warnings.warn('simpleFiles() will go away in a future version of Yum.'
                      'Use returnFileEntries(primary_only=True)\n',
                      Errors.YumDeprecationWarning, stacklevel=2)
        if self.files and ftype in self.files:
            return self.files[ftype]
        return []
    
    filelist = property(fget=lambda self: self.returnFileEntries(ftype='file'))
    dirlist = property(fget=lambda self: self.returnFileEntries(ftype='dir'))
    ghostlist = property(fget=lambda self: self.returnFileEntries(ftype='ghost'))
    requires = property(fget=lambda self: self.returnPrco('requires'))
    provides = property(fget=lambda self: self.returnPrco('provides'))
    obsoletes = property(fget=lambda self: self.returnPrco('obsoletes'))
    conflicts = property(fget=lambda self: self.returnPrco('conflicts'))
    provides_names = property(fget=lambda self: self.returnPrcoNames('provides'))
    requires_names = property(fget=lambda self: self.returnPrcoNames('requires'))
    conflicts_names = property(fget=lambda self: self.returnPrcoNames('conflicts'))
    obsoletes_names = property(fget=lambda self: self.returnPrcoNames('obsoletes'))
    provides_print = property(fget=lambda self: self.returnPrco('provides', True))
    requires_print = property(fget=lambda self: self.returnPrco('requires', True))
    conflicts_print = property(fget=lambda self: self.returnPrco('conflicts', True))
    obsoletes_print = property(fget=lambda self: self.returnPrco('obsoletes', True))
    changelog = property(fget=lambda self: self.returnChangelog())
    EVR = property(fget=lambda self: self.returnEVR())
    
    def _getBaseName(self):
        """ Return the "base name" of the package, atm. we can only look at
            the sourcerpm. """
        if hasattr(self, '_base_package_name_ret'):
            return self._base_package_name_ret

        if hasattr(self, 'sourcerpm') and self.sourcerpm:
            (n, v, r, e, a) = rpmUtils.miscutils.splitFilename(self.sourcerpm)
            if n != self.name:
                self._base_package_name_ret = n
                return n

        # If there is no sourcerpm, or sourcerpm == us, use .name
        self._base_package_name_ret = self.name
        return self._base_package_name_ret

    base_package_name = property(fget=lambda self: self._getBaseName())

    def have_fastReturnFileEntries(self):
        """ Is calling pkg.returnFileEntries(primary_only=True) faster than
            using searchFiles(). """
        return self.repo.sack.have_fastReturnFileEntries()

    def obsoletedBy(self, obsoleters, limit=0):
        """ Returns list of obsoleters that obsolete this package. Note that we
            don't do obsoleting loops. If limit is != 0, then we stop after
            finding that many. """
        provtup = (self.name, 'EQ', (self.epoch, self.version, self.release))
        ret = []
        for obspo in obsoleters:
            if obspo.inPrcoRange('obsoletes', provtup):
                ret.append(obspo)
                if limit and len(ret) > limit:
                    break
        return ret



# This is kind of deprecated
class PackageEVR:

    """
    A comparable epoch, version, and release representation. Note that you
    almost certainly want to use pkg.verEQ() or pkg.verGT() etc. instead.
    """
    
    def __init__(self,e,v,r):
        self.epoch = e
        self.ver = v
        self.version = v
        self.rel = r
        self.release = r
        
    def compare(self,other):
        return rpmUtils.miscutils.compareEVR((self.epoch, self.ver, self.rel), (other.epoch, other.ver, other.rel))
    
    def __lt__(self, other):
        if self.compare(other) < 0:
            return True
        return False

        
    def __gt__(self, other):
        if self.compare(other) > 0:
            return True
        return False

    def __le__(self, other):
        if self.compare(other) <= 0:
            return True
        return False

    def __ge__(self, other):
        if self.compare(other) >= 0:
            return True
        return False

    def __eq__(self, other):
        return comparePoEVREQ(self, other)

    def __ne__(self, other):
        if not (self == other):
            return True
        return False
    

#  This is the real base class of actual packages, it has a repo. and is
# usable on it's own, in theory (but in practise see sqlitesack).
class YumAvailablePackage(PackageObject, RpmBase):
    """derived class for the  packageobject and RpmBase packageobject yum
       uses this for dealing with packages in a repository"""

    def __init__(self, repo, pkgdict = None):
        PackageObject.__init__(self)
        RpmBase.__init__(self)
        
        self.repoid = repo.id
        self.repo = repo
        self.state = None
        self._loadedfiles = False
        self._verify_local_pkg_cache = None

        if pkgdict != None:
            self.importFromDict(pkgdict)
            self.ver = self.version
            self.rel = self.release
        self.pkgtup = (self.name, self.arch, self.epoch, self.version, self.release)

    def _ui_from_repo(self):
        """ This reports the repo the package is from, we integrate YUMDB info.
            for RPM packages so a package from "fedora" that is installed has a
            ui_from_repo of "@fedora". Note that, esp. with the --releasever
            option, "fedora" or "rawhide" isn't authoritive.
            So we also check against the current releasever and if it is
            different we also print the YUMDB releasever. This means that
            installing from F12 fedora, while running F12, would report as
            "@fedora/13". """
        if self.repoid == 'installed' and 'from_repo' in self.yumdb_info:
            end = ''
            if (self.rpmdb.releasever is not None and
                'releasever' in self.yumdb_info and
                self.yumdb_info.releasever != self.rpmdb.releasever):
                end = '/' + self.yumdb_info.releasever
            return '@' + self.yumdb_info.from_repo + end
        return self.repoid
    ui_from_repo = property(fget=lambda self: self._ui_from_repo())

    def exclude(self):
        """remove self from package sack"""
        self.repo.sack.delPackage(self)
        
    def printVer(self):
        """returns a printable version string - including epoch, if it's set"""
        if self.epoch != '0':
            ver = '%s:%s-%s' % (self.epoch, self.version, self.release)
        else:
            ver = '%s-%s' % (self.version, self.release)
        
        return ver
    
    def compactPrint(self):
        ver = self.printVer()
        return "%s.%s %s" % (self.name, self.arch, ver)

    def _size(self):
        return self.packagesize
    
    def _remote_path(self):
        return self.relativepath

    def _remote_url(self):
        """returns a URL that can be used for downloading the package.
        Note that if you're going to download the package in your tool,
        you should use self.repo.getPackage."""
        base = self.basepath
        if base:
            # urljoin sucks in the reverse way that os.path.join sucks :)
            if base[-1] != '/':
                base = base + '/'
            return urlparse.urljoin(base, self.remote_path)
        return urlparse.urljoin(self.repo.urls[0], self.remote_path)

    size = property(fget=lambda self: self._size())
    remote_path = property(_remote_path)
    remote_url = property(_remote_url)

    def _committer(self):
        "Returns the name of the last person to do a commit to the changelog."

        if hasattr(self, '_committer_ret'):
            return self._committer_ret

        def _nf2ascii(x):
            """ does .encode("ascii", "replace") but it never fails. """
            ret = []
            for val in x:
                if ord(val) >= 128:
                    val = '?'
                ret.append(val)
            return "".join(ret)

        if not len(self.changelog): # Empty changelog is _possible_ I guess
            self._committer_ret = self.packager
            return self._committer_ret
        val = self.changelog[0][1]
        # Chagnelog data is in multiple locale's, so we convert to ascii
        # ignoring "bad" chars.
        val = _nf2ascii(val)
        # Hacky way to get rid of version numbers...
        ix = val.find('> ')
        if ix != -1:
            val = val[0:ix+1]
        self._committer_ret = val
        return self._committer_ret

    committer  = property(_committer)
    
    def _committime(self):
        "Returns the time of the last commit to the changelog."

        if hasattr(self, '_committime_ret'):
            return self._committime_ret

        if not len(self.changelog): # Empty changelog is _possible_ I guess
            self._committime_ret = self.buildtime
            return self._committime_ret
        
        self._committime_ret = self.changelog[0][0]
        return self._committime_ret

    committime = property(_committime)
    
    # FIXME test this to see if it causes hell elsewhere
    def _checksum(self):
        "Returns the 'default' checksum"
        return self.checksums[0][1]
    checksum = property(_checksum)

    def getDiscNum(self):
        if self.basepath is None:
            return None
        (scheme, netloc, path, query, fragid) = urlparse.urlsplit(self.basepath)
        if scheme == "media":
            if len(fragid) == 0:
                return 0
            return int(fragid)
        return None
    
    def returnHeaderFromPackage(self):
        rpmfile = self.localPkg()
        ts = rpmUtils.transaction.initReadOnlyTransaction()
        try:
            hdr = rpmUtils.miscutils.hdrFromPackage(ts, rpmfile)
        except rpmUtils.RpmUtilsError:
            raise Errors.RepoError, 'Package Header %s: RPM Cannot open' % self
        return hdr
        
    def returnLocalHeader(self):
        """returns an rpm header object from the package object's local
           header cache"""
        
        if os.path.exists(self.localHdr()):
            try: 
                hlist = rpm.readHeaderListFromFile(self.localHdr())
                hdr = hlist[0]
            except (rpm.error, IndexError):
                raise Errors.RepoError, 'Package Header %s: Cannot open' % self
        else:
            raise Errors.RepoError, 'Package Header %s: Not Available' % self

        return hdr

       
    def localPkg(self):
        """return path to local package (whether it is present there, or not)"""
        if not hasattr(self, 'localpath'):
            rpmfn = os.path.basename(self.remote_path)
            self.localpath = self.repo.pkgdir + '/' + rpmfn
        return self.localpath

    def localHdr(self):
        """return path to local cached Header file downloaded from package 
           byte ranges"""
           
        if not hasattr(self, 'hdrpath'):
            pkgname = os.path.basename(self.remote_path)
            hdrname = pkgname[:-4] + '.hdr'
            self.hdrpath = self.repo.hdrdir + '/' + hdrname

        return self.hdrpath
    
    def verifyLocalPkg(self):
        """check the package checksum vs the localPkg
           return True if pkg is good, False if not"""

        #  This is called a few times now, so we want some way to not have to
        # read+checksum "large" datasets multiple times per. transaction.
        try:
            nst = os.stat(self.localPkg())
        except OSError, e:
            return False
        if (hasattr(self, '_verify_local_pkg_cache') and
            self._verify_local_pkg_cache):
            ost = self._verify_local_pkg_cache
            if (ost.st_ino   == nst.st_ino   and
                ost.st_dev   == nst.st_dev   and
                ost.st_mtime == nst.st_mtime and
                ost.st_size  == nst.st_size):
                return True

        (csum_type, csum) = self.returnIdSum()
        
        try:
            filesum = misc.checksum(csum_type, self.localPkg(),
                                    datasize=self.packagesize)
        except Errors.MiscError:
            return False
        
        if filesum != csum:
            return False
        
        self._verify_local_pkg_cache = nst

        return True

    # See: http://www.freedesktop.org/wiki/CommonExtendedAttributes
    def _localXattrUrl(self):
        """ Get the user.xdg.origin.url value from the local pkg. ... if it's
            present. We cache this so we can access it after the file has been
            deleted (keepcache=False). """

        if xattr is None:
            return None

        if hasattr(self, '__cached_localXattrUrl'):
            return getattr(self, '__cached_localXattrUrl')

        if not self.verifyLocalPkg():
            return None

        try:
            ret = xattr.get(self.localPkg(), 'user.xdg.origin.url')
        except: # Documented to be "EnvironmentError", but make sure
            return None

        setattr(self, '__cached_localXattrUrl', ret)
        return ret

    xattr_origin_url = property(lambda x: x._localXattrUrl())

    def prcoPrintable(self, prcoTuple):
        """convert the prco tuples into a nicer human string"""
        warnings.warn('prcoPrintable() will go away in a future version of Yum.\n',
                      Errors.YumDeprecationWarning, stacklevel=2)
        return misc.prco_tuple_to_string(prcoTuple)

    def requiresList(self):
        """return a list of requires in normal rpm format"""
        return self.requires_print

    def returnChecksums(self):
        return [(self.checksum_type, self.pkgId, 1)]
        
    def importFromDict(self, pkgdict):
        """handles an mdCache package dictionary item to populate out 
           the package information"""
        
        # translates from the pkgdict, populating out the information for the
        # packageObject
        
        if hasattr(pkgdict, 'nevra'):
            (n, e, v, r, a) = pkgdict.nevra
            self.name = n
            self.epoch = e
            self.version = v
            self.arch = a
            self.release = r
        
        if hasattr(pkgdict, 'time'):
            self.buildtime = pkgdict.time['build']
            self.filetime = pkgdict.time['file']
        
        if hasattr(pkgdict, 'size'):
            self.packagesize = pkgdict.size['package']
            self.archivesize = pkgdict.size['archive']
            self.installedsize = pkgdict.size['installed']
        
        if hasattr(pkgdict, 'location'):
            url = pkgdict.location.get('base')
            if url == '':
                url = None

            self.basepath = url
            self.relativepath = pkgdict.location['href']

        if hasattr(pkgdict, 'hdrange'):
            self.hdrstart = pkgdict.hdrange['start']
            self.hdrend = pkgdict.hdrange['end']
        
        if hasattr(pkgdict, 'info'):
            for item in ['summary', 'description', 'packager', 'group',
                         'buildhost', 'sourcerpm', 'url', 'vendor']:
                setattr(self, item, pkgdict.info[item])
            self.summary = self.summary.replace('\n', '')
            
            self.licenses.append(pkgdict.info['license'])
        
        if hasattr(pkgdict, 'files'):
            for fn in pkgdict.files:
                ftype = pkgdict.files[fn]
                if ftype not in self.files:
                    self.files[ftype] = []
                self.files[ftype].append(fn)
        
        if hasattr(pkgdict, 'prco'):
            for rtype in pkgdict.prco:
                for rdict in pkgdict.prco[rtype]:
                    name = rdict['name']
                    f = rdict.get('flags')
                    e = rdict.get('epoch')
                    v = rdict.get('ver')
                    r = rdict.get('rel')
                    self.prco[rtype].append((name, f, (e,v,r)))

        if hasattr(pkgdict, 'changelog'):
            for cdict in pkgdict.changelog:
                date = cdict.get('date')
                text = cdict.get('value')
                author = cdict.get('author')
                self._changelog.append((date, author, text))
        
        if hasattr(pkgdict, 'checksum'):
            ctype = pkgdict.checksum['type']
            csum = pkgdict.checksum['value']
            csumid = pkgdict.checksum['pkgid']
            if csumid is None or csumid.upper() == 'NO':
                csumid = 0
            elif csumid.upper() == 'YES':
                csumid = 1
            else:
                csumid = 0
            self._checksums.append((ctype, csum, csumid))

# from here down this is for dumping a package object back out to metadata
    
    
    def _return_remote_location(self):
        # break self.remote_url up into smaller pieces
        base = os.path.dirname(self.remote_url)
        href = os.path.basename(self.remote_url)
        msg = """<location xml:base="%s" href="%s"/>\n""" % (
                  misc.to_xml(base,attrib=True), misc.to_xml(href, attrib=True))
        return msg
        
    def _dump_base_items(self):
        
        packager = url = ''
        if self.packager:
            packager = misc.to_unicode(misc.to_xml(self.packager))
        
        if self.url:
            url = misc.to_unicode(misc.to_xml(self.url))
        (csum_type, csum, csumid) = self.checksums[0]
        msg = """
  <name>%s</name>
  <arch>%s</arch>
  <version epoch="%s" ver="%s" rel="%s"/>
  <checksum type="%s" pkgid="YES">%s</checksum>
  <summary>%s</summary>
  <description>%s</description>
  <packager>%s</packager>
  <url>%s</url>
  <time file="%s" build="%s"/>
  <size package="%s" installed="%s" archive="%s"/>\n""" % (self.name, 
         self.arch, self.epoch, self.ver, self.rel, csum_type, csum, 
         misc.to_unicode(misc.to_xml(self.summary)), 
         misc.to_unicode(misc.to_xml(self.description)), 
         packager, url, self.filetime, 
         self.buildtime, self.packagesize, self.size, self.archivesize)
        
        msg += self._return_remote_location()
        return msg

    def _dump_format_items(self):
        msg = "  <format>\n"
        if self.license:
            msg += """    <rpm:license>%s</rpm:license>\n""" % misc.to_xml(self.license)
        else:
            msg += """    <rpm:license/>\n"""
            
        if self.vendor:
            msg += """    <rpm:vendor>%s</rpm:vendor>\n""" % misc.to_xml(self.vendor)
        else:
            msg += """    <rpm:vendor/>\n"""
            
        if self.group:
            msg += """    <rpm:group>%s</rpm:group>\n""" % misc.to_xml(self.group)
        else:
            msg += """    <rpm:group/>\n"""
            
        if self.buildhost:
            msg += """    <rpm:buildhost>%s</rpm:buildhost>\n""" % misc.to_xml(self.buildhost)
        else:
            msg += """    <rpm:buildhost/>\n"""
            
        if self.sourcerpm:
            msg += """    <rpm:sourcerpm>%s</rpm:sourcerpm>\n""" % misc.to_xml(self.sourcerpm)
        else: # b/c yum 2.4.3 and OLD y-m-p willgfreak out if it is not there.
            msg += """    <rpm:sourcerpm/>\n"""
        
        msg +="""    <rpm:header-range start="%s" end="%s"/>""" % (self.hdrstart,
                                                               self.hdrend)
        msg += self._dump_pco('provides')
        msg += self._dump_requires()
        msg += self._dump_pco('conflicts')         
        msg += self._dump_pco('obsoletes')         
        msg += self._dump_files(True)
        if msg[-1] != '\n':
            msg += """\n"""
        msg += """  </format>"""
        
        return msg

    def _dump_pco(self, pcotype):
           
        msg = ""
        mylist = getattr(self, pcotype)
        if mylist: msg = "\n    <rpm:%s>\n" % pcotype
        for (name, flags, (e,v,r)) in mylist:
            pcostring = '''      <rpm:entry name="%s"''' % misc.to_xml(name, attrib=True)
            if flags:
                pcostring += ''' flags="%s"''' % misc.to_xml(flags, attrib=True)
                if e:
                    pcostring += ''' epoch="%s"''' % misc.to_xml(e, attrib=True)
                if v:
                    pcostring += ''' ver="%s"''' % misc.to_xml(v, attrib=True)
                if r:
                    pcostring += ''' rel="%s"''' % misc.to_xml(r, attrib=True)
                    
            pcostring += "/>\n"
            msg += pcostring
            
        if mylist: msg += "    </rpm:%s>" % pcotype
        return msg
    
    def _dump_files(self, primary=False):
        msg ="\n"
        if not primary:
            files = self.returnFileEntries('file')
            dirs = self.returnFileEntries('dir')
            ghosts = self.returnFileEntries('ghost')
        else:
            files = self.returnFileEntries('file', primary_only=True)
            dirs = self.returnFileEntries('dir', primary_only=True)
            ghosts = self.returnFileEntries('ghost', primary_only=True)
                
        for fn in files:
            msg += """    <file>%s</file>\n""" % misc.to_xml(fn)
        for fn in dirs:
            msg += """    <file type="dir">%s</file>\n""" % misc.to_xml(fn)
        for fn in ghosts:
            msg += """    <file type="ghost">%s</file>\n""" % misc.to_xml(fn)
        
        return msg


    def _requires_with_pre(self):
        raise NotImplementedError()
                    
    def _dump_requires(self):
        """returns deps in XML format"""
        mylist = self._requires_with_pre()

        msg = ""

        if mylist: msg = "\n    <rpm:requires>\n"
        if hasattr(self, '_collapse_libc_requires') and self._collapse_libc_requires:
            libc_requires = filter(lambda x: x[0].startswith('libc.so.6'), mylist)
            if libc_requires:
                rest = sorted(libc_requires, cmp=compareVerOnly, key=itemgetter(0))
                best = rest.pop()
                if len(rest) > 0 and best[0].startswith('libc.so.6()'): # rpmvercmp will sort this one as 'highest' so we need to remove it from the list
                    best = rest.pop()
                newlist = []
                for i in mylist:
                    if i[0].startswith('libc.so.6') and i != best:
                        continue
                    newlist.append(i)
                mylist = newlist
        
        for (name, flags, (e,v,r),pre) in mylist:
            if name.startswith('rpmlib('):
                continue
            # this drops out requires that the pkg provides for itself.
            if name in self.provides_names or \
                    (name.startswith('/') and \
                         (name in self.filelist or name in self.dirlist or
                          name in self.ghostlist)):
                if not flags:
                    continue
                else:
                    if self.checkPrco('provides', (name, flags, (e,v,r))):
                        continue
            prcostring = '''      <rpm:entry name="%s"''' % misc.to_xml(name, attrib=True)
            if flags:
                prcostring += ''' flags="%s"''' % misc.to_xml(flags, attrib=True)
                if e:
                    prcostring += ''' epoch="%s"''' % misc.to_xml(e, attrib=True)
                if v:
                    prcostring += ''' ver="%s"''' % misc.to_xml(v, attrib=True)
                if r:
                    prcostring += ''' rel="%s"''' % misc.to_xml(r, attrib=True)
            if pre:
                prcostring += ''' pre="%s"''' % pre
                    
            prcostring += "/>\n"
            msg += prcostring
            
        if mylist: msg += "    </rpm:requires>"
        return msg

    def _dump_changelog(self, clog_limit):
        if not self.changelog:
            return ""
        msg = "\n"
        # We need to output them "backwards", so the oldest is first
        if not clog_limit:
            clogs = self.changelog
        else:
            clogs = self.changelog[:clog_limit]
        last_ts = 0
        hack_ts = 0
        for (ts, author, content) in reversed(clogs):
            if ts != last_ts:
                hack_ts = 0
            else:
                hack_ts += 1
            last_ts = ts
            ts += hack_ts
            msg += """<changelog author="%s" date="%s">%s</changelog>\n""" % (
                        misc.to_xml(author, attrib=True), misc.to_xml(str(ts)), 
                        misc.to_xml(content))
        return msg

    def xml_dump_primary_metadata(self):
        msg = """\n<package type="rpm">"""
        msg += misc.to_unicode(self._dump_base_items())
        msg += misc.to_unicode(self._dump_format_items())
        msg += """\n</package>"""
        return misc.to_utf8(msg)

    def xml_dump_filelists_metadata(self):
        msg = """\n<package pkgid="%s" name="%s" arch="%s">
    <version epoch="%s" ver="%s" rel="%s"/>\n""" % (self.checksum, self.name, 
                                     self.arch, self.epoch, self.ver, self.rel)
        msg += misc.to_unicode(self._dump_files())
        msg += "</package>\n"
        return misc.to_utf8(msg)

    def xml_dump_other_metadata(self, clog_limit=0):
        msg = """\n<package pkgid="%s" name="%s" arch="%s">
    <version epoch="%s" ver="%s" rel="%s"/>\n""" % (self.checksum, self.name, 
                                     self.arch, self.epoch, self.ver, self.rel)
        msg += "%s\n</package>\n" % misc.to_unicode(self._dump_changelog(clog_limit))
        return misc.to_utf8(msg)



#  This is a tweak on YumAvailablePackage() and is a base class for packages
# which are actual rpms.
class YumHeaderPackage(YumAvailablePackage):
    """Package object built from an rpm header"""
    def __init__(self, repo, hdr):
        """hand in an rpm header, we'll assume it's installed and query from there"""
       
        YumAvailablePackage.__init__(self, repo)

        self.hdr = hdr
        self.name = misc.share_data(self.hdr['name'])
        this_a = self.hdr['arch']
        if not this_a: # this should only happen on gpgkeys and other "odd" pkgs
            this_a = 'noarch'
        self.arch = misc.share_data(this_a)
        self.epoch = misc.share_data(self.doepoch())
        self.version = misc.share_data(self.hdr['version'])
        self.release = misc.share_data(self.hdr['release'])
        self.ver = self.version
        self.rel = self.release
        self.pkgtup = (self.name, self.arch, self.epoch, self.version, self.release)
        self._loaded_summary = None
        self._loaded_description = None
        self.pkgid = self.hdr[rpm.RPMTAG_SHA1HEADER]
        if not self.pkgid:
            self.pkgid = "%s.%s" %(self.hdr['name'], self.hdr['buildtime'])
        self.packagesize = self.hdr['size']
        self.__mode_cache = {}
        self.__prcoPopulated = False

    def _loadSummary(self):
        # Summaries "can be" empty, which rpm return [], see BZ 473239, *sigh*
        if self._loaded_summary is None:
            summary = self._get_hdr()['summary'] or ''
            summary = misc.share_data(summary.replace('\n', ''))
            self._loaded_summary = summary
        return self._loaded_summary
    summary = property(lambda x: x._loadSummary())

    def _loadDescription(self):
        if self._loaded_description is None:
            description = self._get_hdr()['description'] or ''
            description = misc.share_data(description)
            self._loaded_description = description
        return self._loaded_description
    description = property(lambda x: x._loadDescription())

    def __str__(self):
        if self.epoch == '0':
            val = '%s-%s-%s.%s' % (self.name, self.version, self.release,
                                        self.arch)
        else:
            val = '%s:%s-%s-%s.%s' % (self.epoch,self.name, self.version,
                                           self.release, self.arch)
        return val

    def returnPrco(self, prcotype, printable=False):
        if not self.__prcoPopulated:
            self._populatePrco()
            self.__prcoPopulated = True
        return YumAvailablePackage.returnPrco(self, prcotype, printable)

    def _get_hdr(self):
        return self.hdr

    def _populatePrco(self):
        "Populate the package object with the needed PRCO interface."

        tag2prco = { "OBSOLETE": misc.share_data("obsoletes"),
                     "CONFLICT": misc.share_data("conflicts"),
                     "REQUIRE":  misc.share_data("requires"),
                     "PROVIDE":  misc.share_data("provides") }
        hdr = self._get_hdr()
        for tag in tag2prco:
            name = hdr[getattr(rpm, 'RPMTAG_%sNAME' % tag)]
            name = map(misc.share_data, name)
            if not name: # empty or none or whatever, doesn't matter
                continue

            lst = hdr[getattr(rpm, 'RPMTAG_%sFLAGS' % tag)]
            flag = map(rpmUtils.miscutils.flagToString, lst)
            flag = map(misc.share_data, flag)

            lst = hdr[getattr(rpm, 'RPMTAG_%sVERSION' % tag)]
            vers = map(rpmUtils.miscutils.stringToVersion, lst)
            vers = map(lambda x: (misc.share_data(x[0]), misc.share_data(x[1]),
                                  misc.share_data(x[2])), vers)

            prcotype = tag2prco[tag]
            self.prco[prcotype] = map(misc.share_data, zip(name,flag,vers))
    
    def tagByName(self, tag):
        warnings.warn("tagByName() will go away in a furture version of Yum.\n",
                      Errors.YumFutureDeprecationWarning, stacklevel=2)
        try:
            return getattr(self, tag)
        except AttributeError:
            raise Errors.MiscError, "Unknown header tag %s" % tag

    def __getattr__(self, thing):
        #FIXME - if an error - return AttributeError, not KeyError 
        # ONLY FIX THIS AFTER THE API BREAK
        if thing.startswith('__') and thing.endswith('__'):
            # If these existed, then we wouldn't get here ...
            # So these are missing.
            raise AttributeError, "%s has no attribute %s" % (self, thing)
        try:
            return self.hdr[thing]
        except KeyError:
            #  Note above, API break to fix this ... this at least is a nicer
            # msg. so we know what we accessed that is bad.
            raise KeyError, "%s has no attribute %s" % (self, thing)
        except ValueError:
            #  Note above, API break to fix this ... this at least is a nicer
            # msg. so we know what we accessed that is bad.
            raise ValueError, "%s has no attribute %s" % (self, thing)

    def doepoch(self):
        tmpepoch = self.hdr['epoch']
        if tmpepoch is None:
            epoch = '0'
        else:
            epoch = str(tmpepoch)
        
        return epoch

    def returnLocalHeader(self):
        return self.hdr
    

    def _loadFiles(self):
        files = self.hdr['filenames']
        fileflags = self.hdr['fileflags']
        filemodes = self.hdr['filemodes']
        filetuple = zip(files, filemodes, fileflags)
        if not self._loadedfiles:
            for (fn, mode, flag) in filetuple:
                #garbage checks
                if mode is None or mode == '':
                    if 'file' not in self.files:
                        self.files['file'] = []
                    self.files['file'].append(fn)
                    continue
                if mode not in self.__mode_cache:
                    self.__mode_cache[mode] = stat.S_ISDIR(mode)
          
                fkey = 'file'
                if self.__mode_cache[mode]:
                    fkey = 'dir'
                elif flag is not None and (flag & 64):
                    fkey = 'ghost'
                self.files.setdefault(fkey, []).append(fn)

            self._loadedfiles = True
            
    def returnFileEntries(self, ftype='file', primary_only=False):
        """return list of files based on type"""
        self._loadFiles()
        return YumAvailablePackage.returnFileEntries(self,ftype,primary_only)
    
    def returnChangelog(self):
        # note - if we think it is worth keeping changelogs in memory
        # then create a _loadChangelog() method to put them into the 
        # self._changelog attr
        if len(self.hdr['changelogname']) > 0:
            return zip(misc.to_unicode(self.hdr['changelogtime'], errors='replace'),
                       misc.to_unicode(self.hdr['changelogname'], errors='replace'),
                       misc.to_unicode(self.hdr['changelogtext'], errors='replace'))
        return []

    def returnChecksums(self):
        raise NotImplementedError()

    def _size(self):
        return self.hdr['size']

    def _is_pre_req(self, flag):
        """check the flags for a requirement, return 1 or 0 whether or not requires
           is a pre-requires or a not"""
        # FIXME this should probably be put in rpmUtils.miscutils since 
        # - that's what it is
        if flag is not None:
            # Note: RPMSENSE_PREREQ == 0 since rpm-4.4'ish
            if flag & (rpm.RPMSENSE_PREREQ |
                       rpm.RPMSENSE_SCRIPT_PRE |
                       rpm.RPMSENSE_SCRIPT_POST):
                return 1
        return 0

    def _requires_with_pre(self):
        """returns requires with pre-require bit"""
        name = self.hdr[rpm.RPMTAG_REQUIRENAME]
        lst = self.hdr[rpm.RPMTAG_REQUIREFLAGS]
        flag = map(flagToString, lst)
        pre = map(self._is_pre_req, lst)
        lst = self.hdr[rpm.RPMTAG_REQUIREVERSION]
        vers = map(stringToVersion, lst)
        if name is not None:
            lst = zip(name, flag, vers, pre)
        mylist = misc.unique(lst)
        return mylist

class _CountedReadFile:
    """ Has just a read() method, and keeps a count so we can find out how much
        has been read. Implemented so we can get the real size of the file from
        prelink. """
    
    def __init__(self, fp):
        self.fp = fp
        self.read_size = 0

    def read(self, size):
        ret = self.fp.read(size)
        self.read_size += len(ret)
        return ret

class _PkgVerifyProb:
    """ Holder for each "problem" we find with a pkg.verify(). """
    
    def __init__(self, type, msg, ftypes, fake=False):
        self.type           = type
        self.message        = msg
        self.database_value = None
        self.disk_value     = None
        self.file_types     = ftypes
        self.fake           = fake

    def __cmp__(self, other):
        if other is None:
            return 1
        type2sort = {'type' :  1, 'symlink' : 2, 'checksum' : 3, 'size'    :  4,
                     'user' :  4, 'group'   : 5, 'mode' : 6, 'genchecksum' :  7,
                     'mtime' : 8, 'missing' : 9, 'permissions-missing'     : 10,
                     'state' : 11, 'missingok' : 12, 'ghost' : 13}
        ret = cmp(type2sort[self.type], type2sort[other.type])
        if not ret:
            for attr in ['disk_value', 'database_value', 'file_types']:
                x = getattr(self,  attr)
                y = getattr(other, attr)
                if x is None:
                    assert y is None
                    continue
                ret = cmp(x, y)
                if ret:
                    break
        return ret

# From: lib/rpmvf.h ... not in rpm *sigh*
_RPMVERIFY_DIGEST   = (1 << 0)
_RPMVERIFY_FILESIZE = (1 << 1)
_RPMVERIFY_LINKTO   = (1 << 2)
_RPMVERIFY_USER     = (1 << 3)
_RPMVERIFY_GROUP    = (1 << 4)
_RPMVERIFY_MTIME    = (1 << 5)
_RPMVERIFY_MODE     = (1 << 6)
_RPMVERIFY_RDEV     = (1 << 7)
_RPMVERIFY_CAPS     = (1 << 8)
_RPMVERIFY_CONTEXTS = (1 << 15)

class YUMVerifyPackageFile(object):
    def __init__(self, filename):
        self.filename = filename

        self.readlink = None
        self.mtime    = None
        self.dev      = None
        self.user     = None
        self.group    = None
        self.mode     = None
        self.digest   = None
        self.size     = None

        self.verify_ftype  = False

        self.rpmfile_type  = set()
        self.rpmfile_state = None

    def _setVerifiedAttr(self, attr, val, vattr=None):
        if vattr is None:
            vattr = "verify_" + attr
        attr = "_" + attr
        setattr(self, attr, val)
        setattr(self, vattr, val is not None)

    readlink = property(fget=lambda x: x._readlink,
                        fdel=lambda x: setattr(x, 'readlink', None),
                        fset=lambda x,y: x._setVerifiedAttr("readlink", y))
    mtime    = property(fget=lambda x: x._mtime,
                        fdel=lambda x: setattr(x, 'mtime', None),
                        fset=lambda x,y: x._setVerifiedAttr("mtime", y))
    dev      = property(fget=lambda x: x._dev,
                        fdel=lambda x: setattr(x, 'dev', None),
                        fset=lambda x,y: x._setVerifiedAttr("dev", y))
    user     = property(fget=lambda x: x._user,
                        fdel=lambda x: setattr(x, 'user', None),
                        fset=lambda x,y: x._setVerifiedAttr("user", y))
    group    = property(fget=lambda x: x._group,
                        fdel=lambda x: setattr(x, 'group', None),
                        fset=lambda x,y: x._setVerifiedAttr("group", y))
    # Mode is special, because it's shared with ftype.
    digest   = property(fget=lambda x: x._digest,
                        fdel=lambda x: setattr(x, 'digest', None),
                        fset=lambda x,y: x._setVerifiedAttr("digest", y))
    size     = property(fget=lambda x: x._size,
                        fdel=lambda x: setattr(x, 'size', None),
                        fset=lambda x,y: x._setVerifiedAttr("size", y))

    def _setVerifiedMode(self, attr, val):
        self.verify_mode  = val is not None
        self.verify_ftype = val is not None
        attr = "_" + attr
        setattr(self, attr, val)

    mode = property(fget=lambda x: x._mode,
                    fdel=lambda x: setattr(x, 'mode', None),
                    fset=lambda x,y: x._setVerifiedMode("mode", y))

    @staticmethod
    def _ftype(mode):
        """ Given a "mode" return the name of the type of file. """
        if stat.S_ISREG(mode):  return "file"
        if stat.S_ISDIR(mode):  return "directory"
        if stat.S_ISLNK(mode):  return "symlink"
        if stat.S_ISFIFO(mode): return "fifo"
        if stat.S_ISCHR(mode):  return "character device"
        if stat.S_ISBLK(mode):  return "block device"
        return "<unknown>"

    ftype = property(fget=lambda x: x._ftype(x.mode))


class _RPMVerifyPackageFile(YUMVerifyPackageFile):
    def __init__(self, fi, filetuple, csum_type, override_vflags=False):
        YUMVerifyPackageFile.__init__(self, filetuple[0])

        flags          = filetuple[4]
        if override_vflags:
            vflags = -1
        else:
            vflags = filetuple[9]

        if vflags & _RPMVERIFY_FILESIZE:
            self.size      = filetuple[1]

        if vflags & _RPMVERIFY_RDEV|_RPMVERIFY_MODE:
            mode           = filetuple[2]
            if mode < 0:
                # Stupid rpm, should be unsigned value but is signed ...
                # so we "fix" it via. this hack
                mode = (mode & 0xFFFF)

            self.mode = mode
            if not (vflags & _RPMVERIFY_MODE):
                self.verify_mode  = False
            if not (vflags & _RPMVERIFY_RDEV):
                self.verify_ftype = False

        if vflags & _RPMVERIFY_MTIME:
            self.mtime     = filetuple[3]
        if vflags & _RPMVERIFY_RDEV:
            self.dev       = filetuple[5]

        self.rpmfile_types = rpmfile_types = set()
        if flags & rpm.RPMFILE_CONFIG:
            rpmfile_types.add('configuration')
        if flags & rpm.RPMFILE_DOC:
            rpmfile_types.add('documentation')
        if flags & rpm.RPMFILE_GHOST:
            rpmfile_types.add('ghost')
        if flags & rpm.RPMFILE_LICENSE:
            rpmfile_types.add('license')
        if flags & rpm.RPMFILE_PUBKEY:
            rpmfile_types.add('public key')
        if flags & rpm.RPMFILE_README:
            rpmfile_types.add('README')
        if flags & rpm.RPMFILE_MISSINGOK:
            rpmfile_types.add('missing ok')

        # 6 == inode
        # 7 == link
        state = filetuple[8]
        statemap = {rpm.RPMFILE_STATE_NORMAL : 'normal',
                    rpm.RPMFILE_STATE_REPLACED : 'replaced',
                    rpm.RPMFILE_STATE_NOTINSTALLED : 'not installed',
                    rpm.RPMFILE_STATE_WRONGCOLOR : 'wrong color',
                    rpm.RPMFILE_STATE_NETSHARED : 'netshared'}

        if state in statemap:
            self.rpmfile_state = statemap[state]
        else:
            self.rpmfile_state = "<unknown>"

        if vflags & _RPMVERIFY_USER:
            self.user      = filetuple[10]
        if vflags & _RPMVERIFY_GROUP:
            self.group     = filetuple[11]
        if vflags & _RPMVERIFY_DIGEST:
            self.digest    = (csum_type, filetuple[12])

        if self.ftype == 'symlink' and vflags & _RPMVERIFY_LINKTO:
            self.readlink = fi.FLink() # fi.foo is magic, don't think about it
        elif vflags & _RPMVERIFY_LINKTO:
            self.readlink = ''


class YUMVerifyPackage:
    """ A holder for YUMVerifyPackageFile objects. """
    def __init__(self, po):
        self.po = po
        self._files = {}

    def __contains__(self, fname):
        """ Note that this checks if a filename is part of the package, and
            not a full YUMVerifyPackageFile(). """
        return fname in self._files

    def __iter__(self):
        for fn in self._files:
            yield self._files[fn]

    def add(self, vpf):
        self._files[vpf.filename] = vpf

    def remove(self, vpf):
        del self._files[vpf.filename]

    def discard(self, vpf):
        if vpf.filename not in self:
            return
        self.remove(vpf)

    def clear(self):
        self._files = {}


class _RPMVerifyPackage(YUMVerifyPackage):
    def __init__(self, po, fi, def_csum_type, patterns, all):
        YUMVerifyPackage.__init__(self, po)

        self._presetup = (fi, def_csum_type, patterns, all)
    def _setup(self):
        if not hasattr(self, '_presetup'):
            return

        (fi, def_csum_type, patterns, all) = self._presetup
        del self._presetup

        for ft in fi:
            fn = ft[0]
            if patterns:
                matched = False
                for p in patterns:
                    if fnmatch.fnmatch(fn, p):
                        matched = True
                        break
                if not matched: 
                    continue

            self.add(_RPMVerifyPackageFile(fi, ft, def_csum_type, all))

    def __contains__(self, *args, **kwargs):
        self._setup()
        return YUMVerifyPackage.__contains__(self, *args, **kwargs)
    def __iter__(self, *args, **kwargs):
        self._setup()
        return YUMVerifyPackage.__iter__(self, *args, **kwargs)
    def add(self, *args, **kwargs):
        self._setup()
        return YUMVerifyPackage.add(self, *args, **kwargs)
    def remove(self, *args, **kwargs):
        self._setup()
        return YUMVerifyPackage.remove(self, *args, **kwargs)
    # discard uses contains...
    def clear(self, *args, **kwargs):
        if hasattr(self, '_presetup'):
            del self._presetup
        return YUMVerifyPackage.clear(self, *args, **kwargs)


_installed_repo = FakeRepository('installed')
_installed_repo.cost = 0
# This is a tweak on YumHeaderPackage() for installed rpm packages.
class YumInstalledPackage(YumHeaderPackage):
    """super class for dealing with packages in the rpmdb"""
    def __init__(self, hdr, yumdb=None):
        YumHeaderPackage.__init__(self, _installed_repo, hdr)
        if yumdb:
            self.yumdb_info = yumdb.get_package(self)

    def verify(self, patterns=[], deps=False, script=False,
               fake_problems=True, all=False, fast=False, callback=None):
        """verify that the installed files match the packaged checksum
           optionally verify they match only if they are in the 'pattern' list
           returns a tuple """
        fi = self.hdr.fiFromHeader()
        results = {} # fn = problem_obj?

        # Use prelink_undo_cmd macro?
        prelink_cmd = "/usr/sbin/prelink"
        have_prelink = os.path.exists(prelink_cmd)

        # determine what checksum algo to use:
        csum_type = 'md5' # default for legacy
        if hasattr(rpm, 'RPMTAG_FILEDIGESTALGO'):
            csum_num = self.hdr[rpm.RPMTAG_FILEDIGESTALGO]
            if csum_num:
                if csum_num in RPM_CHECKSUM_TYPES:
                    csum_type = RPM_CHECKSUM_TYPES[csum_num]
                # maybe an else with an error code here? or even a verify issue?

        pfs = _RPMVerifyPackage(self, fi, csum_type, patterns, all)

        if callback is not None:
            pfs = callback(pfs)

        for pf in pfs:
            fn = pf.filename
            ftypes = list(pf.rpmfile_types)
            if pf.rpmfile_state != "normal":
                ftypes.append("state=" + pf.rpmfile_state)
                if fake_problems:
                    results[fn] = [_PkgVerifyProb('state',
                                                  'state is not normal',
                                                  ftypes, fake=True)]
                continue

            if 'missing ok' in pf.rpmfile_types and fake_problems:
                results[fn] = [_PkgVerifyProb('missingok', 'missing but ok',
                                              ftypes, fake=True)]
            if 'missing ok' in pf.rpmfile_types and not all:
                continue # rpm just skips missing ok, so we do too

            if 'ghost' in pf.rpmfile_types and fake_problems:
                results[fn] = [_PkgVerifyProb('ghost', 'ghost file', ftypes,
                                              fake=True)]
            if 'ghost' in pf.rpmfile_types and not all:
                continue

            # do check of file status on system
            problems = []
            if os.path.lexists(pf.filename):
                # stat
                my_st = os.lstat(pf.filename)
                my_st_size = my_st.st_size
                try:
                    my_user  = pwd.getpwuid(my_st[stat.ST_UID])[0]
                except KeyError, e:
                    my_user = 'uid %s not found' % my_st[stat.ST_UID]
                try:
                    my_group = grp.getgrgid(my_st[stat.ST_GID])[0]
                except KeyError, e:
                    my_group = 'gid %s not found' % my_st[stat.ST_GID]

                my_ftype = YUMVerifyPackageFile._ftype(my_st.st_mode)

                verify_dev = False
                if (pf.verify_dev and (pf.ftype.endswith("device") or
                                       my_ftype.endswith("device"))):
                    verify_dev = True
                if verify_dev:
                    if pf.ftype != my_ftype:
                        prob = _PkgVerifyProb('type','file type does not match',
                                              ftypes)
                        prob.database_value = pf.ftype
                        prob.disk_value = my_ftype
                        problems.append(prob)
                    elif (pf.dev & 0xFFFF) != (my_st.st_dev & 0xFFFF):
                        prob =_PkgVerifyProb('type','dev does not match',ftypes)
                        prob.database_value = hex(pf.dev & 0xffff)
                        prob.disk_value = hex(my_st.st_dev & 0xffff)
                        problems.append(prob)

                if pf.verify_readlink:
                    my_fnl = ''
                    if my_ftype == "symlink":
                        my_fnl = os.readlink(pf.filename)
                    if my_fnl != pf.readlink:
                        prob = _PkgVerifyProb('symlink',
                                              'symlink does not match', ftypes)
                        prob.database_value = pf.readlink
                        prob.disk_value     = my_fnl
                        problems.append(prob)

                check_content = True
                if 'ghost' in ftypes:
                    check_content = False
                if my_ftype == "symlink" and pf.ftype == "file":
                    # Don't let things hide behind symlinks
                    my_st_size = os.stat(pf.filename).st_size
                elif my_ftype != "file":
                    check_content = False
                check_perms = True
                if my_ftype == "symlink":
                    #  No, rpm doesn't check user/group on the dst. of the
                    # symlink ... so we don't.
                    check_perms = False

                if (check_content and pf.verify_mtime and
                    int(my_st.st_mtime) != int(pf.mtime)):
                    prob = _PkgVerifyProb('mtime', 'mtime does not match',
                                          ftypes)
                    prob.database_value = pf.mtime
                    prob.disk_value     = int(my_st.st_mtime)
                    problems.append(prob)

                if check_perms and pf.verify_user and my_user != pf.user:
                    prob = _PkgVerifyProb('user', 'user does not match', ftypes)
                    prob.database_value = pf.user
                    prob.disk_value = my_user
                    problems.append(prob)
                if check_perms and pf.verify_group and my_group != pf.group:
                    prob = _PkgVerifyProb('group', 'group does not match',
                                          ftypes)
                    prob.database_value = pf.group
                    prob.disk_value     = my_group
                    problems.append(prob)

                my_mode = my_st.st_mode
                if 'ghost' in ftypes: #  This is what rpm does, although it
                    my_mode &= 0777   # doesn't usually get here.
                if check_perms and pf.verify_mode and my_mode != pf.mode:
                    prob = _PkgVerifyProb('mode', 'mode does not match', ftypes)
                    prob.database_value = pf.mode
                    prob.disk_value     = my_st.st_mode
                    problems.append(prob)

                verify_digest = pf.verify_digest
                if fast and not problems and (my_st_size == pf.size):
                    verify_digest = False
                if not pf.digest:
                    verify_digest = False

                # Note that because we might get the _size_ from prelink,
                # we need to do the checksum, even if we just throw it away,
                # just so we get the size correct.
                if (check_content and
                    (verify_digest or (pf.verify_size and have_prelink and 
                                       my_st_size != pf.size))):
                    if pf.digest:
                        digest_type = pf.digest[0]
                        csum = pf.digest[0] + ':' + pf.digest[1]
                    else:
                        digest_type = csum_type
                        csum = ''
                    try:
                        my_csum = misc.checksum(digest_type, pf.filename)
                        my_csum = digest_type + ':' + my_csum
                    except Errors.MiscError:
                        # Don't have permission?
                        my_csum = None

                    if pf.verify_digest and my_csum is None:
                        prob = _PkgVerifyProb('genchecksum',
                                              'checksum not available', ftypes)
                        prob.database_value = csum
                        prob.disk_value     = None
                        problems.append(prob)
                        
                    if my_csum != csum and have_prelink:
                        #  This is how rpm -V works, try and if that fails try
                        # again with prelink.
                        p = Popen([prelink_cmd, "-y", pf.filename], 
                            bufsize=-1, stdin=PIPE,
                            stdout=PIPE, stderr=PIPE, close_fds=True)
                        (ig, fp, er) = (p.stdin, p.stdout, p.stderr)
                        # er.read(1024 * 1024) # Try and get most of the stderr
                        fp = _CountedReadFile(fp)
                        tcsum = misc.checksum(digest_type, fp)
                        if fp.read_size: # If prelink worked
                            my_csum = tcsum
                            my_csum = digest_type + ':' + my_csum
                            my_st_size = fp.read_size

                    if pf.verify_digest and my_csum != csum:
                        prob = _PkgVerifyProb('checksum',
                                              'checksum does not match', ftypes)
                        prob.database_value = csum
                        prob.disk_value     = my_csum
                        problems.append(prob)

                # Size might be got from prelink ... *sigh*.
                if check_content and pf.verify_size and my_st_size != pf.size:
                    prob = _PkgVerifyProb('size', 'size does not match', ftypes)
                    prob.database_value = pf.size
                    prob.disk_value     = my_st_size
                    problems.append(prob)

            else:
                try:
                    os.stat(pf.filename)
                    perms_ok = True # Shouldn't happen
                except OSError, e:
                    perms_ok = True
                    if e.errno == errno.EACCES:
                        perms_ok = False

                if perms_ok:
                    prob = _PkgVerifyProb('missing', 'file is missing', ftypes)
                else:
                    prob = _PkgVerifyProb('permissions-missing',
                                          'file is missing (Permission denied)',
                                          ftypes)
                problems.append(prob)

            if problems:
                results[pf.filename] = problems
                
        return results
        
                             
# This is a tweak on YumHeaderPackage() for rpm packages which are on disk.
class YumLocalPackage(YumHeaderPackage):
    """Class to handle an arbitrary package from a file path
       this inherits most things from YumInstalledPackage because
       installed packages and an arbitrary package on disk act very
       much alike. init takes a ts instance and a filename/path 
       to the package."""

    def __init__(self, ts=None, filename=None):
        if ts is None:
            #  This shouldn't be used "normally" within yum, but is very useful
            # for small scripts and debugging/etc.
            ts = rpmUtils.transaction.initReadOnlyTransaction()

        if filename is None:
            raise Errors.MiscError, \
                 'No Filename specified for YumLocalPackage instance creation'
                 
        self.pkgtype = 'local'
        self.localpath = filename
        self._checksum = None

        
        try:
            hdr = rpmUtils.miscutils.hdrFromPackage(ts, self.localpath)
        except RpmUtilsError, e:
            raise Errors.MiscError, \
                'Could not open local rpm file: %s: %s' % (self.localpath, e)
        
        fakerepo = FakeRepository(filename)
        fakerepo.cost = 0
        YumHeaderPackage.__init__(self, fakerepo, hdr)
        self.id = self.pkgid
        self._stat = os.stat(self.localpath)
        self.filetime = str(self._stat[-2])
        self.packagesize = str(self._stat[6])
        self.arch = self.isSrpm()
        self.pkgtup = (self.name, self.arch, self.epoch, self.ver, self.rel)
        self._hdrstart = None
        self._hdrend = None
        self.checksum_type = misc._default_checksums[0]

        # these can be set by callers that need these features (ex: createrepo)
        self._reldir = None 
        self._baseurl = "" 
        # self._packagenumber will be needed when we do sqlite creation here

        
    def isSrpm(self):
        if self.tagByName('sourcepackage') == 1 or not self.tagByName('sourcerpm'):
            return 'src'
        else:
            return self.tagByName('arch')
        
    def localPkg(self):
        return self.localpath
    
    def _do_checksum(self, checksum_type=None):
        if checksum_type is None:
            checksum_type = misc._default_checksums[0]
        if not self._checksum:
            self._checksum = misc.checksum(checksum_type, self.localpath)
            self._checksums = [(checksum_type, self._checksum, 1)]

        return self._checksum    

    checksum = property(fget=lambda self: self._do_checksum())   

    def returnChecksums(self):
        self._do_checksum()
        return self._checksums

    def verifyLocalPkg(self):
        """ don't bother "checking" the package matches itself. """
        return True

    def _get_header_byte_range(self):
        """takes an rpm file or fileobject and returns byteranges for location of the header"""
        if self._hdrstart and self._hdrend:
            return (self._hdrstart, self._hdrend)
      
           
        fo = open(self.localpath, 'r')
        #read in past lead and first 8 bytes of sig header
        fo.seek(104)
        # 104 bytes in
        binindex = fo.read(4)
        # 108 bytes in
        (sigindex, ) = struct.unpack('>I', binindex)
        bindata = fo.read(4)
        # 112 bytes in
        (sigdata, ) = struct.unpack('>I', bindata)
        # each index is 4 32bit segments - so each is 16 bytes
        sigindexsize = sigindex * 16
        sigsize = sigdata + sigindexsize
        # we have to round off to the next 8 byte boundary
        disttoboundary = (sigsize % 8)
        if disttoboundary != 0:
            disttoboundary = 8 - disttoboundary
        # 112 bytes - 96 == lead, 8 = magic and reserved, 8 == sig header data
        hdrstart = 112 + sigsize  + disttoboundary
        
        fo.seek(hdrstart) # go to the start of the header
        fo.seek(8,1) # read past the magic number and reserved bytes

        binindex = fo.read(4) 
        (hdrindex, ) = struct.unpack('>I', binindex)
        bindata = fo.read(4)
        (hdrdata, ) = struct.unpack('>I', bindata)
        
        # each index is 4 32bit segments - so each is 16 bytes
        hdrindexsize = hdrindex * 16 
        # add 16 to the hdrsize to account for the 16 bytes of misc data b/t the
        # end of the sig and the header.
        hdrsize = hdrdata + hdrindexsize + 16
        
        # header end is hdrstart + hdrsize 
        hdrend = hdrstart + hdrsize 
        fo.close()
        self._hdrstart = hdrstart
        self._hdrend = hdrend
       
        return (hdrstart, hdrend)
        
    hdrend = property(fget=lambda self: self._get_header_byte_range()[1])
    hdrstart = property(fget=lambda self: self._get_header_byte_range()[0])

    def _return_remote_location(self):

        # if we start seeing fullpaths in the location tag - this is the culprit
        if self._reldir and self.localpath.startswith(self._reldir):
            relpath = self.localpath.replace(self._reldir, '')
            if relpath[0] == '/': relpath = relpath[1:]
        else:
            relpath = self.localpath

        if self._baseurl:
            msg = """<location xml:base="%s" href="%s"/>\n""" % (
                                     misc.to_xml(self._baseurl, attrib=True),
                                     misc.to_xml(relpath, attrib=True))
        else:
            msg = """<location href="%s"/>\n""" % misc.to_xml(relpath, attrib=True)

        return msg


#  This is a tweak on YumLocalPackage() to download rpm packages to disk, and
# then use them directly.
class YumUrlPackage(YumLocalPackage):
    """Class to handle an arbitrary package from a URL
       this inherits most things from YumLocalPackage, but will download a
       remote package to make it local.
       init takes a YumBase, a ts instance and a url to the package."""

    def __init__(self, yb=None, ts=None, url=None, ua=None):
        if url.lower().startswith("file:"):
            result = url[len("file:"):]
        elif not misc.re_remote_url(url):
            result = url
        else:
            cb = None
            pd = {}
            for repo in yb.repos.listEnabled():
                cb = repo.callback # Hacky, but these are "always" the same
                if (repo.proxy == yb.conf.proxy and
                    repo.proxy_username == yb.conf.proxy_username and
                    repo.proxy_password == yb.conf.proxy_password):
                    # Even more hacky...
                    pd = repo.proxy_dict
                    break
            fname = os.path.basename(url)
            local = misc.getCacheDir()
            if local is None: # bugger...
                local = "%s/../" % repo.cachedir
            local = "%s/%s" % (local, fname)
            try:
                ug = URLGrabber(bandwidth = yb.conf.bandwidth,
                                retry = yb.conf.retries,
                                throttle = yb.conf.throttle,
                                progress_obj = cb,
                                proxies=pd)
                if ua is not None:
                    ug.opts.user_agent = ua
                result = ug.urlgrab(url, local, text=fname)
            except URLGrabError, e:
                raise Errors.MiscError("Cannot download %s: %s" % (url, e))
        YumLocalPackage.__init__(self, ts, result)
