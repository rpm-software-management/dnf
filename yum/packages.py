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

import rpm
import os
import os.path
import misc
import re
import fnmatch
import rpmUtils
import rpmUtils.arch
import rpmUtils.miscutils
import Errors

import repomd.packageObject

base=None

def buildPkgRefDict(pkgs):
    """take a list of pkg objects and return a dict the contains all the possible
       naming conventions for them eg: for (name,i386,0,1,1)
       dict[name] = (name, i386, 0, 1, 1)
       dict[name.i386] = (name, i386, 0, 1, 1)
       dict[name-1-1.i386] = (name, i386, 0, 1, 1)       
       dict[name-1] = (name, i386, 0, 1, 1)       
       dict[name-1-1] = (name, i386, 0, 1, 1)
       dict[0:name-1-1.i386] = (name, i386, 0, 1, 1)
       """
    pkgdict = {}
    for pkg in pkgs:
        pkgtup = (pkg.name, pkg.arch, pkg.epoch, pkg.version, pkg.release)
        (n, a, e, v, r) = pkgtup
        name = n
        nameArch = '%s.%s' % (n, a)
        nameVerRelArch = '%s-%s-%s.%s' % (n, v, r, a)
        nameVer = '%s-%s' % (n, v)
        nameVerRel = '%s-%s-%s' % (n, v, r)
        full = '%s:%s-%s-%s.%s' % (e, n, v, r, a)
        for item in [name, nameArch, nameVerRelArch, nameVer, nameVerRel, full]:
            if not pkgdict.has_key(item):
                pkgdict[item] = []
            pkgdict[item].append(pkg)
            
    return pkgdict
       
def parsePackages(pkgs, usercommands, casematch=0):
    """matches up the user request versus a pkg list:
       for installs/updates available pkgs should be the 'others list' 
       for removes it should be the installed list of pkgs
       takes an optional casematch option to determine if case should be matched
       exactly. Defaults to not matching."""

    pkgdict = buildPkgRefDict(pkgs)
    exactmatch = []
    matched = []
    unmatched = []
    for command in usercommands:
        if pkgdict.has_key(command):
            exactmatch.extend(pkgdict[command])
            del pkgdict[command]
        else:
            # anything we couldn't find a match for
            # could mean it's not there, could mean it's a wildcard
            if re.match('.*[\*,\[,\],\{,\},\?].*', command):
                trylist = pkgdict.keys()
                restring = fnmatch.translate(command)
                if casematch:
                    regex = re.compile(restring) # case sensitive
                else:
                    regex = re.compile(restring, flags=re.I) # case insensitive
                foundit = 0
                for item in trylist:
                    if regex.match(item):
                        matched.extend(pkgdict[item])
                        del pkgdict[item]
                        foundit = 1
 
                if not foundit:    
                    unmatched.append(command)
                    
            else:
                # we got nada
                unmatched.append(command)

    matched = misc.unique(matched)
    unmatched = misc.unique(unmatched)
    exactmatch = misc.unique(exactmatch)
    return exactmatch, matched, unmatched


def returnBestPackages(pkgdict, arch=None):
    """returns a list of package tuples that are the 'best' packages for this
       arch. Best == highest version and best scoring/sorting arch
       should consider multiarch separately"""
    returnlist = []
    compatArchList = rpmUtils.arch.getArchList(arch)
    for pkgname in pkgdict.keys():
        # go through the packages, pitch out the ones that can't be used
        # on this system at all
        pkglist = pkgdict[pkgname]
        uselist = []
        multiLib = []
        singleLib = []
        for pkg in pkglist:
            (n, a, e, v, r) = pkg
            if a not in compatArchList:
                continue
            elif rpmUtils.arch.multilibArches.has_key(a):
                multiLib.append(pkg)
            else:
                singleLib.append(pkg)
        # we should have two lists now - one of singleLib packages
        # one of multilib packages
        # go through each one and find the best package(s)
        for pkglist in [multiLib, singleLib]:
            if len(pkglist) > 0:
                best = pkglist[0]
            else:
                continue
            for pkg in pkglist[1:]:
                best = bestPackage(best, pkg)
            if best is not None:
                returnlist.append(best)
    
    return returnlist

def bestPackage(pkg1, pkg2):
    """compares two packages (assumes the names are the same), and returns
       the one with the best version and the best arch, the sorting is:
       for compatible arches, the highest version is best so:
       foo-1.1-1.i686 is better than foo-1.1-1.i386 on an i686 machine
       but foo-1.2-1.alpha is not better than foo-1.1-1.i386 on an i686
       machine and foo-1.3-1.i386 is better than foo-1.1-1.i686 on an i686
       machine."""
    (n1, a1, e1, v1, r1) = pkg1
    (n2, a2, e2, v2, r2) = pkg2
    rc = rpmUtils.miscutils.compareEVR((e1, v1, r1), (e2, v2, r2))
    if rc == 0:
        # tiebreaker
        bestarch = rpmUtils.arch.getBestArchFromList([a1, a2])
        if bestarch is None: # how the hell did this happen?
            return None
        if bestarch == a1:
            return pkg1
        if bestarch == a2:
            return pkg2
    elif rc > 0:
        return pkg1
    elif rc < 0:
        return pkg2
    
# goal for the below is to have a packageobject that can be used by generic
# functions independent of the type of package - ie: installed or available


class YumInstalledPackage:
    """super class for dealing with packages in the rpmdb"""
    def __init__(self, hdr):
        """hand in an rpm header, we'll assume it's installed and query from there"""
        self.hdr = hdr
        self.name = self.tagByName('name')
        self.arch = self.tagByName('arch')
        self.epoch = self.doepoch()
        self.version = self.tagByName('version')
        self.release = self.tagByName('release')
        self.repoid = 'installed'
        self.summary = self.tagByName('summary')
        self.description = self.tagByName('description')
    
    def __str__(self):
        if self.epoch == '0':
            val = '%s - %s-%s.%s' % (self.name, self.version, self.release, 
                                        self.arch)
        else:
            val = '%s - %s:%s-%s.%s' % (self.name, self.epoch, self.version,
                                           self.release, self.arch)
        return val
        
    def tagByName(self, tag):
        data = self.hdr[tag]
        return data
    
    def doepoch(self):
        tmpepoch = self.hdr['epoch']
        if tmpepoch is None:
            epoch = '0'
        else:
            epoch = str(tmpepoch)
        
        return epoch
    
    def returnSimple(self, thing):
        return getattr(self, thing)
    
    def requiresList(self):
        """return a list of all of the strings of the package requirements"""
        reqlist = []
        names = self.hdr[rpm.RPMTAG_REQUIRENAME]
        flags = self.hdr[rpm.RPMTAG_REQUIREFLAGS]
        ver = self.hdr[rpm.RPMTAG_REQUIREVERSION]
        if names is not None:
            tmplst = zip(names, flags, ver)
        
        for (n, f, v) in tmplst:
            req = rpmUtils.miscutils.formatRequire(n, v, f)
            reqlist.append(req)
        
        return reqlist

    def pkgtup(self):
        return (self.name, self.arch, self.epoch, self.version, self.release)
    
    def size(self):
        return self.tagByName('size')

class YumLocalPackage(YumInstalledPackage):
    """Class to handle an arbitrary package from a file path
       this inherits most things from YumInstalledPackage because
       installed packages and an arbitrary package on disk act very
       much alike. init takes a ts instance and a filename/path 
       to the package."""

    def __init__(self, ts=None, filename=None):
        if ts is None:
            raise Errors.MiscError, \
                 'No Transaction Set Instance for YumLocalPackage instance creation'
        if filename is None:
            raise Errors.MiscError, \
                 'No Filename specified for YumLocalPackage instance creation'
        self.filename = filename
        self.repoid = filename
        self.hdr = rpmUtils.miscutils.hdrFromPackage(ts, self.filename)
        self.name = self.tagByName('name')
        self.arch = self.tagByName('arch')
        self.epoch = self.doepoch()
        self.version = self.tagByName('version')
        self.release = self.tagByName('release')
        self.summary = self.tagByName('summary')
        self.description = self.tagByName('description')

class YumAvailablePackage(repomd.packageObject.RpmXMLPackageObject):
    """derived class for the repomd packageobject we use
    this for dealing with packages in a repository"""

   
    def size(self):
        return self.returnSimple('packagesize')

    def pkgtup(self):
        return self.returnPackageTuple()

    def returnLocalHeader(self):
        """returns an rpm header object from the package object's local
           header cache"""
        
        if os.path.exists(self.localHdr()):
            try: 
                hlist = rpm.readHeaderListFromFile(self.localHdr())
                hdr = hlist[0]
            except (rpm.error, IndexError):
                raise Errors.RepoError, 'Cannot open package header'
        else:
            raise Errors.RepoError, 'Package Header Not Available'

        return hdr

    def getProvidesNames(self):
        """returns a list of providesNames"""
        
        provnames = []
        prov = self.returnPrco('provides')
        
        for (name, flag, vertup) in prov:
            provnames.append(name)

        return provnames
       
    def localPkg(self):
        """return path to local package (whether it is present there, or not)"""
        if not hasattr(self, 'localpath'):
            repo = base.repos.getRepo(self.repoid)
            remote = self.returnSimple('relativepath')
            rpmfn = os.path.basename(remote)
            self.localpath = repo.pkgdir + '/' + rpmfn
        return self.localpath

    def localHdr(self):
        """return path to local cached Header file downloaded from package 
           byte ranges"""
           
        if not hasattr(self, 'hdrpath'):
            repo = base.repos.getRepo(self.repoid)
            pkgpath = self.returnSimple('relativepath')
            pkgname = os.path.basename(pkgpath)
            hdrname = pkgname[:-4] + '.hdr'
            self.hdrpath = repo.hdrdir + '/' + hdrname

        return self.hdrpath
        

