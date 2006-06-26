#!/usr/bin/python -tt

import rpm
from rpmUtils import miscutils
import misc
from packages import YumInstalledPackage

class RPMDBPackageSack:

    def __init__(self, rootdir='/'):
        self.excludes = {}
        self.ts = rpm.TransactionSet(rootdir)
        self.ts.setVSFlags((rpm._RPMVSF_NOSIGNATURES | rpm._RPMVSF_NODIGESTS))

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
        # We don't need these
        return

    def _checkIndexes(self, failure='error'):
        return

    def delPackage(self, obj):
        self.excludes[obj.pkgId] = 1

    def delPackageById(self, pkgId):
        self.excludes[pkgId] = 1

    def getChangelog(self, pkgId):
        mi = self.ts.dbMatch(rpm.RPMTAG_SHA1HEADER, pkgId)
        hdr = mi.next()

        times = hdr[rpm.RPMTAG_CHANGELOGTIME]
        names = hdr[rpm.RPMTAG_CHANGELOGNAME]
        texts = hdr[rpm.RPMTAG_CHANGELOGTEXT]

        result = []
        for i in range(0, len(times)):
            result.append((times[i], names[i], texts[i]))
        return result

    def getPrco(self, pkgId, prcotype=None):
        mi = self.ts.dbMatch(rpm.RPMTAG_SHA1HEADER, pkgId)
        hdr = mi.next()

        if prcotype:
            types = (prcotype,)
        else:
            types = self.dep_table.keys()

        result = {}
        for t in types:
            result[t] = self._getDependencies(hdr, self.dep_table[t])

        return lst

    def getFiles(self, pkgId):
        mi = self.ts.dbMatch(rpm.RPMTAG_SHA1HEADER, pkgId)
        hdr = mi.next()

        dirs = hdr[rpm.RPMTAG_DIRNAMES]
        filenames = hdr[rpm.RPMTAG_BASENAMES]

        for i in range(0, len(dirs)):
            print "%s%s" % (dirs[i], filenames[i])

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

    def getPackageDetails(self, pkgId):
        mi = self.ts.dbMatch(rpm.RPMTAG_SHA1HEADER, pkgId)
        return self.hdr2class(mi.next())

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

            # If it's not a porvides or filename, we are done
            if prcotype != 'provides' or name[0] != '/':
                return result

            # FIXME: Search package files

        return result

    def searchProvides(self, name):
        return self.searchPrco(name, 'provides')

    def searchRequires(self, name):
        return self.searchPrco(name, 'requires')

    def seatchObsoletes(self, name):
        return self.searchPrco(name, 'obsoletes')

    def searchConflicts(self, name):
        return self.searchPrco(name, 'conflicts')

    def simplePkgList(self, repoid=None):
        return self.returnPackages()

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
        return self.mi2list(self.ts.dbMatch())

    def searchNevra(self, name=None, epoch=None, ver=None, rel=None, arch=None):
        mi = self.ts.dbMatch()
        if name:
            mi.pattern(rpm.RPMTAG_NAME, rpm.RPMMIRE_STRCMP, name)
        if epoch:
            mi.pattern(rpm.RPMTAG_EPOCH, rpm.RPMMIRE_STRCMP, epoch)
        if ver:
            mi.pattern(rpm.RPMTAG_VERSION, rpm.RPMMIRE_STRCMP, ver)
        if rel:
            mi.pattern(rpm.RPMTAG_RELEASE, rpm.RPMMIRE_STRCMP, rel)
        if arch:
            mi.pattern(rpm.RPMTAG_ARCH, rpm.RPMMIRE_STRCMP, arch)

        return self.mi2list(mi)

    def excludeArchs(self, archlist):
        for arch in archlist:
            mi = self.ts.dbMatch()
            mi.pattern(rpm.RPMTAG_ARCH, rpm.RPMMIRE_STRCMP, arch)
            for hdr in mi:
                self.delPackageById(hdr[rpm.RPMTAG_SHA1HEADER])



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

    def hdr2class(self, hdr, nevra_only=False):
        class tmpObject:
            pass
        y = tmpObject()
        y.nevra = (hdr[rpm.RPMTAG_NAME],
                   hdr[rpm.RPMTAG_EPOCH],
                   hdr[rpm.RPMTAG_VERSION],
                   hdr[rpm.RPMTAG_RELEASE],
                   hdr[rpm.RPMTAG_ARCH])
        y.sack = self
        y.pkgId = hdr[rpm.RPMTAG_SHA1HEADER]

        if nevra_only:
            return y

        y.hdrange = {'start'    : hdr[rpm.RPMTAG_],
                     'end'      : hdr[rpm.RPMTAG_]}
        y.location = {'href'    : hdr[rpm.RPMTAG_],
                      'value'   : '',
                      'base'    : hdr[rpm.RPMTAG_]}
        y.checksum = {'pkgid'   : 'YES',
                      'type'    : hdr[rpm.RPMTAG_],
                      'value'   : hdr[rpm.RPMTAG_]}
        y.time = {'build'       : hdr[rpm.RPMTAG_BUILDTIME],
                  'file'        : hdr[rpm.RPMTAG_]}
        y.size = {'package'     : hdr[rpm.RPMTAG_SIZE],
                  'archive'     : hdr[rpm.RPMTAG_ARCHIVESIZE],
                  'installed'   : hdr[rpm.RPMTAG_]}
        y.info = {'summary'     : hdr[rpm.RPMTAG_SUMMARY],
                  'description' : hdr[rpm.RPMTAG_DESCRIPTION],
                  'packager'    : hdr[rpm.RPMTAG_PACKAGER],
                  'group'       : hdr[rpm.RPMTAG_GROUP],
                  'buildhost'   : hdr[rpm.RPMTAG_BUILDHOST],
                  'sourcerpm'   : hdr[rpm.RPMTAG_SOURCERPM],
                  'url'         : hdr[rpm.RPMTAG_URL],
                  'vendor'      : hdr[rpm.RPMTAG_VENDOR],
                  'license'     : hdr[rpm.RPMTAG_LICENSE]}

        return y


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

def main():
    sack = RPMDBPackageSack()
    #pkgs = sack.returnPackages()
    pkgs = sack.searchNevra(name="kernel-default", rel='6')
    #pkgs = sack.returnNewestByNameArch(("kernel-default", "i586"))
    #pkgs = sack.returnNewestByName(("yum"))

    ## ret = sack.searchProvides("zmd")
    ## print ret
    ## ret = sack.searchRequires("zmd")
    ## print ret

    for p in pkgs:
        print p
        #sack.getFiles(p[0])
        #print sack.getChangelog(p[0])

if __name__ == '__main__':
    main()

