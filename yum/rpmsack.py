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

import rpm
import types
import warnings

from rpmUtils import miscutils
from rpmUtils.transaction import initReadOnlyTransaction
import misc
from packages import YumInstalledPackage
from packageSack import ListPackageSack, PackageSackBase

class RPMDBPackageSack(PackageSackBase):
    '''
    Represent rpmdb as a packagesack
    '''

    DEP_TABLE = { 
            'requires'  : (rpm.RPMTAG_REQUIRENAME,
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

    def __init__(self, root='/'):
        self.root = root
        self._header_dict = {}

    def _get_pkglist(self):
        '''Getter for the pkglist property. 
        Returns a list of package tuples.
        '''
        return [ self._hdr2pkgTuple(hdr)
            for hdr, idx in self._all_packages() ]

    pkglist = property(_get_pkglist, None)

    def readOnlyTS(self):
        return initReadOnlyTransaction(root=self.root)

    def buildIndexes(self):
        # Not used here
        return

    def _checkIndexes(self, failure='error'):
        # Not used here
        return

    def delPackage(self, obj):
        # Not supported with this sack type
        pass

    def searchAll(self, name, query_type='like'):
        ts = self.readOnlyTS()
        result = {}

        # check provides
        tag = self.DEP_TABLE['provides'][0]
        mi = ts.dbMatch()
        mi.pattern(tag, rpm.RPMMIRE_GLOB, name)
        for hdr in mi:
            pkg = self._makePackageObject(hdr, mi.instance())
            if not result.has_key(pkg.pkgid):
                result[pkg.pkgid] = pkg
        del mi
        ts.close()
        
        fileresults = self.searchFiles(name)
        for pkg in fileresults:
            if not result.has_key(pkg.pkgid):
                result[pkg.pkgid] = pkg
        
        return result.values()

    def searchFiles(self, name):
        """search the filelists in the rpms for anything matching name"""
        ts = self.readOnlyTS()
        result = {}
        
        mi = ts.dbMatch('basenames', name)
        for hdr in mi:
            pkg = self._makePackageObject(hdr, mi.instance())
            if not result.has_key(pkg.pkgid):
                result[pkg.pkgid] = pkg
        del mi
        ts.close()
        
        return result.values()
        
    def searchPrco(self, name, prcotype):
        
        ts = self.readOnlyTS()
        result = {}
        tag = self.DEP_TABLE[prcotype][0]
        mi = ts.dbMatch(tag, name)
        for hdr in mi:
            po = self._makePackageObject(hdr, mi.instance())
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
        ts.close()
        
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
            
        return len(self.searchNevra(name=name, arch=arch, epoch=epoch, ver=ver, rel=rel)) > 0

    def returnNewestByNameArch(self, naTup=None):

        #FIXME - should this (or any packagesack) be returning tuples?
        if not naTup:
            return
        
        (name, arch) = naTup

        allpkg = [ pkgtup 
            for (hdr, pkgtup, idx) in self._search(name=name, arch=arch) ]

        if not allpkg:
            # FIXME: raise  ...
            print 'No Package Matching %s' % name

        return misc.newestInList(allpkg)

    def returnNewestByName(self, name=None):
        if not name:
            return

        allpkg = [ pkgtup
            for (hdr, pkgtup, idx) in self._search(name=name) ]

        if not allpkg:
            # FIXME: raise  ...
            print 'No Package Matching %s' % name

        return misc.newestInList(allpkg)

    def returnPackages(self, repoid=None):
        return [ self._makePackageObject(hdr, idx)
            for hdr, idx in self._all_packages() ]

    def searchNevra(self, name=None, epoch=None, ver=None, rel=None, arch=None):
        return [ self._makePackageObject(hdr, idx)
            for (hdr, pkgtup, idx) in self._search(name, epoch, ver, rel, arch) ]

    def excludeArchs(self, archlist):
        pass

    # Helper functions
    def _all_packages(self):
        '''Generator that yield (header, index) for all packages
        '''
        ts = self.readOnlyTS()
        mi = ts.dbMatch()

        for hdr in mi:
            if hdr['name'] != 'gpg-pubkey':
                yield (hdr, mi.instance())
        del mi
        ts.close()
        del ts

    def _header_from_index(self, idx):
        """returns a package header having been given an index"""
        
        ts = self.readOnlyTS()
        try:
            mi = ts.dbMatch(0, idx)
        except (TypeError, StopIteration), e:
            #FIXME: raise some kind of error here
            print 'No index matching %s found in rpmdb, this is bad' % idx
            yield None # it should REALLY not be returning none - this needs to be right
        else:
            hdr = mi.next()
            yield hdr
            del hdr

        del mi
        ts.close()
        del ts

    def _make_header_dict(self):
        """generate a header indexes dict that is pkgtup = index number"""
        
        for (hdr, idx) in self._all_packages():
            pkgtup = self._hdr2pkgTuple(hdr)
            self._header_dict[pkgtup] = idx
        
        
    def _search(self, name=None, epoch=None, ver=None, rel=None, arch=None):
        '''Generator that yield (header, pkgtup, index) for matching packages
        '''
        # Create a match closure for what is being searched for 
        lookfor = []        # A list of (package_tuple_idx, search_value)
        loc = locals()
        for (i, arg) in enumerate(('name', 'arch', 'epoch', 'ver', 'rel')):
            val = loc[arg]
            if val != None:
                lookfor.append((i, val))

        def match(tup):
            for idx, val in lookfor:
                if tup[idx] != val:
                    return False
            return True

        # Find and yield matches
        if not self._header_dict:
            self._make_header_dict()
        
        for pkgtup in self._header_dict.keys():
            if match(pkgtup):
                idx = self._header_dict[pkgtup]
                for h in self._header_from_index(idx):
                    yield h, pkgtup, idx

    def _search2(self, name=None, epoch=None, version=None, release=None, arch=None):
        '''Generator that yield (header, index) for matching packages

        This version uses RPM to do the work but it's significantly slower than _search()
        Not actually used.
        '''
        ts = self.readOnlyTS()
        mi = ts.dbMatch()

        # Set up the search patterns
        for arg in ('name', 'epoch', 'version', 'release', 'arch'):
            val = locals()[arg]
            if val != None:
                mi.pattern(arg,  rpm.RPMMIRE_DEFAULT, val)

        # Report matches
        for hdr in mi:
            if hdr['name'] != 'gpg-pubkey':
                yield (hdr, mi.instance())

        ts.close()

    def _makePackageObject(self, hdr, index):
        po = YumInstalledPackage(hdr)
        po.idx = index
        return po
        
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
        return [ hdr for hdr, idx in self._all_packages() ]

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

        out = []
        for hdr, tup, idx in self._search(name=name, arch=arch, epoch=epoch, ver=ver, rel=rel):
            out.append(tup)
        return out

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
        """returns a list of header indexes based on the pkgtuple provided"""

        warnings.warn('returnIndexbyTuple() will go away in a future version of Yum.\n',
                DeprecationWarning, stacklevel=2)

        name, arch, epoch, version, release = pkgtuple

        # Normalise epoch
        if epoch in (None, 0, '(none)', ''):
            epoch = '0'

        out = []
        for hdr, tup, idx in self._search(name, epoch, version, release, arch):
            out.append(idx)
        return out
        
    def addDB(self, ts):
        # Can't support this now
        raise NotImplementedError

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
    sack = RPMDBPackageSack('/')
    for p in sack.simplePkgList():
        print p

if __name__ == '__main__':
    main()

