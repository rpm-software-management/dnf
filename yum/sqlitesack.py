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
import types
import re
import repos
import yumRepo
from packages import YumAvailablePackage
import Errors
import misc

# Simple subclass of YumAvailablePackage that can load 'simple headers' from
# the database when they are requested
class YumAvailablePackageSqlite(YumAvailablePackage):
    def __init__(self, pkgdict, repoid):
        YumAvailablePackage.__init__(self, repoid, pkgdict)
        self.sack = pkgdict.sack
        self.pkgId = pkgdict.pkgId
        self.simple['id'] = self.pkgId
        self.changelog = None
    
    def loadChangelog(self):
        if hasattr(self, 'dbusedother'):
            return
        self.dbusedother = 1
        self.changelog = self.sack.getChangelog(self.pkgId)

    def returnSimple(self, varname):
        if (not self.simple.has_key(varname) and not hasattr(self,'dbusedsimple')):
            # Make sure we only try once to get the stuff from the database
            self.dbusedsimple = 1
            details = self.sack.getPackageDetails(self.pkgId)
            self.importFromDict(details)

        return YumAvailablePackage.returnSimple(self,varname)

    def loadFiles(self):
        if (hasattr(self,'dbusedfiles')):
            return
        self.dbusedfiles = 1
        self.files = self.sack.getFiles(self.pkgId)

    def returnChangelog(self):
        self.loadChangelog()
        return YumAvailablePackage.returnChangelog(self)
            
    def returnFileEntries(self, ftype='file'):
        self.loadFiles()
        return YumAvailablePackage.returnFileEntries(self,ftype)
    
    def returnFileTypes(self):
        self.loadFiles()
        return YumAvailablePackage.returnFileTypes(self)

    def returnPrco(self, prcotype):
        if not self.prco[prcotype]:
           self.prco = self.sack.getPrco(self.pkgId, prcotype)
        return self.prco[prcotype]

class YumSqlitePackageSack(yumRepo.YumPackageSack):
    """ Implementation of a PackageSack that uses sqlite cache instead of fully
    expanded metadata objects to provide information """

    def __init__(self, packageClass):
        # Just init as usual and create a dict to hold the databases
        yumRepo.YumPackageSack.__init__(self,packageClass)
        self.primarydb = {}
        self.filelistsdb = {}
        self.otherdb = {}
        self.excludes = {}
        
    def buildIndexes(self):
        # We don't need these
        return

    def _checkIndexes(self, failure='error'):
        return

    # Remove a package
    # Because we don't want to remove a package from the database we just
    # add it to the exclude list
    def delPackage(self, obj):
        repoid = obj.repoid
        self.excludes[repoid][obj.pkgId] = 1

    def addDict(self, repoid, datatype, dataobj, callback=None):
        if (not self.excludes.has_key(repoid)): 
            self.excludes[repoid] = {}
        if datatype == 'metadata':
            if (self.primarydb.has_key(repoid)):
              return
            self.added[repoid] = ['primary']
            self.primarydb[repoid] = dataobj
        elif datatype == 'filelists':
            if (self.filelistsdb.has_key(repoid)):
              return
            self.added[repoid] = ['filelists']
            self.filelistsdb[repoid] = dataobj
        elif datatype == 'otherdata':
            if (self.otherdb.has_key(repoid)):
              return
            self.added[repoid] = ['otherdata']
            self.otherdb[repoid] = dataobj
        else:
            # We can not handle this yet...
            raise "Sorry sqlite does not support %s" % (datatype)
    
    def getChangelog(self,pkgId):
        result = []
        for (rep,cache) in self.otherdb.items():
            cur = cache.cursor()
            cur.execute("select changelog.date as date,\
                changelog.author as author,\
                changelog.changelog as changelog from packages,changelog where packages.pkgId = %s and packages.pkgKey = changelog.pkgKey",pkgId)
            for ob in cur.fetchall():
                result.append(( ob['date'],
                                ob['author'],
                                ob['changelog']
                              ))
        return result

    def getPrco(self,pkgId, prcotype=None):
        if prcotype is not None:
            result = {'requires': [], 'provides': [], 'obsoletes': [], 'conflicts': []}
        else:
            result = { prcotype: [] }
        for (rep, cache) in self.primarydb.items():
            cur = cache.cursor()
            for prco in result.keys():
                cur.execute("select %s.name as name, %s.version as version,\
                    %s.release as release, %s.epoch as epoch, %s.flags as flags\
                    from packages,%s\
                    where packages.pkgId = %s and packages.pkgKey = %s.pkgKey", prco, prco, prco, prco, prco, prco, pkgId, prco)
                for ob in cur.fetchall():
                    name = ob['name']
                    version = ob['version']
                    release = ob['release']
                    epoch = ob['epoch']
                    flags = ob['flags']
                    result[prco].append((name, flags, (epoch, version, release)))
        return result

    # Get all files for a certain pkgId from the filelists.xml metadata
    def getFiles(self,pkgId):
        for (rep,cache) in self.filelistsdb.items():
            found = False
            result = {}
            cur = cache.cursor()
            cur.execute("select filelist.dirname as dirname,\
                filelist.filetypes as filetypes,\
                filelist.filenames as filenames from packages,filelist\
                where packages.pkgId = %s and packages.pkgKey = filelist.pkgKey", pkgId)
            for ob in cur.fetchall():
                found = True
                dirname = ob['dirname']
                filetypes = decodefiletypelist(ob['filetypes'])
                filenames = decodefilenamelist(ob['filenames'])
                while(filenames):
                    if dirname:
                        filename = dirname+'/'+filenames.pop()
                    else:
                        filename = filenames.pop()
                    filetype = filetypes.pop()
                    result.setdefault(filetype,[]).append(filename)
            if (found):
                return result    
        return {}
            
    # Search packages that either provide something containing name
    # or provide a file containing name 
    def searchAll(self,name, query_type='like'):
    
        # This should never be called with a name containing a %
        assert(name.find('%') == -1)
        result = []
        quotename = name.replace("'","''")
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            cur.execute("select DISTINCT packages.pkgId as pkgId from provides,packages where provides.name LIKE '%%%s%%' AND provides.pkgKey = packages.pkgKey" % quotename)
            for ob in cur.fetchall():
                if (self.excludes[rep].has_key(ob['pkgId'])):
                    continue
                pkg = self.getPackageDetails(ob['pkgId'])
                result.append((self.pc(pkg,rep)))

        for (rep,cache) in self.filelistsdb.items():
            cur = cache.cursor()
            (dir,filename) = os.path.split(quotename)
            # This query means:
            # Either name is a substring of dirname or the directory part
            # in name is a substring of dirname and the file part is part
            # of filelist
            cur.execute("select packages.pkgId as pkgId,\
                filelist.dirname as dirname,\
                filelist.filetypes as filetypes,\
                filelist.filenames as filenames \
                from packages,filelist where \
                (filelist.dirname LIKE '%%%s%%' \
                OR (filelist.dirname LIKE '%%%s%%' AND\
                filelist.filenames LIKE '%%%s%%'))\
                AND (filelist.pkgKey = packages.pkgKey)" % (quotename,dir,filename))
                    
        # cull the results for false positives
        for ob in cur.fetchall():
            # Check if it is an actual match
            # The query above can give false positives, when
            # a package provides /foo/aaabar it will also match /foo/bar
            if (self.excludes[rep].has_key(ob['pkgId'])):
                continue
            real = False
            for filename in decodefilenamelist(ob['filenames']):
                if (ob['dirname']+'/'+filename).find(name) != -1:
                    real = True
            if (not real):
                continue
            pkg = self.getPackageDetails(ob['pkgId'])
            result.append((self.pc(pkg,rep)))
        return result     
    
    def returnObsoletes(self):
        obsoletes = {}
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            cur.execute("select packages.name as name,\
                packages.pkgId as pkgId,\
                packages.arch as arch, packages.epoch as epoch,\
                packages.release as release, packages.version as version,\
                obsoletes.name as oname, obsoletes.epoch as oepoch,\
                obsoletes.release as orelease, obsoletes.version as oversion,\
                obsoletes.flags as oflags\
                from obsoletes,packages where obsoletes.pkgKey = packages.pkgKey")
            for ob in cur.fetchall():
                # If the package that is causing the obsoletes is excluded
                # continue without processing the obsoletes
                if (self.excludes[rep].has_key(ob['pkgId'])):
                    continue
                key = ( ob['name'],ob['arch'],
                        ob['epoch'],ob['version'],
                        ob['release'])
                (n,f,e,v,r) = ( ob['oname'],ob['oflags'],
                                ob['oepoch'],ob['oversion'],
                                ob['orelease'])

                obsoletes.setdefault(key,[]).append((n,f,(e,v,r)))

        return obsoletes

    def getPackageDetails(self,pkgId):
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            cur.execute("select * from packages where pkgId = %s",pkgId)
            for ob in cur.fetchall():
                pkg = self.db2class(ob)
                return pkg

    def searchPrco(self, name, prcotype):
        """return list of packages having prcotype name (any evr and flag)"""
        results = []
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            cur.execute("select * from %s where name = %s" , (prcotype, name))
            prcos = cur.fetchall()
            for res in prcos:
                cur.execute("select * from packages where pkgKey = %s" , (res['pkgKey']))
                for x in cur.fetchall():
                    pkg = self.db2class(x)
                    if (self.excludes[rep].has_key(pkg.pkgId)):
                        continue
                                            
                    # Add this provides to prco otherwise yum doesn't understand
                    # that it matches
                    pkg.prco = {prcotype: 
                      [
                      { 'name': res.name,
                        'flags': res.flags,
                        'rel': res.release,
                        'ver': res.version,
                        'epoch': res.epoch
                      }
                      ]
                    }
                    results.append(self.pc(pkg,rep))


        # If it's not a provides or a filename, we are done
        if prcotype != "provides" or name[0] != '/':
            return results

        # If it is a filename, search the primary.xml file info
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            cur.execute("select * from files where name = %s" , (name))
            files = cur.fetchall()
            for res in files:
                cur.execute("select * from packages where pkgKey = %s" , (res['pkgKey']))
                for x in cur.fetchall():
                    pkg = self.db2class(x)
                    if (self.excludes[rep].has_key(pkg.pkgId)):
                        continue
                                            
                    pkg.files = {name: res['type']}
                    results.append(self.pc(pkg,rep))

        matched = 0
        globs = ['.*bin\/.*', '^\/etc\/.*', '^\/usr\/lib\/sendmail$']
        for glob in globs:
            globc = re.compile(glob)
            if globc.match(name):
                matched = 1

        if matched: # if its in the primary.xml files then skip the other check
            return results
        
        # If it is a filename, search the files.xml file info
        for (rep,cache) in self.filelistsdb.items():
            cur = cache.cursor()
            (dirname,filename) = os.path.split(name)
            if name.find('%') == -1: # no %'s in the thing safe to LIKE
                cur.execute("select packages.pkgId as pkgId,\
                    filelist.dirname as dirname,\
                    filelist.filetypes as filetypes,\
                    filelist.filenames as filenames \
                    from packages,filelist where \
                    (filelist.dirname LIKE '%%%s%%' \
                    OR (filelist.dirname LIKE '%%%s%%' AND\
                    filelist.filenames LIKE '%%%s%%'))\
                    AND (filelist.pkgKey = packages.pkgKey)" % (name,dir,filename))
            else: 
                cur.execute("select packages.pkgId as pkgId,\
                    filelist.dirname as dirname,\
                    filelist.filetypes as filetypes,\
                    filelist.filenames as filenames \
                    from filelist,packages where dirname = %s AND filelist.pkgKey = packages.pkgKey" , (dirname))

            files = cur.fetchall()
            
            for res in files:
                if (self.excludes[rep].has_key(res['pkgId'])):
                    continue
                
                quicklookup = {}
                for fn in decodefilenamelist(res['filenames']):
                    quicklookup[fn] = 1
                    
                # If it matches the dirname, that doesnt mean it matches
                # the filename, check if it does
                if filename and not quicklookup.has_key(filename):
                    continue
                
                # If it matches we only know the packageId
                pkg = self.getPackageDetails(res['pkgId'])
                results.append(self.pc(pkg,rep))
        
        return results

    def searchProvides(self, name):
        """return list of packages providing name (any evr and flag)"""
        return self.searchPrco(name, "provides")
                
    def searchRequires(self, name):
        """return list of packages requiring name (any evr and flag)"""
        return self.searchPrco(name, "requires")

    def searchObsoletes(self, name):
        """return list of packages obsoleting name (any evr and flag)"""
        return self.searchPrco(name, "obsoletes")

    def searchConflicts(self, name):
        """return list of packages conflicting with name (any evr and flag)"""
        return self.searchPrco(name, "conflicts")

    # TODO this seems a bit ugly and hackish
    def db2class(self,db,nevra_only=False):
      class tmpObject:
        pass
      y = tmpObject()
      y.nevra = (db.name,db.epoch,db.version,db.release,db.arch)
      y.sack = self
      y.pkgId = db.pkgId
      if (nevra_only):
        return y
      y.hdrange = {'start': db.rpm_header_start,'end': db.rpm_header_end}
      y.location = {'href': db.location_href,'value': '', 'base': db.location_base}
      y.checksum = {'pkgid': 'YES','type': db.checksum_type, 
                    'value': db.checksum_value }
      y.time = {'build': db.time_build, 'file': db.time_file }
      y.size = {'package': db.size_package, 'archive': db.size_archive, 'installed': db.size_installed }
      y.info = {'summary': db.summary, 'description': db['description'],
                'packager': db.rpm_packager, 'group': db.rpm_group,
                'buildhost': db.rpm_buildhost, 'sourcerpm': db.rpm_sourcerpm,
                'url': db.url, 'vendor': db.rpm_vendor, 'license': db.rpm_license }
      return y

    def simplePkgList(self, repoid=None):
        """returns a list of pkg tuples (n, a, e, v, r) optionally from a single repoid"""
        simplelist = []
        for (rep,cache) in self.primarydb.items():
            if (repoid == None or repoid == rep):
                cur = cache.cursor()
                cur.execute("select pkgId,name,epoch,version,release,arch from packages")
                for pkg in cur.fetchall():
                    if (self.excludes[rep].has_key(pkg.pkgId)):
                        continue                        
                    simplelist.append((pkg.name, pkg.arch, pkg.epoch, pkg.version, pkg.release)) 
                    
        return simplelist

    def returnNewestByNameArch(self, naTup=None):
        # If naTup is set do it from the database otherwise use our parent's
        # returnNewestByNameArch
        if (not naTup):
            # TODO process excludes here
            return yumRepo.YumPackageSack.returnNewestByNameArch(self, naTup)

        # First find all packages that fulfill naTup
        allpkg = []
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            cur.execute("select pkgId,name,epoch,version,release,arch from packages where name=%s and arch=%s",naTup)
            for x in cur.fetchall():
                if (self.excludes[rep].has_key(x.pkgId)):
                    continue                    
                allpkg.append(self.pc(self.db2class(x,True),rep))
        
        # if we've got zilch then raise
        if not allpkg:
            raise Errors.PackageSackError, 'No Package Matching %s.%s' % naTup
        return misc.newestInList(allpkg)

    def returnNewestByName(self, name=None):
        # If name is set do it from the database otherwise use our parent's
        # returnNewestByName
        if (not name):
            return yumRepo.YumPackageSack.returnNewestByName(self, name)

        # First find all packages that fulfill name
        allpkg = []
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            cur.execute("select pkgId,name,epoch,version,release,arch from packages where name=%s", name)
            for x in cur.fetchall():
                if (self.excludes[rep].has_key(x.pkgId)):
                    continue                    
                allpkg.append(self.pc(self.db2class(x,True),rep))
        
        # if we've got zilch then raise
        if not allpkg:
            raise Errors.PackageSackError, 'No Package Matching %s' % name
        return misc.newestInList(allpkg)

    def returnPackages(self, repoid=None):
        """Returns a list of packages, only containing nevra information """
        returnList = []
        for (rep,cache) in self.primarydb.items():
            if (repoid == None or repoid == rep):
                cur = cache.cursor()
                cur.execute("select pkgId,name,epoch,version,release,arch from packages")
                for x in cur.fetchall():
                    if (self.excludes[rep].has_key(x.pkgId)):
                        continue                    
                    returnList.append(self.pc(self.db2class(x,True),rep))
        return returnList

    def searchNevra(self, name=None, epoch=None, ver=None, rel=None, arch=None):        
        """return list of pkgobjects matching the nevra requested"""
        returnList = []
        
        # make sure some dumbass didn't pass us NOTHING to search on
        empty = True
        for arg in (name, epoch, ver, rel, arch):
            if arg:
                empty = False
        if empty:
            return returnList
        
        # make up our execute string
        q = "select * from packages WHERE"
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
            #cur.execute("select * from packages WHERE name = %s AND epoch = %s AND version = %s AND release = %s AND arch = %s" , (name,epoch,ver,rel,arch))
            cur.execute(q)
            for x in cur.fetchall():
                if (self.excludes[rep].has_key(x.pkgId)):
                    continue
                returnList.append(self.pc(self.db2class(x),rep))
        return returnList
    
    def excludeArchs(self, archlist):
        """excludes incompatible arches - archlist is a list of compat arches"""
        tmpstring = "select * from packages WHERE "
        for arch in archlist:
            tmpstring = tmpstring + 'arch != "%s" AND ' % arch
        
        last = tmpstring.rfind('AND') # clip that last AND
        querystring = tmpstring[:last]
        for (rep, cache) in self.primarydb.items():
            cur = cache.cursor()
            cur.execute(querystring)
            for x in cur.fetchall():
                obj = self.pc(self.db2class(x), rep)
                self.delPackage(obj)

# Simple helper functions

# Return a string representing filenamelist (filenames can not contain /)
def encodefilenamelist(filenamelist):
    return '/'.join(filenamelist)

# Return a list representing filestring (filenames can not contain /)
def decodefilenamelist(filenamestring):
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

