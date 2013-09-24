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
# Copyright 2004 Duke University
# Written by Seth Vidal <skvidal at phy.duke.edu>

"""
Classes and functions dealing with rpm package representations.
"""

from __future__ import absolute_import
import os.path
from . import misc
import re
import fnmatch
import stat
import dnf.rpmUtils.miscutils
import dnf.exceptions
from .constants import *

def comparePoEVR(po1, po2):
    """
    Compare two Package or PackageEVR objects.
    """
    (e1, v1, r1) = (po1.epoch, po1.version, po1.release)
    (e2, v2, r2) = (po2.epoch, po2.version, po2.release)
    return dnf.rpmUtils.miscutils.compareEVR((e1, v1, r1), (e2, v2, r2))
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
            return list(u.values())
        matched    = pkgunique(matched)
        exactmatch = pkgunique(exactmatch)
    else:
        raise ValueError("Bad value for unique: %s" % unique)
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
            return self.nvra
        else:
            return self.envra
    ui_envra = property(fget=lambda self: self._ui_envra())

    def _ui_nevra(self):
        if self.epoch == '0':
            return self.nvra
        else:
            return self.nevra
    ui_nevra = property(fget=lambda self: self._ui_nevra())

    def _ui_evr(self):
        if self.epoch == '0':
            return self.vr
        else:
            return self.evr
    ui_evr = property(fget=lambda self: self._ui_evr())

    def _ui_evra(self):
        if self.epoch == '0':
            return self.vra
        else:
            return self.evra
    ui_evra = property(fget=lambda self: self._ui_evra())

    def _ui_nevr(self):
        if self.epoch == '0':
            return self.nvr
        else:
            return self.nevr
    ui_nevr = property(fget=lambda self: self._ui_nevr())

    def _na(self):
        return '%s.%s' % (self.name, self.arch)
    na = property(fget=lambda self: self._na())

    def _vr(self):
        return '%s-%s' % (self.version, self.release)
    vr = property(fget=lambda self: self._vr())

    def _vra(self):
        return '%s-%s.%s' % (self.version, self.release, self.arch)
    vra = property(fget=lambda self: self._vra())

    def _evr(self):
        return '%s:%s-%s' % (self.epoch, self.version, self.release)
    evr = property(fget=lambda self: self._evr())

    def _evra(self):
        return '%s:%s-%s.%s' % (self.epoch,self.version,self.release, self.arch)
    evra = property(fget=lambda self: self._evra())

    def _nvr(self):
        return '%s-%s-%s' % (self.name, self.version, self.release)
    nvr = property(fget=lambda self: self._nvr())

    def _nvra(self):
        return '%s-%s-%s.%s' % (self.name, self.version,self.release, self.arch)
    nvra = property(fget=lambda self: self._nvra())

    def _nevr(self):
        return '%s-%s:%s-%s' % (self.name, self.epoch,self.version,self.release)
    nevr = property(fget=lambda self: self._nevr())

    def _nevra(self):
        return '%s-%s:%s-%s.%s' % (self.name,
                                   self.epoch, self.version, self.release,
                                   self.arch)
    nevra = property(fget=lambda self: self._nevra())

    def _envr(self):
        return '%s:%s-%s-%s' % (self.epoch,self.name, self.version,self.release)
    envr = property(fget=lambda self: self._envr())

    def _envra(self):
        return '%s:%s-%s-%s.%s' % (self.epoch, self.name,
                                   self.version, self.release,
                                   self.arch)
    envra = property(fget=lambda self: self._envra())

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
        """ Uses verCMP, tests if the other rpm-version is <  ours. """
        return self.verCMP(other) <  0
    def verLE(self, other):
        """ Uses verCMP, tests if the other rpm-version is <= ours. """
        return self.verCMP(other) <= 0
    def verGT(self, other):
        """ Uses verCMP, tests if the other rpm-version is >  ours. """
        return self.verCMP(other) >  0
    def verGE(self, other):
        """ Uses verCMP, tests if the other rpm-version is >= ours. """
        return self.verCMP(other) >= 0

    def __repr__(self):
        return "<%s : %s (%s)>" % (self.__class__.__name__, str(self),hex(id(self)))

    def returnChecksums(self):
        return self._checksums

    checksums = property(fget=lambda self: self.returnChecksums())

    def returnIdSum(self):
        for (csumtype, csum, csumid) in self.checksums:
            if csumid:
                return (csumtype, csum)
