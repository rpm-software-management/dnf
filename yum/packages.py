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

import metadata.packageObject
base=None # will be filled with the baseclass

def buildPkgRefDict(pkgs):
    """take a list of pkg tuples and return a dict the contains all the possible
       naming conventions for them eg: for (name,i386,0,1,1)
       dict[name] = (name, i386, 0, 1, 1)
       dict[name.i386] = (name, i386, 0, 1, 1)
       dict[name-1-1.i386] = (name, i386, 0, 1, 1)       
       dict[name-1] = (name, i386, 0, 1, 1)       
       dict[name-1-1] = (name, i386, 0, 1, 1)
       dict[0:name-1-1.i386] = (name, i386, 0, 1, 1)
       """
    pkgdict = {}
    for pkgtup in pkgs:
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
            pkgdict[item].append(pkgtup)
            
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
            excactmatch.extend(pkgdict[command])
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


class YumInstalledPackage:
    """super class for dealing with packages in the rpmdb"""
    
class YumAvailablePackage:
    """super class for dealing with packages in a repository"""
    
    
class YumPackage(metadata.packageObject.RpmXMLPackageObject):
    """super class for the metadata packageobject we use"""
       
    def getHeader(self):
        """returns an rpm header object from the package object"""
        # this function sucks - it should use the urlgrabber
        # testfunction to check the headers and loop on that

        rel = self.returnSimple('relativepath')
        pkgname = os.path.basename(rel)
        hdrname = pkgname[:-4] + '.hdr'
        url = self.returnSimple('basepath')
        start = self.returnSimple('hdrstart')
        end = self.returnSimple('hdrend')
        repoid = self.returnSimple('repoid')
        repo = base.repos.getRepo(self.returnSimple('repoid'))
        hdrpath = repo.hdrdir + '/' + hdrname
        if os.path.exists(hdrpath):
            base.log(4, 'Cached header %s exists, checking' % hdrpath)
            try: 
                hlist = rpm.readHeaderListFromFile(hdrpath)
            except rpm.error:
                os.unlink(hdrpath)
                hdrpath = repo.get(url=url, relative=rel, local=hdrpath, 
                               start=start, end=end)
                hlist = rpm.readHeaderListFromFile(hdrpath)
        else:
            hdrpath = repo.get(url=url, relative=rel, local=hdrpath, 
                            start=start, end=end)
            hlist = rpm.readHeaderListFromFile(hdrpath)

        hdr = hlist[0]
       
        return hdr                                   

    def getProvidesNames(self):
        """returns a list of providesNames"""
        
        provnames = []
        prov = self.returnPrco('provides')
        
        for (name, flag, vertup) in prov:
            provnames.append(name)

        return provnames
       

