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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# Copyright 2005 Duke University 

import os
import os.path
import fnmatch

import yumRepo
from packages import PackageObject, RpmBase, YumAvailablePackage, parsePackages
import Errors
import misc

from sqlutils import executeSQL, sql_esc, sql_esc_glob
import dnf.rpmUtils.miscutils
import sqlutils
import constants
import operator
from misc import seq_max_split
from i18n import to_utf8, to_unicode
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
            if ob['pre'].lower() in ['true', 1]:
                pre = "1"
            prco_set = (_share_data(ob['name']), _share_data(ob['flags']),
                        (_share_data(ob['epoch']),
                         _share_data(ob['version']),
                         _share_data(ob['release'])), pre)
            requires.append(prco_set)
        return requires

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
