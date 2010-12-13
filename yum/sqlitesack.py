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
# Copyright 2005 Duke University 

#
# Implementation of the YumPackageSack class that uses an sqlite backend
#

import os
import os.path
import fnmatch

import yumRepo
from packages import PackageObject, RpmBase, YumAvailablePackage, parsePackages
import Errors
import misc

from sqlutils import executeSQL, sql_esc, sql_esc_glob
import rpmUtils.miscutils
import sqlutils
import constants
import operator
from yum.misc import seq_max_split
from yum.i18n import to_utf8, to_unicode
import sys
import re
import warnings

def catchSqliteException(func):
    """This decorator converts sqlite exceptions into RepoError"""
    def newFunc(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlutils.sqlite.Error, e:
            # 2.4.x requires this, but 2.6.x complains about even hasattr()
            # of e.message ... *sigh*
            if sys.hexversion < 0x02050000:
                if hasattr(e,'message'):
                    raise Errors.RepoError, str(e.message)
                else:
                    raise Errors.RepoError, str(e)
            raise Errors.RepoError, str(e)

    newFunc.__name__ = func.__name__
    newFunc.__doc__ = func.__doc__
    newFunc.__dict__.update(func.__dict__)
    return newFunc

def _share_data(value):
    return misc.share_data(value)

# FIXME: parsePackages()
def _parse_pkg_n(match, regexp_match, n):
    if match == n:
        return True
    if not regexp_match:
        return False

    if (match and n and match[0] not in ('?', '*') and match[0] != n[0]):
        return False
    if regexp_match(n):
        return True
    return False

def _parse_pkg(match, regexp_match, data, e,v,r,a):

    n = data['n']
    assert e, 'Nothing in epoch'
    # Worthless speed hacks?
    if match == n:
        return True
    if (match and n and match[0] not in ('?', '*') and
        match[0] != n[0] and match[0] != e[0]):
        return False

    if 'nameArch' not in data:
        data['nameArch'] = '%s.%s' % (n, a)
        data['nameVerRelArch'] = '%s-%s-%s.%s' % (n, v, r, a)
        data['nameVer'] = '%s-%s' % (n, v)
        data['nameVerRel'] = '%s-%s-%s' % (n, v, r)
        data['envra'] = '%s:%s-%s-%s.%s' % (e, n, v, r, a)
        data['nevra'] = '%s-%s:%s-%s.%s' % (n, e, v, r, a)
    data = set([n, data['nameArch'], data['nameVerRelArch'], data['nameVer'],
                data['nameVerRel'], data['envra'], data['nevra']])

    if match in data:
        return True
    if not regexp_match:
        return False

    for item in data:
        if regexp_match(item):
            return True
    return False

def _excluder_match(excluder, match, regexp_match, data, e,v,r,a):
    if False: pass
    elif excluder in ('eq', 'match'):
        if _parse_pkg(match, regexp_match, data, e,v,r,a):
            return True

    elif excluder in ('name.eq', 'name.match'):
        if _parse_pkg_n(match, regexp_match, data['n']):
            return True

    elif excluder in ('arch.eq', 'arch.match'):
        if _parse_pkg_n(match, regexp_match, a):
            return True

    elif excluder == 'nevr.eq':
        if 'nevr' not in data:
            data['nevr'] = '%s-%s:%s-%s' % (data['n'], e, v, r)
        if match == data['nevr']:
            return True

    elif excluder in ('nevra.eq', 'nevra.match'):
        if 'nevra' not in data:
            data['nevra'] = '%s-%s:%s-%s.%s' % (data['n'], e, v, r, a)
        if _parse_pkg_n(match, regexp_match, data['nevra']):
            return True

    elif excluder == 'name.in':
        if data['n'] in match:
            return True

    elif excluder == 'nevr.in':
        if 'nevr' not in data:
            data['nevr'] = '%s-%s:%s-%s' % (data['n'], e, v, r)
        if data['nevr'] in match:
            return True

    elif excluder == 'nevra.in':
        if 'nevra' not in data:
            data['nevra'] = '%s-%s:%s-%s.%s' % (data['n'], e, v, r, a)
        if data['nevra'] in match:
            return True

    elif excluder == 'pkgtup.eq':
        if match == data['pkgtup']:
            return True

    elif excluder == 'pkgtup.in':
        if data['pkgtup'] in match:
            return True

    elif excluder == 'marked':
        if data['marked']:
            return True

    elif excluder == 'washed':
        if not data['marked']:
            return True

    elif excluder == '*':
        return True

    else:
        assert False, 'Bad excluder: ' + excluder
        return None

    return False


class YumAvailablePackageSqlite(YumAvailablePackage, PackageObject, RpmBase):
    def __init__(self, repo, db_obj):
        self.prco = { 'obsoletes': (),
                      'conflicts': (),
                      'requires': (),
                      'provides': () }
        self.sack = repo.sack
        self.repoid = repo.id
        self.repo = repo
        self.state = None
        self._loadedfiles = False
        self._files = None
        self._read_db_obj(db_obj)
        # for stupid metadata created without epochs listed in the version tag
        # die die
        if self.epoch is None:
            self.epoch = '0'
        self.id = self.pkgId
        self.ver = self.version 
        self.rel = self.release 
        self.pkgtup = (self.name, self.arch, self.epoch, self.version, self.release)

        self._changelog = None
        self._hash = None
        

    files = property(fget=lambda self: self._loadFiles())

    def _read_db_obj(self, db_obj, item=None):
        """read the db obj. If asked for a specific item, return it.
           otherwise populate out into the object what exists"""
        if item:
            try:
                return db_obj[item]
            except (IndexError, KeyError):
                return None

        for item in ['name', 'arch', 'epoch', 'version', 'release', 'pkgKey']:
            try:
                setattr(self, item, _share_data(db_obj[item]))
            except (IndexError, KeyError):
                pass

        try:
            self.pkgId = db_obj['pkgId']

            checksum_type = _share_data(db_obj['checksum_type'])
            check_sum = (checksum_type, db_obj['pkgId'], True)
            self._checksums = [ check_sum ]
        except (IndexError, KeyError):
            pass

    @catchSqliteException
    def _sql_MD(self, MD, sql, *args):
        """ Exec SQL against an MD of the repo, return a cursor. """

        cache = getattr(self.sack, MD + 'db')[self.repo]
        cur = cache.cursor()
        executeSQL(cur, sql, *args)
        return cur

    def __getattr__(self, varname):
        db2simplemap = { 'packagesize' : 'size_package',
                         'archivesize' : 'size_archive',
                         'installedsize' : 'size_installed',
                         'buildtime' : 'time_build',
                         'hdrstart' : 'rpm_header_start',
                         'hdrend' : 'rpm_header_end',
                         'basepath' : 'location_base',
                         'relativepath': 'location_href',
                         'filetime' : 'time_file',
                         'packager' : 'rpm_packager',
                         'group' : 'rpm_group',
                         'buildhost' : 'rpm_buildhost',
                         'sourcerpm' : 'rpm_sourcerpm',
                         'vendor' : 'rpm_vendor',
                         'license' : 'rpm_license',
                         'checksum_value' : 'pkgId',
                        }

        # If these existed, then we wouldn't get here ... and nothing in the DB
        # starts and ends with __'s. So these are missing.
        if varname.startswith('__') and varname.endswith('__'):
            raise AttributeError, varname
        
        dbname = db2simplemap.get(varname, varname)
        try:
            r = self._sql_MD('primary',
                         "SELECT %s FROM packages WHERE pkgId = ?" % dbname,
                         (self.pkgId,)).fetchone()
        except Errors.RepoError, e:
            if str(e).startswith('no such column'):
                #FIXME - after API break make this an AttributeError Raise
                raise KeyError, str(e)
            raise                         
        value = r[0]
        if varname == 'epoch' and value is None:
            value = '0'
        if varname in ('summary', 'description') and value is None:
            # Maybe others here? ... location_base is a bad NONO though.
            value = '' # Description for picasa, probably among others *sigh*
        if varname in {'vendor' : 1, 'packager' : 1, 'buildhost' : 1,
                       'license' : 1, 'group' : 1,
                       'summary' : 1, 'description' : 1, 'sourcerpm' : 1,
                       'url' : 1}:
            value  = _share_data(value)
        setattr(self, varname, value)
            
        return value
        
    def _loadFiles(self):
        if self._loadedfiles:
            return self._files

        result = {}
        
        #FIXME - this should be try, excepting
        self.sack.populate(self.repo, mdtype='filelists')
        cur = self._sql_MD('filelists',
                           "SELECT dirname, filetypes, filenames " \
                           "FROM   filelist JOIN packages USING(pkgKey) " \
                           "WHERE  packages.pkgId = ?", (self.pkgId,))
        for ob in cur:
            dirname = ob['dirname']
            filetypes = decodefiletypelist(ob['filetypes'])
            filenames = decodefilenamelist(ob['filenames'])
            while(filetypes):
                if dirname:
                    filename = dirname+'/'+filenames.pop()
                else:
                    filename = filenames.pop()
                filetype = _share_data(filetypes.pop())
                result.setdefault(filetype,[]).append(filename)
        self._loadedfiles = True
        self._files = result

        return self._files

    def _loadChangelog(self):
        result = []
        if not self._changelog:
            if self.repo not in self.sack.otherdb:
                try:
                    self.sack.populate(self.repo, mdtype='otherdata')
                except Errors.RepoError:
                    self._changelog = result
                    return
            cur = self._sql_MD('other',
                               "SELECT date, author, changelog " \
                               "FROM   changelog JOIN packages USING(pkgKey) " \
                               "WHERE  pkgId = ? ORDER BY date DESC",
                               (self.pkgId,))
            # Check count(pkgId) here, the same way we do in searchFiles()?
            # Failure mode is much less of a problem.
            for ob in cur:
                # Note: Atm. rpm only does days, where (60 * 60 * 24) == 86400
                #       and we have the hack in _dump_changelog() to keep the
                #       order the same, so this is a quick way to get rid of
                #       any extra "seconds".
                #       We still leak the seconds if there are 100 updates in
                #       a day ... but don't do that. It also breaks if rpm ever
                #       gets fixed (but that is unlikely).
                c_date = 100 * (ob['date'] / 100)
                c_author = to_utf8(ob['author'])
                c_log = to_utf8(ob['changelog'])
                result.append((c_date, _share_data(c_author), c_log))
            self._changelog = result
            return
        
    def returnIdSum(self):
        return (self.checksum_type, self.pkgId)
    
    def returnChangelog(self):
        self._loadChangelog()
        return self._changelog
    
    def returnFileEntries(self, ftype='file', primary_only=False):
        """return list of files based on type, you can pass primary_only=True
           to limit to those files in the primary repodata"""
        if primary_only and not self._loadedfiles:
            sql = "SELECT name as fname FROM files WHERE pkgKey = ? and type = ?"
            cur = self._sql_MD('primary', sql, (self.pkgKey, ftype))
            return map(lambda x: x['fname'], cur)

        self._loadFiles()
        return RpmBase.returnFileEntries(self,ftype,primary_only)
    
    def returnFileTypes(self, primary_only=False):
        """return list of types of files in the package, you can pass
           primary_only=True to limit to those files in the primary repodata"""
        if primary_only and not self._loadedfiles:
            sql = "SELECT DISTINCT type as ftype FROM files WHERE pkgKey = ?"
            cur = self._sql_MD('primary', sql, (self.pkgKey,))
            return map(lambda x: x['ftype'], cur)

        self._loadFiles()
        return RpmBase.returnFileTypes(self)

    def simpleFiles(self, ftype='file'):
        warnings.warn('simpleFiles() will go away in a future version of Yum.'
                      'Use returnFileEntries(primary_only=True)\n',
                      Errors.YumDeprecationWarning, stacklevel=2)
        sql = "SELECT name as fname FROM files WHERE pkgKey = ? and type = ?"
        cur = self._sql_MD('primary', sql, (self.pkgKey, ftype))
        return map(lambda x: x['fname'], cur)

    def returnPrco(self, prcotype, printable=False):
        prcotype = _share_data(prcotype)
        if isinstance(self.prco[prcotype], tuple):
            sql = "SELECT name, version, release, epoch, flags " \
                  "FROM %s WHERE pkgKey = ?" % prcotype
            cur = self._sql_MD('primary', sql, (self.pkgKey,))
            self.prco[prcotype] = [ ]
            for ob in cur:
                if not ob['name']:
                    continue
                prco_set = (_share_data(ob['name']), _share_data(ob['flags']),
                            (_share_data(ob['epoch']),
                             _share_data(ob['version']),
                             _share_data(ob['release'])))
                self.prco[prcotype].append(_share_data(prco_set))

        return RpmBase.returnPrco(self, prcotype, printable)
    
    def _requires_with_pre(self):
        """returns requires with pre-require bit"""
        sql = "SELECT name, version, release, epoch, flags,pre " \
              "FROM requires WHERE pkgKey = ?"
        cur = self._sql_MD('primary', sql, (self.pkgKey,))
        requires = []
        for ob in cur:
            pre = "0"
            if ob['pre'].lower() in ['TRUE', 1]:
                pre = "1"
            prco_set = (_share_data(ob['name']), _share_data(ob['flags']),
                        (_share_data(ob['epoch']),
                         _share_data(ob['version']),
                         _share_data(ob['release'])), pre)
            requires.append(prco_set)
        return requires

class YumSqlitePackageSack(yumRepo.YumPackageSack):
    """ Implementation of a PackageSack that uses sqlite cache instead of fully
    expanded metadata objects to provide information """

    def __init__(self, packageClass):
        # Just init as usual and create a dict to hold the databases
        yumRepo.YumPackageSack.__init__(self, packageClass)
        self.primarydb = {}
        self.filelistsdb = {}
        self.otherdb = {}
        self.excludes = {}     # of [repo] => {} of pkgId's => 1
        self._excludes = set() # of (repo, pkgKey)
        self._exclude_whitelist = set() # of (repo, pkgKey)
        self._all_excludes = {}
        self._search_cache = {
            'provides' : { },
            'requires' : { },
            }
        self._key2pkg = {}
        self._pkgname2pkgkeys = {}
        self._pkgtup2pkgs = {}
        self._pkgnames_loaded = set()
        self._pkgmatch_fails = set()
        self._provmatch_fails = set()
        self._arch_allowed = None
        self._pkgExcluder = []
        self._pkgExcludeIds = {}
        self._pkgobjlist_dirty = False

    @catchSqliteException
    def _sql_MD(self, MD, repo, sql, *args):
        """ Exec SQL against an MD of the repo, return a cursor. """

        cache = getattr(self, MD + 'db')[repo]
        cur = cache.cursor()
        executeSQL(cur, sql, *args)
        return cur

    def _sql_MD_pkg_num(self, MD, repo):
        """ Give a count of pkgIds in the given repo DB """
        sql = "SELECT count(pkgId) FROM packages"
        return self._sql_MD('primary', repo, sql).fetchone()[0]
        
    def _clean_pkgobjlist(self):
        """ If the pkgobjlist is dirty (possible pkgs on it which are excluded)
            then clean it, and return the clean list. """
        assert hasattr(self, 'pkgobjlist')

        if self._pkgobjlist_dirty:
            pol = filter(lambda x: not self._pkgExcluded(x), self.pkgobjlist)
            self.pkgobjlist = pol
            self._pkgobjlist_dirty = False

        return self.pkgobjlist

    def __len__(self):
        # First check if everything is excluded
        all_excluded = True
        for (repo, cache) in self.primarydb.items():
            if repo not in self._all_excludes:
                all_excluded = False
                break
        if all_excluded:
            return 0
            
        if hasattr(self, 'pkgobjlist'):
            return len(self._clean_pkgobjlist())

        exclude_num = 0
        for repo in self.excludes:
            exclude_num += len(self.excludes[repo])
        pkg_num = 0
        for repo in self.primarydb:
            pkg_num += self._sql_MD_pkg_num('primary', repo)
        return pkg_num - exclude_num

    def dropCachedData(self):
        if hasattr(self, '_memoize_requires'):
            del self._memoize_requires
        if hasattr(self, '_memoize_provides'):
            del self._memoize_provides
        if hasattr(self, 'pkgobjlist'):
            del self.pkgobjlist
        self._pkgobjlist_dirty = False
        self._key2pkg = {}
        self._pkgname2pkgkeys = {}
        self._pkgnames_loaded = set()
        self._pkgmatch_fails = set()
        self._provmatch_fails = set()
        self._pkgtup2pkgs = {}
        self._search_cache = {
            'provides' : { },
            'requires' : { },
            }
        misc.unshare_data()

    @catchSqliteException
    def close(self):
        self.dropCachedData()

        for dataobj in self.primarydb.values() + \
                       self.filelistsdb.values() + \
                       self.otherdb.values():
            dataobj.close()
        self.primarydb = {}
        self.filelistsdb = {}
        self.otherdb = {}
        self.excludes = {}
        self._excludes = set()
        self._exclude_whitelist = set()
        self._all_excludes = {}
        self._pkgExcluder = []
        self._pkgExcludeIds = {}
        self._pkgobjlist_dirty = False

        yumRepo.YumPackageSack.close(self)

    def buildIndexes(self):
        # We don't need to play with returnPackages() caching as it handles
        # additions to excludes after the cache is built.
        pass

    def _checkIndexes(self, failure='error'):
        return

    def _delPackageRK(self, repo, pkgKey):
        ''' Exclude a package so that _pkgExcluded*() knows it's gone.
            Note that this doesn't update self.exclude. '''
        self._excludes.add((repo, pkgKey))
        # Don't keep references around, just wastes memory.
        if repo in self._key2pkg:
            po = self._key2pkg[repo].pop(pkgKey, None)
            if po is not None: # Will also be in the pkgtup2pkgs cache...
                pos = self._pkgtup2pkgs[po.pkgtup]
                pos = filter(lambda x: id(x) == id(po), pos)
                self._pkgtup2pkgs[po.pkgtup] = pos

    # Remove a package
    # Because we don't want to remove a package from the database we just
    # add it to the exclude list
    def delPackage(self, obj):
        if obj.repo not in self.excludes:
            self.excludes[obj.repo] = {}
        self.excludes[obj.repo][obj.pkgId] = 1
        if (obj.repo, obj.pkgKey) in self._exclude_whitelist:
            self._exclude_whitelist.discard((obj.repo, obj.pkgKey))
        self._delPackageRK(obj.repo, obj.pkgKey)
        self._pkgobjlist_dirty = True

    def _delAllPackages(self, repo):
        """ Exclude all packages from the repo. """
        self._all_excludes[repo] = True
        if repo in self.excludes:
            del self.excludes[repo]
        if repo in self._key2pkg:
            del self._key2pkg[repo]
        if repo in self._pkgname2pkgkeys:
            del self._pkgname2pkgkeys[repo]

    def _excluded(self, repo, pkgId):
        if repo in self._all_excludes:
            return True
        
        if repo in self.excludes and pkgId in self.excludes[repo]:
            return True
                
        return False

    def _pkgKeyExcluded(self, repo, pkgKey):
        if self._all_excludes and repo in self._all_excludes:
            return True

        return self._excludes and (repo, pkgKey) in self._excludes

    def _pkgExcludedRKNEVRA(self, repo,pkgKey, n,e,v,r,a):
        ''' Main function to use for "can we use this package" question.
                . Tests repo against allowed repos.
                . Tests pkgKey against allowed packages.
                . Tests arch against allowed arches.
                . Tests addPackageExcluder() calls.
        '''

        if self._exclude_whitelist and (repo,pkgKey) in self._exclude_whitelist:
            return False

        if self._pkgKeyExcluded(repo, pkgKey):
            return True

        if self._arch_allowed is not None and a not in self._arch_allowed:
            self._delPackageRK(repo, pkgKey)
            return True

        if not self._pkgExcluder:
            return False

        data = {'n' : n.lower(), 'pkgtup' : (n, a, e, v, r), 'marked' : False}
        e = e.lower()
        v = v.lower()
        r = r.lower()
        a = a.lower()

        for repoid, excluder, match, regexp_match in self._pkgExcluder:
            if repoid is not None and repoid != repo.id:
                continue

            exSPLIT = excluder.split('.', 1)
            if len(exSPLIT) != 2:
                assert False, 'Bad excluder: ' + excluder
                continue

            exT, exM = exSPLIT
            if False: pass
            elif exT == 'exclude':
                if _excluder_match(exM, match, regexp_match, data, e,v,r,a):
                    self._delPackageRK(repo, pkgKey)
                    return True

            elif exT == 'include':
                if _excluder_match(exM, match, regexp_match, data, e,v,r,a):
                    break

            elif exT == 'mark':
                if data['marked']:
                    pass # Speed opt. don't do matches we don't need to do.
                elif _excluder_match(exM, match, regexp_match, data, e,v,r,a):
                    data['marked'] = True

            elif exT == 'wash':
                if not data['marked']:
                    pass # Speed opt. don't do matches we don't need to do.
                elif _excluder_match(exM, match, regexp_match, data, e,v,r,a):
                    data['marked'] = False

            else:
                assert False, 'Bad excluder: ' + excluder

        self._exclude_whitelist.add((repo, pkgKey))
        return False

    def _pkgExcludedRKT(self, repo,pkgKey, pkgtup):
        ''' Helper function to call _pkgExcludedRKNEVRA.
            Takes a repo, pkgKey and a package tuple'''
        (n,a,e,v,r) = pkgtup
        return self._pkgExcludedRKNEVRA(repo, pkgKey, n,e,v,r,a)

    def _pkgExcludedRKD(self, repo,pkgKey, data):
        ''' Helper function to call _pkgExcludedRKNEVRA.
            Takes a repo, pkgKey and a dict of package data'''
        (n,a,e,v,r) = (data['name'], data['arch'],
                       data['epoch'], data['version'], data['release'])
        return self._pkgExcludedRKNEVRA(repo, pkgKey, n,e,v,r,a)

    def _pkgExcluded(self, po):
        ''' Helper function to call _pkgExcludedRKNEVRA.
            Takes a package object. '''
        return self._pkgExcludedRKT(po.repo, po.pkgKey, po.pkgtup)

    def addPackageExcluder(self, repoid, excluderid, excluder, *args):
        """ Add an "excluder" for all packages in the repo/sack. Can basically
            do anything based on nevra, changes lots of exclude decisions from
            "preload package; test; delPackage" into "load excluder".
            Excluderid is used so the caller doesn't have to track
            "have I loaded the excluder for this repo.", it's probably only
            useful when repoid is None ... if it turns out utterly worthless
            then it's still not a huge wart. """
        if excluderid is not None and excluderid in self._pkgExcludeIds:
            return

        match        = None
        regexp_match = None
        if False: pass
        elif excluder.endswith('.eq'):
            assert len(args) == 1
            match = args[0].lower()
        elif excluder.endswith('.in'):
            assert len(args) == 1
            match = args[0]
        elif excluder.endswith('.match'):
            assert len(args) == 1
            match = args[0].lower()
            if misc.re_glob(match):
                regexp_match = re.compile(fnmatch.translate(match)).match
        elif excluder.endswith('.*'):
            assert len(args) == 0
        elif excluder.endswith('.marked'):
            assert len(args) == 0
        elif excluder.endswith('.washed'):
            assert len(args) == 0
        #  Really need to do this, need to cleanup pkgExcluder first though
        # or it does nothing.
        # self._pkgobjlist_dirty = True
        self._pkgExcluder.append((repoid, excluder, match, regexp_match))
        if excluderid is not None:
            self._pkgExcludeIds[excluderid] = len(self._pkgExcluder)

        self._exclude_whitelist = set()
        self._pkgobjlist_dirty  = True

    def _packageByKey(self, repo, pkgKey, exclude=True):
        """ Lookup a pkg by it's pkgKey, if we don't have it load it """
        # Speed hack, so we don't load the pkg. if the pkgKey is dead.
        assert exclude
        if exclude and self._pkgKeyExcluded(repo, pkgKey):
            return None

        if repo not in self._key2pkg:
            self._key2pkg[repo] = {}
            self._pkgname2pkgkeys[repo] = {}
        if pkgKey not in self._key2pkg[repo]:
            sql = "SELECT pkgKey, pkgId, name, epoch, version, release, arch " \
                  "FROM packages WHERE pkgKey = ?"
            data = self._sql_MD('primary', repo, sql, (pkgKey,)).fetchone()
            if data is None:
                msg = "pkgKey %s doesn't exist in repo %s" % (pkgKey, repo)
                raise Errors.RepoError, msg
            if exclude and self._pkgExcludedRKD(repo, pkgKey, data):
                return None
            po = self.pc(repo, data)
            self._key2pkg[repo][pkgKey] = po
            self._pkgtup2pkgs.setdefault(po.pkgtup, []).append(po)
            pkgkeys = self._pkgname2pkgkeys[repo].setdefault(data['name'], [])
            pkgkeys.append(pkgKey)
        elif exclude and self._pkgExcluded(self._key2pkg[repo][pkgKey]):
            self._delPackageRK(repo, pkgKey)
            return None
        return self._key2pkg[repo][pkgKey]
        
    def _packageByKeyData(self, repo, pkgKey, data, exclude=True):
        """ Like _packageByKey() but we already have the data for .pc() """
        assert exclude
        if exclude and self._pkgExcludedRKD(repo, pkgKey, data):
            return None
        if repo not in self._key2pkg:
            self._key2pkg[repo] = {}
            self._pkgname2pkgkeys[repo] = {}
        if data['pkgKey'] not in self._key2pkg.get(repo, {}):
            po = self.pc(repo, data)
            self._key2pkg[repo][pkgKey] = po
            self._pkgtup2pkgs.setdefault(po.pkgtup, []).append(po)
            pkgkeys = self._pkgname2pkgkeys[repo].setdefault(data['name'], [])
            pkgkeys.append(pkgKey)
        return self._key2pkg[repo][data['pkgKey']]

    def _pkgtupByKeyData(self, repo, pkgKey, data):
        """ Like _packageByKeyData() but we don't create the package, we just
            return the pkgtup. """
        if self._pkgExcludedRKD(repo, pkgKey, data):
            return None
        prepo = self._key2pkg.get(repo)
        if prepo is None:
            self._key2pkg[repo] = {}
            self._pkgname2pkgkeys[repo] = {}
        elif data['pkgKey'] in prepo:
            return prepo[data['pkgKey']].pkgtup
        return (data['name'], data['arch'],
                data['epoch'], data['version'], data['release'])

    def _packagesByName(self, pkgname):
        """ Load all pkgnames from cache, with a given name. """
        ret = []
        for repo in self.primarydb:
            pkgkeys = self._pkgname2pkgkeys.get(repo, {}).get(pkgname, [])
            if not pkgkeys:
                continue

            for pkgkey in pkgkeys:
                pkg = self._packageByKey(repo, pkgkey)
                if pkg is None:
                    continue
                ret.append(pkg)
        return ret

    def addDict(self, repo, datatype, dataobj, callback=None):
        if repo in self.added:
            if datatype in self.added[repo]:
                return
        else:
            self.added[repo] = []

        if repo not in self.excludes:
            self.excludes[repo] = {}

        if dataobj is None:
            raise Errors.RepoError, "Tried to add None %s to %s" % (datatype, repo)

        if datatype == 'metadata':
            self.primarydb[repo] = dataobj
        elif datatype == 'filelists':
            self.filelistsdb[repo] = dataobj
        elif datatype == 'otherdata':
            self.otherdb[repo] = dataobj
        else:
            # We can not handle this yet...
            raise Errors.RepoError, "Sorry sqlite does not support %s in %s" % (datatype, repo)
    
        self.added[repo].append(datatype)

        
    # Get all files for a certain pkgId from the filelists.xml metadata
    # Search packages that either provide something containing name
    # or provide a file containing name 
    def searchAll(self,name, query_type='like'):
        # this function is just silly and it reduces down to just this
        return self.searchPrco(name, 'provides')

    def _sql_pkgKey2po(self, repo, cur, pkgs=None, have_data=False):
        """ Takes a cursor and maps the pkgKey rows into a list of packages. """
        if pkgs is None: pkgs = []
        for ob in cur:
            if have_data:
                pkg = self._packageByKeyData(repo, ob['pkgKey'], ob)
            else:
                pkg = self._packageByKey(repo, ob['pkgKey'])
            if pkg is None:
                continue
            pkgs.append(pkg)
        return pkgs

    def _skip_all(self):
        """ Are we going to skip every package in all our repos? """
        skip_all = True
        for repo in self.added:
            if repo not in self._all_excludes:
                skip_all = False
                break
        return skip_all

    @catchSqliteException
    def _search_primary_files(self, name):
        querytype = 'glob'
        name = os.path.normpath(name)
        if not misc.re_glob(name):
            querytype = '='        
        results = []
        
        for (rep,cache) in self.primarydb.items():
            if rep in self._all_excludes:
                continue
            cur = cache.cursor()
            executeSQL(cur, "select DISTINCT pkgKey from files where name %s ?" % querytype, (name,))
            self._sql_pkgKey2po(rep, cur, results)

        return misc.unique(results)
        
    @catchSqliteException
    def _have_fastReturnFileEntries(self):
        """ Return true if pkg.returnFileEntries(primary_only=True) is fast.
            basically does "CREATE INDEX pkgfiles ON files (pkgKey);" exist. """

        for (rep,cache) in self.primarydb.items():
            if rep in self._all_excludes:
                continue
            cur = cache.cursor()
            executeSQL(cur, "PRAGMA index_info(pkgfiles)")
            #  If we get anything, we're fine. There might be a better way of
            # saying "anything" but this works.
            for ob in cur:
                break
            else:
                return False

        return True

    def have_fastReturnFileEntries(self):
        """ Is calling pkg.returnFileEntries(primary_only=True) faster than
            using searchFiles(). """
        if not hasattr(self, '_cached_fRFE'):
            self._cached_fRFE = self._have_fastReturnFileEntries()
        return self._cached_fRFE

    @catchSqliteException
    def searchFiles(self, name, strict=False):
        """search primary if file will be in there, if not, search filelists, use globs, if possible"""
        
        if self._skip_all():
            return []

        # optimizations:
        # if it is not  glob, then see if it is in the primary.xml filelists, 
        # if so, just use those for the lookup
        
        glob = True
        file_glob = True
        querytype = 'glob'
        name = os.path.normpath(name)
        dirname  = os.path.dirname(name)
        filename = os.path.basename(name)
        if strict or not misc.re_glob(name):
            glob = False
            file_glob = False
            querytype = '='
        elif not misc.re_glob(filename):
            file_glob = False

        # Take off the trailing slash to act like rpm
        if name[-1] == '/':
            name = name[:-1]
       
        pkgs = []

        # ultra simple optimization 
        if misc.re_primary_filename(name):
            if not misc.re_glob(dirname): # is the dirname a glob?
                return self._search_primary_files(name)
        
        if len(self.filelistsdb) == 0:
            # grab repo object from primarydb and force filelists population in this sack using repo
            # sack.populate(repo, mdtype, callback, cacheonly)
            for (repo,cache) in self.primarydb.items():
                if repo in self._all_excludes:
                    continue

                self.populate(repo, mdtype='filelists')

        # Check to make sure the DB data matches, this should always pass but
        # we've had weird errors. So check it for a bit.
        for repo in self.filelistsdb:
            # Only check each repo. once ... the libguestfs check :).
            if hasattr(repo, '_checked_filelists_pkgs'):
                continue
            pri_pkgs = self._sql_MD_pkg_num('primary',   repo)
            fil_pkgs = self._sql_MD_pkg_num('filelists', repo)
            if pri_pkgs != fil_pkgs:
                raise Errors.RepoError
            repo._checked_filelists_pkgs = True

        sql_params = []
        dirname_check = ""
        if not glob:
            (pattern, esc) = sql_esc(filename)
            dirname_check = "dirname = ? and filenames LIKE ? %s and " % esc
            sql_params.append(dirname)
            sql_params.append('%' + pattern + '%')
        elif not file_glob:
            (pattern, esc) = sql_esc(filename)
            dirname_check = "dirname GLOB ? and filenames LIKE ? %s and " % esc
            sql_params.append(dirname)
            sql_params.append('%' + pattern + '%')
        elif filename == '*':
            # We only care about matching on dirname...
            for (rep,cache) in self.filelistsdb.items():
                if rep in self._all_excludes:
                    continue

                cur = cache.cursor()
                sql_params.append(dirname)
                executeSQL(cur, """SELECT pkgKey FROM filelist
                                   WHERE dirname %s ?""" % (querytype,),
                           sql_params)
                self._sql_pkgKey2po(rep, cur, pkgs)

            return misc.unique(pkgs)

        for (rep,cache) in self.filelistsdb.items():
            if rep in self._all_excludes:
                continue

            cur = cache.cursor()

            # grab the entries that are a single file in the 
            # filenames section, use sqlites globbing if it is a glob
            executeSQL(cur, "select pkgKey from filelist where \
                    %s length(filetypes) = 1 and \
                    dirname || ? || filenames \
                    %s ?" % (dirname_check, querytype), sql_params + ['/',name])
            self._sql_pkgKey2po(rep, cur, pkgs)

            if file_glob:
                name_re = re.compile(fnmatch.translate(name))
            def filelist_globber(sql_dirname, sql_filenames):
                # Note: Can't return bool, because sqlite doesn't like it in
                #       weird ways. Test:
                #                         install '*bin/autoheader'
                #                         provides /lib/security/pam_loginuid.so
                files = sql_filenames.split('/')
                if not file_glob:
                    return int(filename in files)

                fns = map(lambda f: '%s/%s' % (sql_dirname, f), files)
                for match in fns:
                    if name_re.match(match):
                        return 1
                return 0

            cache.create_function("filelist_globber", 2, filelist_globber)
            # for all the ones where filenames is multiple files, 
            # make the files up whole and use python's globbing method
            executeSQL(cur, "select pkgKey from filelist where \
                             %s length(filetypes) > 1 \
                             and filelist_globber(dirname,filenames)" % dirname_check,
                       sql_params)

            self._sql_pkgKey2po(rep, cur, pkgs)

        pkgs = misc.unique(pkgs)
        return pkgs
        
    @catchSqliteException
    def searchPrimaryFields(self, fields, searchstring):
        """search arbitrary fields from the primarydb for a string"""
        if self._skip_all():
            return []

        result = []
        if len(fields) < 1:
            return result
        
        searchstring = searchstring.replace("'", "''")
        (searchstring, esc) = sql_esc(searchstring)
        sql = "select DISTINCT pkgKey from packages where %s like '%%%s%%'%s " % (fields[0], searchstring, esc)
        
        for f in fields[1:]:
            sql = "%s or %s like '%%%s%%'%s " % (sql, f, searchstring, esc)
        
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            executeSQL(cur, sql)
            self._sql_pkgKey2po(rep, cur, result)
        return result    

    @catchSqliteException
    def searchPrimaryFieldsMultipleStrings(self, fields, searchstrings):
        """search arbitrary fields from the primarydb for a multiple strings
           return packages, number of items it matched as a list of tuples"""
           
        if self._skip_all():
            return []

        result = [] # (pkg, num matches)
        if not fields or not searchstrings:
            return result
        
        # NOTE: I can't see any reason not to use this all the time, speed
        # comparison shows them as basically equal.
        if len(searchstrings) > (constants.PATTERNS_MAX / len(fields)):
            tot = {}
            for searchstring in searchstrings:
                matches = self.searchPrimaryFields(fields, searchstring)
                for po in matches:
                    tot[po] = tot.get(po, 0) + 1
            for po in sorted(tot, key=operator.itemgetter, reverse=True):
                result.append((po, tot[po]))
            return result
       
        unionstring = "select pkgKey, SUM(cumul) AS total from ( "
        endunionstring = ")GROUP BY pkgKey ORDER BY total DESC"
                
        #SELECT pkgkey, SUM(cumul) AS total FROM (SELECT pkgkey, 1 
        #AS cumul FROM packages WHERE description LIKE '%foo%' UNION ... ) 
        #GROUP BY pkgkey ORDER BY total DESC;
        selects = []
        
        for s in searchstrings:         
            s = s.replace("'", "''")
            (s, esc) = sql_esc(s)
            sql="select pkgKey,1 AS cumul from packages where %s like '%%%s%%'%s " % (fields[0], s, esc)
            for f in fields[1:]:
                sql = "%s or %s like '%%%s%%'%s " % (sql, f, s, esc)
            selects.append(sql)
        
        totalstring = unionstring + " UNION ALL ".join(selects) + endunionstring

        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            executeSQL(cur, totalstring)
            for ob in cur:
                pkg = self._packageByKey(rep, ob['pkgKey'])
                if pkg is None:
                    continue
                result.append((pkg, ob['total']))
        return result
        
    @catchSqliteException
    def returnObsoletes(self, newest=False):
        if self._skip_all():
            return {}

        if newest:
            raise NotImplementedError()

        obsoletes = {}
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            executeSQL(cur, "select packages.name as name,\
                packages.pkgKey as pkgKey,\
                packages.arch as arch, packages.epoch as epoch,\
                packages.release as release, packages.version as version,\
                obsoletes.name as oname, obsoletes.epoch as oepoch,\
                obsoletes.release as orelease, obsoletes.version as oversion,\
                obsoletes.flags as oflags\
                from obsoletes,packages where obsoletes.pkgKey = packages.pkgKey")
            for ob in cur:
                key = ( _share_data(ob['name']), _share_data(ob['arch']),
                        _share_data(ob['epoch']), _share_data(ob['version']),
                        _share_data(ob['release']))
                if self._pkgExcludedRKT(rep, ob['pkgKey'], key):
                    continue

                (n,f,e,v,r) = ( _share_data(ob['oname']),
                                _share_data(ob['oflags']),
                                _share_data(ob['oepoch']),
                                _share_data(ob['oversion']),
                                _share_data(ob['orelease']))

                key = _share_data(key)
                val = _share_data((n,f,(e,v,r)))
                obsoletes.setdefault(key,[]).append(val)

        return obsoletes

    @catchSqliteException
    def getPackageDetails(self,pkgId):
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            executeSQL(cur, "select * from packages where pkgId = ?", (pkgId,))
            for ob in cur:
                return ob
    
    @catchSqliteException
    def _getListofPackageDetails(self, pkgId_list):
        pkgs = []
        if len(pkgId_list) == 0:
            return pkgs
        pkgid_query = str(tuple(pkgId_list))

        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            executeSQL(cur, "select * from packages where pkgId in %s" %(pkgid_query,))
            for ob in cur:
                pkgs.append(ob)
        
        return pkgs
        
    @catchSqliteException
    def _search_get_memoize(self, prcotype):
        if not hasattr(self, '_memoize_' + prcotype):
            memoize = {}

            for (rep,cache) in self.primarydb.items():
                if rep in self._all_excludes:
                    continue

                cur = cache.cursor()
                executeSQL(cur, "select * from %s" % prcotype)
                for x in cur:
                    val = (_share_data(x['name']), _share_data(x['flags']),
                           (_share_data(x['epoch']), _share_data(x['version']),
                            _share_data(x['release'])))
                    val = _share_data(val)
                    key = (rep, val[0])
                    pkgkey = _share_data(x['pkgKey'])
                    val = (pkgkey, val)
                    memoize.setdefault(key, []).append(val)
            setattr(self, '_memoize_' + prcotype, memoize)
        return getattr(self, '_memoize_' + prcotype)

    @catchSqliteException
    def _search(self, prcotype, name, flags, version):

        if self._skip_all():
            return {}
        
        name = to_unicode(name)
        if flags == 0:
            flags = None
        if type(version) in (str, type(None), unicode):
            req = (name, flags, rpmUtils.miscutils.stringToVersion(
                version))
        elif type(version) in (tuple, list): # would this ever be a list?
            req = (name, flags, version)

        prcotype = _share_data(prcotype)
        req      = _share_data(req)
        if req in self._search_cache[prcotype]:
            return self._search_cache[prcotype][req]

        result = { }

        #  Requires is the biggest hit, pre-loading provides actually hurts
        #  NOTE: Disabling atm. ... small install/updates get a significant hit.
        # And even large updates take a hit with the memoize path, maybe we
        # fixed something with later change? ... maybe I was on crack?
        #  Speed seems to depend on _search_cache.
        if True: # prcotype != 'requires':
            primarydb_items = self.primarydb.items()
            preload = False
        else:
            primarydb_items = []
            preload = True
            memoize = self._search_get_memoize(prcotype)
            for (rep,cache) in self.primarydb.items():
                if rep in self._all_excludes:
                    continue

                tmp = {}
                for x in memoize.get((rep, name), []):
                    pkgkey, val = x
                    if rpmUtils.miscutils.rangeCompare(req, val):
                        tmp.setdefault(pkgkey, []).append(val)
                for pkgKey, hits in tmp.iteritems():
                    pkg = self._packageByKey(rep, pkgKey)
                    if pkg is None:
                        continue
                    result[pkg] = hits

        for (rep,cache) in primarydb_items:
            if rep in self._all_excludes:
                continue

            cur = cache.cursor()
            executeSQL(cur, "select * from %s where name=?" % prcotype,
                       (name,))
            tmp = { }
            for x in cur:
                val = (_share_data(x['name']), _share_data(x['flags']),
                       (_share_data(x['epoch']), _share_data(x['version']),
                        _share_data(x['release'])))
                val = _share_data(val)
                if rpmUtils.miscutils.rangeCompare(req, val):
                    tmp.setdefault(x['pkgKey'], []).append(val)
            for pkgKey, hits in tmp.iteritems():
                pkg = self._packageByKey(rep, pkgKey)
                if pkg is None:
                    continue
                result[pkg] = hits

        if prcotype != 'provides' or name[0] != '/':
            if not preload:
                self._search_cache[prcotype][req] = result
            return result

        if not misc.re_primary_filename(name):
            # If it is not in the primary.xml files
            # search the files.xml file info
            for pkg in self.searchFiles(name, strict=True):
                result[pkg] = [(name, None, None)]
            if not preload:
                self._search_cache[prcotype][req] = result
            return result

        # If it is a filename, search the primary.xml file info
        
        for pkg in self._search_primary_files(name):
            result[pkg] = [(name, None, None)]
            self._search_cache[prcotype][req] = result
        return result

    def getProvides(self, name, flags=None, version=(None, None, None)):
        return self._search("provides", name, flags, version)

    def getRequires(self, name, flags=None, version=(None, None, None)):
        return self._search("requires", name, flags, version)

    @catchSqliteException
    def searchNames(self, names=[], return_pkgtups=False):
        """return a list of packages matching any of the given names. This is 
           only a match on package name, nothing else"""
        
        if self._skip_all():
            return []
        
        loaded_all_names = hasattr(self, 'pkgobjlist')
        returnList = []
        user_names = set(names)
        names = []
        for pkgname in user_names:
            if pkgname in self._pkgmatch_fails:
                continue

            if loaded_all_names or pkgname in self._pkgnames_loaded:
                returnList.extend(self._packagesByName(pkgname))
            else:
                names.append(pkgname)

        if return_pkgtups:
            returnList = [pkg.pkgtup for pkg in returnList]
        if not names:
            return returnList

        max_entries = constants.PATTERNS_INDEXED_MAX
        if len(names) > max_entries:
            # Unique is done at user_names time, above.
            for names in seq_max_split(names, max_entries):
                returnList.extend(self.searchNames(names, return_pkgtups))
            return returnList

        pat_sqls = []
        qsql = """select pkgId,pkgKey,name,epoch,version,release,arch
                      from packages where """
        for name in names:
            pat_sqls.append("name = ?")
        qsql = qsql + " OR ".join(pat_sqls)

        for (repo, cache) in self.primarydb.items():
            cur = cache.cursor()
            executeSQL(cur, qsql, names)

            if return_pkgtups:
                for ob in cur:
                    pkgtup = self._pkgtupByKeyData(repo, ob['pkgKey'], ob)
                    if pkgtup is None:
                        continue
                    returnList.append(pkgtup)
                continue

            self._sql_pkgKey2po(repo, cur, returnList, have_data=True)

        if not return_pkgtups:
            # Mark all the processed pkgnames as fully loaded
            self._pkgnames_loaded.update([name for name in names])

        return returnList
 
    @catchSqliteException
    def searchPrco(self, name, prcotype):
        """return list of packages matching name and prcotype """
        # we take name to be a string of some kind
        # we parse the string to see if it is a foo > 1.1 or if it is just 'foo'
        # or what - so we can answer correctly
        
        if self._skip_all():
            return []
        try:
            (n,f,(e,v,r)) = misc.string_to_prco_tuple(name)
        except Errors.MiscError, e:
            raise Errors.PackageSackError, to_unicode(e)

        # The _b means this is a byte string
        # The _u means this is a unicode string
        # A bare n is used when, it's unicode but hasn't been evaluated
        # whether that's actually the right thing to do
        n_b = n
        n_u = to_unicode(n)
        n = n_u

        glob = True
        querytype = 'glob'
        if not misc.re_glob(n):
            glob = False
            querytype = '='

        basic_results = []
        results = []
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            executeSQL(cur, "select DISTINCT pkgKey from %s where name %s ?" % (prcotype,querytype), (n,))
            self._sql_pkgKey2po(rep, cur, basic_results)
        
        # now we have a list of items matching just the name - let's match them out
        for po in basic_results:
            if misc.re_filename(n) and v is None:
                # file dep add all matches to the results
                results.append(po)
                continue

            if not glob:
                if po.checkPrco(prcotype, (n_b, f, (e,v,r))):
                    results.append(po)
            else:
                # if it is a glob we can't really get any closer to checking it
                results.append(po)
        # If it's not a provides or a filename, we are done
        if prcotype != "provides":
            return results
        if not misc.re_filename(n):
            return results

        # If it is a filename, search the primary.xml file info
        results.extend(self._search_primary_files(n))

        # If it is in the primary.xml files then skip the other check
        if misc.re_primary_filename(n) and not glob:
            return misc.unique(results)

        # If it is a filename, search the files.xml file info
        results.extend(self.searchFiles(n))
        return misc.unique(results)

    def searchProvides(self, name):
        """return list of packages providing name (any evr and flag)"""
        if name in self._provmatch_fails:
            return []
        ret = self.searchPrco(name, "provides")
        if not ret:
            self._provmatch_fails.add(name)
        return ret
                
    def searchRequires(self, name):
        """return list of packages requiring name (any evr and flag)"""
        return self.searchPrco(name, "requires")

    def searchObsoletes(self, name):
        """return list of packages obsoleting name (any evr and flag)"""
        return self.searchPrco(name, "obsoletes")

    def searchConflicts(self, name):
        """return list of packages conflicting with name (any evr and flag)"""
        return self.searchPrco(name, "conflicts")


    def db2class(self, db, nevra_only=False):
        print 'die die die die die db2class'
        class tmpObject:
            pass
        y = tmpObject()
        
        y.nevra = (db['name'],db['epoch'],db['version'],db['release'],db['arch'])
        y.sack = self
        y.pkgId = db['pkgId']
        if nevra_only:
            return y
        
        y.hdrange = {'start': db['rpm_header_start'],'end': db['rpm_header_end']}
        y.location = {'href': db['location_href'],'value': '', 'base': db['location_base']}
        y.checksum = {'pkgid': 'YES','type': db['checksum_type'], 
                    'value': db['pkgId'] }
        y.time = {'build': db['time_build'], 'file': db['time_file'] }
        y.size = {'package': db['size_package'], 'archive': db['size_archive'], 'installed': db['size_installed'] }
        y.info = {'summary': db['summary'], 'description': db['description'],
                'packager': db['rpm_packager'], 'group': db['rpm_group'],
                'buildhost': db['rpm_buildhost'], 'sourcerpm': db['rpm_sourcerpm'],
                'url': db['url'], 'vendor': db['rpm_vendor'], 'license': db['rpm_license'] }
        return y

    @catchSqliteException
    def returnNewestByNameArch(self, naTup=None, patterns=None, ignore_case=False):

        # If naTup is set do it from the database otherwise use our parent's
        # returnNewestByNameArch
        if (not naTup):
            return yumRepo.YumPackageSack.returnNewestByNameArch(self, naTup,
                                                                 patterns,
                                                                 ignore_case)

        # First find all packages that fulfill naTup
        allpkg = []
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            executeSQL(cur, "select pkgId,pkgKey,name,epoch,version,release,arch from packages where name=? and arch=?", naTup)
            self._sql_pkgKey2po(rep, cur, allpkg, have_data=True)
        
        # if we've got zilch then raise
        if not allpkg:
            raise Errors.PackageSackError, 'No Package Matching %s.%s' % naTup
        return misc.newestInList(allpkg)

    @catchSqliteException
    def returnNewestByName(self, name=None, patterns=None, ignore_case=False):
        """return list of newest packages based on name matching
           this means(in name.arch form): foo.i386 and foo.noarch will
           be compared to each other for highest version.
           Note that given: foo-1.i386; foo-2.i386 and foo-3.x86_64
           The last _two_ pkgs will be returned, not just one of them. """
        # If name is set do it from the database otherwise use our parent's
        # returnNewestByName
        if self._skip_all():
            return []

        if (not name):
            return yumRepo.YumPackageSack.returnNewestByName(self, name,
                                                             patterns,
                                                             ignore_case)

        # First find all packages that fulfill name
        allpkg = []
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            executeSQL(cur, "select pkgId,pkgKey,name,epoch,version,release,arch from packages where name=?", (name,))
            self._sql_pkgKey2po(rep, cur, allpkg, have_data=True)
        
        # if we've got zilch then raise
        if not allpkg:
            raise Errors.PackageSackError, 'No Package Matching %s' % name
        return misc.newestInList(allpkg)

    # Do what packages.matchPackageNames does, but query the DB directly
    @catchSqliteException
    def matchPackageNames(self, pkgspecs):
        if self._skip_all():
            return [], [], []

        matched = []
        exactmatch = []
        unmatched = list(pkgspecs)

        for p in pkgspecs:
            if misc.re_glob(p):
                query = PARSE_QUERY % ({ "op": "glob", "q": p })
                matchres = matched
            else:
                query = PARSE_QUERY % ({ "op": "=", "q": p })
                matchres = exactmatch

            for (rep, db) in self.primarydb.items():
                cur = db.cursor()
                executeSQL(cur, query)
                pmatches = self._sql_pkgKey2po(rep, cur)
                if len(pmatches):
                    unmatched.remove(p)
                matchres.extend(pmatches)

        exactmatch = misc.unique(exactmatch)
        matched = misc.unique(matched)
        unmatched = misc.unique(unmatched)
        return exactmatch, matched, unmatched

    def _setupPkgObjList(self, repoid=None, patterns=None, ignore_case=False):
        """Setup need_full and patterns for _yieldSQLDataList, also see if
           we can get away with just using searchNames(). """

        if patterns is None:
            patterns = []

        fields = ['name', 'sql_nameArch', 'sql_nameVerRelArch',
                  'sql_nameVer', 'sql_nameVerRel',
                  'sql_envra', 'sql_nevra']
        need_full = False
        for pat in patterns:
            if (misc.re_full_search_needed(pat) and
                (ignore_case or pat not in self._pkgnames_loaded)):
                need_full = True
                break

        pat_max = constants.PATTERNS_MAX
        if not need_full:
            fields = ['name']
            pat_max = constants.PATTERNS_INDEXED_MAX
        if len(patterns) > pat_max:
            patterns = []
        if ignore_case:
            patterns = sql_esc_glob(patterns)
        else:
            tmp = []
            need_glob = False
            for pat in patterns:
                if misc.re_glob(pat):
                    tmp.append((pat, 'glob'))
                    need_glob = True
                else:
                    tmp.append((pat, '='))
            if not need_full and not need_glob and patterns:
                return (need_full, patterns, fields, True)
            patterns = tmp
        return (need_full, patterns, fields, False)

    @catchSqliteException
    def _yieldSQLDataList(self, repoid, patterns, fields, ignore_case):
        """Yields all the package data for the given params. Excludes are done
           at this stage. """

        pat_sqls = []
        pat_data = []
        for (pattern, rest) in patterns:
            if not ignore_case and pattern in self._pkgmatch_fails:
                continue

            for field in fields:
                if ignore_case:
                    pat_sqls.append("%s LIKE ?%s" % (field, rest))
                else:
                    pat_sqls.append("%s %s ?" % (field, rest))
                pat_data.append(pattern)
        if patterns and not pat_sqls:
            return

        if pat_sqls:
            qsql = _FULL_PARSE_QUERY_BEG + " OR ".join(pat_sqls)
        else:
            qsql = """select pkgId, pkgKey, name,epoch,version,release,arch
                      from packages"""

        for (repo,cache) in self.primarydb.items():
            if (repoid == None or repoid == repo.id):
                cur = cache.cursor()
                executeSQL(cur, qsql, pat_data)
                for x in cur:
                    yield (repo, x)

    def _buildPkgObjList(self, repoid=None, patterns=None, ignore_case=False):
        """Builds a list of packages, only containing nevra information.
           Excludes are done at this stage. """

        returnList = []

        data = self._setupPkgObjList(repoid, patterns, ignore_case)
        (need_full, patterns, fields, names) = data
        if names:
            return self.searchNames(patterns)

        for (repo, x) in self._yieldSQLDataList(repoid, patterns, fields,
                                                ignore_case):
            # Can't use: _sql_pkgKey2po because we change repos.
            po = self._packageByKeyData(repo, x['pkgKey'], x)
            if po is None:
                continue
            returnList.append(po)
        if not patterns and repoid is None:
            self.pkgobjlist = returnList
            self._pkgnames_loaded = set() # Save memory
        if not need_full and repoid is None:
            # Mark all the processed pkgnames as fully loaded
            self._pkgnames_loaded.update([po.name for po in returnList])
        if need_full:
            for (pat, rest) in patterns:
                if rest not in ('=', ''): # Wildcards: 'glob' or ' ESCAPE "!"'
                    continue
                for pkg in returnList:
                    if pkg.name == pat:
                        self._pkgnames_loaded.add(pkg.name)
                        break
        if not returnList:
            for (pat, rest) in patterns:
                self._pkgmatch_fails.add(pat)

        return returnList
                
    def returnPackages(self, repoid=None, patterns=None, ignore_case=False):
        """Returns a list of packages, only containing nevra information. The
           packages are processed for excludes. Note that the packages are
           always filtered to those matching the patterns/case. """

        if self._skip_all():
            return []

        internal_pkgoblist = hasattr(self, 'pkgobjlist')
        if internal_pkgoblist:
            pkgobjlist = self._clean_pkgobjlist()
        else:
            pkgobjlist = self._buildPkgObjList(repoid, patterns, ignore_case)
            internal_pkgoblist = hasattr(self, 'pkgobjlist')

        if internal_pkgoblist and patterns:
            internal_pkgoblist = False
            pkgobjlist = parsePackages(pkgobjlist, patterns, not ignore_case,
                                       unique='repo-pkgkey')
            pkgobjlist = pkgobjlist[0] + pkgobjlist[1]

        # Can't unexclude things, and new excludes are done above...
        if repoid is None:
            if internal_pkgoblist:
                pkgobjlist = pkgobjlist[:]
            return pkgobjlist

        returnList = []
        for po in pkgobjlist:
            if repoid != po.repoid:
                continue
            returnList.append(po)

        return returnList

    def simplePkgList(self, patterns=None, ignore_case=False):
        """Returns a list of pkg tuples (n, a, e, v, r), optionally from a
           single repoid. Note that the packages are always filtered to those
           matching the patterns/case. """

        if self._skip_all():
            return []

        internal_pkgoblist = hasattr(self, 'pkgobjlist')
        if internal_pkgoblist:
            return yumRepo.YumPackageSack.simplePkgList(self, patterns,
                                                        ignore_case)

        repoid = None
        returnList = []
        # Haven't loaded everything, so _just_ get the pkgtups...
        data = self._setupPkgObjList(repoid, patterns, ignore_case)
        (need_full, patterns, fields, names) = data
        if names:
            return [pkg.pkgtup for pkg in self.searchNames(patterns)]

        for (repo, x) in self._yieldSQLDataList(repoid, patterns, fields,
                                                ignore_case):
            # NOTE: Can't unexclude things...
            pkgtup = self._pkgtupByKeyData(repo, x['pkgKey'], x)
            if pkgtup is None:
                continue
            returnList.append(pkgtup)
        return returnList

    @catchSqliteException
    def searchNevra(self, name=None, epoch=None, ver=None, rel=None, arch=None):        
        """return list of pkgobjects matching the nevra requested"""
        if self._skip_all():
            return []

        returnList = []
        
        if name: # Almost always true...
            for pkg in self.searchNames(names=[name]):
                match = True
                for (col, var) in [('epoch', epoch), ('version', ver),
                                   ('arch', arch), ('release', rel)]:
                    if var and getattr(pkg, col) != var:
                        match = False
                        break
                if match:
                    returnList.append(pkg)
            return returnList

        # make sure some dumbass didn't pass us NOTHING to search on
        empty = True
        for arg in (name, epoch, ver, rel, arch):
            if arg:
                empty = False
        if empty:
            return returnList
        
        # make up our execute string
        q = "select pkgId,pkgKey,name,epoch,version,release,arch from packages WHERE"
        for (col, var) in [('name', name), ('epoch', epoch), ('version', ver),
                           ('arch', arch), ('release', rel)]:
            if var:
                if q[-5:] != 'WHERE':
                    q = q + ' AND %s = "%s"' % (col, var)
                else:
                    q = q + ' %s = "%s"' % (col, var)
            
        # Search all repositories            
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            executeSQL(cur, q)
            self._sql_pkgKey2po(rep, cur, returnList, have_data=True)
        return returnList
    
    @catchSqliteException
    def excludeArchs(self, archlist):
        """excludes incompatible arches - archlist is a list of compat arches"""

        if self._arch_allowed is None:
            self._arch_allowed = set(archlist)
        else:
            self._arch_allowed = self._arch_allowed.intersection(archlist)
        sarchlist = map(lambda x: "'%s'" % x , archlist)
        arch_query = ",".join(sarchlist)

        for (rep, cache) in self.primarydb.items():
            cur = cache.cursor()

            #  This is a minor hack opt. for source repos. ... if they are
            # enabled normally, we don't want to exclude each package so we
            # check it and exclude the entire thing.
            if not rep.id.endswith("-source") or 'src' in self._arch_allowed:
                continue
            has_arch = False
            executeSQL(cur, "SELECT DISTINCT arch FROM packages")
            for row in cur:
                if row[0] in archlist:
                    has_arch = True
                    break
            if not has_arch:
                self._delAllPackages(rep)
                return

# Simple helper functions

# Return a string representing filenamelist (filenames can not contain /)
def encodefilenamelist(filenamelist):
    return '/'.join(filenamelist)

# Return a list representing filestring (filenames can not contain /)
def decodefilenamelist(filenamestring):
    filenamestring = filenamestring.replace('//', '/')
    return filenamestring.split('/')

# Return a string representing filetypeslist
# filetypes should be file, dir or ghost
def encodefiletypelist(filetypelist):
    result = ''
    ft2string = {'file': 'f','dir': 'd','ghost': 'g'}
    for x in filetypelist:
        result += ft2string[x]
    return result

# Return a list representing filetypestring
# filetypes should be file, dir or ghost
def decodefiletypelist(filetypestring):
    string2ft = {'f':'file','d': 'dir','g': 'ghost'}
    return [string2ft[x] for x in filetypestring]


# Query used by matchPackageNames
# op is either '=' or 'like', q is the search term
# Check against name, nameArch, nameVerRelArch, nameVer, nameVerRel,
# envra, nevra
PARSE_QUERY = """
select pkgKey from packages
where name %(op)s '%(q)s'
   or name || '.' || arch %(op)s '%(q)s'
   or name || '-' || version %(op)s '%(q)s'
   or name || '-' || version || '-' || release %(op)s '%(q)s'
   or name || '-' || version || '-' || release || '.' || arch %(op)s '%(q)s'
   or epoch || ':' || name || '-' || version || '-' || release || '.' || arch %(op)s '%(q)s'
   or name || '-' || epoch || ':' || version || '-' || release || '.' || arch %(op)s '%(q)s'
"""

# This is roughly the same as above, and used by _buildPkgObjList().
#  Use " to quote because we using ? ... and sqlutils.QmarkToPyformat gets
# confused.
_FULL_PARSE_QUERY_BEG = """
SELECT pkgId,pkgKey,name,epoch,version,release,arch,
  name || "." || arch AS sql_nameArch,
  name || "-" || version || "-" || release || "." || arch AS sql_nameVerRelArch,
  name || "-" || version AS sql_nameVer,
  name || "-" || version || "-" || release AS sql_nameVerRel,
  epoch || ":" || name || "-" || version || "-" || release || "." || arch AS sql_envra,
  name || "-" || epoch || ":" || version || "-" || release || "." || arch AS sql_nevra
  FROM packages
  WHERE
"""
