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
import re
import yumRepo
from packages import YumAvailablePackage
import Errors
import misc

# Simple subclass of YumAvailablePackage that can load 'simple headers' from
# the database when they are requested
class YumAvailablePackageSqlite(YumAvailablePackage):
    def __init__(self, repo, pkgdict):
        YumAvailablePackage.__init__(self, repo, pkgdict)
        self.sack = pkgdict.sack
        self.pkgId = pkgdict.pkgId
        self.simple['id'] = self.pkgId
        self._changelog = None
        
    def returnSimple(self, varname):
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
                         'license' : 'rpm_license'
                        }
        if not self.simple.has_key(varname):
            dbname = varname
            if db2simplemap.has_key(varname):
                dbname = db2simplemap[varname]
            cache = self.sack.primarydb[self.repo]
            c = cache.cursor()
            query = "select %s from packages where pkgId = '%s'" % (dbname, self.pkgId)
            #c.execute("select %s from packages where pkgId = %s",
            #          dbname, self.pkgId)
            c.execute(query)
            r = c.fetchone()
            self.simple[varname] = r[0]
            
        return YumAvailablePackage.returnSimple(self,varname)
    
    def _loadChecksums(self):
        if not self._checksums:
            cache = self.sack.primarydb[self.repo]
            c = cache.cursor()
            query = "select checksum_type, checksum_value from packages where pkgId = '%s'" % self.pkgId
            c.execute(query)
            for ob in c.fetchall():
                self._checksums.append((ob['checksum_type'], ob['checksum_value'], True))

    
    def returnChecksums(self):
        self._loadChecksums()
        return self._checksums

        
    def _loadFiles(self):
        if self._loadedfiles:
            return
        result = {}
        self.files = result        
        #FIXME - this should be try, excepting
        self.sack.populate(self.repo, with='filelists')
        cache = self.sack.filelistsdb[self.repo]
        cur = cache.cursor()
        cur.execute("select filelist.dirname as dirname, "
                    "filelist.filetypes as filetypes, " 
                    "filelist.filenames as filenames from packages,filelist "
                    "where packages.pkgId = %s and "
                    "packages.pkgKey = filelist.pkgKey", self.pkgId)
        for ob in cur.fetchall():
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
        self._loadedfiles = True
        self.files = result

    def _loadChangelog(self):
        result = []
        if not self._changelog:
            if not self.sack.otherdb.has_key(self.repo):
                #FIXME should this raise an exception or should it try to populate
                # the otherdb
                self._changelog = result
                return
            cache = self.sack.otherdb[self.repo]
            cur = cache.cursor()
            cur.execute("select changelog.date as date, "
                        "changelog.author as author, "
                        "changelog.changelog as changelog "
                        "from packages,changelog where packages.pkgId = %s "
                        "and packages.pkgKey = changelog.pkgKey", self.pkgId)
            for ob in cur.fetchall():
                result.append( (ob['date'], ob['author'], ob['changelog']) )
        self._changelog = result
    
    def returnChangelog(self):
        self._loadChangelog()
        return self._changelog
    
    def returnFileEntries(self, ftype='file'):
        self._loadFiles()
        return YumAvailablePackage.returnFileEntries(self,ftype)
    
    def returnFileTypes(self):
        self._loadFiles()
        return YumAvailablePackage.returnFileTypes(self)

    def returnPrco(self, prcotype, printable=False):
        if not self.prco[prcotype]:
            cache = self.sack.primarydb[self.repo]
            cur = cache.cursor()
            query = "select %s.name as name, %s.version as version, "\
                        "%s.release as release, %s.epoch as epoch, "\
                        "%s.flags as flags from packages,%s "\
                        "where packages.pkgId = '%s' and "\
                        "packages.pkgKey = %s.pkgKey" % (prcotype, prcotype, 
                        prcotype, prcotype, prcotype, prcotype, self.pkgId, 
                        prcotype)
            cur.execute(query)
            for ob in cur.fetchall():
                self.prco[prcotype].append((ob['name'], ob['flags'],
                                           (ob['epoch'], ob['version'], 
                                            ob['release'])))

        return YumAvailablePackage.returnPrco(self, prcotype, printable)

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
        repo = obj.repo
        self.excludes[repo][obj.pkgId] = 1

    def addDict(self, repo, datatype, dataobj, callback=None):
        if (not self.excludes.has_key(repo)): 
            self.excludes[repo] = {}
        if datatype == 'metadata':
            if (self.primarydb.has_key(repo)):
              return
            self.added[repo] = ['primary']
            self.primarydb[repo] = dataobj
        elif datatype == 'filelists':
            if (self.filelistsdb.has_key(repo)):
              return
            self.added[repo] = ['filelists']
            self.filelistsdb[repo] = dataobj
        elif datatype == 'otherdata':
            if (self.otherdb.has_key(repo)):
              return
            self.added[repo] = ['otherdata']
            self.otherdb[repo] = dataobj
        else:
            # We can not handle this yet...
            raise "Sorry sqlite does not support %s" % (datatype)
    
    # Get all files for a certain pkgId from the filelists.xml metadata
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
                result.append((self.pc(rep,pkg)))

        for (rep,cache) in self.filelistsdb.items():
            cur = cache.cursor()
            (dirname,filename) = os.path.split(quotename)
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
                AND (filelist.pkgKey = packages.pkgKey)" % (quotename,dirname,filename))
                    
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
            result.append((self.pc(rep,pkg)))
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
                    results.append(self.pc(rep,pkg))


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
                    results.append(self.pc(rep,pkg))

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
                    AND (filelist.pkgKey = packages.pkgKey)" % (name,dirname,filename))
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
                results.append(self.pc(rep,pkg))
        
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

    def simplePkgList(self):
        """returns a list of pkg tuples (n, a, e, v, r) from the sack"""
        
        if hasattr(self, 'pkglist'):
            if self.pkglist:
                return self.pkglist
            
        simplelist = []
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            cur.execute("select pkgId,name,epoch,version,release,arch from packages")
            for pkg in cur.fetchall():
                if (self.excludes[rep].has_key(pkg.pkgId)):
                    continue                        
                simplelist.append((pkg.name, pkg.arch, pkg.epoch, pkg.version, pkg.release)) 
        
        self.pkglist = simplelist
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
                allpkg.append(self.pc(rep,self.db2class(x,True)))
        
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
                allpkg.append(self.pc(rep,self.db2class(x,True)))
        
        # if we've got zilch then raise
        if not allpkg:
            raise Errors.PackageSackError, 'No Package Matching %s' % name
        return misc.newestInList(allpkg)

    def returnPackages(self, repoid=None):
        """Returns a list of packages, only containing nevra information """
        returnList = []
        for (repo,cache) in self.primarydb.items():
            if (repoid == None or repoid == repo.id):
                cur = cache.cursor()
                cur.execute("select pkgId,name,epoch,version,release,arch from packages")
                for x in cur.fetchall():
                    if (self.excludes[repo].has_key(x.pkgId)):
                        continue
                    returnList.append(self.pc(repo,self.db2class(x,True)))
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
                returnList.append(self.pc(rep,self.db2class(x)))
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
                obj = self.pc(rep,self.db2class(x))
                self.delPackage(obj)

# Simple helper functions

# Return a string representing filenamelist (filenames can not contain /)
def encodefilenamelist(filenamelist):
    return '/'.join(filenamelist)

# Return a list representing filestring (filenames can not contain /)
def decodefilenamelist(filenamestring):
    return misc.unique(filenamestring.split('/'))

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

