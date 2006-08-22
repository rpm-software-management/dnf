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
import types
import fnmatch
from rpmUtils import RpmUtilsError
import rpmUtils.arch
import rpmUtils.miscutils
import Errors

base=None

def comparePoEVR(po1, po2):
    (e1, v1, r1) = (po1.epoch, po1.ver, po1.rel)
    (e2, v2, r2) = (po2.epoch, po2.ver, po2.rel)
    return rpmUtils.miscutils.compareEVR((e1, v1, r1), (e2, v2, r2))

def buildPkgRefDict(pkgs):
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
        pkgtup = (pkg.name, pkg.arch, pkg.epoch, pkg.version, pkg.release)
        (n, a, e, v, r) = pkgtup
        name = n
        nameArch = '%s.%s' % (n, a)
        nameVerRelArch = '%s-%s-%s.%s' % (n, v, r, a)
        nameVer = '%s-%s' % (n, v)
        nameVerRel = '%s-%s-%s' % (n, v, r)
        envra = '%s:%s-%s-%s.%s' % (e, n, v, r, a)
        nevra = '%s-%s:%s-%s.%s' % (n, e, v, r, a)
        for item in [name, nameArch, nameVerRelArch, nameVer, nameVerRel, envra, nevra]:
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


# goal for the below is to have a packageobject that can be used by generic
# functions independent of the type of package - ie: installed or available
class PackageObject:
    """Base Package Object - sets up the default storage dicts and the
       most common returns"""
       
    def __init__(self):
        self.simple = {} # simple things, name, arch, e,v,r, size, etc
        self.checksums = [] # (type, checksum, id(0,1)
        
    def __str__(self):
        return self.returnNevraPrintable()

    def returnSimple(self, varname):
        return self.simple[varname]

    def simpleItems(self):
        return self.simple.keys()            

    def returnID(self):
        return self.returnSimple('id')

    def returnPackageTuple(self):
        return (self.returnSimple('name'), self.returnSimple('arch'), 
                self.returnSimple('epoch'),self.returnSimple('version'), 
                self.returnSimple('release'))
        
    def returnNevraTuple(self):
        return (self.returnSimple('name'), self.returnSimple('epoch'), 
                self.returnSimple('version'),self.returnSimple('release'), 
                self.returnSimple('arch'))
    
    def returnNevraPrintable(self):
        """return printable string for the pkgname/object
           name - epoch:ver-rel.arch"""
        if self.returnSimple('epoch') == '0':
            string = '%s - %s-%s.%s' % (self.returnSimple('name'), 
                                        self.returnSimple('version'),
                                        self.returnSimple('release'), 
                                        self.returnSimple('arch'))
        else:
            string = '%s - %s:%s-%s.%s' % (self.returnSimple('name'), 
                                           self.returnSimple('epoch'), 
                                           self.returnSimple('version'), 
                                           self.returnSimple('release'), 
                                           self.returnSimple('arch'))
        return string                                           

    def returnEVR(self):
        """returns a tuple of epoch, ver, rel"""
        return (self.returnSimple('epoch'), self.returnSimple('version'), self.returnSimple('release'))
        
        return                            

    def returnChangelog(self):
        """return changelog entries"""
        return self.changelog


class RpmBase:
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
        self.changelog = [] # (ctime, cname, ctext)
        self.licenses = []

    def __lt__(self, other):
        val = False
        rc = comparePoEVR(self, other)
        if rc < 0:
            val = True
        
        return val
        
    def __gt__(self, other):
        val = False
        rc = comparePoEVR(self, other)
        if rc > 0:
            val = True
        
        return val

    def __le__(self, other):
        val = False
        rc = comparePoEVR(self, other)
        if rc <= 0:
            val = True
        
        return val
    

    def __ge__(self, other):
        val = False
        rc = comparePoEVR(self, other)
        if rc >= 0:
            val = True
        
        return val
    

    def __eq__(self, other):
        val = False
        rc = comparePoEVR(self, other)
        if rc == 0:
            val = True
        
        return val
    

    def __ne__(self, other):
        val = False
        rc = comparePoEVR(self, other)
        if rc != 0:
            val = True
        
        return val
    
    def __hash__(self):
        mystr = '%s - %s:%s-%s-%s.%s' % (self.repoid, self.epoch, self.name,
                                         self.ver, self.rel, self.arch)
        return hash(mystr)
        
    def returnPrco(self, prcotype):
        """return list of provides, requires, conflicts or obsoletes"""
        if self.prco.has_key(prcotype):
            return self.prco[prcotype]
        else:
            return []

    def checkPrco(self, prcotype, prcotuple):
        """returns 1 or 0 if the pkg contains the requested tuple/tuple range"""
        # get rid of simple cases - nothing
        if not self.prco.has_key(prcotype):
            return 0
        # exact match    
        if prcotuple in self.prco[prcotype]:
            return 1
        else:
            # make us look it up and compare
            (reqn, reqf, (reqe, reqv ,reqr)) = prcotuple
            if reqf is not None:
                if self.inPrcoRange(prcotype, prcotuple):
                    return 1
                else:
                    return 0
            else:
                for (n, f, (e, v, r)) in self.returnPrco(prcotype):
                    if reqn == n:
                        return 1

        return 0
                
    def inPrcoRange(self, prcotype, reqtuple):
        """returns true if the package has a the prco that satisfies 
           the reqtuple range, assume false.
           Takes: prcotype, requested prco tuple"""
        # we only ever get here if we have a versioned prco
        # nameonly shouldn't ever raise it
        (reqn, reqf, (reqe, reqv, reqr)) = reqtuple
        # find the named entry in pkgobj, do the comparsion
        for (n, f, (e, v, r)) in self.returnPrco(prcotype):
            if reqn == n:
                # found it
                if f != 'EQ':
                    # isn't this odd, it's not 'EQ' - it really should be
                    # use the pkgobj's evr for the comparison
                    (e, v, r) = self.returnEVR()
                # and you thought we were done having fun
                # if the requested release is left out then we have
                # to remove release from the package prco to make sure the match
                # is a success - ie: if the request is EQ foo 1:3.0.0 and we have 
                # foo 1:3.0.0-15 then we have to drop the 15 so we can match
                if reqr is None:
                    r = None
                if reqe is None:
                    e = None
                if reqv is None: # just for the record if ver is None then we're going to segfault
                    v = None
                rc = rpmUtils.miscutils.compareEVR((e, v, r), (reqe, reqv, reqr))
                
                if rc >= 1:
                    if reqf in ['GT', 'GE', 4, 12]:
                        return 1
                if rc == 0:
                    if reqf in ['GE', 'LE', 'EQ', 8, 10, 12]:
                        return 1
                if rc <= -1:
                    if reqf in ['LT', 'LE', 2, 10]:
                        return 1
        return 0
        
    def returnChangelog(self):
        """return changelog entries"""
        return self.changelog
        
    def returnFileEntries(self, ftype='file'):
        """return list of files based on type"""
        if self.files.has_key(ftype):
            return self.files[ftype]
        else:
            return []
            
    def returnFileTypes(self):
        """return list of types of files in the package"""
        return self.files.keys()
    


class YumAvailablePackage(PackageObject, RpmBase):
    """derived class for the  packageobject and RpmBase packageobject yum
       uses this for dealing with packages in a repository"""

    def __init__(self, repoid, pkgdict = None):
        PackageObject.__init__(self)
        RpmBase.__init__(self)
        
        self.simple['repoid'] = repoid
        self.repoid = repoid
        self.state = None
        
        if pkgdict != None:
            self.importFromDict(pkgdict)
            # quick, common definitions
            self.name = self.returnSimple('name')
            self.epoch = self.returnSimple('epoch')
            self.version = self.returnSimple('version')
            self.release = self.returnSimple('release')
            self.ver = self.returnSimple('version')
            self.rel = self.returnSimple('release')
            self.arch = self.returnSimple('arch')
            self.pkgtup = self._pkgtup()
         
    def size(self):
        return self.returnSimple('packagesize')

    def _pkgtup(self):
        return self.returnPackageTuple()

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
    
    def prcoPrintable(self, prcoTuple):
        """convert the prco tuples into a nicer human string"""
        (name, flag, (e, v, r)) = prcoTuple
        flags = {'GT':'>', 'GE':'>=', 'EQ':'=', 'LT':'<', 'LE':'<='}
        if flag is None:
            return name
        
        base = '%s %s ' % (name, flags[flag])
        if e not in [0, '0', None]:
            base += '%s:' % e
        if v is not None:
            base += '%s' % v
        if r is not None:
            base += '-%s' % r
        
        return base
    
    def requiresList(self):
        """return a list of requires in normal rpm format"""
        
        reqlist = []
        
        for prcoTuple in self.returnPrco('requires'):
            prcostr = self.prcoPrintable(prcoTuple)
            reqlist.append(prcostr)
        
        return reqlist
        
    def importFromDict(self, pkgdict):
        """handles an mdCache package dictionary item to populate out 
           the package information"""
        
        # translates from the pkgdict, populating out the information for the
        # packageObject
        
        if hasattr(pkgdict, 'nevra'):
            (n, e, v, r, a) = pkgdict.nevra
            self.simple['name'] = n
            self.simple['epoch'] = e
            self.simple['version'] = v
            self.simple['arch'] = a
            self.simple['release'] = r
        
        if hasattr(pkgdict, 'time'):
            self.simple['buildtime'] = pkgdict.time['build']
            self.simple['filetime'] = pkgdict.time['file']
        
        if hasattr(pkgdict, 'size'):
            self.simple['packagesize'] = pkgdict.size['package']
            self.simple['archivesize'] = pkgdict.size['archive']
            self.simple['installedsize'] = pkgdict.size['installed']
        
        if hasattr(pkgdict, 'location'):
            if not pkgdict.location.has_key('base'):
                url = None
            elif pkgdict.location['base'] == '':
                url = None
            else:
                url = pkgdict.location['base']

            self.simple['basepath'] = url
            self.simple['relativepath'] = pkgdict.location['href']
        
        if hasattr(pkgdict, 'hdrange'):
            self.simple['hdrstart'] = pkgdict.hdrange['start']
            self.simple['hdrend'] = pkgdict.hdrange['end']
        
        if hasattr(pkgdict, 'info'):
            infodict = pkgdict.info
            for item in ['summary', 'description', 'packager', 'group',
                         'buildhost', 'sourcerpm', 'url', 'vendor']:
                self.simple[item] = infodict[item]
            
            self.licenses.append(infodict['license'])
        
        if hasattr(pkgdict, 'files'):
            for file in pkgdict.files.keys():
                ftype = pkgdict.files[file]
                if not self.files.has_key(ftype):
                    self.files[ftype] = []
                self.files[ftype].append(file)
        
        if hasattr(pkgdict, 'prco'):
            for rtype in pkgdict.prco.keys():
                for rdict in pkgdict.prco[rtype]:
                    name = rdict['name']
                    f = e = v = r  = None
                    if rdict.has_key('flags'): f = rdict['flags']
                    if rdict.has_key('epoch'): e = rdict['epoch']
                    if rdict.has_key('ver'): v = rdict['ver']
                    if rdict.has_key('rel'): r = rdict['rel']
                    self.prco[rtype].append((name, f, (e,v,r)))

        if hasattr(pkgdict, 'changelog'):
            for cdict in pkgdict.changelog:
                date = text = author = None
                if cdict.has_key('date'): date = cdict['date']
                if cdict.has_key('value'): text = cdict['value']
                if cdict.has_key('author'): author = cdict['author']
                self.changelog.append((date, author, text))
        
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
            self.checksums.append((ctype, csum, csumid))
            


class YumHeaderPackage(YumAvailablePackage):
    """Package object built from an rpm header"""
    def __init__(self, hdr, repoid):
        """hand in an rpm header, we'll assume it's installed and query from there"""
       
        YumAvailablePackage.__init__(self, repoid)

        self.hdr = hdr
        self.name = self.tagByName('name')
        self.arch = self.tagByName('arch')
        self.epoch = self.doepoch()
        self.version = self.tagByName('version')
        self.release = self.tagByName('release')
        self.ver = self.tagByName('version')
        self.rel = self.tagByName('release')
        self.pkgtup = self._pkgtup()
        self.summary = self.tagByName('summary')
        self.description = self.tagByName('description')
        self.pkgid = self.tagByName(rpm.RPMTAG_SHA1HEADER)

        self._populatePrco()
        
    def __str__(self):
        if self.epoch == '0':
            val = '%s - %s-%s.%s' % (self.name, self.version, self.release, 
                                        self.arch)
        else:
            val = '%s - %s:%s-%s.%s' % (self.name, self.epoch, self.version,
                                           self.release, self.arch)
        return val

    def _populatePrco(self):
        "Populate the package object with the needed PRCO interface."

        for tag in ['OBSOLETE', 'CONFLICT', 'REQUIRE', 'PROVIDE']:
            name = self.hdr[getattr(rpm, 'RPMTAG_%sNAME' % tag)]

            list = self.hdr[getattr(rpm, 'RPMTAG_%sFLAGS' % tag)]
            flag = []
            for i in list:
                value = rpmUtils.miscutils.flagToString(i)
                flag.append(value)

            list = self.hdr[getattr(rpm, 'RPMTAG_%sVERSION' % tag)]
            vers = []
            for i in list:
                value = rpmUtils.miscutils.stringToVersion(i)
                vers.append(value)

            prcotype = tag.lower() + 's'
            if name is not None:
                self.prco[prcotype] = zip(name, flag, vers)
    
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
        if hasattr(self, thing):
            return getattr(self, thing)
        else:
            return self.tagByName(thing)

    def returnLocalHeader(self):
        return self.hdr


    def getProvidesNames(self):
        """returns a list of providesNames"""
        
        provnames = self.tagByName('providename')
        if type(provnames) is not types.ListType():
            if type(provnames) is types.StringType():
                provnames = [provnames]
            else:
                provnames = []

        return provnames

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

    def _pkgtup(self):
        return (self.name, self.arch, self.epoch, self.version, self.release)
    
    def size(self):
        return self.tagByName('size')

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


class YumInstalledPackage(YumHeaderPackage):
    """super class for dealing with packages in the rpmdb"""
    def __init__(self, hdr):
        YumHeaderPackage.__init__(self, hdr, "installed")

class YumLocalPackage(YumHeaderPackage):
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
                 
        self.pkgtype = 'local'
        self.localpath = filename
        
        try:
            hdr = rpmUtils.miscutils.hdrFromPackage(ts, self.localpath)
        except RpmUtilsError, e:
            raise Errors.MiscError, \
                'Could not open local rpm file: %s' % self.localpath
       
        YumHeaderPackage.__init__(self, hdr, filename)
        
    def localPkg(self):
        return self.localpath
    
