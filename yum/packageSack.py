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
# Copyright 2006 Duke University

"""
Classes for manipulating and querying groups of packages.
"""

from Errors import PackageSackError
import warnings
import re
import fnmatch
import misc
from packages import parsePackages
import rpmUtils.miscutils
from rpmUtils.miscutils import compareEVR

class PackageSackVersion:
    def __init__(self):
        self._num = 0
        self._chksum = misc.Checksums(['sha1'])

    def __str__(self):
        return "%u:%s" % (self._num, self._chksum.hexdigest())

    def __eq__(self, other):
        if other is None: return False
        if type(other) in (type(''), type(u'')):
            return str(self) == other
        if self._num != other._num: return False
        if self._chksum.digest() != other._chksum.digest(): return False
        return True
    def __ne__(self, other):
        return not (self == other)

    def update(self, pkg, csum):
        self._num += 1
        self._chksum.update(str(pkg))
        if csum is not None:
            self._chksum.update(csum[0])
            self._chksum.update(csum[1])


class PackageSackBase(object):
    """Base class that provides the interface for PackageSacks."""
    def __init__(self):
        self.added = {}

    def __len__(self):
        return len(self.returnPackages())
        
    def __iter__(self):
        ret = self.returnPackages()
        if hasattr(ret, '__iter__'):
            return ret.__iter__()
        else:
            return iter(ret)

    def __cmp__(self, other):
        if other is None:
            return 1

        s_repos = list(self.added)
        o_repos = list(other.added)
        if len(s_repos) != len(o_repos):
            return len(s_repos) - len(o_repos)
        for (s_repo, o_repo) in zip(sorted(s_repos), sorted(o_repos)):
            ret = cmp(s_repo, o_repo)
            if ret:
                return ret
        return 0

    def setCompatArchs(self, compatArchs):
        raise NotImplementedError()

    def populate(self, repo, mdtype, callback, cacheOnly):
        raise NotImplementedError()

    def packagesByTuple(self, pkgtup):
        """return a list of package objects by (n,a,e,v,r) tuple"""
        warnings.warn('packagesByTuple() will go away in a future version of Yum.\n',
                DeprecationWarning, stacklevel=2)
        
        return self.searchPkgTuple(pkgtup)
        
        
    def searchNevra(self, name=None, epoch=None, ver=None, rel=None, arch=None):
        """return list of pkgobjects matching the nevra requested"""
        raise NotImplementedError()

    def searchNames(self, names=[], return_pkgtups=False):
        raise NotImplementedError()

    def searchPO(self, po):
        """return list of package objects matching the name, epoch, ver, rel,
           arch of the package object passed in"""
           
        return self.searchNevra(name=po.name, epoch=po.epoch, ver=po.ver, 
                                rel=po.rel, arch=po.arch)
    
    def searchPkgTuple(self, pkgtup):
        """return list of pkgobject matching the (n,a,e,v,r) tuple"""
        (n,a,e,v,r) = pkgtup
        return self.searchNevra(name=n, arch=a, epoch=e, ver=v, rel=r)
        
    def contains(self, name=None, arch=None, epoch=None, ver=None, rel=None, po=None):
        """return if there are any packages in the sack that match the given NAEVR 
           or the NAEVR of the given po"""
        if po:
            name = po.name
            arch = po.arch
            epoch = po.epoch
            ver = po.version
            rel = po.release
        return bool(self.searchNevra(name=name, arch=arch, epoch=epoch, ver=ver, rel=rel))

    def getProvides(self, name, flags=None, version=(None, None, None)):
        """return dict { packages -> list of matching provides }"""
        raise NotImplementedError()

    def getRequires(self, name, flags=None, version=(None, None, None)):
        """return dict { packages -> list of matching requires }"""
        raise NotImplementedError()

    def searchRequires(self, name):
        """return list of package requiring the name (any evr and flag)"""
        raise NotImplementedError()

    def searchProvides(self, name):
        """return list of package providing the name (any evr and flag)"""
        raise NotImplementedError()

    def searchConflicts(self, name):
        """return list of package conflicting with the name (any evr and flag)"""
        raise NotImplementedError()

    def searchObsoletes(self, name):
        """return list of package obsoleting the name (any evr and flag)"""
        raise NotImplementedError()

    def returnObsoletes(self, newest=False):
        """returns a dict of obsoletes dict[obsoleting pkgtuple] = [list of obs]"""
        raise NotImplementedError()

    def have_fastReturnFileEntries(self):
        """ Is calling pkg.returnFileEntries(primary_only=True) faster than
            using searchFiles(). """
        raise NotImplementedError()

    def searchFiles(self, name):
        """return list of packages by filename"""
        raise NotImplementedError()

    def addPackage(self, obj):
        """add a pkgobject to the packageSack"""
        raise NotImplementedError()

    def buildIndexes(self):
        """builds the useful indexes for searching/querying the packageSack
           This should be called after all the necessary packages have been
           added/deleted"""
        raise NotImplementedError()

    def delPackage(self, obj):
        """delete a pkgobject"""
        raise NotImplementedError()

    def returnPackages(self, repoid=None, patterns=None, ignore_case=False):
        """return list of all packages"""
        raise NotImplementedError()

    def addPackageExcluder(self, repoid, excluderid, excluder, *args):
        """ Add an "excluder" for all packages in the repo/sack. Can basically
            do anything based on nevra, changes lots of exclude decisions from
            "preload package; test; delPackage" into "load excluder".
            Excluderid is used so the caller doesn't have to track
            "have I loaded the excluder for this repo.", it's probably only
            useful when repoid is None ... if it turns out utterly worthless
            then it's still not a huge wart. """
        raise NotImplementedError()

    def simpleVersion(self, main_only=False, groups={}):
        """ Return a simple version for all available packages. """
        def _up_revs(arepos, repoid, rev, pkg, csum):
            arevs = arepos.setdefault(repoid, {})
            rpsv = arevs.setdefault(None, PackageSackVersion())
            rpsv.update(pkg, csum)
            if rev is not None:
                rpsv = arevs.setdefault(rev, PackageSackVersion())
                rpsv.update(pkg, csum)

        main = PackageSackVersion()
        arepos = {}
        main_grps = {}
        arepos_grps = {}
        for pkg in sorted(self.returnPackages()):
            csum = pkg.returnIdSum()
            main.update(pkg, csum)

            for group in groups:
                if pkg.name in groups[group]:
                    if group not in main_grps:
                        main_grps[group] = PackageSackVersion()
                        arepos_grps[group] = {}
                    main_grps[group].update(pkg, csum)

            if main_only:
                continue

            rev = pkg.repo.repoXML.revision
            _up_revs(arepos, pkg.repoid, rev, pkg, csum)
            for group in groups:
                if pkg.name in groups[group]:
                    _up_revs(arepos_grps[group], pkg.repoid, rev, pkg, csum)

        if groups:
            return [main, arepos, main_grps, arepos_grps]
        return [main, arepos]

    def returnNewestByNameArch(self, naTup=None,
                               patterns=None, ignore_case=False):
        """return list of newest packages based on name, arch matching
           this means(in name.arch form): foo.i386 and foo.noarch are not
           compared to each other for highest version only foo.i386 and
           foo.i386 will be compared
           Note that given: foo-1.i386; foo-2.i386 and foo-3.x86_64
           The last _two_ pkgs will be returned, not just one of them. """
        raise NotImplementedError()

    def returnNewestByName(self, name=None, patterns=None, ignore_case=False):
        """return list of newest packages based on name matching
           this means(in name.arch form): foo.i386 and foo.noarch will
           be compared to each other for highest version."""
        raise NotImplementedError()

    def simplePkgList(self, patterns=None, ignore_case=False):
        """returns a list of pkg tuples (n, a, e, v, r)"""
        raise NotImplementedError()

    def printPackages(self):
        raise NotImplementedError()

    def excludeArchs(self, archlist):
        """exclude incompatible arches. archlist is a list of compatible arches"""
        raise NotImplementedError()

    def searchPackages(self, fields, criteria_re, callback):
        raise NotImplementedError()

    def searchAll(self, arg, query_type):
        raise NotImplementedError()
    
    def matchPackageNames(self, pkgspecs):
        """take a list strings and match the packages in the sack against it
           this will match against:
           name
           name.arch
           name-ver-rel.arch
           name-ver
           name-ver-rel
           epoch:name-ver-rel.arch
           name-epoch:ver-rel.arch
           
           return [exact matches], [glob matches], [unmatch search terms]
           """
        # Setup match() for the search we're doing
        matched = []
        exactmatch = []
        unmatched = set(pkgspecs)

        specs = {}
        for p in pkgspecs:
            if misc.re_glob(p):
                restring = fnmatch.translate(p)
                specs[p] = re.compile(restring)
            else:
                specs[p] = p

        #  We don't use simplePkgList() here because that loads all of the
        # rpmdb, if we are Eg. doing a "remove PackageKit".
        pkgs = self.returnPackages(patterns=unmatched)
        for pkgtup in [pkg.pkgtup for pkg in pkgs]:
            (n,a,e,v,r) = pkgtup
            names = set((
                n, 
                '%s.%s' % (n, a),
                '%s-%s-%s.%s' % (n, v, r, a),
                '%s-%s' % (n, v),
                '%s-%s-%s' % (n, v, r),
                '%s:%s-%s-%s.%s' % (e, n, v, r, a),
                '%s-%s:%s-%s.%s' % (n, e, v, r, a),
                ))
                
            for (term,query) in specs.items():
                if term == query:
                    if query in names:
                        exactmatch.append(self.searchPkgTuple(pkgtup)[0])
                        unmatched.discard(term)
                else:
                    for n in names:
                        if query.match(n):
                            matched.append(self.searchPkgTuple(pkgtup)[0])
                            unmatched.discard(term)
        return misc.unique(exactmatch), misc.unique(matched), list(unmatched)

    def returnLeafNodes(self, repoid=None):
        """returns a list of package objects that are not required by
           any other package in this repository"""
           
        def _return_all_provides(po):
            """ Return all the provides, via. yield. """
            # These are done one by one, so that we get lazy loading
            for prov in po.provides_names:
                yield prov
            for prov in po.filelist:
                yield prov
            for prov in po.dirlist:
                yield prov
            for prov in po.ghostlist:
                yield prov

        # fixme - maybe cache this list?
        
        req = {}
        orphans = []

        # prebuild the req dict    
        for po in self.returnPackages(repoid=repoid):
            if not po.requires_names:
                continue
            for r in po.requires_names:
                if r not in req:
                    req[r] = set()
                if len(req[r]) > 1: #  We only need to know if another pkg.
                    continue        # reqs. the provide. So 2 pkgs. is enough.
                req[r].add(po.name)
     
        for po in self.returnPackages(repoid=repoid):
            preq = 0
            for p in _return_all_provides(po):
                if p in req:
                    #  If this pkg provides something that is required by
                    # anything but itself (or another version of itself) it
                    # isn't an orphan.
                    if len(req[p]) > 1 or po.name not in req[p]:
                        preq += 1
                        break
        
            if preq == 0:
                orphans.append(po)
        
        return orphans

class MetaSack(PackageSackBase):
    """Represents the aggregate of multiple package sacks, such that they can
       all be treated as one unified sack."""

    def __init__(self):
        PackageSackBase.__init__(self)
        self.sacks = {}
        self.compatarchs = None

    def __len__(self):
        ret = 0
        for sack in sorted(self.sacks.values()):
            ret += len(sack)
        return ret

    def dropCachedData(self):
        for sack in self.sacks.values():
            if hasattr(sack, 'dropCachedData'):
                sack.dropCachedData()

    def addSack(self, repoid, sack):
        """Adds a repository's packageSack to this MetaSack."""
        self.sacks[repoid] = sack

        # Make sure the new sack follows the same rules we have been given.
        sack.setCompatArchs(self.compatarchs)

    def populate(self, repo, mdtype, callback, cacheOnly):
        self.sacks[repo.id].populate(repo, mdtype, callback, cacheOnly)

    def setCompatArchs(self, compatArchs):
        for sack in self.sacks.values():
            sack.setCompatArchs(compatArchs)

    def packagesByTuple(self, pkgtup):
        """return a list of package objects by (n,a,e,v,r) tuple"""
        warnings.warn('packagesByTuple() will go away in a future version of Yum.\n',
                DeprecationWarning, stacklevel=2)
        return self._computeAggregateListResult("packagesByTuple", pkgtup)

    def searchNevra(self, name=None, epoch=None, ver=None, rel=None, arch=None):
        """return list of pkgobjects matching the nevra requested"""
        return self._computeAggregateListResult("searchNevra", name, epoch, ver, rel, arch)

    def searchNames(self, names=[], return_pkgtups=False):
        return self._computeAggregateListResult("searchNames", names, return_pkgtups)

    def getProvides(self, name, flags=None, version=(None, None, None)):
        """return dict { packages -> list of matching provides }"""
        return self._computeAggregateDictResult("getProvides", name, flags, version)

    def getRequires(self, name, flags=None, version=(None, None, None)):
        """return dict { packages -> list of matching requires }"""
        return self._computeAggregateDictResult("getRequires", name, flags, version)

    def searchRequires(self, name):
        """return list of package requiring the name (any evr and flag)"""
        return self._computeAggregateListResult("searchRequires", name)

    def searchProvides(self, name):
        """return list of package providing the name (any evr and flag)"""
        return self._computeAggregateListResult("searchProvides", name)

    def searchConflicts(self, name):
        """return list of package conflicting with the name (any evr and flag)"""
        return self._computeAggregateListResult("searchConflicts", name)

    def searchObsoletes(self, name):
        """return list of package obsoleting the name (any evr and flag)"""
        return self._computeAggregateListResult("searchObsoletes", name)

    def returnObsoletes(self, newest=False):
        """returns a dict of obsoletes dict[obsoleting pkgtuple] = [list of obs]"""
        if not newest:
            return self._computeAggregateDictResult("returnObsoletes")
        
        obsdict = self._computeAggregateDictResult("returnObsoletes")

        names = set((obstup[0] for obstup in obsdict))
        nobsdict = {}
        last_name = ''
        last_pkg = None
        #  It takes about 0.2 of a second to convert these into packages, just
        # so we can sort them, which is ~40% of this functions time. So we sort
        # the pkgtups "by hand".
        def _pkgtup_nevr_cmp(x, y):
            """ Compare two pkgtup's (ignore arch): n, a, e, v, r. """
            ret = cmp(x[0], y[0])
            if ret: return ret
            # This is negated so we get higher versions first, in the list.
            return -compareEVR((x[2], x[3], x[4]), (y[2], y[3], y[4]))
        def _pkgtup_nevr_eq(x, y):
            return _pkgtup_nevr_cmp(x, y) == 0
        for pkgtup in sorted(self.searchNames(names, return_pkgtups=True),
                             cmp=_pkgtup_nevr_cmp):
            name = pkgtup[0]
            if last_name == name and not _pkgtup_nevr_eq(last_pkgtup, pkgtup):
                continue
            last_name = name
            last_pkgtup = pkgtup
            if pkgtup in obsdict:
                nobsdict[pkgtup] = obsdict[pkgtup]
        return nobsdict
        
    def searchFiles(self, name):
        """return list of packages by filename"""
        return self._computeAggregateListResult("searchFiles", name)

    def addPackage(self, obj):
        """Add a pkgobject to the packageSack.  This is a meaningless operation
           for the MetaSack."""
        pass

    def buildIndexes(self):
        """builds the useful indexes for searching/querying the packageSack
           This should be called after all the necessary packages have been
           added/deleted"""
        for sack in self.sacks.values():
            sack.buildIndexes()

    def delPackage(self, obj):
        """Delete a pkgobject if it exists in every sub-sack."""
        obj.repo.sack.delPackage(obj)


    def returnPackages(self, repoid=None, patterns=None, ignore_case=False):
        """Returns a list of packages. Note that the packages are
           always filtered to those matching the patterns/case. An optional
           repoid allows you to easily get data for a specific repo. """
        if not repoid:
            return self._computeAggregateListResult("returnPackages",
                                                    None, patterns, ignore_case)
        return self.sacks[repoid].returnPackages(patterns=patterns,
                                                 ignore_case=ignore_case)

    def addPackageExcluder(self, repoid, excluderid, excluder, *args):
        """ Add an "excluder" for all packages in the repo/sack. Can basically
            do anything based on nevra, changes lots of exclude decisions from
            "preload package; test; delPackage" into "load excluder".
            Excluderid is used so the caller doesn't have to track
            "have I loaded the excluder for this repo.", it's probably only
            useful when repoid is None ... if it turns out utterly worthless
            then it's still not a huge wart. """
        if not repoid:
            calr = self._computeAggregateListResult
            return calr("addPackageExcluder", None, excluderid, excluder, *args)
        return self.sacks[repoid].addPackageExcluder(None,
                                                     excluderid,excluder, *args)

    def returnNewestByNameArch(self, naTup=None,
                               patterns=None, ignore_case=False):
        """return list of newest packages based on name, arch matching
           this means(in name.arch form): foo.i386 and foo.noarch are not
           compared to each other for highest version only foo.i386 and
           foo.i386 will be compared.
           Note that given: foo-1.i386; foo-2.i386 and foo-3.x86_64
           The last _two_ pkgs will be returned, not just one of them. """
        calr = self._computeAggregateListResult
        pkgs = calr("returnNewestByNameArch", naTup, patterns, ignore_case)
        pkgs = packagesNewestByNameArch(pkgs)
        if not pkgs and (naTup or patterns):
            ui_pats = ", ".join(patterns or [])
            raise PackageSackError, 'No Package Matching %s' % ui_pats
        return pkgs
                
    def returnNewestByName(self, name=None, patterns=None, ignore_case=False):
        """return list of newest packages based on name matching
           this means(in name.arch form): foo.i386 and foo.noarch will
           be compared to each other for highest version."""
        pkgs = self._computeAggregateListResult("returnNewestByName", name,
                                                patterns, ignore_case)
        pkgs = packagesNewestByName(pkgs)
        if not pkgs and (name or patterns):
            if name:
                ui_pats = name
            else:
                ui_pats = ", ".join(patterns or [])
            raise PackageSackError, 'No Package Matching %s' % ui_pats
        return pkgs
        
    def simplePkgList(self, patterns=None, ignore_case=False):
        """returns a list of pkg tuples (n, a, e, v, r)"""
        return self._computeAggregateListResult("simplePkgList",
                                                patterns, ignore_case)

    def printPackages(self):
        for sack in self.sacks.values():
            sack.printPackages()

    def excludeArchs(self, archlist):
        """exclude incompatible arches. archlist is a list of compatible arches"""
        for sack in self.sacks.values():
            sack.excludeArchs(archlist)

    def searchPackages(self, fields, criteria_re, callback):
        return self._computeAggregateDictResult("searchPackages", fields, criteria_re, callback)

    def searchAll(self, arg, query_type):
        return self._computeAggregateListResult("searchAll", arg, query_type)

    def matchPackageNames(self, pkgspecs):
        matched = []
        exactmatch = []
        unmatched = None
        for sack in self.sacks.values():
            if hasattr(sack, "matchPackageNames"):
                e, m, u = [], [], []
                try:
                    e, m, u = sack.matchPackageNames(pkgspecs)
                except PackageSackError:
                    continue

                exactmatch.extend(e)
                matched.extend(m)
                if unmatched is None:
                    unmatched = set(u)
                else:
                    unmatched = unmatched.intersection(set(u))

        matched = misc.unique(matched)
        exactmatch = misc.unique(exactmatch)
        if unmatched is None:
            unmatched = []
        else:
            unmatched = list(unmatched)
        return exactmatch, matched, unmatched

    def _computeAggregateListResult(self, methodName, *args):
        result = []
        for sack in sorted(self.sacks.values()):
            if hasattr(sack, methodName):
                method = getattr(sack, methodName)
                try:
                    sackResult = apply(method, args)
                except PackageSackError:
                    continue

                if sackResult:
                    result.extend(sackResult)

        return result

    def _computeAggregateDictResult(self, methodName, *args):
        result = {}
        for sack in sorted(self.sacks.values()):
            if hasattr(sack, methodName):
                method = getattr(sack, methodName)
                try:
                    sackResult = apply(method, args)
                except PackageSackError:
                    continue

                if sackResult:
                    result.update(sackResult)
        return result



class PackageSack(PackageSackBase):
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
        ret = 0
        for repo in self.pkgsByRepo:
            ret += len(self.pkgsByRepo[repo])
        return ret
    

    def _checkIndexes(self, failure='error'):
        """check to see if the indexes are built, if not do what failure demands
           either error out or build the indexes, default is to error out"""
           
        if not self.indexesBuilt:
            if failure == 'error':
                raise PackageSackError, 'Indexes not yet built, cannot search'
            elif failure == 'build':
                self.buildIndexes()

    def dropCachedData(self):
        """ Do nothing, mainly for the testing code. """
        self.clearIndexes()

    def setCompatArchs(self, compatarchs):
        self.compatarchs = compatarchs

    def searchNevra(self, name=None, epoch=None, ver=None, rel=None, arch=None):
        """return list of pkgobjects matching the nevra requested"""
        self._checkIndexes(failure='build')
        if (name, epoch, ver, rel, arch) in self.nevra:
            return self.nevra[(name, epoch, ver, rel, arch)]
        elif name is not None:
            pkgs = self.nevra.get((name, None, None, None, None), [])
        else: 
            pkgs = []
            for pkgsbyRepo in self.pkgsByRepo.itervalues():
                pkgs.extend(pkgsbyRepo)

        result = [ ]
        for po in pkgs:
            if ((name and name!=po.name) or
                (epoch and epoch!=po.epoch) or
                (ver and ver!=po.ver) or
                (rel and rel!=po.rel) or
                (arch and arch!=po.arch)):
                continue
            result.append(po)
        return result
        
    def searchNames(self, names=[], return_pkgtups=False):
        """return list of pkgobjects matching the names requested"""
        self._checkIndexes(failure='build')
        result = []
        done = set()
        for name in names:
            if name in done:
                continue
            done.add(name)
            result.extend(self.nevra.get((name, None, None, None, None), []))
        if return_pkgtups:
            return [pkg.pkgtup for pkg in result]
        return result

    def getProvides(self, name, flags=None, version=(None, None, None)):
        """return dict { packages -> list of matching provides }"""
        self._checkIndexes(failure='build')
        if version is None:
            version = (None, None, None)
        elif type(version) in (str, type(None), unicode):
            version = rpmUtils.miscutils.stringToVersion(version)
        result = { }
        for po in self.provides.get(name, []):
            hits = po.matchingPrcos('provides', (name, flags, version))
            if hits:
                result[po] = hits
        if name[0] == '/':
            hit = (name, None, (None, None, None))
            for po in self.searchFiles(name):
                result.setdefault(po, []).append(hit)
        return result

    def getRequires(self, name, flags=None, version=(None, None, None)):
        """return dict { packages -> list of matching requires }"""
        self._checkIndexes(failure='build')
        if version is None:
            version = (None, None, None)
        elif type(version) in (str, type(None), unicode):
            version = rpmUtils.miscutils.stringToVersion(version)
        result = { }
        for po in self.requires.get(name, []):
            hits = po.matchingPrcos('requires', (name, flags, version))
            if hits:
                result[po] = hits
        return result

    def searchPrco(self, name, prcotype):
        self._checkIndexes(failure='build')
        prcodict = getattr(self, prcotype)
        (n,f,(e,v,r)) = misc.string_to_prco_tuple(name)
        
        basic_results = []
        results = []
        if n in prcodict:
            basic_results.extend(prcodict[n])

        for po in basic_results:
            if po.checkPrco(prcotype, (n, f, (e,v,r))):
                results.append(po)

        if prcotype != "provides":
            return results
            
        if not misc.re_filename(n):
            return results

        results.extend(self.searchFiles(n))
        return misc.unique(results)

            
    def searchRequires(self, name):
        """return list of package requiring the item requested"""

        return self.searchPrco(name, 'requires')

    def searchProvides(self, name):
        """return list of package providing the item requested"""
        
        return self.searchPrco(name, 'provides')

    def searchConflicts(self, name):
        """return list of package conflicting with item requested"""
        
        return self.searchPrco(name, 'conflicts')
        
    def searchObsoletes(self, name):
        """return list of package obsoleting the item requested"""

        return self.searchPrco(name, 'obsoletes')
        
    def returnObsoletes(self, newest=False):
        """returns a dict of obsoletes dict[obsoleting pkgtuple] = [list of obs]"""
        obs = {}
        for po in self.returnPackages():
            if len(po.obsoletes) == 0:
                continue
            obs.setdefault(po.pkgtup, []).extend(po.obsoletes)

        if not newest:
            return obs

        # FIXME - this is slooooooooooooooooooooooooooooooow
        # get the dict back
        newest_tups = set((pkg.pkgtup for pkg in self.returnNewestByName()))

        # go through each of the keys of the obs dict and see if it is in the
        # sack of newest pkgs - if it is not - remove the entry
        togo = []
        for obstup in obs:
            if obstup not in newest_tups:
                togo.append(obstup)
        for obstup in togo:
            del obs[obstup]
            
        return obs
        
    def have_fastReturnFileEntries(self):
        """ Is calling pkg.returnFileEntries(primary_only=True) faster than
            using searchFiles(). """
        return True

    def searchFiles(self, name):
        """ Return list of packages by filename. """
        self._checkIndexes(failure='build')
        if name in self.filenames:
            return self.filenames[name]
        else:
            return []

    def _addToDictAsList(self, dict, key, data):
        if key not in dict:
            dict[key] = []
        #if data not in dict[key]: - if I enable this the whole world grinds to a halt
        # need a faster way of looking for the object in any particular list
        dict[key].append(data)

    def _delFromListOfDict(self, dict, key, data):
        if key not in dict:
            return
        try:
            dict[key].remove(data)
        except ValueError:
            pass
            
        if len(dict[key]) == 0: # if it's an empty list of the dict, then kill it
            del dict[key]
            
            
    def addPackage(self, obj):
        """add a pkgobject to the packageSack"""

        repoid = obj.repoid
        (name, arch, epoch, ver, rel) = obj.pkgtup
        
        if not self.compatarchs or arch in self.compatarchs:
            self._addToDictAsList(self.pkgsByRepo, repoid, obj)
        if self.indexesBuilt:
            self._addPackageToIndex(obj)

    def buildIndexes(self):
        """builds the useful indexes for searching/querying the packageSack
           This should be called after all the necessary packages have been 
           added/deleted"""

        self.clearIndexes()
        
        for repoid in self.pkgsByRepo:
            for obj in self.pkgsByRepo[repoid]:
                self._addPackageToIndex(obj)
        self.indexesBuilt = 1


    def clearIndexes(self):
        # blank out the indexes
        self.obsoletes = {}
        self.requires = {}
        self.provides = {}
        self.conflicts = {}
        self.filenames = {}
        self.nevra = {}
        self.pkgsByID = {}

        self.indexesBuilt = 0
        
    def _addPackageToIndex(self, obj):
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
        self._addToDictAsList(self.pkgsByID, obj.id, obj)
        (name, arch, epoch, ver, rel) = obj.pkgtup
        self._addToDictAsList(self.nevra, (name, epoch, ver, rel, arch), obj)
        self._addToDictAsList(self.nevra, (name, None, None, None, None), obj)

    def _delPackageFromIndex(self, obj):
        for (n, fl, (e,v,r)) in obj.returnPrco('obsoletes'):
            self._delFromListOfDict(self.obsoletes, n, obj)
        for (n, fl, (e,v,r)) in obj.returnPrco('requires'):
            self._delFromListOfDict(self.requires, n, obj)
        for (n, fl, (e,v,r)) in obj.returnPrco('provides'):
            self._delFromListOfDict(self.provides, n, obj)
        for (n, fl, (e,v,r)) in obj.returnPrco('conflicts'):
            self._delFromListOfDict(self.conflicts, n, obj)
        for ftype in obj.returnFileTypes():
            for file in obj.returnFileEntries(ftype):
                self._delFromListOfDict(self.filenames, file, obj)
        self._delFromListOfDict(self.pkgsByID, obj.id, obj)
        (name, arch, epoch, ver, rel) = obj.pkgtup
        self._delFromListOfDict(self.nevra, (name, epoch, ver, rel, arch), obj)
        self._delFromListOfDict(self.nevra, (name, None, None, None, None), obj)
        
    def delPackage(self, obj):
        """delete a pkgobject"""
        self._delFromListOfDict(self.pkgsByRepo, obj.repoid, obj)
        if self.indexesBuilt: 
            self._delPackageFromIndex(obj)
        
    def returnPackages(self, repoid=None, patterns=None, ignore_case=False):
        """return list of all packages, takes optional repoid"""
        returnList = []
        if repoid is None:
            for repo in self.pkgsByRepo:
                returnList.extend(self.pkgsByRepo[repo])
        else:
            try:
                returnList = self.pkgsByRepo[repoid]
            except KeyError:
                # nothing to return
                pass
        
        if patterns:
            returnList = parsePackages(returnList, patterns, not ignore_case,
                                       unique='repo-pkgkey')
            returnList = returnList[0] + returnList[1]
        return returnList

    def returnNewestByNameArch(self, naTup=None,
                               patterns=None, ignore_case=False):
        """return list of newest packages based on name, arch matching
           this means(in name.arch form): foo.i386 and foo.noarch are not 
           compared to each other for highest version only foo.i386 and 
           foo.i386 will be compared
           Note that given: foo-1.i386; foo-2.i386 and foo-3.x86_64
           The last _two_ pkgs will be returned, not just one of them. """

        highdict = {}
        # If naTup is set, only iterate through packages that match that
        # name
        if (naTup):
            self._checkIndexes(failure='build')
            where = self.nevra.get((naTup[0],None,None,None,None))
            if (not where):
                raise PackageSackError, 'No Package Matching %s.%s' % naTup
        else:
            where = self.returnPackages(patterns=patterns,
                                        ignore_case=ignore_case)

        for pkg in where:
            if (pkg.name, pkg.arch) not in highdict:
                highdict[(pkg.name, pkg.arch)] = pkg
            else:
                pkg2 = highdict[(pkg.name, pkg.arch)]
                if pkg.verGT(pkg2):
                    highdict[(pkg.name, pkg.arch)] = pkg
        
        if naTup:
            if naTup in highdict:
                return [highdict[naTup]]
            else:
                raise PackageSackError, 'No Package Matching %s.%s' % naTup
        
        return highdict.values()
        
    def returnNewestByName(self, name=None, patterns=None, ignore_case=False):
        """return list of newest packages based on name matching
           this means(in name.arch form): foo.i386 and foo.noarch will
           be compared to each other for highest version."""

        highdict = {}
        if patterns is None and name is not None:
            pkgs = self.searchNevra(name=name)
        else:
            pkgs = self.returnPackages(patterns=patterns,
                                       ignore_case=ignore_case)

        for pkg in pkgs:
            if pkg.name not in highdict:
                highdict[pkg.name] = [pkg]
            else:
                pkg2 = highdict[pkg.name][0]
                if pkg.verGT(pkg2):
                    highdict[pkg.name] = [pkg]
                if pkg.verEQ(pkg2):
                    highdict[pkg.name].append(pkg)
                
        if name:
            if name in highdict:
                return highdict[name]
            else:
                raise PackageSackError, 'No Package Matching  %s' % name
        
        #this is a list of lists - break it back out into a single list
        returnlist = []
        for polst in highdict.values():
            for po in polst:
                returnlist.append(po)

        return returnlist
           
    def simplePkgList(self, patterns=None, ignore_case=False):
        """returns a list of pkg tuples (n, a, e, v, r) optionally from a single repoid"""
        
        # Don't cache due to excludes
        return [pkg.pkgtup for pkg in self.returnPackages(patterns=patterns,
                                                          ignore_case=False)]
                       
    def printPackages(self):
        for pkg in self.returnPackages():
            print pkg

    def excludeArchs(self, archlist):
        """exclude incompatible arches. archlist is a list of compatible arches"""
        
        for pkg in self.returnPackages():
            if pkg.arch not in archlist:
                self.delPackage(pkg)

    def searchPackages(self, fields, criteria_re, callback):
        matches = {}

        for po in self.returnPackages():
            tmpvalues = []
            for field in fields:
                value = getattr(po, field)
                if value and criteria_re.search(value):
                    tmpvalues.append(value)
            if len(tmpvalues) > 0:
                if callback:
                    callback(po, tmpvalues)
                matches[po] = tmpvalues
 
        return matches

def packagesNewestByName(pkgs):
    """ Does the same as PackageSack.returnNewestByName().
        Note that given: foo-1.i386; foo-2.i386 and foo-3.x86_64"""
    newest = {}
    for pkg in pkgs:
        key = pkg.name

        # Can't use pkg.__cmp__ because it takes .arch into account
        cval = 1
        if key in newest:
            cval = pkg.verCMP(newest[key][0])
        if cval > 0:
            newest[key] = [pkg]
        elif cval == 0:
            newest[key].append(pkg)
    ret = []
    for vals in newest.itervalues():
        ret.extend(vals)
    return ret
def packagesNewestByNameArch(pkgs):
    """ Does the same as PackageSack.returnNewestByNameArch()
        The last _two_ pkgs will be returned, not just one of them."""
    newest = {}
    for pkg in pkgs:
        key = (pkg.name, pkg.arch)
        if key in newest and pkg.verLE(newest[key]):
            continue
        newest[key] = pkg
    return newest.values()

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
    
