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

# represent rpmdb as a packagesack
# starts up
# buildIndexes() populates the lookup lists
# pkglist and tuples point to match iterator indexes for quick access

import rpm
import types
import warnings

from Errors import PackageSackError
from rpmUtils import miscutils
import misc
from packages import YumInstalledPackage
from packageSack import ListPackageSack, PackageSackBase

class RPMDBPackageSack(PackageSackBase):

    def __init__(self, ts=None):
        self.excludes = {}
        self.ts = ts
        self.pkglist = []
        self.dep_table = { 'requires'  : (rpm.RPMTAG_REQUIRENAME,
                                          rpm.RPMTAG_REQUIREVERSION,
                                          rpm.RPMTAG_REQUIREFLAGS),
                           'provides'  : (rpm.RPMTAG_PROVIDENAME,
                                          rpm.RPMTAG_PROVIDEVERSION,
                                          rpm.RPMTAG_PROVIDEFLAGS),
                           'conflicts' : (rpm.RPMTAG_CONFLICTNAME,
                                          rpm.RPMTAG_CONFLICTVERSION,
                                          rpm.RPMTAG_CONFLICTFLAGS),
                           'obsoletes' : (rpm.RPMTAG_OBSOLETENAME,
                                          rpm.RPMTAG_OBSOLETEVERSION,
                                          rpm.RPMTAG_OBSOLETEFLAGS)
                           }
        if self.ts:
            self.buildIndexes()

    def buildIndexes(self):
        self.header_indexes = {}
        
        mi = self.ts.dbMatch()
        for hdr in mi:
            pkgtuple = self._hdr2pkgTuple(hdr)
            if not self.header_indexes.has_key(pkgtuple):
                self.header_indexes[pkgtuple] = []
            else:
                continue
            self.header_indexes[pkgtuple].append(mi.instance())
        
        self.pkglist = self.header_indexes.keys()
        
        del mi

    def _checkIndexes(self, failure='error'):
        return

    def delPackage(self, obj):
        self.excludes[obj.pkgId] = 1

    def searchAll(self, name, query_type='like'):
        result = {}

        # check provides
        table = self.dep_table['provides']
        mi = self.ts.dbMatch()
        mi.pattern(table[0], rpm.RPMMIRE_GLOB, name)
        for hdr in mi:
            pkg = YumInstalledPackage(hdr)
            if not result.has_key(pkg.pkgid):
                result[pkg.pkgid] = pkg

        del mi
        
        fileresults = self.searchFiles(name)
        for pkg in fileresults:
            if not result.has_key(pkg.pkgid):
                result[pkg.pkgid] = pkg
        
        return result.values()

    def searchFiles(self, name):
        """search the filelists in the rpms for anything matching name"""
        
        result = {}
        
        mi = self.ts.dbMatch('basenames', name)
        for hdr in mi:
            pkg = YumInstalledPackage(hdr)
            if not result.has_key(pkg.pkgid):
                result[pkg.pkgid] = pkg
        del mi
        
        return result.values()
        
    def searchPrco(self, name, prcotype):
        result = {}
        table = self.dep_table[prcotype]
        mi = self.ts.dbMatch(table[0], name)
        for hdr in mi:
            po = YumInstalledPackage(hdr)
            prcotup = (name, None, (None, None, None))
            if po.checkPrco(prcotype, prcotup):
                if not result.has_key(po.pkgid):
                    result[po.pkgid] = po
            
            # If it's not a provides or filename, we are done
            if prcotype != 'provides' or name[0] != '/':
                if not result.has_key(po.pkgid):
                    result[po.pkgid] = po
            else:
                fileresults = self.searchFiles(name)
                for pkg in fileresults:
                    if not result.has_key(pkg.pkgid):
                        result[pkg.pkgid] = pkg
        
        del mi
        
        return result.values()

    def searchProvides(self, name):
        return self.searchPrco(name, 'provides')

    def searchRequires(self, name):
        return self.searchPrco(name, 'requires')

    def searchObsoletes(self, name):
        return self.searchPrco(name, 'obsoletes')

    def searchConflicts(self, name):
        return self.searchPrco(name, 'conflicts')

    def simplePkgList(self):
        return self.pkglist
   
    def installed(self, name=None, arch=None, epoch=None, ver=None, rel=None, po=None):
        if po:
            name = po.name
            arch = po.arch
            epoch = po.epoch
            ver = po.ver
            rel = po.rel
            
        if len(self.searchNevra(name=name, arch=arch, epoch=epoch, ver=ver, rel=rel)) > 0:
            return 1
        return 0
    

    def returnNewestByNameArch(self, naTup=None):

        #FIXME - should this (or any packagesack) be returning tuples?
        if not naTup:
            return
        
        (name, arch) = naTup
        allpkg = []

        mi = self.ts.dbMatch(rpm.RPMTAG_NAME, naTup[0])
        arch = naTup[1]
        for hdr in mi:
            if hdr[rpm.RPMTAG_ARCH] == arch:
                allpkg.append(self._hdr2pkgTuple(hdr))
        
        del mi
        if not allpkg:
            # FIXME: raise  ...
            print 'No Package Matching %s' % name
        return misc.newestInList(allpkg)

    def returnNewestByName(self, name=None):
        if not name:
            return

        allpkg = self.mi2list(self.ts.dbMatch(rpm.RPMTAG_NAME, name))
        if not allpkg:
            # FIXME: raise  ...
            print 'No Package Matching %s' % name
        return misc.newestInList(allpkg)

    def returnPackages(self, repoid=None):
        all = []
        for pkg in self.header_indexes.keys():
            some = self.indexes2list(self.header_indexes[pkg])
            all.extend(some)
        return all

    def searchNevra(self, name=None, epoch=None, ver=None, rel=None, arch=None):
    
        
        if name and epoch and ver and rel and arch:
            if self.header_indexes.has_key((name,arch,epoch,ver,rel)):
                indexes = self.header_indexes[(name,arch,epoch,ver,rel)]
                return self.indexes2list(indexes)
            else:
                return []

        
        removedict = {}
        indexes = []
        
        for pkgtup in self.simplePkgList():
            (n, a, e, v, r) = pkgtup
            if name is not None:
                if name != n:
                    removedict[pkgtup] = 1
                    continue
            if arch is not None:
                if arch != a:
                    removedict[pkgtup] = 1
                    continue
            if epoch is not None:
                if epoch != e:
                    removedict[pkgtup] = 1
                    continue
            if ver is not None:
                if ver != v:
                    removedict[pkgtup] = 1
                    continue
            if rel is not None:
                if rel != r:
                    removedict[pkgtup] = 1
                    continue
                    
        for pkgtup in self.simplePkgList():
            if not removedict.has_key(pkgtup):
                indexes.extend(self.header_indexes[pkgtup])
        
        return self.indexes2list(indexes)

    def excludeArchs(self, archlist):
        pass
        #for arch in archlist:
        #    mi = self.ts.dbMatch()
        #    mi.pattern(rpm.RPMTAG_ARCH, rpm.RPMMIRE_STRCMP, arch)
        #    for hdr in mi:
        #        self.delPackageById(hdr[rpm.RPMTAG_SHA1HEADER])


    # Helper functions

    def mi2list(self, mi):
        returnList = []
        for hdr in mi:
            returnList.append(YumInstalledPackage(hdr))
        return returnList

    def hdrByindex(self, index):
        mi = self.ts.dbMatch(0, index)
        hdr = mi.next()
        return hdr
    
    def indexes2list(self, indexlist):
    
        """return YumInstalledPackage objects in a list for each index in the list"""
        all = []
        for idx in indexlist:
            hdr  = self.hdrByindex(idx)
            all.append(YumInstalledPackage(hdr))
        
        return all

    def _hdr2pkgTuple(self, hdr):
        name = hdr['name']
        arch = hdr['arch']
        ver = str(hdr['version']) # convert these to strings to be sure
        rel = str(hdr['release'])
        epoch = hdr['epoch']
        if epoch is None:
            epoch = '0'
        else:
            epoch = str(epoch)
    
        return (name, arch, epoch, ver, rel)

    # deprecated options for compat only - remove once rpmdb is converted:
    def getPkgList(self):
        warnings.warn('getPkgList() will go away in a future version of Yum.\n'
                'Please access this via the pkglist attribute.',
                DeprecationWarning, stacklevel=2)
    
        return self.pkglist

    def getHdrList(self):
        warnings.warn('getHdrList() will go away in a future version of Yum.\n',
                DeprecationWarning, stacklevel=2)
    
        hdrlist = []
        for pkg in self.header_indexes.keys():
            for idx in self.header_indexes[pkg]:
                hdr = self.hdrByindex(idx)
                hdrlist.append(hdr)
        return hdrlist

    def getNameArchPkgList(self):
        warnings.warn('getNameArchPkgList() will go away in a future version of Yum.\n',
                DeprecationWarning, stacklevel=2)
    
        lst = []
        for (name, arch, epoch, ver, rel) in self.pkglist:
            lst.append((name, arch))
        
        return miscutils.unique(lst)
        
        
    def getNamePkgList(self):
        warnings.warn('getNamePkgList() will go away in a future version of Yum.\n',
                DeprecationWarning, stacklevel=2)
    
        lst = []
        for (name, arch, epoch, ver, rel) in self.pkglist:
            lst.append(name)
            
        return miscutils.unique(lst)

    
    def returnTupleByKeyword(self, name=None, arch=None, epoch=None, ver=None, rel=None):
        warnings.warn('returnTuplebyKeyword() will go away in a future version of Yum.\n',
                DeprecationWarning, stacklevel=2)
    
        lst = self.searchNevra(name=name, arch=arch, epoch=epoch, ver=ver, rel=rel)
        returnlist = []
        for po in lst:
            returnlist.append(po.pkgtup)
        
        return returnlist

    def returnHeaderByTuple(self, pkgtuple):
        warnings.warn('returnHeaderByTuple() will go away in a future version of Yum.\n',
                DeprecationWarning, stacklevel=2)
        """returns a list of header(s) based on the pkgtuple provided"""
        
        (n, a, e, v, r) = pkgtuple
        
        lst = self.searchNevra(name=n, arch=a, epoch=e, ver=v, rel=r)
        if len(lst) > 0:
            item = lst[0]
            return [item.hdr]
            
        else:
            return []

    def returnIndexByTuple(self, pkgtuple):
        warnings.warn('returnIndexbyTuple() will go away in a future version of Yum.\n',
                DeprecationWarning, stacklevel=2)
        """returns a list of header indexes based on the pkgtuple provided"""
        
        if self.header_indexes.has_key(pkgtuple):
            return self.header_indexes[pkgtuple]
        
        return []
        
    def addDB(self, ts):
        warnings.warn('addDB()() will go away in a future version of Yum.\n',
                DeprecationWarning, stacklevel=2)
    
        self.ts = ts
        self.buildIndexes()

    def whatProvides(self, name, flags, version):
        """searches the rpmdb for what provides the arguments
           returns a list of pkgtuples of providing packages, possibly empty"""

        pkgs = self.searchProvides(name)
        
        if name[0] =='/':
            morepkgs = self.searchFiles(name)
            pkgs.extend(morepkgs)
        
        if flags == 0:
            flags = None
        if type(version) is types.StringType:
            (r_e, r_v, r_r) = miscutils.stringToVersion(version)
        elif type(version) in (types.TupleType, types.ListType): # would this ever be a ListType?
            (r_e, r_v, r_r) = version
        elif type(version) is types.NoneType:
            r_e = r_v = r_r = None
        
        defSack = ListPackageSack() # holder for items definitely providing this dep
        
        for po in pkgs:
            if name[0] == '/' and r_v is None:
                # file dep add all matches to the defSack
                defSack.addPackage(po)
                continue

            if po.checkPrco('provides', (name, flags, (r_e, r_v, r_r))):
                defSack.addPackage(po)
        
        returnlist = []
        for pkg in defSack.returnPackages():
            returnlist.append(pkg.pkgtup)
        
        return returnlist
            

def main():
    ts = rpm.TransactionSet('/')
    ts.setVSFlags((rpm._RPMVSF_NOSIGNATURES | rpm._RPMVSF_NODIGESTS))

    sack = RPMDBPackageSack(ts)
    sack.buildIndexes()

    for p in sack.simplePkgList():
        print p

if __name__ == '__main__':
    main()

