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
# Copyright 2003 Duke University

import libxml2
from mdErrors import PackageSackError
import mdUtils

class PackageSack:
    """represents sets (sacks) of Package Objects"""
    def __init__(self):
        self.nevra = {} #nevra[(Name, Epoch, Version, Release, Arch)] = []
        self.obsoletes = {} #obs[obsoletename] = [pkg1, pkg2, pkg3] 
                 #the package lists are packages that obsolete the key name
        self.requires = {} #req[reqname] = [pkg1, pkg2, pkg3]
                 #the package lists are packages that require the key name
        self.provides = {} #ditto of above but for provides
        self.conflicts = {} #ditto of above but for conflicts
        self.filenames = {} # duh
        self.pkgsByRepo = {} #pkgsByRepo['repoid']= [pkg1, pkg2, pkg3]
        self.pkgsByID = {} #pkgsById[pkgid] = [pkg1, pkg2] (should really only ever be one value but
                           #you might have repos with the same package in them
        self.compatarchs = None # dict of compatible archs for addPackage
        self.indexesBuilt = 0
        
        
    def __len__(self):
        return len(self.simplePkgList())
    
    def __iter__(self):
        if hasattr(self.returnPackages(), '__iter__'):
            return self.returnPackages().__iter__()
        else:
            return iter(self.returnPackages())

    def _checkIndexes(self, failure='error'):
        """check to see if the indexes are built, if not do what failure demands
           either error out or build the indexes, default is to error out"""
           
        if not self.indexesBuilt:
            if failure == 'error':
                raise PackageSackError, 'Indexes not yet built, cannot search'
            elif failure == 'build':
                self.buildIndexes()

    def searchNevra(self, name=None, epoch=None, ver=None, rel=None, arch=None):
        """return list of pkgobjects matching the nevra requested"""
        self._checkIndexes(failure='build')
        if self.nevra.has_key((name, epoch, ver, rel, arch)):
            return self.nevra[(name, epoch, ver, rel, arch)]
        else:
            return []
           
        
    def searchID(self, pkgid):
        """return list of packages based on pkgid"""
        self._checkIndexes(failure='build')        
        if self.pkgsByID.has_key(pkgid):
            return self.pkgsByID[pkgid]
        else:
            return []
            
    def searchRequires(self, name):
        """return list of package requiring the name (any evr and flag)"""
        self._checkIndexes(failure='build')        
        if self.requires.has_key(name):
            return self.requires[name]
        else:
            return []

    def searchProvides(self, name):
        """return list of package providing the name (any evr and flag)"""
        # FIXME - should this do a pkgobj.checkPrco((name, flag, (e,v,r,))??
        # has to do a searchFiles and a searchProvides for things starting with /
        self._checkIndexes(failure='build')        
        returnList = []
        if name[0] == '/':
             returnList.extend(self.searchFiles(name))
        if self.provides.has_key(name):
            returnList.extend(self.provides[name])
        return returnList

    def searchConflicts(self, name):
        """return list of package conflicting with the name (any evr and flag)"""
        self._checkIndexes(failure='build')        
        if self.conflicts.has_key(name):
            return self.conflicts[name]
        else:
            return []

    def searchObsoletes(self, name):
        """return list of package obsoleting the name (any evr and flag)"""
        self._checkIndexes(failure='build')        
        if self.obsoletes.has_key(name):
            return self.obsoletes[name]
        else:
            return []

    def returnObsoletes(self):
        """returns a dict of obsoletes dict[obsoleting pkgtuple] = [list of obs]"""
        obs = {}
        for po in self.returnPackages():
            pkgtuple = po.returnPackageTuple()
            if len(po.returnPrco('obsoletes')) == 0:
                continue

            if not obs.has_key(pkgtuple):
                obs[pkgtuple] = po.returnPrco('obsoletes')
            else:
                obs[pkgtuple].extend(po.returnPrco('obsoletes'))
        
        return obs
        
    def searchFiles(self, file):
        """return list of packages by filename
           FIXME - need to add regex match against keys in file list
        """
        self._checkIndexes(failure='build')
        if self.filenames.has_key(file):
            return self.filenames[file]
        else:
            return []

    def _addToDictAsList(self, dict, key, data):
        if not dict.has_key(key):
            dict[key] = []
        #if data not in dict[key]: - if I enable this the whole world grinds to a halt
        # need a faster way of looking for the object in any particular list
        dict[key].append(data)

    def _delFromListOfDict(self, dict, key, data):
        if not dict.has_key(key):
            dict[key] = []
        try:
            dict[key].remove(data)
        except ValueError:
            pass
            
        if len(dict[key]) == 0: # if it's an empty list of the dict, then kill it
            del dict[key]
            
            
    def addPackage(self, obj):
        """add a pkgobject to the packageSack"""

        repoid = obj.returnSimple('repoid')
        (name, epoch, ver, rel, arch) = obj.returnNevraTuple()
        
        if self.compatarchs:
            if self.compatarchs.has_key(arch):
                self._addToDictAsList(self.pkgsByRepo, repoid, obj)
        else:
            self._addToDictAsList(self.pkgsByRepo, repoid, obj)


    def buildIndexes(self):
        """builds the useful indexes for searching/querying the packageSack
           This should be called after all the necessary packages have been 
           added/deleted"""
        
        # blank out the indexes
        self.obsoletes = {}
        self.requires = {}
        self.provides = {}
        self.conflicts = {}
        self.filenames = {}
        self.nevra = {}
        self.pkgsByID = {}
        
        for repoid in self.pkgsByRepo.keys():
            for obj in self.pkgsByRepo[repoid]:
            # store the things provided just on name, not the whole require+version
            # this lets us reduce the set of pkgs to search when we're trying to depSolve
                for (n, fl, (e,v,r)) in obj.returnPrco('obsoletes'):
                    self._addToDictAsList(self.obsoletes, n, obj)
                for (n, fl, (e,v,r)) in obj.returnPrco('requires'):
                    self._addToDictAsList(self.requires, n, obj)
                for (n, fl, (e,v,r)) in obj.returnPrco('provides'):
                    self._addToDictAsList(self.provides, n, obj)
                for (n, fl, (e,v,r)) in obj.returnPrco('conflicts'):
                    self._addToDictAsList(self.conflicts, n, obj)
                for ftype in obj.returnFileTypes():
                    for file in obj.returnFileEntries(ftype):
                        self._addToDictAsList(self.filenames, file, obj)
                self._addToDictAsList(self.pkgsByID, obj.returnSimple('id'), obj)
                (name, epoch, ver, rel, arch) = obj.returnNevraTuple()
                self._addToDictAsList(self.nevra, (name, epoch, ver, rel, arch), obj)
                self._addToDictAsList(self.nevra, (name, None, None, None, None), obj)
        
        self.indexesBuilt = 1
        

        
    def delPackage(self, obj):
        """delete a pkgobject"""
        self._delFromListOfDict(self.pkgsByRepo, obj.returnSimple('repoid'), obj)
        if self.indexesBuilt: # if we've built indexes, delete it b/c we've just deleted something
            self.indexesBuilt = 0
        
    def returnPackages(self, repoid=None):
        """return list of all packages, takes optional repoid"""
        returnList = []
        if repoid is None:
            for repo in self.pkgsByRepo.keys():
                returnList.extend(self.pkgsByRepo[repo])
        else:
            try:
                returnList = self.pkgsByRepo[repoid]
            except KeyError:
                # nothing to return
                pass
        
        return returnList

    def returnNewestByNameArch(self, naTup=None):
        """return list of newest packages based on name, arch matching
           this means(in name.arch form): foo.i386 and foo.noarch are not 
           compared to each other for highest version only foo.i386 and 
           foo.i386 will be compared"""
        highdict = {}
        # If naTup is set, only iterate through packages that match that
        # name
        if (naTup):
            where = self.nevra.get((naTup[0],None,None,None,None))
            if (not where):
                raise PackageSackError, 'No Package Matching %s.%s' % naTup
        else:
            where = self.returnPackages()

        for pkg in where:
            (n, e, v ,r, a) = pkg.returnNevraTuple()
            if not highdict.has_key((n, a)):
                highdict[(n, a)] = pkg
            else:
                pkg2 = highdict[(n, a)]
                (e2, v2, r2) = pkg2.returnEVR()
                rc = mdUtils.compareEVR((e,v,r), (e2, v2, r2))
                if rc > 0:
                    highdict[(n, a)] = pkg
        
        if naTup:
            if highdict.has_key(naTup):
                return highdict[naTup]
            else:
                raise PackageSackError, 'No Package Matching %s.%s' % naTup
        
        return highdict.values()
        
    def returnNewestByName(self, name=None):
        """return list of newest packages based on name matching
           this means(in name.arch form): foo.i386 and foo.noarch will
           be compared to each other for highest version"""
        highdict = {}
        for pkg in self.returnPackages():
            (n, e, v ,r, a) = pkg.returnNevraTuple()
            if not highdict.has_key(n):
                highdict[n] = []
                highdict[n].append(pkg)
            else:
                pkg2 = highdict[n][0]
                (e2, v2, r2) = pkg2.returnEVR()
                rc = mdUtils.compareEVR((e,v,r), (e2, v2, r2))
                if rc > 0:
                    highdict[n] = [pkg]
                elif rc == 0:
                    highdict[n].append(pkg)
                
        if name:
            if highdict.has_key(name):
                return highdict[name]
            else:
                raise PackageSackError, 'No Package Matching  %s' % name
                
        return highdict.values()
           
    def simplePkgList(self, repoid=None):
        """returns a list of pkg tuples (n, a, e, v, r) optionally from a single repoid"""
        simplelist = []
        for pkg in self.returnPackages(repoid):
            simplelist.append(pkg.returnPackageTuple())
        return simplelist
                       
    def printPackages(self):
        for pkg in self.returnPackages():
            print pkg.returnNevraPrintable()

        

# packageSack should be a base class
# two derived classes could be DBPackageSack and XMLPackageSack
# one for importing this data from the localdb 
# another from XML metadata files

class XMLPackageSack(PackageSack):
    """Derived class from PackageSack to build list from XML metadata file. 
       Needs the Package Object Class passed to it for the Sack"""
    def __init__(self, pkgObjectClass):
        PackageSack.__init__(self)
        self.repoStatus = {} #[repoid]= [primary, filelist, other] (so you can tell 
                             #what things have been loaded or not - b/c w/o primary, 
                             #filelist and other really can't be loaded
        self.pkgObjectClass = pkgObjectClass                           

                
    def addFile(self, repoid, file, callback=None):
        """takes a repository id and an xml file. It populates whatever it can, 
           if you try to populate with a filelist or other metadata file 
           before the primary metadata you'll not like the results"""
        try:
            reader = libxml2.newTextReaderFilename(file)
        except libxml2.treeError:
            raise PackageSackError, "Invalid or non-existent file: %s" % (file)

        else:
            reader.Read()
            xmlfiletype=reader.Name() # - first node should be the type
            if xmlfiletype == 'metadata':
                if not self._checkRepoStatus(repoid, itemcheck='primary'):
                    self.loadPrimaryMD(reader, repoid, callback)

            elif xmlfiletype == 'filelists':
                if not self._checkRepoStatus(repoid, itemcheck='filelists'):
                    self.loadFileMD(reader, repoid, callback)

            elif xmlfiletype == 'otherdata':
                if not self._checkRepoStatus(repoid, itemcheck='other'):
                    self.loadOtherMD(reader, repoid, callback)

            else:
                print 'Error: other unknown root element %s' % xmlfiletype 


    def _checkRepoStatus(self, repoid, itemcheck='primary'):
        """return 1 if itemcheck is in repo"""
        if self.repoStatus.has_key(repoid):
            if itemcheck in self.repoStatus[repoid]:
                return 1
        return 0
            
    def loadPrimaryMD(self, reader, repoid, callback=None):
        """load all the data from the primary metadata xml file"""
        
        pkgcount = 9999 # big number
        current = 1
        if reader.HasAttributes():
            pkgcount = int(reader.GetAttribute('packages'))
            

        
        ret = reader.Read()
        while ret:
            if reader.NodeType() == 14:
                ret = reader.Read()
                continue
            
            if reader.NodeType() == 1 and reader.Name() == 'package':
                if reader.HasAttributes():
                    if reader.GetAttribute('type') == 'rpm':
                        current+=1
                        po = self.pkgObjectClass(reader, repoid)
                        self.addPackage(po)
            if callback: callback(current, pkgcount, name=repoid)
            ret = reader.Read()
            continue

        # update the repoStatus                
        if not self.repoStatus.has_key(repoid):
            self.repoStatus[repoid] = []
        if not 'primary' in self.repoStatus[repoid]:
            self.repoStatus[repoid].append('primary')


    def loadFileMD(self, reader, repoid, callback=None):
        """load all the filelist metadata from the file"""

        pkgcount = 9999 # big number
        current = 1
        if reader.HasAttributes():
            pkgcount = int(reader.GetAttribute('packages'))

        ret = reader.Read()
        while ret:
            if reader.NodeType() == 14:
                ret = reader.Read()
                continue
            
            if reader.NodeType() == 1 and reader.Name() == 'package':
                if reader.HasAttributes():
                    pkgid = reader.GetAttribute('pkgid')
                    pkgs = self.searchID(pkgid)
                    pkgmatch = 0
                    mydepth = reader.Depth()
                    current+=1

                    for pkg in pkgs:
                        if pkg.returnSimple('repoid') == repoid: # check for matching repo
                            reader.Read()
                            pkgmatch+=1
                            
                            while 1:
                                if reader.NodeType() == 15 and reader.Depth() == mydepth:
                                    break
                                    
                                elif reader.NodeType() == 14:
                                    ret = reader.Read()
                                    continue

                                elif reader.NodeType() == 1:
                                    if reader.LocalName() == 'file':
                                        (ftype, file) = pkg.loadFileEntry(reader)
                                        #self._addToDictAsList(self.filenames, file, pkg)

                                ret = reader.Read()
                                continue        

                    if pkgmatch < 1:
                        # FIXME - raise a warning? Emit error? bitch? moan?
                        pass

                               
            ret = reader.Read()
            if callback: callback(current, pkgcount, name=repoid) # give us some pretty output
            continue

        # update the repostatus
        if not 'filelist' in self.repoStatus[repoid]:
            self.repoStatus[repoid].append('filelist')
        # we've just added file items - build up the indexes again
        self.buildIndexes()
        
            
    def loadOtherMD(self, reader, repoid, callback=None):
        """load the changelog, etc data from the other.xml file"""

        pkgcount = 9999 # big number
        current = 1
        if reader.HasAttributes():
            pkgcount = int(reader.GetAttribute('packages'))

        ret = reader.Read()
        while ret:
            if reader.NodeType() == 14:
                ret = reader.Read()
                continue
            
            if reader.NodeType() == 1 and reader.Name() == 'package':
                current+=1
                if reader.HasAttributes():
                    pkgid = reader.GetAttribute('pkgid')
                    pkgs = self.searchID(pkgid)
                    pkgmatch = 0
                    mydepth = reader.Depth()
                    #current+=1
                    

                    for pkg in pkgs:
                        if pkg.returnSimple('repoid') == repoid: # check for matching repo
                            reader.Read()
                            pkgmatch+=1
                            
                            while 1:
                                if reader.NodeType() == 15 and reader.Depth() == mydepth:
                                    break
                                    
                                elif reader.NodeType() == 14:
                                    ret = reader.Read()                                                        
                                    continue

                                elif reader.NodeType() == 1:
                                    if reader.LocalName() == 'changelog':
                                        pkg.loadChangeLogEntry(reader)

                                ret = reader.Read()
                                continue        

                    if pkgmatch < 1:
                        # FIXME - raise a warning? Emit error? bitch? moan?
                        pass
            if callback: callback(current, pkgcount, name=repoid)
            ret = reader.Read()
            continue
                                        
        if not 'other' in self.repoStatus[repoid]:
            self.repoStatus[repoid].append('other')
        # we've just added file items - build up the indexes again
        self.buildIndexes()
        

class ListPackageSack(PackageSack):
    """Derived class from PackageSack to build new Sack from list of
       pkgObjects - like one returned from self.returnNewestByNameArch()
       or self.returnNewestByName()"""
       
    def __init__(self, Objlist=None):
        PackageSack.__init__(self)
        if Objlist is not None:
            self.addList(Objlist)
    
    def addList(self, ObjList):
        for pkgobj in ObjList:
            self.addPackage(pkgobj)
    
