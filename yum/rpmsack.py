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
import Errors
from packages import YumInstalledPackage
from packageSack import PackageSackBase

class RPMInstalledPackage(YumInstalledPackage):

    def __init__(self, rpmhdr, index, rpmdb):
        hdr = {}
        for key in ['name', 'arch', 'epoch', 'version', 'release',
                    'summary', 'description', 'size',
                    rpm.RPMTAG_SHA1HEADER]:
            hdr[key] = rpmhdr[key]
        YumInstalledPackage.__init__(self, hdr)

        # NOTE: We keep summary/description/url because it doesn't add much
        # and "yum search" uses them all.
        self.url       = rpmhdr['url']
        # Also keep sourcerpm for pirut/etc.
        self.sourcerpm = rpmhdr['sourcerpm']

        self.idx   = index
        self.rpmdb = rpmdb

        self._has_hdr = False
        del self.hdr

    def __getattr__(self, varname):
        # Note that we can't use hasattr(self, 'hdr') or we'll recurse
        if self._has_hdr:
            return self.hdr[thing]

        ts = self.rpmdb.readOnlyTS()
        mi = ts.dbMatch(0, self.idx)
        hdr = mi.next()

        self._has_hdr = True
        self.hdr = val = hdr

        if varname != 'hdr':   # This is very unusual, for anything it does
            val = hdr[varname] # happen for it might be worth adding at __init__

        return val


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
        self._idx2pkg = {}
        self._name2pkg = {}
        self._tup2pkg = {}
        self._completely_loaded = False
        self._simple_pkgtup_list = []
        self.ts = None

        self._cache = {
            'files' : { },
            'provides' : { },
            'requires' : { },
            'conflicts' : { },
            'obsoletes' : { },
            }
        
    def _get_pkglist(self):
        '''Getter for the pkglist property. 
        Returns a list of package tuples.
        '''
        if not self._simple_pkgtup_list:
            for (hdr, mi) in self._all_packages():
                self._simple_pkgtup_list.append(self._hdr2pkgTuple(hdr))
            
        return self._simple_pkgtup_list

    pkglist = property(_get_pkglist, None)

    def readOnlyTS(self):
        if not self.ts:
            self.ts =  initReadOnlyTransaction(root=self.root)
        return self.ts

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

        fileresults = self.searchFiles(name)
        for pkg in fileresults:
            if not result.has_key(pkg.pkgid):
                result[pkg.pkgid] = pkg
        
        return result.values()

    def searchFiles(self, name):
        """search the filelists in the rpms for anything matching name"""

        result = self._cache['files'].get(name)
        if result is not None:
            return result

        ts = self.readOnlyTS()
        result = {}
        
        mi = ts.dbMatch('basenames', name)
        for hdr in mi:
            pkg = self._makePackageObject(hdr, mi.instance())
            if not result.has_key(pkg.pkgid):
                result[pkg.pkgid] = pkg
        del mi

        result = result.values()
        self._cache['files'][name] = result
        return result
        
    def searchPrco(self, name, prcotype):

        result = self._cache[prcotype].get(name)
        if result is not None:
            return result

        ts = self.readOnlyTS()
        result = {}
        tag = self.DEP_TABLE[prcotype][0]
        mi = ts.dbMatch(tag, name)
        for hdr in mi:
            po = self._makePackageObject(hdr, mi.instance())
            result[po.pkgid] = po
        del mi

        # If it's not a provides or filename, we are done
        if prcotype == 'provides' and name[0] == '/':
            fileresults = self.searchFiles(name)
            for pkg in fileresults:
                result[pkg.pkgid] = pkg
        
        result = result.values()
        self._cache[prcotype][name] = result
        return result

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

    installed = PackageSackBase.contains

    def returnNewestByNameArch(self, naTup=None, patterns=None):

        #FIXME - should this (or any packagesack) be returning tuples?
        if not naTup:
            return
        
        (name, arch) = naTup

        allpkg = [ po.pkgtup for po in self._search(name=name, arch=arch) ]

        if not allpkg:
            raise Errors.PackageSackError, 'No Package Matching %s' % name

        return misc.newestInList(allpkg)

    def returnNewestByName(self, name=None):
        if not name:
            return

        allpkgs = self._search(name=name)

        if not allpkgs:
            raise Errors.PackageSackError, 'No Package Matching %s' % name

        return misc.newestInList(allpkgs)

    def returnPackages(self, repoid=None, patterns=None):
        if not self._completely_loaded:
            for hdr, idx in self._all_packages():
                self._makePackageObject(hdr, idx)
            self._completely_loaded = True
        return self._idx2pkg.values()

    def searchNevra(self, name=None, epoch=None, ver=None, rel=None, arch=None):
        return self._search(name, epoch, ver, rel, arch)

    def contains(self, name=None, arch=None, epoch=None, ver=None, rel=None, po=None):
        """return if there are any packages in the sack that match the given NAEVR 
           or the NAEVR of the given po"""
        if po:
            name = po.name
            arch = po.arch
            epoch = po.epoch
            ver = po.version
            rel = po.release

        if name and arch and epoch and ver and rel: # cheater lookup
            if (name, arch, epoch, ver, rel) in self._tup2pkg:
                return True
            
        return bool(self.searchNevra(name=name, arch=arch, epoch=epoch, ver=ver, rel=rel))

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

    def _header_from_index(self, idx):
        """returns a package header having been given an index"""
        warnings.warn('_header_from_index() will go away in a future version of Yum.\n',
                Errors.YumFutureDeprecationWarning, stacklevel=2)

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

    def _search(self, name=None, epoch=None, ver=None, rel=None, arch=None):
        '''Generator that yields matching packages
        '''
        pkgtup = (name, arch, epoch, ver, rel)
        if self._tup2pkg.has_key(pkgtup):
            return [self._tup2pkg[pkgtup]]

        loc = locals()
        ret = []

        if self._completely_loaded:
            if name is not None:
                pkgs = self._name2pkg.get(name, [])
            else:
                pkgs = self.returnPkgs()
            for po in pkgs:
                for tag in ('name', 'epoch', 'ver', 'rel', 'arch'):
                    if loc[tag] is not None and loc[tag] != getattr(po, tag):
                        break
                else:
                    ret.append(po)
            return ret

        ts = self.readOnlyTS()
        if name is not None:
            mi = ts.dbMatch('name', name)
        elif arch is not None:
            mi = ts.dbMatch('arch', arch)
        else:
            mi = ts.dbMatch()
            self._completely_loaded = True

        for hdr in mi:
            po = self._makePackageObject(hdr, mi.instance())
            for tag in ('name', 'epoch', 'ver', 'rel', 'arch'):
                if loc[tag] is not None and loc[tag] != getattr(po, tag):
                    break
            else:
                ret.append(po)
        return ret

    def _makePackageObject(self, hdr, index):
        if self._idx2pkg.has_key(index):
            return self._idx2pkg[index]
        po = RPMInstalledPackage(hdr, index, self)
        self._idx2pkg[index] = po
        self._name2pkg.setdefault(po.name, []).append(po)
        self._tup2pkg[po.pkgtup] = po
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
        return [po.pkgtup for po in self._search(name=name, arch=arch, epoch=epoch, ver=ver, rel=rel)]

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

        return [po.idx for po in self._search(name, epoch, version, release, arch)]
        
    def addDB(self, ts):
        # Can't support this now
        raise NotImplementedError

    def getProvides(self, name, flags=None, version=(None, None, None)):
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
        
        result = { }
        
        for po in pkgs:
            if name[0] == '/' and r_v is None:
                result[po] = [(name, None, (None, None, None))]
                continue
            hits = po.matchingPrcos(
                'provides', (name, flags, (r_e, r_v, r_r)))
            if hits:
                result[po] = hits
        return result

    def whatProvides(self, name, flags, version):
        # XXX deprecate?
        return [po.pkgtup for po in self.getProvides(name, flags, version)]

    def getRequires(self, name, flags=None, version=(None, None, None)):
        """searches the rpmdb for what provides the arguments
           returns a list of pkgtuples of providing packages, possibly empty"""

        pkgs = self.searchRequires(name)

        if flags == 0:
            flags = None
        if type(version) is types.StringType:
            (r_e, r_v, r_r) = miscutils.stringToVersion(version)
        elif type(version) in (types.TupleType, types.ListType): # would this ever be a ListType?
            (r_e, r_v, r_r) = version
        elif type(version) is types.NoneType:
            r_e = r_v = r_r = None

        result = { }

        for po in pkgs:
            if name[0] == '/' and r_v is None:
                # file dep add all matches to the defSack
                result[po] = [(name, None, (None, None, None))]
                continue
            hits = po.matchingPrcos(
                'requires', (name, flags, (r_e, r_v, r_r)))
            if hits:
                result[po] = hits
        return result

    def whatRequires(self, name, flags, version):
        # XXX deprecate?
        return [po.pkgtup for po in self.getRequires(name, flags, version)]
            
def main():
    sack = RPMDBPackageSack('/')
    for p in sack.simplePkgList():
        print p

if __name__ == '__main__':
    main()

