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
# Copyright 2009 Red Hat, Inc
# written by seth vidal

# parse sqlite tag database
# return pkgnames and tag that was matched
from sqlutils import sqlite, executeSQL, sql_esc
from Errors import PkgTagsError
import sqlutils
import sys
import misc

def catchSqliteException(func):
    """This decorator converts sqlite exceptions into PkgTagsError"""
    def newFunc(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except sqlutils.sqlite.Error, e:
            # 2.4.x requires this, but 2.6.x complains about even hasattr()
            # of e.message ... *sigh*
            if sys.hexversion < 0x02050000:
                if hasattr(e,'message'):
                    raise PkgTagsError, str(e.message)
                else:
                    raise PkgTagsError, str(e)
            raise PkgTagsError, str(e)

    newFunc.__name__ = func.__name__
    newFunc.__doc__ = func.__doc__
    newFunc.__dict__.update(func.__dict__)
    return newFunc



class PackageTagDB(object):
    @catchSqliteException
    def __init__(self, repoid, sqlite_file):
        self.sqlite_file = sqlite_file
        self.repoid = repoid
        # take a path to the sqlite tag db
        # open it and leave a cursor in place for the db
        self._conn = sqlite.connect(sqlite_file)
        self.cur = self._conn.cursor()

    def _getTagsCount(self):
        ''' Unused, so no need to cache. '''
        for n in self._sql_exec("select count(*) from packagetags",):
            return n[0]

    count = property(fget=lambda self: self._getTagsCount(),
                     doc="Number of entries in the pkgtag DB")
        
    @catchSqliteException
    def _sql_exec(self, sql, *args):
        """ Exec SQL against an MD of the repo, return a cursor. """
        
        executeSQL(self.cur, sql, *args)
        return self.cur
    
    def search_tags(self, tag):
        """Search by tag name/glob
           Return dict of dict[packagename] = [stringmatched, stringmatched, ...]"""
        res = {}
        (tag, esc) = sql_esc(tag)
        query = "SELECT name, tag, score FROM packagetags where tag like ? %s" % esc
        tag = '%' + tag + '%' 
        rows = self._sql_exec(query, (tag,))
        for (name, tag, score) in rows:
            if name not in res:
                res[name] = []
            res[name].append(tag)
            
        return res
        
    def search_names(self, name):
        """Search by package name/glob.
           Return dict of dict[packagename] = [tag1, tag2, tag3, tag4, ...]"""
        res = {}
        (name, esc) = sql_esc(name)
        query = "SELECT name, tag, score FROM packagetags where name like ?%s " % esc
        name = '%' + name + '%' 
        rows = self._sql_exec(query, (name,))
        for (name, tag, score) in rows:
            if name not in res:
                res[name] = []
            res[name].append(tag)

        return res

class PackageTags(object):
    def __init__(self):
        self.db_objs = {}
        
    def add(self, repoid, sqlite_file):
        if repoid in self.db_objs:
            raise PkgTagsError, "Already added tags from %s" % repoid
            
        dbobj = PackageTagDB(repoid, sqlite_file)
        self.db_objs[repoid] = dbobj

    def remove(self, repoid):
        if repoid in self.db_objs:
            del self.db_objs[repoid]
        else:
            raise PkgTagsError, "No tag db for %s" % repoid
    
    def search_names(self, name):
        res = {}
        for ptd in self.db_objs.values():
            for (name, taglist) in ptd.search_names(name).items():
                if not name in res:
                    res[name] = []
                res[name].extend(taglist)
        
        out = {}
        for (name, taglist) in res.items():
            out[name] = misc.unique(taglist)
        return out

    def search_tags(self, tagname):
        res = {}
        for ptd in self.db_objs.values():
            for (name, taglist) in ptd.search_tags(tagname).items():
                if not name in res:
                    res[name] = []
                res[name].extend(taglist)
        out = {}
        for (name, taglist) in res.items():
            out[name] = misc.unique(taglist)
        return out
        
