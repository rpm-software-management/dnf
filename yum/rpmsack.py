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
from Errors import PackageSackError
from rpmUtils import miscutils
import misc
from packages import YumInstalledPackage

class RPMDBPackageSack:

    def __init__(self, ts):
        self.excludes = {}
        self.ts = ts
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

    def buildIndexes(self):
        self.match_on_index = 1
        self.header_indexes = {}
        
        try:
            # we need the find a known index so we can test if
            # rpm/rpm-python allows us to grab packages by db index.
            mi = self.ts.dbMatch()
            hdr = mi.next()
            known_index = mi.instance()
            mi = self.ts.dbMatch(0, known_index)
            hdr = mi.next()
        except (TypeError, StopIteration), e:
            raise PackageSackError, "Match Iterators not supported, upgrade rpmlib"
            
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
            pkg = hdr2class(hdr)
            if not result.has_key(pkg.pkgId):
                result[pkg.pkgId] = pkg

        # FIXME
        # check filelists/dirlists
        
        return result.values()

    def returnObsoletes(self):
        obsoletes = {}

        tags = self.dep_table['obsoletes']
        mi = self.ts.dbMatch()
        for hdr in mi:
            if not len(hdr[rpm.RPMTAG_OBSOLETENAMES]):
                continue

            key = (hdr[rpm.RPMTAG_NAME],
                   hdr[rpm.RPMTAG_ARCH],
                   hdr[rpm.RPMTAG_EPOCH],
                   hdr[rpm.RPMTAG_VERSION],
                   hdr[rpm.RPMTAG_RELEASE])

            obsoletes[key] = self._getDependencies(hdr, tags)

        return obsoletes


    def searchPrco(self, name, prcotype):
        result = []
        table = self.dep_table[prcotype]
        mi = self.ts.dbMatch()
        mi.pattern(table[0], rpm.RPMMIRE_STRCMP, name)
        for hdr in mi:
            pkg = self.hdr2class(hdr, True)
            names = hdr[table[0]]
            vers = hdr[table[1]]
            flags = hdr[table[2]]

            for i in range(0, len(names)):
                n = names[i]
                if n != name:
                    continue

                (e, v, r) = miscutils.stringToVersion(vers[i])
                pkg.prco = {prcotype: [{'name' : name,
                                        'flags' : self._parseFlags (flags[i]),
                                        'epoch' : e,
                                        'ver' : v,
                                        'rel' : r}
                                       ]
                            }
                result.append(pkg)

            # If it's not a provides or filename, we are done
            if prcotype != 'provides' or name[0] != '/':
                return result

            # FIXME: Search package files

        return result

    def searchProvides(self, name):
        return self.searchPrco(name, 'provides')

    def searchRequires(self, name):
        return self.searchPrco(name, 'requires')

    def searchObsoletes(self, name):
        return self.searchPrco(name, 'obsoletes')

    def searchConflicts(self, name):
        return self.searchPrco(name, 'conflicts')

    def simplePkgList(self, repoid=None):
        return self.pkglist

    def returnNewestByNameArch(self, naTup=None):
        if not naTup:
            return

        allpkg = []

        mi = self.ts.dbMatch(rpm.RPMTAG_NAME, naTup[0])
        arch = naTup[1]
        for hdr in mi:
            if hdr[rpm.RPMTAG_ARCH] == arch:
                allpkg.append(self.hdr2tuple (hdr))

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
            indexes = self.header_indexes[(n,a,e,v,r)]
            return self.indexes2list(indexes)
        
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

    def packagesByTuple(self, pkgtup):
        """return a list of package objects by (n,a,e,v,r) tuple"""
        (n,a,e,v,r) = pkgtup
        return self.searchNevra(name=n, arch=a, epoch=e, ver=v, rel=r)

    def excludeArchs(self, archlist):
        pass
        #for arch in archlist:
        #    mi = self.ts.dbMatch()
        #    mi.pattern(rpm.RPMTAG_ARCH, rpm.RPMMIRE_STRCMP, arch)
        #    for hdr in mi:
        #        self.delPackageById(hdr[rpm.RPMTAG_SHA1HEADER])



    # Helper functions

    def _parseFlags(self, flags):
        flagstr = ''
        if flags & rpm.RPMSENSE_LESS:
            flagstr += '<'
        if flags & rpm.RPMSENSE_GREATER:
            flagstr += '>'
        if flags & rpm.RPMSENSE_EQUAL:
            flagstr += '='
        return flagstr

    def _getDependencies(self, hdr, tags):
        # tags is a tuple containing 3 rpm tags:
        # first one to get dep names, the 2nd to get dep versions,
        # and the 3rd to get dep flags
        deps = []

        names = hdr[tags[0]]
        vers  = hdr[tags[1]]
        flags = hdr[tags[2]]

        for i in range(0, len(names)):
            deps.append(names[i],
                        self._parseFlags(flags[i]),
                        miscutils.stringToVersion(vers[i]))

        return deps

    def mi2list(self, mi):
        returnList = []
        for hdr in mi:
            returnList.append(YumInstalledPackage(hdr))
        return returnList

    def hdr2tuple(self, hdr):
        return (hdr[rpm.RPMTAG_SHA1HEADER],
                hdr[rpm.RPMTAG_NAME],
                hdr[rpm.RPMTAG_EPOCH],
                hdr[rpm.RPMTAG_VERSION],
                hdr[rpm.RPMTAG_RELEASE],
                hdr[rpm.RPMTAG_ARCH])

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


def main():
    ts = rpm.TransactionSet('/')
    ts.setVSFlags((rpm._RPMVSF_NOSIGNATURES | rpm._RPMVSF_NODIGESTS))

    sack = RPMDBPackageSack(ts)
    sack.buildIndexes()

    for p in sack.returnPackages():
        print p

if __name__ == '__main__':
    main()

