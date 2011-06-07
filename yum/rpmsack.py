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
import glob
import os
import os.path

from rpmUtils import miscutils
from rpmUtils import arch
from rpmUtils.transaction import initReadOnlyTransaction
import misc
import Errors
from packages import YumInstalledPackage, parsePackages
from packageSack import PackageSackBase, PackageSackVersion

# For returnPackages(patterns=)
import fnmatch
import re

from yum.i18n import to_unicode, _
import constants

import yum.depsolve

def _open_no_umask(*args):
    """ Annoying people like to set umask's for root, which screws everything
        up for user readable stuff. """
    oumask = os.umask(022)
    try:
        ret = open(*args)
    finally:
        os.umask(oumask)

    return ret

def _iopen(*args):
    """ IOError wrapper BS for open, stupid exceptions. """
    try:
        ret = open(*args)
    except IOError, e:
        return None, e
    return ret, None


class RPMInstalledPackage(YumInstalledPackage):

    def __init__(self, rpmhdr, index, rpmdb):
        self._has_hdr = True
        YumInstalledPackage.__init__(self, rpmhdr, yumdb=rpmdb.yumdb)

        self.idx   = index
        self.rpmdb = rpmdb

        self._has_hdr = False
        del self.hdr

    def _get_hdr(self):
        # Note that we can't use hasattr(self, 'hdr') or we'll recurse
        if self._has_hdr:
            return self.hdr

        ts = self.rpmdb.readOnlyTS()
        mi = ts.dbMatch(0, self.idx)
        try:
            return mi.next()
        except StopIteration:
            raise Errors.PackageSackError, 'Rpmdb changed underneath us'

    def __getattr__(self, varname):
        # If these existed, then we wouldn't get here...
        # Prevent access of __foo__, _cached_foo etc from loading the header 
        if varname.startswith('_'):
            raise AttributeError, "%s has no attribute %s" % (self, varname)

        if varname != 'hdr': # Don't cache the hdr, unless explicitly requested
            #  Note that we don't even cache the .blah value, but looking up the
            # header is _really_ fast so it's not obvious any of it is worth it.
            # This is different to prco etc. data, which is loaded separately.
            val = self._get_hdr()
        else:
            self.hdr = val = self._get_hdr()
            self._has_hdr = True
        if varname != 'hdr':   #  This is unusual, for anything that happens
            val = val[varname] # a lot we should preload at __init__.
                               # Also note that pkg.no_value raises KeyError.

        return val
    
    def requiring_packages(self):
        """return list of installed pkgs requiring this package"""
        pkgset = set()
        for (reqn, reqf, reqevr) in self.provides:
            for pkg in self.rpmdb.getRequires(reqn,reqf,reqevr):
                if pkg != self:
                    pkgset.add(pkg)
                
        for fn in self.filelist + self.dirlist:
            for pkg in self.rpmdb.getRequires(fn, None, (None, None, None)):
                if pkg != self:
                    pkgset.add(pkg)
                
        return list(pkgset)
        

    def required_packages(self):
        pkgset = set()
        for (reqn, reqf, reqevr) in self.requires:
            for pkg in self.rpmdb.getProvides(reqn, reqf, reqevr):
                if pkg != self:
                    pkgset.add(pkg)
        
        return list(pkgset)
        
class RPMDBProblem:
    '''
    Represents a problem in the rpmdb, from the check_*() functions.
    '''
    def __init__(self, pkg, problem, **kwargs):
        self.pkg = pkg
        self.problem = problem
        for kwarg in kwargs:
            setattr(self, kwarg, kwargs[kwarg])

    def __cmp__(self, other):
        if other is None:
            return 1
        return cmp(self.pkg, other.pkg) or cmp(self.problem, other.problem)


class RPMDBProblemDependency(RPMDBProblem):
    def __str__(self):
        if self.problem == 'requires':
            return "%s %s %s" % (self.pkg, _('has missing requires of'),
                                 self.missing)

        return "%s %s %s: %s" % (self.pkg, _('has installed conflicts'),
                                 self.found,', '.join(map(str, self.conflicts)))


class RPMDBProblemDuplicate(RPMDBProblem):
    def __init__(self, pkg, **kwargs):
        RPMDBProblem.__init__(self, pkg, "duplicate", **kwargs)

    def __str__(self):
        return _("%s is a duplicate with %s") % (self.pkg, self.duplicate)


class RPMDBProblemObsoleted(RPMDBProblem):
    def __init__(self, pkg, **kwargs):
        RPMDBProblem.__init__(self, pkg, "obsoleted", **kwargs)

    def __str__(self):
        return _("%s is obsoleted by %s") % (self.pkg, self.obsoleter)


class RPMDBProblemProvides(RPMDBProblem):
    def __init__(self, pkg, **kwargs):
        RPMDBProblem.__init__(self, pkg, "provides", **kwargs)

    def __str__(self):
        return _("%s provides %s but it cannot be found") % (self.pkg,
                                                             self.provide)


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

    # Do we want to cache rpmdb data in a file, for later use?
    __cache_rpmdb__ = True

    def __init__(self, root='/', releasever=None, cachedir=None,
                 persistdir='/var/lib/yum'):
        self.root = root
        self._idx2pkg = {}
        self._name2pkg = {}
        self._pkgnames_loaded = set()
        self._tup2pkg = {}
        self._completely_loaded = False
        self._pkgname_fails = set()
        self._pkgmatch_fails = set()
        self._provmatch_fails = set()
        self._simple_pkgtup_list = []
        self._get_pro_cache = {}
        self._get_req_cache  = {}
        self._loaded_gpg_keys = False
        if cachedir is None:
            cachedir = persistdir + "/rpmdb-indexes"
        self.setCacheDir(cachedir)
        if not os.path.normpath(persistdir).startswith(self.root):
            self._persistdir = root +  '/' + persistdir
        else:
            self._persistdir = persistdir
        self._have_cached_rpmdbv_data = None
        self._cached_conflicts_data = None
        # Store the result of what happens, if a transaction completes.
        self._trans_cache_store = {}
        self.ts = None
        self.releasever = releasever
        self.auto_close = False # this forces a self.ts.close() after
                                     # most operations so it doesn't leave
                                     # any lingering locks.
        self._cached_rpmdb_mtime = None

        self._cache = {
            'provides' : { },
            'requires' : { },
            'conflicts' : { },
            'obsoletes' : { },
            }
        
        addldb_path = os.path.normpath(self._persistdir + '/yumdb')
        version_path = os.path.normpath(cachedir + '/version')
        self.yumdb = RPMDBAdditionalData(db_path=addldb_path,
                                         version_path=version_path)

    def _get_pkglist(self):
        '''Getter for the pkglist property. 
        Returns a list of package tuples.
        '''
        if not self._simple_pkgtup_list:
            csumpkgtups = self.preloadPackageChecksums(load_packages=False)
            if csumpkgtups is not None:
                self._simple_pkgtup_list = csumpkgtups.keys()

        if not self._simple_pkgtup_list:
            for (hdr, mi) in self._get_packages():
                self._simple_pkgtup_list.append(self._hdr2pkgTuple(hdr))
            
        return self._simple_pkgtup_list

    pkglist = property(_get_pkglist, None)

    def dropCachedData(self):
        """ Drop all cached data, this is a big perf. hit if we need to load
            the data back in again. Also note that if we ever call this while
            a transaction is ongoing we'll have multiple copies of packages
            which is _bad_. """
        self._idx2pkg = {}
        self._name2pkg = {}
        self._pkgnames_loaded = set()
        self._tup2pkg = {}
        self._completely_loaded = False
        self._pkgmatch_fails = set()
        self._pkgname_fails = set()
        self._provmatch_fails = set()
        self._simple_pkgtup_list = []
        self._get_pro_cache = {}
        self._get_req_cache = {}
        #  We can be called on python shutdown (due to yb.__del__), at which
        # point other modules might not be available.
        if misc is not None:
            misc.unshare_data()
        self._cache = {
            'provides' : { },
            'requires' : { },
            'conflicts' : { },
            'obsoletes' : { },
            }
        self._have_cached_rpmdbv_data = None
        self._cached_conflicts_data = None
        self.transactionReset() # Should do nothing, but meh...
        self._cached_rpmdb_mtime = None

    def dropCachedDataPostTransaction(self, txmbrs):
        """ Drop cached data that is assocciated with the given transaction,
            this tries to keep as much data as possible and even does a
            "preload" on the checksums. This should be called once, when a
            transaction is complete. """
        # -- Below -- self._idx2pkg = {}
        # -- Below -- self._name2pkg = {}
        # -- Below -- self._pkgnames_loaded = set()
        # -- Below -- self._tup2pkg = {}
        self._completely_loaded = False
        self._pkgmatch_fails = set()
        # -- Below -- self._pkgname_fails = set()
        self._provmatch_fails = set()
        self._simple_pkgtup_list = []
        self._get_pro_cache = {}
        self._get_req_cache = {}
        #  We can be called on python shutdown (due to yb.__del__), at which
        # point other modules might not be available.
        if misc is not None:
            misc.unshare_data()
        self._cache = {
            'provides' : { },
            'requires' : { },
            'conflicts' : { },
            'obsoletes' : { },
            }
        self._have_cached_rpmdbv_data = None
        self._cached_conflicts_data = None
        self.transactionReset() # Should do nothing, but meh...

        #  We are keeping some data from before, and sometimes (Eg. remove only)
        # we never open the rpmdb again ... so get the mtime now.
        rpmdbfname  = self.root + "/var/lib/rpm/Packages"
        self._cached_rpmdb_mtime = os.path.getmtime(rpmdbfname)

        def _safe_del(x, y):
            """ Make sure we never traceback here, because it screws our yumdb
                if we do. """
            # Maybe use x.pop(y, None) ?
            if y in x:
                del x[y]

        precache = []
        for txmbr in txmbrs:
            self._pkgnames_loaded.discard(txmbr.name)
            _safe_del(self._name2pkg, txmbr.name)

            if txmbr.output_state in constants.TS_INSTALL_STATES:
                self._pkgname_fails.discard(txmbr.name)
                precache.append(txmbr)
                if txmbr.reinstall:
                    #  For reinstall packages we have:
                    #
                    # 1. one txmbr: the new install.
                    # 2. two rpmdb entries: the new; the old;
                    #
                    # ...so we need to remove the old one, given only the new
                    # one.
                    ipo = self._tup2pkg[txmbr.pkgtup]
                    _safe_del(self._idx2pkg, ipo.idx)
                    _safe_del(self._tup2pkg, txmbr.pkgtup)

            if txmbr.output_state in constants.TS_REMOVE_STATES:
                _safe_del(self._idx2pkg, txmbr.po.idx)
                _safe_del(self._tup2pkg, txmbr.pkgtup)

        for txmbr in precache:
            (n, a, e, v, r) = txmbr.pkgtup
            pkg = self.searchNevra(n, e, v, r, a)
            if not pkg:
                # Wibble?
                self._deal_with_bad_rpmdbcache("dCDPT(pkg checksums)")
                continue

            pkg = pkg[0]
            csum = txmbr.po.returnIdSum()
            if csum is None:
                continue

            (T, D) = (str(csum[0]), str(csum[1]))
            if ('checksum_type' in pkg.yumdb_info._read_cached_data or
                'checksum_data' in pkg.yumdb_info._read_cached_data):
                continue
            pkg.yumdb_info._read_cached_data['checksum_type'] = T
            pkg.yumdb_info._read_cached_data['checksum_data'] = D

    def setCacheDir(self, cachedir):
        """ Sets the internal cachedir value for the rpmdb, to be the
            "rpmdb-indexes" directory in the persisent yum storage. """
        if not os.path.normpath(cachedir).startswith(self.root):
            self._cachedir = self.root + '/' + cachedir
        else:
            self._cachedir = '/' + cachedir

        if hasattr(self, 'yumdb'): # Need to keep this upto date, after init.
            version_path = os.path.normpath(self._cachedir + '/version')
            self.yumdb.conf.version_path = version_path

    def readOnlyTS(self):
        if not self.ts:
            self.ts =  initReadOnlyTransaction(root=self.root)
        if not self.ts.open:
            self.ts = initReadOnlyTransaction(root=self.root)
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
        result = {}

        # check provides
        tag = self.DEP_TABLE['provides'][0]
        mi = self._get_packages(patterns=[(tag, rpm.RPMMIRE_GLOB, name)])
        for hdr, idx in mi:
            pkg = self._makePackageObject(hdr, idx)
            result.setdefault(pkg.pkgid, pkg)

        fileresults = self.searchFiles(name)
        for pkg in fileresults:
            result.setdefault(pkg.pkgid, pkg)
        
        return result.values()

    def searchFiles(self, name):
        """search the filelists in the rpms for anything matching name"""

        result = {}
        
        name = os.path.normpath(name)
        # Note that globs can't be done. As of 4.8.1:
        #   mi.pattern('basenames', rpm.RPMMIRE_GLOB, name)
        # ...produces no results.

        for hdr, idx in self._get_packages('basenames', name):
            pkg = self._makePackageObject(hdr, idx)
            result.setdefault(pkg.pkgid, pkg)

        return result.values()
        
    def searchPrco(self, name, prcotype):

        result = self._cache[prcotype].get(name)
        if result is not None:
            return result
        (n,f,(e,v,r)) = misc.string_to_prco_tuple(name)
        glob = False
        
        if misc.re_glob(n):
            glob = True
            
        result = {}
        tag = self.DEP_TABLE[prcotype][0]
        for hdr, idx in self._get_packages(tag, misc.to_utf8(n)):
            po = self._makePackageObject(hdr, idx)
            if not glob:
                if po.checkPrco(prcotype, (n, f, (e,v,r))):
                    result[po.pkgid] = po
            else:
                result[po.pkgid] = po

        # If it's not a provides or filename, we are done
        if prcotype == 'provides' and name[0] == '/':
            fileresults = self.searchFiles(name)
            for pkg in fileresults:
                result[pkg.pkgid] = pkg
        
        result = result.values()
        self._cache[prcotype][name] = result

        return result

    def searchProvides(self, name):
        if name in self._provmatch_fails:
            return []
        ret = self.searchPrco(name, 'provides')
        if not ret:
            self._provmatch_fails.add(name)
        return ret

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

        allpkg = self._search(name=name, arch=arch)

        if not allpkg:
            raise Errors.PackageSackError, 'No Package Matching %s' % name

        return [ po.pkgtup for po in misc.newestInList(allpkg) ]

    def returnNewestByName(self, name=None):
        if not name:
            return

        allpkgs = self._search(name=name)

        if not allpkgs:
            raise Errors.PackageSackError, 'No Package Matching %s' % name

        return misc.newestInList(allpkgs)

    @staticmethod
    def _compile_patterns(patterns, ignore_case=False):
        if not patterns or len(patterns) > constants.PATTERNS_MAX:
            return None
        ret = []
        for pat in patterns:
            if not pat:
                continue

            qpat = pat[0]
            if qpat in ('?', '*', '['):
                qpat = None
            if ignore_case:
                if qpat is not None:
                    qpat = qpat.lower()
                ret.append((qpat, re.compile(fnmatch.translate(pat), re.I)))
            else:
                ret.append((qpat, re.compile(fnmatch.translate(pat))))
        return ret
    @staticmethod
    def _match_repattern(repatterns, hdr, ignore_case):
        """ This is basically parsePackages() but for rpm hdr objects. """
        if repatterns is None:
            return True

        for qpat, repat in repatterns:
            epoch = hdr['epoch']
            if epoch is None:
                epoch = '0'
            else:
                epoch = str(epoch)
            qname = hdr['name'][0]
            if ignore_case:
                qname = qname.lower()
            if qpat is not None and qpat != qname and qpat != epoch[0]:
                continue
            if repat.match(hdr['name']):
                return True
            if repat.match("%(name)s-%(version)s-%(release)s.%(arch)s" % hdr):
                return True
            if repat.match("%(name)s.%(arch)s" % hdr):
                return True
            if repat.match("%(name)s-%(version)s" % hdr):
                return True
            if repat.match("%(name)s-%(version)s-%(release)s" % hdr):
                return True
            if repat.match(epoch + ":%(name)s-%(version)s-%(release)s.%(arch)s"
                           % hdr):
                return True
            if repat.match("%(name)s-%(epoch)s:%(version)s-%(release)s.%(arch)s"
                           % hdr):
                return True
        return False

    def returnPackages(self, repoid=None, patterns=None, ignore_case=False):
        """Returns a list of packages. Note that the packages are
           always filtered to those matching the patterns/case. repoid is
           ignored, and is just here for compatibility with non-rpmdb sacks. """

        #  See if we can load the "patterns" via. dbMatch('name', ...) because
        # that's basically instant and walking the entire rpmdb isn't.
        #  We assume that if we get "Yum" and _something_ matches, that we have
        # _all_ the matches. IOW there can be either Yum or yum, but not BOTH.
        if not self._completely_loaded and patterns:
            ret = []
            for pat in patterns:
                #  We aren't wasting anything here, because the next bit
                # will pick up any loads :)
                pkgs = self.searchNames([pat])
                if not pkgs:
                    break
                ret.extend(pkgs)
            else:
                return ret

        ret = []
        if patterns and not ignore_case:
            tpats = []
            for pat in patterns:
                if pat in self._pkgmatch_fails:
                    continue
                if pat in self._pkgnames_loaded:
                    ret.extend(self._name2pkg[pat])
                    continue
                tpats.append(pat)
            patterns = tpats
            if not patterns:
                return ret

        if not self._completely_loaded:
            rpats = self._compile_patterns(patterns, ignore_case)
            for hdr, idx in self._get_packages():
                if self._match_repattern(rpats, hdr, ignore_case):
                    self._makePackageObject(hdr, idx)
            self._completely_loaded = patterns is None

        pkgobjlist = self._idx2pkg.values()
        # Remove gpg-pubkeys, as no sane callers expects/likes them...
        if self._loaded_gpg_keys:
            pkgobjlist = [pkg for pkg in pkgobjlist if pkg.name != 'gpg-pubkey']
        if patterns:
            pkgobjlist = parsePackages(pkgobjlist, patterns, not ignore_case)
            self._pkgmatch_fails.update(pkgobjlist[2])
            if ret:
                pkgobjlist = pkgobjlist[0] + pkgobjlist[1] + ret
            else:
                pkgobjlist = pkgobjlist[0] + pkgobjlist[1]
            for pkg in pkgobjlist:
                for pat in patterns:
                    if pkg.name == pat:
                        self._pkgnames_loaded.add(pkg.name)
        return pkgobjlist

    def _uncached_returnConflictPackages(self):
        """ Load the packages which have conflicts from the rpmdb, newer
            versions of rpm have an index here so this is as fast as
            cached (we test rpm version at cache write time). """

        if self._cached_conflicts_data is None:
            result = {}

            for hdr, idx in self._get_packages('conflictname'):
                if not hdr[rpm.RPMTAG_CONFLICTNAME]:
                    # Pre. rpm-4.9.x the above dbMatch() does nothing.
                    continue

                po = self._makePackageObject(hdr, idx)
                result[po.pkgid] = po
                if po._has_hdr:
                    continue # Unlikely, but, meh...

                po.hdr = hdr
                po._has_hdr = True
                po.conflicts
                po._has_hdr = False
                del po.hdr
            self._cached_conflicts_data = result.values()

        return self._cached_conflicts_data

    def _write_conflicts_new(self, pkgs, rpmdbv):
        if not os.access(self._cachedir, os.W_OK):
            return

        conflicts_fname = self._cachedir + '/conflicts'
        fo = _open_no_umask(conflicts_fname + '.tmp', 'w')
        fo.write("%s\n" % rpmdbv)
        fo.write("%u\n" % len(pkgs))
        for pkg in sorted(pkgs):
            for var in pkg.pkgtup:
                fo.write("%s\n" % var)
        fo.close()
        os.rename(conflicts_fname + '.tmp', conflicts_fname)

    def _write_conflicts(self, pkgs):
        rpmdbv = self.simpleVersion(main_only=True)[0]
        self._write_conflicts_new(pkgs, rpmdbv)

    def _deal_with_bad_rpmdbcache(self, caller):
        """ This shouldn't be called, but people are hitting weird stuff so
            we want to deal with it so it doesn't stay broken "forever". """
        misc.unlink_f(self._cachedir + "/version")
        misc.unlink_f(self._cachedir + '/conflicts')
        misc.unlink_f(self._cachedir + '/file-requires')
        misc.unlink_f(self._cachedir + '/pkgtups-checksums')
        #  We have a couple of options here, we can:
        #
        # . Ignore it and continue - least invasive, least likely to get any
        #   bugs fixed.
        #
        # . Ignore it and continue, when not in debug mode - Helps users doing
        #   weird things (and we won't know), but normal bugs will be seen by
        #   anyone not running directly from a package.
        #
        # . Always throw - but at least it shouldn't happen again.
        #
        if __debug__:
            raise Errors.PackageSackError, 'Rpmdb checksum is invalid: %s' % caller

    def _read_conflicts(self):
        if not self.__cache_rpmdb__:
            return None

        def _read_str(fo):
            return fo.readline()[:-1]

        conflict_fname = self._cachedir + '/conflicts'
        fo, e = _iopen(conflict_fname)
        if fo is None:
            return None
        frpmdbv = fo.readline()
        rpmdbv = self.simpleVersion(main_only=True)[0]
        if not frpmdbv or rpmdbv != frpmdbv[:-1]:
            return None

        ret = []
        try:
            # Read the conflicts...
            pkgtups_num = int(_read_str(fo))
            while pkgtups_num > 0:
                pkgtups_num -= 1

                # n, a, e, v, r
                pkgtup = (_read_str(fo), _read_str(fo),
                          _read_str(fo), _read_str(fo), _read_str(fo))
                int(pkgtup[2]) # Check epoch is valid
                ret.extend(self.searchPkgTuple(pkgtup))
            if fo.readline() != '': # Should be EOF
                return None
        except ValueError:
            self._deal_with_bad_rpmdbcache("conflicts")
            return None

        self._cached_conflicts_data = ret
        return self._cached_conflicts_data

    def transactionCacheConflictPackages(self, pkgs):
        if self.__cache_rpmdb__:
            self._trans_cache_store['conflicts'] = pkgs

    def returnConflictPackages(self):
        """ Return a list of packages that have conflicts. """
        pkgs = self._read_conflicts()
        if pkgs is None:
            pkgs = self._uncached_returnConflictPackages()
            if self.__cache_rpmdb__:
                self._write_conflicts(pkgs)

        return pkgs

    def transactionResultVersion(self, rpmdbv):
        """ We are going to do a transaction, and the parameter will be the
            rpmdb version when we finish. The idea being we can update all
            our rpmdb caches for that rpmdb version. """

        if not self.__cache_rpmdb__:
            self._trans_cache_store = {}
            return

        if 'conflicts' in self._trans_cache_store:
            pkgs = self._trans_cache_store['conflicts']
            self._write_conflicts_new(pkgs, rpmdbv)

        if 'file-requires' in self._trans_cache_store:
            data = self._trans_cache_store['file-requires']
            self._write_file_requires(rpmdbv, data)

        if 'pkgtups-checksums' in self._trans_cache_store:
            data = self._trans_cache_store['pkgtups-checksums']
            self._write_package_checksums(rpmdbv, data)

        self._trans_cache_store = {}

    def transactionReset(self):
        """ We are going to reset the transaction, because the data we've added
            already might now be invalid (Eg. skip-broken, or splitting a
            transaction). """

        self._trans_cache_store = {}

    def returnGPGPubkeyPackages(self):
        """ Return packages of the gpg-pubkeys ... hacky. """
        ts = self.readOnlyTS()
        mi = ts.dbMatch('name', 'gpg-pubkey')
        ret = []
        for hdr in mi:
            self._loaded_gpg_keys = True
            ret.append(self._makePackageObject(hdr, mi.instance()))
        return ret

    def _read_file_requires(self):
        def _read_str(fo):
            return fo.readline()[:-1]

        assert self.__cache_rpmdb__

        fo, e = _iopen(self._cachedir + '/file-requires')
        if fo is None:
            return None, None

        rpmdbv = self.simpleVersion(main_only=True)[0]
        frpmdbv = fo.readline()
        if not frpmdbv or rpmdbv != frpmdbv[:-1]:
            return None, None

        iFR = {}
        iFP = {}
        try:
            # Read the requires...
            pkgtups_num = int(_read_str(fo))
            while pkgtups_num > 0:
                pkgtups_num -= 1

                # n, a, e, v, r
                pkgtup = (_read_str(fo), _read_str(fo),
                          _read_str(fo), _read_str(fo), _read_str(fo))
                int(pkgtup[2]) # Check epoch is valid

                files_num = int(_read_str(fo))
                while files_num > 0:
                    files_num -= 1

                    fname = _read_str(fo)

                    iFR.setdefault(pkgtup, []).append(fname)

            # Read the provides...
            files_num = int(_read_str(fo))
            while files_num > 0:
                files_num -= 1
                fname = _read_str(fo)
                pkgtups_num = int(_read_str(fo))
                while pkgtups_num > 0:
                    pkgtups_num -= 1

                    # n, a, e, v, r
                    pkgtup = (_read_str(fo), _read_str(fo),
                              _read_str(fo), _read_str(fo), _read_str(fo))
                    int(pkgtup[2]) # Check epoch is valid

                    iFP.setdefault(fname, []).append(pkgtup)

            if fo.readline() != '': # Should be EOF
                return None, None
        except ValueError:
            self._deal_with_bad_rpmdbcache("file requires")
            return None, None

        return iFR, iFP

    def fileRequiresData(self):
        """ Get a cached copy of the fileRequiresData for
            depsolving/checkFileRequires, note the giant comment in that
            function about how we don't keep this perfect for the providers of
            the requires. """
        if self.__cache_rpmdb__:
            iFR, iFP = self._read_file_requires()
            if iFR is not None:
                return iFR, set(), iFP

        installedFileRequires = {}
        installedUnresolvedFileRequires = set()
        resolved = set()
        for pkg in self.returnPackages():
            for name, flag, evr in pkg.requires:
                if not name.startswith('/'):
                    continue
                installedFileRequires.setdefault(pkg.pkgtup, []).append(name)
                if name not in resolved:
                    dep = self.getProvides(name, flag, evr)
                    resolved.add(name)
                    if not dep:
                        installedUnresolvedFileRequires.add(name)

        fileRequires = set()
        for fnames in installedFileRequires.itervalues():
            fileRequires.update(fnames)
        installedFileProviders = {}
        for fname in fileRequires:
            pkgtups = [pkg.pkgtup for pkg in self.getProvides(fname)]
            installedFileProviders[fname] = pkgtups

        ret =  (installedFileRequires, installedUnresolvedFileRequires,
                installedFileProviders)
        if self.__cache_rpmdb__:
            rpmdbv = self.simpleVersion(main_only=True)[0]
            self._write_file_requires(rpmdbv, ret)

        return ret

    def transactionCacheFileRequires(self, installedFileRequires,
                                     installedUnresolvedFileRequires,
                                     installedFileProvides,
                                     problems):
        if not self.__cache_rpmdb__:
            return

        if installedUnresolvedFileRequires or problems:
            return

        data = (installedFileRequires,
                installedUnresolvedFileRequires,
                installedFileProvides)

        self._trans_cache_store['file-requires'] = data

    def _write_file_requires(self, rpmdbversion, data):
        if not os.access(self._cachedir, os.W_OK):
            return

        (installedFileRequires,
         installedUnresolvedFileRequires,
         installedFileProvides) = data

        #  Have to do this here, as well as in transactionCacheFileRequires,
        # because fileRequiresData() calls us directly.
        if installedUnresolvedFileRequires:
            return

        fo = _open_no_umask(self._cachedir + '/file-requires.tmp', 'w')
        fo.write("%s\n" % rpmdbversion)

        fo.write("%u\n" % len(installedFileRequires))
        for pkgtup in sorted(installedFileRequires):
            for var in pkgtup:
                fo.write("%s\n" % var)
            filenames = set(installedFileRequires[pkgtup])
            fo.write("%u\n" % len(filenames))
            for fname in sorted(filenames):
                fo.write("%s\n" % fname)

        fo.write("%u\n" % len(installedFileProvides))
        for fname in sorted(installedFileProvides):
            fo.write("%s\n" % fname)

            pkgtups = set(installedFileProvides[fname])
            fo.write("%u\n" % len(pkgtups))
            for pkgtup in sorted(pkgtups):
                for var in pkgtup:
                    fo.write("%s\n" % var)
        fo.close()
        os.rename(self._cachedir + '/file-requires.tmp',
                  self._cachedir + '/file-requires')

    def preloadPackageChecksums(self, load_packages=True):
        """ As simpleVersion() et. al. requires it, we "cache" this yumdb data
            as part of our rpmdb cache. We cache it with rpmdb data, even
            though someone _could_ use yumdb to alter it without changing the
            rpmdb ... don't do that.
            NOTE: This is also used as a cache of pkgtups in the rpmdb. """
        if not self.__cache_rpmdb__:
            return

        def _read_str(fo):
            return fo.readline()[:-1]

        fo, e = _iopen(self._cachedir + '/pkgtups-checksums')
        if fo is None:
            return

        rpmdbv = self.simpleVersion(main_only=True)[0]
        frpmdbv = fo.readline()
        if not frpmdbv or rpmdbv != frpmdbv[:-1]:
            return

        checksum_data = {}
        try:
            # Read the checksums...
            pkgtups_num = int(_read_str(fo))
            while pkgtups_num > 0:
                pkgtups_num -= 1

                # n, a, e, v, r
                pkgtup = (_read_str(fo), _read_str(fo),
                          _read_str(fo), _read_str(fo), _read_str(fo))
                int(pkgtup[2]) # Check epoch is valid

                T = _read_str(fo)
                D = _read_str(fo)
                if T == '-':
                    checksum_data[pkgtup] = None
                else:
                    checksum_data[pkgtup] = (T, D)

            if fo.readline() != '': # Should be EOF
                return
        except ValueError:
            self._deal_with_bad_rpmdbcache("pkg checksums")
            return

        if not load_packages:
             return checksum_data

        for pkgtup in checksum_data:
            if checksum_data[pkgtup] is None:
                continue

            (n, a, e, v, r) = pkgtup
            pkg = self.searchNevra(n, e, v, r, a)
            if not pkg:
                self._deal_with_bad_rpmdbcache("pkg checksums")
                continue
            pkg = pkg[0]
            (T, D) = checksum_data[pkgtup]
            if ('checksum_type' in pkg.yumdb_info._read_cached_data or
                'checksum_data' in pkg.yumdb_info._read_cached_data):
                continue
            pkg.yumdb_info._read_cached_data['checksum_type'] = T
            pkg.yumdb_info._read_cached_data['checksum_data'] = D

    def transactionCachePackageChecksums(self, pkg_checksum_tups):
        if not self.__cache_rpmdb__:
            return

        self._trans_cache_store['pkgtups-checksums'] = pkg_checksum_tups

    def _write_package_checksums(self, rpmdbversion, data):
        if not os.access(self._cachedir, os.W_OK):
            return

        pkg_checksum_tups = data
        fo = _open_no_umask(self._cachedir + '/pkgtups-checksums.tmp', 'w')
        fo.write("%s\n" % rpmdbversion)
        fo.write("%u\n" % len(pkg_checksum_tups))
        for pkgtup, TD in sorted(pkg_checksum_tups):
            for var in pkgtup:
                fo.write("%s\n" % var)
            if TD is None:
                TD = ('-', '-')
            for var in TD:
                fo.write("%s\n" % var)
        fo.close()
        os.rename(self._cachedir + '/pkgtups-checksums.tmp',
                  self._cachedir + '/pkgtups-checksums')

    def _get_cached_simpleVersion_main(self):
        """ Return the cached string of the main rpmdbv. """
        if self._have_cached_rpmdbv_data is not None:
            return self._have_cached_rpmdbv_data

        if not self.__cache_rpmdb__:
            return None

        #  This test is "obvious" and the only thing to come out of:
        # http://lists.rpm.org/pipermail/rpm-maint/2007-November/001719.html
        # ...if anything gets implemented, we should change.
        rpmdbvfname = self._cachedir + "/version"
        rpmdbfname  = self.root + "/var/lib/rpm/Packages"

        if os.path.exists(rpmdbvfname) and os.path.exists(rpmdbfname):
            # See if rpmdb has "changed" ...
            nmtime = os.path.getmtime(rpmdbvfname)
            omtime = os.path.getmtime(rpmdbfname)
            if omtime <= nmtime:
                fo, e = _iopen(rpmdbvfname)
                if fo is None:
                    return None
                rpmdbv = fo.readline()[:-1]
                self._have_cached_rpmdbv_data  = rpmdbv
        return self._have_cached_rpmdbv_data

    def _put_cached_simpleVersion_main(self, rpmdbv):
        self._have_cached_rpmdbv_data  = str(rpmdbv)

        if not self.__cache_rpmdb__:
            return

        if self._cached_rpmdb_mtime is None:
            return # We haven't loaded any packages!!!

        rpmdbfname  = self.root + "/var/lib/rpm/Packages"
        if not os.path.exists(rpmdbfname):
            return # haha

        _cached_rpmdb_mtime = os.path.getmtime(rpmdbfname)
        if self._cached_rpmdb_mtime != _cached_rpmdb_mtime:
            #  Something altered the rpmdb since we loaded our first package,
            # so don't save the rpmdb version as who knows what happened.
            return

        rpmdbvfname = self._cachedir + "/version"
        if not os.access(self._cachedir, os.W_OK):
            if os.path.exists(self._cachedir):
                return

            try:
                os.makedirs(self._cachedir)
            except (IOError, OSError), e:
                return

        fo = _open_no_umask(rpmdbvfname + ".tmp", "w")
        fo.write(self._have_cached_rpmdbv_data)
        fo.write('\n')
        fo.close()
        os.rename(rpmdbvfname + ".tmp", rpmdbvfname)

    def simpleVersion(self, main_only=False, groups={}):
        """ Return a simple version for all installed packages. """
        def _up_revs(irepos, repoid, rev, pkg, csum):
            irevs = irepos.setdefault(repoid, {})
            rpsv = irevs.setdefault(None, PackageSackVersion())
            rpsv.update(pkg, csum)
            if rev is not None:
                rpsv = irevs.setdefault(rev, PackageSackVersion())
                rpsv.update(pkg, csum)

        if main_only and not groups:
            rpmdbv = self._get_cached_simpleVersion_main()
            if rpmdbv is not None:
                return [rpmdbv, {}]

        main = PackageSackVersion()
        irepos = {}
        main_grps = {}
        irepos_grps = {}
        for pkg in sorted(self.returnPackages()):
            ydbi = pkg.yumdb_info
            csum = None
            if 'checksum_type' in ydbi and 'checksum_data' in ydbi:
                csum = (ydbi.checksum_type, ydbi.checksum_data)
            main.update(pkg, csum)

            for group in groups:
                if pkg.name in groups[group]:
                    if group not in main_grps:
                        main_grps[group] = PackageSackVersion()
                        irepos_grps[group] = {}
                    main_grps[group].update(pkg, csum)

            if main_only:
                continue

            repoid = 'installed'
            rev = None
            if 'from_repo' in pkg.yumdb_info:
                repoid = '@' + pkg.yumdb_info.from_repo
                if 'from_repo_revision' in pkg.yumdb_info:
                    rev = pkg.yumdb_info.from_repo_revision

            _up_revs(irepos, repoid, rev, pkg, csum)
            for group in groups:
                if pkg.name in groups[group]:
                    _up_revs(irepos_grps[group], repoid, rev, pkg, csum)

        if self._have_cached_rpmdbv_data is None:
            self._put_cached_simpleVersion_main(main)

        if groups:
            return [main, irepos, main_grps, irepos_grps]
        return [main, irepos]

    @staticmethod
    def _find_search_fields(fields, searchstrings, hdr):
        count = 0
        for s in searchstrings:
            for field in fields:
                value = to_unicode(hdr[field])
                if value and value.lower().find(s) != -1:
                    count += 1
                    break
        return count

    def searchPrimaryFieldsMultipleStrings(self, fields, searchstrings,
                                           lowered=False):
        if not lowered:
            searchstrings = map(lambda x: x.lower(), searchstrings)
        ret = []
        for hdr, idx in self._get_packages():
            n = self._find_search_fields(fields, searchstrings, hdr)
            if n > 0:
                ret.append((self._makePackageObject(hdr, idx), n))
        return ret
    def searchNames(self, names=[]):
        returnList = []
        for name in names:
            returnList.extend(self._search(name=name))
        return returnList

    def searchNevra(self, name=None, epoch=None, ver=None, rel=None, arch=None):
        return self._search(name, epoch, ver, rel, arch)

    def excludeArchs(self, archlist):
        pass
    
    def returnLeafNodes(self, repoid=None):
        ts = self.readOnlyTS()
        return [ self._makePackageObject(h, mi) for (h, mi) in ts.returnLeafNodes(headers=True) ]
        
    # Helper functions
    def _get_packages(self, *args, **kwds):
        '''dbMatch() wrapper generator that yields (header, index) for matches
        '''
        ts = self.readOnlyTS()

        mi = ts.dbMatch(*args, **kwds)
        for h in mi:
            if h['name'] != 'gpg-pubkey':
                yield (h, mi.instance())
        del mi

        if self.auto_close:
            self.ts.close()

    def _search(self, name=None, epoch=None, ver=None, rel=None, arch=None):
        '''List of matching packages, to zero or more of NEVRA.'''
        if name is not None and name in self._pkgname_fails:
            return []

        pkgtup = (name, arch, epoch, ver, rel)
        if pkgtup in self._tup2pkg:
            return [self._tup2pkg[pkgtup]]

        loc = locals()
        ret = []

        if self._completely_loaded or name in self._pkgnames_loaded:
            if name is not None:
                pkgs = self._name2pkg.get(name, [])
                if not pkgs:
                    self._pkgname_fails.add(name)
            else:
                pkgs = self.returnPkgs()
            for po in pkgs:
                for tag in ('arch', 'rel', 'ver', 'epoch'):
                    if loc[tag] is not None and loc[tag] != getattr(po, tag):
                        break
                else:
                    ret.append(po)
            return ret

        ts = self.readOnlyTS()
        if name is not None:
            mi = self._get_packages('name', name)
        elif arch is not None:
            mi = self._get_packages('arch', arch)
        else:
            mi = self._get_packages()
            self._completely_loaded = True

        done = False
        for hdr, idx in mi:
            po = self._makePackageObject(hdr, idx)
            #  We create POs out of all matching names, even if we don't return
            # them.
            self._pkgnames_loaded.add(po.name)
            done = True

            for tag in ('arch', 'rel', 'ver', 'epoch'):
                if loc[tag] is not None and loc[tag] != getattr(po, tag):
                    break
            else:
                ret.append(po)

        if not done and name is not None:
            self._pkgname_fails.add(name)

        return ret

    def _makePackageObject(self, hdr, index):
        if index in self._idx2pkg:
            return self._idx2pkg[index]
        po = RPMInstalledPackage(hdr, index, self)
        self._idx2pkg[index] = po
        self._name2pkg.setdefault(po.name, []).append(po)
        self._tup2pkg[po.pkgtup] = po
        if self.__cache_rpmdb__ and self._cached_rpmdb_mtime is None:
            rpmdbfname  = self.root + "/var/lib/rpm/Packages"
            self._cached_rpmdb_mtime = os.path.getmtime(rpmdbfname)

        return po
        
    def _hdr2pkgTuple(self, hdr):
        name = misc.share_data(hdr['name'])
        arch = misc.share_data(hdr['arch'])
         # convert these to strings to be sure
        ver = misc.share_data(str(hdr['version']))
        rel = misc.share_data(str(hdr['release']))
        epoch = hdr['epoch']
        if epoch is None:
            epoch = '0'
        else:
            epoch = str(epoch)
        epoch = misc.share_data(epoch)
        return misc.share_data((name, arch, epoch, ver, rel))

    # deprecated options for compat only - remove once rpmdb is converted:
    def getPkgList(self):
        warnings.warn('getPkgList() will go away in a future version of Yum.\n'
                'Please access this via the pkglist attribute.',
                DeprecationWarning, stacklevel=2)
    
        return self.pkglist

    def getHdrList(self):
        warnings.warn('getHdrList() will go away in a future version of Yum.\n',
                DeprecationWarning, stacklevel=2)
        return [ hdr for hdr, idx in self._get_packages() ]

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

    @staticmethod
    def _genDeptup(name, flags, version):
        """ Given random stuff, generate a usable dep tuple. """

        if flags == 0:
            flags = None

        if type(version) is types.StringType:
            (r_e, r_v, r_r) = miscutils.stringToVersion(version)
        # would this ever be a ListType?
        elif type(version) in (types.TupleType, types.ListType):
            (r_e, r_v, r_r) = version
        else:
            # FIXME: This isn't always  type(version) is types.NoneType:
            # ...not sure what it is though, come back to this
            r_e = r_v = r_r = None

        deptup = (name, misc.share_data(flags),
                  (misc.share_data(r_e), misc.share_data(r_v),
                   misc.share_data(r_r)))
        return misc.share_data(deptup)

    def getProvides(self, name, flags=None, version=(None, None, None)):
        """searches the rpmdb for what provides the arguments
           returns a list of pkg objects of providing packages, possibly empty"""

        name = misc.share_data(name)
        deptup = self._genDeptup(name, flags, version)
        if deptup in self._get_pro_cache:
            return self._get_pro_cache[deptup]
        r_v = deptup[2][1]
        
        pkgs = self.searchProvides(name)
        
        result = { }
        
        for po in pkgs:
            if name[0] == '/' and r_v is None:
                result[po] = [(name, None, (None, None, None))]
                continue
            hits = po.matchingPrcos('provides', deptup)
            if hits:
                result[po] = hits
        self._get_pro_cache[deptup] = result
        return result

    def whatProvides(self, name, flags, version):
        # XXX deprecate?
        return [po.pkgtup for po in self.getProvides(name, flags, version)]

    def getRequires(self, name, flags=None, version=(None, None, None)):
        """searches the rpmdb for what provides the arguments
           returns a list of pkgtuples of providing packages, possibly empty"""

        name = misc.share_data(name)
        deptup = self._genDeptup(name, flags, version)
        if deptup in self._get_req_cache:
            return self._get_req_cache[deptup]
        r_v = deptup[2][1]

        pkgs = self.searchRequires(name)

        result = { }

        for po in pkgs:
            if name[0] == '/' and r_v is None:
                # file dep add all matches to the defSack
                result[po] = [(name, None, (None, None, None))]
                continue
            hits = po.matchingPrcos('requires', deptup)
            if hits:
                result[po] = hits
        self._get_req_cache[deptup] = result
        return result

    def whatRequires(self, name, flags, version):
        # XXX deprecate?
        return [po.pkgtup for po in self.getRequires(name, flags, version)]

    def return_running_packages(self):
        """returns a list of yum installed package objects which own a file
           that are currently running or in use."""
        pkgs = {}
        for pid in misc.return_running_pids():
            for fn in misc.get_open_files(pid):
                for pkg in self.searchFiles(fn):
                    pkgs[pkg] = 1

        return sorted(pkgs.keys())

    def check_dependencies(self, pkgs=None):
        """ Checks for any missing dependencies. """

        if pkgs is None:
            pkgs = self.returnPackages()

        providers = set() # Speedup, as usual :)
        problems = []
        for pkg in sorted(pkgs): # The sort here is mainly for "UI"
            for rreq in pkg.requires:
                if rreq[0].startswith('rpmlib'): continue
                if rreq in providers:            continue

                (req, flags, ver) = rreq
                if self.getProvides(req, flags, ver):
                    providers.add(rreq)
                    continue
                flags = yum.depsolve.flags.get(flags, flags)
                missing = miscutils.formatRequire(req, ver, flags)
                prob = RPMDBProblemDependency(pkg, "requires", missing=missing)
                problems.append(prob)

            for creq in pkg.conflicts:
                if creq[0].startswith('rpmlib'): continue

                (req, flags, ver) = creq
                res = self.getProvides(req, flags, ver)
                if not res:
                    continue
                flags = yum.depsolve.flags.get(flags, flags)
                found = miscutils.formatRequire(req, ver, flags)
                prob = RPMDBProblemDependency(pkg, "conflicts", found=found,
                                              conflicts=res)
                problems.append(prob)
        return problems

    def _iter_two_pkgs(self, ignore_provides):
        last = None
        for pkg in sorted(self.returnPackages()):
            if pkg.name in ignore_provides:
                continue
            if ignore_provides.intersection(set(pkg.provides_names)):
                continue

            if last is None:
                last = pkg
                continue
            yield last, pkg
            last = pkg

    def check_duplicates(self, ignore_provides=[]):
        """ Checks for any "duplicate packages" (those with multiple versions
            installed), we ignore any packages with a provide in the passed
            provide list (this is how installonlyworks, so we do the same). """
        ignore_provides = set(ignore_provides)
        problems = []
        for last, pkg in self._iter_two_pkgs(ignore_provides):
            if pkg.name != last.name:
                continue
            if pkg.verEQ(last) and pkg != last:
                if arch.isMultiLibArch(pkg.arch) and last.arch != 'noarch':
                    continue
                if arch.isMultiLibArch(last.arch) and pkg.arch != 'noarch':
                    continue

            # More than one pkg, they aren't version equal, or aren't multiarch
            problems.append(RPMDBProblemDuplicate(pkg, duplicate=last))
        return problems

    def check_obsoleted(self):
        """ Checks for any packages which are obsoleted by other packages. """
        obsoleters = []
        problems = []
        for pkg in sorted(self.returnPackages()):
            if not pkg.obsoletes:
                continue
            obsoleters.append(pkg)
        for pkg in sorted(self.returnPackages()):
            for obspo in pkg.obsoletedBy(obsoleters):
                problems.append(RPMDBProblemObsoleted(pkg, obsoleter=obspo))
        return problems

    def check_provides(self):
        """ For each package, check that a provides search for it's name (and
            everything it provides) finds it. """
        problems = []
        for pkg in sorted(self.returnPackages()):
            for provtup in pkg.provides:
                name, flags, version = provtup
                if pkg not in self.getProvides(name, flags, version):
                    problems.append(RPMDBProblemProvides(pkg, provide=provtup))
                    break
        return problems

def _sanitize(path):
    return path.replace('/', '').replace('~', '')


class RPMDBAdditionalData(object):
    """class for access to the additional data not able to be stored in the
       rpmdb"""
    # dir: /var/lib/yum/yumdb/
    # pkgs stored in name[0]/name[1]/pkgid-name-ver-rel-arch dirs
    # dirs have files per piece of info we're keeping
    #    repoid, install reason, status, blah, (group installed for?), notes?
    
    def __init__(self, db_path='/var/lib/yum/yumdb', version_path=None):
        self.conf = misc.GenericHolder()
        self.conf.db_path = db_path
        self.conf.version_path = version_path
        self.conf.writable = False
        
        self._packages = {} # pkgid = dir
        if not os.path.exists(self.conf.db_path):
            try:
                os.makedirs(self.conf.db_path)
            except (IOError, OSError), e:
                # some sort of useful thing here? A warning?
                return
            self.conf.writable = True
        else:
            if os.access(self.conf.db_path, os.W_OK):
                self.conf.writable = True
        #  Don't call _load_all_package_paths to preload, as it's expensive
        # if the dirs. aren't in cache.
        self.yumdb_cache = {'attr' : {}}

    def _load_all_package_paths(self):
        # glob the path and get a dict of pkgs to their subdir
        glb = '%s/*/*/' % self.conf.db_path
        pkgdirs = glob.glob(glb)
        for d in pkgdirs:
            pkgid = os.path.basename(d).split('-')[0]
            self._packages[pkgid] = d

    def _get_dir_name(self, pkgtup, pkgid):
        if pkgid in self._packages:
            return self._packages[pkgid]
        (n, a, e, v,r) = pkgtup
        n = _sanitize(n) # Please die in a fire rpmbuild
        thisdir = '%s/%s/%s-%s-%s-%s-%s' % (self.conf.db_path,
                                            n[0], pkgid, n, v, r, a)
        self._packages[pkgid] = thisdir
        return thisdir

    def get_package(self, po=None, pkgtup=None, pkgid=None):
        """Return an RPMDBAdditionalDataPackage Object for this package"""
        if po:
            thisdir = self._get_dir_name(po.pkgtup, po.pkgid)
        elif pkgtup and pkgid:
            thisdir = self._get_dir_name(pkgtup, pkgid)
        else:
            raise ValueError,"Pass something to RPMDBAdditionalData.get_package"
        
        return RPMDBAdditionalDataPackage(self.conf, thisdir,
                                          yumdb_cache=self.yumdb_cache)

    def sync_with_rpmdb(self, rpmdbobj):
        """populate out the dirs and remove all the items no longer in the rpmd
           and/or populate various bits to the currently installed version"""
        # TODO:
        # get list of all items in the yumdb
        # remove any no longer in the rpmdb/andor migrate them up to the currently
        # installed version
        # add entries for items in the rpmdb if they don't exist in the yumdb

        pass

class RPMDBAdditionalDataPackage(object):

    # We do auto hardlink on these attributes
    _auto_hardlink_attrs = set(['checksum_type', 'reason',
                                'installed_by', 'changed_by',
                                'from_repo', 'from_repo_revision',
                                'from_repo_timestamp', 'releasever',
                                'command_line'])

    def __init__(self, conf, pkgdir, yumdb_cache=None):
        self._conf = conf
        self._mydir = pkgdir

        self._read_cached_data = {}

        #  'from_repo' is the most often requested piece of data, and is often
        # the same for a huge number of packages. So we use hardlinks to share
        # data, and try to optimize for that.
        #  It's useful for other keys too (installed_by/changed_by/reason/etc.)
        # so we make it generic.
        self._yumdb_cache = yumdb_cache

    def _auto_cache(self, attr, value, fn, info=None):
        """ Create caches for the attr. We have a per. object read cache so at
            worst we only have to read a single attr once. Then we expand that
            with (dev, ino) cache, so hardlink data can be read once for
            multiple packages. """
        self._read_cached_data[attr] = value
        if self._yumdb_cache is None:
            return

        nlinks = 1
        if info is not None:
            nlinks = info.st_nlink
        if nlinks <= 1 and attr not in self._auto_hardlink_attrs:
            return

        if value in self._yumdb_cache['attr']:
            sinfo = self._yumdb_cache['attr'][value][1]
            if info is not None and sinfo is not None:
                if (info.st_dev, info.st_ino) == (sinfo.st_dev, sinfo.st_ino):
                    self._yumdb_cache['attr'][value][2].add(fn)
                    self._yumdb_cache[fn] = value
                    return
            if self._yumdb_cache['attr'][value][0] >= nlinks:
                # We already have a better cache file.
                return

        self._yumdb_cache['attr'][value] = (nlinks, info, set([fn]))
        self._yumdb_cache[fn]            = value

    def _unlink_yumdb_cache(self, fn):
        """ Remove old values from the link cache. """
        if fn in self._yumdb_cache:
            ovalue = self._yumdb_cache[fn]
            if ovalue in self._yumdb_cache['attr']:
                self._yumdb_cache['attr'][ovalue][2].discard(fn)
                if not self._yumdb_cache['attr'][ovalue][2]:
                    del self._yumdb_cache['attr'][ovalue]
            del self._yumdb_cache[fn]

    def _link_yumdb_cache(self, fn, value):
        """ If we have a matching yumdb cache, link() to it instead of having
            to open()+write(). """
        if self._yumdb_cache is None:
            return False

        self._unlink_yumdb_cache(fn)

        if value not in self._yumdb_cache['attr']:
            return False

        assert self._yumdb_cache['attr'][value][2]
        try:
            lfn = iter(self._yumdb_cache['attr'][value][2]).next()
            misc.unlink_f(fn + '.tmp')
            os.link(lfn, fn + '.tmp')
            os.rename(fn + '.tmp', fn)
        except:
            return False

        self._yumdb_cache['attr'][value][2].add(fn)
        self._yumdb_cache[fn] = value

        return True

    def _attr2fn(self, attr):
        """ Given an attribute, return the filename. """
        return os.path.normpath(self._mydir + '/' + attr)

    def _write(self, attr, value):
        # check for self._conf.writable before going on?
        if not os.path.exists(self._mydir):
            os.makedirs(self._mydir)

        attr = _sanitize(attr)
        if attr in self._read_cached_data:
            del self._read_cached_data[attr]
        fn = self._attr2fn(attr)

        if attr.endswith('.tmp'):
            raise AttributeError, "Cannot set attribute %s on %s" % (attr, self)

        #  These two are special, as they have an index and are used as our
        # cache-breaker.
        if attr in ('checksum_type', 'checksum_data'):
            misc.unlink_f(self._conf.version_path)

        # Auto hardlink some of the attrs...
        if self._link_yumdb_cache(fn, value):
            return

        # Default write()+rename()... hardlink -c can still help.
        misc.unlink_f(fn + '.tmp')

        fo = _open_no_umask(fn + '.tmp', 'w')
        try:
            fo.write(value)
        except (OSError, IOError), e:
            raise AttributeError, "Cannot set attribute %s on %s" % (attr, self)

        fo.flush()
        fo.close()
        del fo
        os.rename(fn +  '.tmp', fn) # even works on ext4 now!:o

        self._auto_cache(attr, value, fn)
    
    def _read(self, attr):
        attr = _sanitize(attr)

        if attr in self._read_cached_data:
            return self._read_cached_data[attr]
        fn = self._attr2fn(attr)

        if attr.endswith('.tmp'):
            raise AttributeError, "%s has no attribute %s" % (self, attr)

        info = misc.stat_f(fn)
        if info is None:
            raise AttributeError, "%s has no attribute %s" % (self, attr)

        if info.st_nlink > 1 and self._yumdb_cache is not None:
            key = (info.st_dev, info.st_ino)
            if key in self._yumdb_cache:
                self._auto_cache(attr, self._yumdb_cache[key], fn, info)
                return self._read_cached_data[attr]

        fo, e = _iopen(fn)
        if fo is None: # This really sucks, don't do that.
            return '<E:%d>' % e.errno
        value = fo.read()
        fo.close()
        del fo

        if info.st_nlink > 1 and self._yumdb_cache is not None:
            self._yumdb_cache[key] = value
        self._auto_cache(attr, value, fn, info)

        return value
    
    def _delete(self, attr):
        """remove the attribute file"""

        attr = _sanitize(attr)
        fn = self._attr2fn(attr)
        if attr in self._read_cached_data:
            del self._read_cached_data[attr]
        self._unlink_yumdb_cache(fn)
        if os.path.exists(fn):
            try:
                os.unlink(fn)
            except (IOError, OSError):
                raise AttributeError, "Cannot delete attribute %s on %s " % (attr, self)
    
    def __getattr__(self, attr):
        return self._read(attr)

    def __setattr__(self, attr, value):
        if not attr.startswith('_'):
            self._write(attr, value)
        else:
            object.__setattr__(self, attr, value)

    def __delattr__(self, attr):
        if not attr.startswith('_'):
            self._delete(attr)
        else:
            object.__delattr__(self, attr)

    def __contains__(self, attr):
        #  This is faster than __iter__ and it makes things fail in a much more
        # obvious way in weird FS corruption cases like: BZ 593436
        x = self.get(attr)
        return x is not None

    def __iter__(self, show_hidden=False):
        for item in self._read_cached_data:
            yield item
        for item in glob.glob(self._mydir + '/*'):
            item = item[(len(self._mydir) + 1):]
            if item in self._read_cached_data:
                continue
            if not show_hidden and item.endswith('.tmp'):
                continue
            yield item

    def clean(self):
        # purge out everything
        for item in self.__iter__(show_hidden=True):
            self._delete(item)
        try:
            os.rmdir(self._mydir)
        except OSError:
            pass

#    def __dir__(self): # for 2.6 and beyond, apparently
#        return list(self.__iter__()) + self.__dict__.keys()

    def get(self, attr, default=None):
        """retrieve an add'l data obj"""

        try:
            res = self._read(attr)
        except AttributeError:
            return default
        return res
        
        
def main():
    sack = RPMDBPackageSack('/')
    for p in sack.simplePkgList():
        print p

if __name__ == '__main__':
    main()

