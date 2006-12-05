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

# TODO
# - Add support for multiple checksums per rpm (not required)

import os
import sqlite
import time
import mdparser
import logging
import logginglevels
from sqlitesack import encodefiletypelist,encodefilenamelist

# This version refers to the internal structure of the sqlite cache files
# increasing this number forces all caches of a lower version number
# to be re-generated
dbversion = '9'

class RepodataParserSqlite:
    def __init__(self, storedir, repoid, callback=None):
        self.storedir = storedir
        self.callback = callback
        self.repodata = {
            'metadata': {},
            'filelists': {},
            'otherdata': {}
        }
        self.repoid = repoid
        self.debug = 0
        self.logger = logging.getLogger("yum.RepodataParserSqlite")
        self.verbose_logger = \
            logging.getLogger("yum.verbose.RepodataParserSqlite")

    def loadCache(self,filename):
        """Load cache from filename, check if it is valid and that dbversion 
        matches the required dbversion"""
        db = sqlite.connect(filename)
        cur = db.cursor()
        cur.execute("select * from db_info")
        info = cur.fetchone()
        # If info is not in there this is an incompelete cache file
        # (this could happen when the user hits ctrl-c or kills yum
        # when the cache is being generated or updated)
        if (not info):
            raise sqlite.DatabaseError, "Incomplete database cache file"

        # Now check the database version
        if (info['dbversion'] != dbversion):
            self.verbose_logger.log(logginglevels.INFO_2, "Warning: cache file is version %s, we need %s, will regenerate", info['dbversion'], dbversion)
            raise sqlite.DatabaseError, "Older version of yum sqlite"

        # This appears to be a valid database, return checksum value and 
        # database object
        return (info['checksum'],db)
        
    def getFilename(self,location):
        return location + '.sqlite'
            
    def getDatabase(self, location, cachetype):
        filename = self.getFilename(location)
        dbchecksum = ''
        # First try to open an existing database
        try:
            (dbchecksum,db) = self.loadCache(filename)
        except (IOError,sqlite.DatabaseError,KeyError):
            # If it doesn't exist, create it
            db = self.makeSqliteCacheFile(filename,cachetype)
        return (db,dbchecksum)

    def _getbase(self, location, checksum, metadatatype):
        (db, dbchecksum) = self.getDatabase(location, metadatatype)
        # db should now contain a valid database object, check if it is
        # up to date
        if (checksum != dbchecksum):
            self.verbose_logger.debug("%s sqlite cache needs updating, reading in metadata", 
                metadatatype)
            parser = mdparser.MDParser(location)
            self.updateSqliteCache(db, parser, checksum, metadatatype)
        db.commit()
        return db

    def getPrimary(self, location, checksum):
        """Load primary.xml.gz from an sqlite cache and update it 
           if required"""
        return self._getbase(location, checksum, 'primary')

    def getFilelists(self, location, checksum):
        """Load filelist.xml.gz from an sqlite cache and update it if 
           required"""
        return self._getbase(location, checksum, 'filelists')

    def getOtherdata(self, location, checksum):
        """Load other.xml.gz from an sqlite cache and update it if required"""
        return self._getbase(location, checksum, 'other')
         
    def createTablesFilelists(self,db):
        """Create the required tables for filelists metadata in the sqlite 
           database"""
        cur = db.cursor()
        self.createDbInfo(cur)
        # This table is needed to match pkgKeys to pkgIds
        cur.execute("""CREATE TABLE packages(
            pkgKey INTEGER PRIMARY KEY,
            pkgId TEXT)
        """)
        cur.execute("""CREATE TABLE filelist(
            pkgKey INTEGER,
            dirname TEXT,
            filenames TEXT,
            filetypes TEXT)
        """)
        cur.execute("CREATE INDEX keyfile ON filelist (pkgKey)")
        cur.execute("CREATE INDEX pkgId ON packages (pkgId)")
    
    def createTablesOther(self,db):
        """Create the required tables for other.xml.gz metadata in the sqlite 
           database"""
        cur = db.cursor()
        self.createDbInfo(cur)
        # This table is needed to match pkgKeys to pkgIds
        cur.execute("""CREATE TABLE packages(
            pkgKey INTEGER PRIMARY KEY,
            pkgId TEXT)
        """)
        cur.execute("""CREATE TABLE changelog(
            pkgKey INTEGER,
            author TEXT,
            date TEXT,
            changelog TEXT)
        """)
        cur.execute("CREATE INDEX keychange ON changelog (pkgKey)")
        cur.execute("CREATE INDEX pkgId ON packages (pkgId)")
        
    def createTablesPrimary(self,db):
        """Create the required tables for primary metadata in the sqlite 
           database"""

        cur = db.cursor()
        self.createDbInfo(cur)
        # The packages table contains most of the information in primary.xml.gz

        q = 'CREATE TABLE packages(\n' \
            'pkgKey INTEGER PRIMARY KEY,\n'

        cols = []
        for col in PackageToDBAdapter.COLUMNS:
            cols.append('%s TEXT' % col)
        q += ',\n'.join(cols) + ')'

        cur.execute(q)

        # Create requires, provides, conflicts and obsoletes tables
        # to store prco data
        for t in ('requires','provides','conflicts','obsoletes'):
            extraCol = ""
            if t == 'requires':
                extraCol= ", pre BOOL DEFAULT FALSE"
            cur.execute("""CREATE TABLE %s (
              name TEXT,
              flags TEXT,
              epoch TEXT,
              version TEXT,
              release TEXT,
              pkgKey TEXT %s)
            """ % (t, extraCol))
        # Create the files table to hold all the file information
        cur.execute("""CREATE TABLE files (
            name TEXT,
            type TEXT,
            pkgKey TEXT)
        """)
        # Create indexes for faster searching
        cur.execute("CREATE INDEX packagename ON packages (name)")
        cur.execute("CREATE INDEX providesname ON provides (name)")
        cur.execute("CREATE INDEX packageId ON packages (pkgId)")
        db.commit()
    
    def createDbInfo(self,cur):
        # Create the db_info table, this contains sqlite cache metadata
        cur.execute("""CREATE TABLE db_info (
            dbversion TEXT,
            checksum TEXT)
        """)

    def insertHash(self,table,hash,cursor):
        """Insert the key value pairs in hash into a database table"""

        keys = hash.keys()
        values = hash.values()
        query = "INSERT INTO %s (" % (table)
        query += ",".join(keys)
        query += ") VALUES ("
        # Quote all values by replacing None with NULL and ' by ''
        for x in values:
            if (x == None):
              query += "NULL,"
            else:
              try:
                query += "'%s'," % (x.replace("'","''"))
              except AttributeError:
                query += "'%s'," % x
        # Remove the last , from query
        query = query[:-1]
        # And replace it with )
        query += ")"
        cursor.execute(query.encode('utf8'))
        return cursor.lastrowid
             
    def makeSqliteCacheFile(self, filename, cachetype):
        """Create an initial database in the given filename"""

        # If it exists, remove it as we were asked to create a new one
        if (os.path.exists(filename)):
            self.verbose_logger.debug("Warning: cache already exists, removing old version")
            try:
                os.unlink(filename)
            except OSError:
                pass

        # Try to create the databse in filename, or use in memory when
        # this fails
        try:
            db = sqlite.connect(filename) 
        except IOError:
            self.verbose_logger.log(logginglevels.INFO_1, "Warning could not create sqlite cache file, using in memory cache instead")
            db = sqlite.connect(":memory:")

        # The file has been created, now create the tables and indexes
        if (cachetype == 'primary'):
            self.createTablesPrimary(db)
        elif (cachetype == 'filelists'):
            self.createTablesFilelists(db)
        elif (cachetype == 'other'):
            self.createTablesOther(db)
        else:
            raise sqlite.DatabaseError, "Sorry don't know how to store %s" % (cachetype)
        return db

    def addPrimary(self, pkgId, package, cur):
        """Add a package to the primary cache"""
        # Store the package info into the packages table
        pkgKey = self.insertHash('packages', PackageToDBAdapter(package), cur)

        # Now store all prco data
        for ptype in package.prco:
            for entry in package.prco[ptype]:
                data = {
                    'pkgKey': pkgKey,
                    'name': entry.get('name'),
                    'flags': entry.get('flags'),
                    'epoch': entry.get('epoch'),
                    'version': entry.get('ver'),
                    'release': entry.get('rel'),
                }
                if ptype == 'requires' and entry.has_key('pre'):
                    if entry.get('pre'):
                        data['pre'] = True
                self.insertHash(ptype,data,cur)
        
        # Now store all file information
        for f in package.files:
            data = {
                'name': f,
                'type': package.files[f],
                'pkgKey': pkgKey,
            }
            self.insertHash('files',data,cur)

    def addFilelists(self, pkgId, package,cur):
        """Add a package to the filelists cache"""
        pkginfo = {'pkgId': pkgId}
        pkgKey = self.insertHash('packages',pkginfo, cur)
        dirs = {}
        for (filename,filetype) in package.files.iteritems():
            (dirname,filename) = (os.path.split(filename))
            if (dirs.has_key(dirname)):
                dirs[dirname]['files'].append(filename)
                dirs[dirname]['types'].append(filetype)
            else:
                dirs[dirname] = {}
                dirs[dirname]['files'] = [filename]
                dirs[dirname]['types'] = [filetype]

        for (dirname,dir) in dirs.items():
            data = {
                'pkgKey': pkgKey,
                'dirname': dirname,
                'filenames': encodefilenamelist(dir['files']),
                'filetypes': encodefiletypelist(dir['types'])
            }
            self.insertHash('filelist',data,cur)

    def addOther(self, pkgId, package,cur):
        pkginfo = {'pkgId': pkgId}
        pkgKey = self.insertHash('packages', pkginfo, cur)
        for entry in package['changelog']:
            data = {
                'pkgKey': pkgKey,
                'author': entry.get('author'),
                'date': entry.get('date'),
                'changelog': entry.get('value'),
            }
            self.insertHash('changelog', data, cur)

    def updateSqliteCache(self, db, parser, checksum, cachetype):
        """Update the sqlite cache by making it fit the packages described
        in dobj (info that has been read from primary.xml metadata) afterwards
        update the checksum of the database to checksum"""
       
        t = time.time()
        delcount = 0
        newcount = 0

        # We start be removing the old db_info, as it is no longer valid
        cur = db.cursor()
        cur.execute("DELETE FROM db_info") 

        # First create a list of all pkgIds that are in the database now
        cur.execute("SELECT pkgId, pkgKey from packages")
        currentpkgs = {}
        for pkg in cur.fetchall():
            currentpkgs[pkg['pkgId']] = pkg['pkgKey']

        if (cachetype == 'primary'):
            deltables = ("packages","files","provides","requires", 
                        "conflicts","obsoletes")
        elif (cachetype == 'filelists'):
            deltables = ("packages","filelist")
        elif (cachetype == 'other'):
            deltables = ("packages","changelog")
        else:
            raise sqlite.DatabaseError,"Unknown type %s" % (cachetype)
        
        # Add packages that are not in the database yet and build up a list of
        # all pkgids in the current metadata

        all_pkgIds = {}
        for package in parser:

            if self.callback is not None:
                self.callback.progressbar(parser.count, parser.total, self.repoid)

            pkgId = package['pkgId']
            all_pkgIds[pkgId] = 1

            # This package is already in the database, skip it now
            if (currentpkgs.has_key(pkgId)):
                continue

            # This is a new package, lets insert it
            newcount += 1
            if cachetype == 'primary':
                self.addPrimary(pkgId, package, cur)
            elif cachetype == 'filelists':
                self.addFilelists(pkgId, package, cur)
            elif cachetype == 'other':
                self.addOther(pkgId, package, cur)

        # Remove those which are not in dobj
        delpkgs = []
        for (pkgId, pkgKey) in currentpkgs.items():
            if not all_pkgIds.has_key(pkgId):
                delcount += 1
                delpkgs.append(str(pkgKey))
        delpkgs = "("+",".join(delpkgs)+")"
        for table in deltables:
            cur.execute("DELETE FROM "+table+ " where pkgKey in %s" % delpkgs)

        cur.execute("INSERT into db_info (dbversion,checksum) VALUES (%s,%s)",
                (dbversion,checksum))
        db.commit()
        self.verbose_logger.log(logginglevels.INFO_2, "Added %s new packages, deleted %s old in %.2f seconds",
            newcount, delcount, time.time()-t)
        return db

    def log(self, level, msg):
        '''Log to callback (if set)
        '''
        if self.callback:
            self.callback.log(level, msg)

class PackageToDBAdapter:

    '''
    Adapt a PrimaryEntry instance to suit the sqlite database. 

    This hides certain attributes and converts some column names in order to
    decouple the parser implementation from the sqlite database schema.
    '''

    NAME_MAPS = {
        'rpm_package': 'package',
        'version': 'ver',
        'release': 'rel',
        'rpm_license': 'license',
        'rpm_vendor': 'vendor',
        'rpm_group': 'group',
        'rpm_buildhost': 'buildhost',
        'rpm_sourcerpm': 'sourcerpm',
        'rpm_packager': 'packager',
        }
    
    COLUMNS = (
            'pkgId',
            'name',
            'arch',
            'version',
            'epoch',
            'release',
            'summary',
            'description',
            'url',
            'time_file',
            'time_build',
            'rpm_license',
            'rpm_vendor',
            'rpm_group',
            'rpm_buildhost',
            'rpm_sourcerpm',
            'rpm_header_start',
            'rpm_header_end',
            'rpm_packager',
            'size_package',
            'size_installed',
            'size_archive',
            'location_href',
            'location_base',
            'checksum_type',
            'checksum_value',
            )

    def __init__(self, package):
        self._pkg = package

    def __getitem__(self, k):
        return self._pkg[self.NAME_MAPS.get(k, k)]

    def keys(self):
        return self.COLUMNS

    def values(self):
        out = []
        for k in self.keys():
            out.append(self[k])
        return out

