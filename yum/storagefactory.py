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
# Copyright 2004 Duke University

import Errors

class Storage:

    def __init__(self):
        pass

    def Name(self):
        pass

    def GetCacheHandler(self, storedir, repoid, callback):
        pass

    def GetPackageSack(self):
        pass

class StorageSqlite(Storage):

    def __init__(self):
        import sqlitecache
        import sqlitesack

        self.sqlitecache = sqlitecache
        self.sqlitesack = sqlitesack

    def Name(self):
        return "sqlite"

    def GetCacheHandler(self, storedir, repoid, callback):
        return self.sqlitecache.RepodataParserSqlite(storedir, repoid, callback)

    def GetPackageSack(self):
        return self.sqlitesack.YumSqlitePackageSack(self.sqlitesack.YumAvailablePackageSqlite)


class StorageSqliteC(Storage):
    def __init__(self):
        import sqlitecachec
        import sqlitesack

        self.sqlitecache = sqlitecachec
        self.sqlitesack = sqlitesack

    def Name(self):
        return "sqlite-c"

    def GetCacheHandler(self, storedir, repoid, callback):
        return self.sqlitecache.RepodataParserSqlite(storedir, repoid, callback)

    def GetPackageSack(self):
        return self.sqlitesack.YumSqlitePackageSack(self.sqlitesack.YumAvailablePackageSqlite)


def GetStorage():
    storage = None

    # Try to load storages, prefering the fastest one.

    try:
        storage = StorageSqliteC()
        return storage
    except:
        pass

    try:
        storage = StorageSqlite()
        return storage
    except:
        pass

    raise Errors.YumBaseError, 'Could not find any working storages.'

