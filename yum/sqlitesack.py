#!/usr/bin/python -tt
#
# Implementation of the YumPackageSack class that uses an sqlite backend
#


import os
import os.path
import types
import repos
from packages import YumAvailablePackage
from repomd import mdUtils

# Simple subclass of YumAvailablePackage that can load 'simple headers' from
# the database when they are requested
class YumAvailablePackageSqlite(YumAvailablePackage):
    def __init__(self, pkgdict, repoid):
        YumAvailablePackage.__init__(self,pkgdict,repoid)
        self.sack = pkgdict.sack
        self.pkgId = pkgdict.pkgId
        self.simple['id'] = self.pkgId
        self.changelog = None
    
    def loadChangelog(self):
        self.changelog = self.sack.getChangelog(self.pkgId)

    def returnSimple(self, varname):
        if (not self.simple.has_key(varname) and not hasattr(self,'dbusedsimple')):
            # Make sure we only try once to get the stuff from the database
            self.dbusedsimple = 1
            details = self.sack.getPackageDetails(self.pkgId)
            self.importFromDict(details,self.simple['repoid'])

        return YumAvailablePackage.returnSimple(self,varname)

    def loadFiles(self):
        if (hasattr(self,'dbusedfiles')):
            return
        self.files = self.sack.getFiles(self.pkgId)
            
    def returnFileEntries(self, ftype='file'):
        self.loadFiles()
        return YumAvailablePackage.returnFileEntries(self,ftype)
    
    def returnFileTypes(self):
        self.loadFiles()
        return YumAvailablePackage.returnFileTypes(self)
        

class YumSqlitePackageSack(repos.YumPackageSack):
    """ Implementation of a PackageSack that uses sqlite cache instead of fully
    expanded metadata objects to provide information """

    def __init__(self, packageClass):
        # Just init as usual and create a dict to hold the databases
        repos.YumPackageSack.__init__(self,packageClass)
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
            print "Added filelists for %s" % (repoid)
        elif datatype == 'otherdata':
            if (self.otherdb.has_key(repoid)):
              return
            self.added[repoid] = ['otherdata']
            self.otherdb[repoid] = dataobj
            print "Added otherdata for %s" % (repoid)
        else:
            # We can not handle this yet...
            raise "Sorry sqlite does not support %s" % (datatype)
    
    def getChangelog(self,pkgId):
        result = []
        for (rep,cache) in self.filelistsdb.items():
            cur = cache.cursor()
            cur.execute("select * from packages,changelog where packages.pkgId = %s and packages.pkgKey = changelog.pkgKey",pkgId)
            for ob in cur.fetchall():
                result.append({ 'author': ob['author'],
                                'value': ob['changelog'],
                                'data': ob['data']
                              })
        return result

    # Get all files for a certain pkgId from the filelists.xml metadata
    def getFiles(self,pkgId):
        for (rep,cache) in self.filelistsdb.items():
            found = False
            result = {}
            cur = cache.cursor()
            cur.execute("select * from packages,filelist where packages.pkgId = %s and packages.pkgKey = filelist.pkgKey", pkgId)
            for ob in cur.fetchall():
                found = True
                dirname = ob['filelist.dirname']
                filetypes = ob['filelist.filetypes'].split('|')[1:-2]
                filenames = ob['filelist.filenames'].split('|')[1:-2]
                while(filenames):
                    filename = dirname+'/'+filenames.pop()
                    filetype = filetypes.pop()
                    result.setdefault(filetype,[]).append(filename)
            if (found):
                return result    
        return {}
            
    def returnObsoletes(self):
        obsoletes = {}
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            cur.execute("select * from obsoletes,packages where obsoletes.pkgKey = packages.pkgKey")
            for ob in cur.fetchall():
                # If the package that is causing the obsoletes is excluded
                # continue without processing the obsoletes
                if (self.excludes[rep].has_key(ob['packages.pkgId'])):
                    continue
                key = ( ob['packages.name'],ob['packages.arch'],
                        ob['packages.epoch'],ob['packages.version'],
                        ob['packages.release'])
                (n,f,e,v,r) = ( ob['obsoletes.name'],ob['obsoletes.flags'],
                                ob['obsoletes.epoch'],ob['obsoletes.version'],
                                ob['obsoletes.release'])

                obsoletes.setdefault(key,[]).append((n,f,(e,v,r)))

        return obsoletes

    def getPackageDetails(self,pkgId):
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            cur.execute("select * from packages where pkgId = %s",pkgId)
            for ob in cur.fetchall():
                pkg = self.db2class(ob)
                return pkg
    
    def searchProvides(self, name):
        """return list of package providing the name (any evr and flag)"""
        provides = []
        # First search the provides cache
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            cur.execute("select * from provides where name = %s" , (name))
            provs = cur.fetchall()
            for res in provs:
                cur.execute("select * from packages where pkgKey = %s" , (res['pkgKey']))
                for x in cur.fetchall():
                    pkg = self.db2class(x)
                    if (self.excludes[rep].has_key(pkg.pkgId)):
                        continue
                                            
                    # Add this provides to prco otherwise yum doesn't understand
                    # that it matches
                    pkg.prco = {'provides': 
                      [
                      { 'name': res.name,
                        'flags': res.flags,
                        'rel': res.release,
                        'ver': res.version,
                        'epoch': res.epoch
                      }
                      ]
                    }
                    provides.append(self.pc(pkg,rep))

        # If it's not a filename, we are done
        if (name.find('/') != 0):
            return provides

        # If it is a filename, search the primary.xml file info
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            cur.execute("select * from files where name = %s" , (name))
            provs = cur.fetchall()
            for res in provs:
                cur.execute("select * from packages where pkgKey = %s" , (res['pkgKey']))
                for x in cur.fetchall():
                    pkg = self.db2class(x)
                    if (self.excludes[rep].has_key(pkg.pkgId)):
                        continue
                                            
                    pkg.files = {name: res['type']}
                    provides.append(self.pc(pkg,rep))

        # If it is a filename, search the primary.xml file info
        for (rep,cache) in self.filelistsdb.items():
            cur = cache.cursor()
            (dirname,filename) = os.path.split(name)
            cur.execute("select * from filelist,packages where dirname = %s AND filelist.pkgKey = packages.pkgKey" , (dirname))
            provs = cur.fetchall()
            for res in provs:
                if (self.excludes[rep].has_key(res['packages.pkgId'])):
                    continue
                                        
                # If it matches the dirname, that doesnt mean it matches
                # the filename, check if it does
                if (filename and res['filelist.filenames'].find('|%s|' % filename) == -1):
                    continue
                # If it matches we only know the packageId
                pkg = self.getPackageDetails(res['packages.pkgId'])
                provides.append(self.pc(pkg,rep))
        return provides
                
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
      y.location = {'href': db.location_href,'value':''}
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
            # TODO process obsoletes here
            return repos.YumPackageSack.returnNewestByNameArch(self, naTup)

        # First find all packages that fulfill naTup
        allpkg = []
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            cur.execute("select pkgId,name,epoch,version,release,arch from packages where name=%s and arch=%s",naTup)
            for x in cur.fetchall():
                if (self.excludes[rep].has_key(x.pkgId)):
                    continue                    
                allpkg.append = self.pc(self.db2class(x,True),rep) 
        # Now find the newest one
        newest = allpkg.pop()
        for pkg in allpkg:
            (e2, v2, r2) = newest.returnEVR()
            (e,v,r) = pkg.returnEVR()
            rc = mdUtils.compareEVR((e,v,r), (e2, v2, r2))
            if (rc > 0):
                newest = pkg
        return newest

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
        # Search all repositories
        for (rep,cache) in self.primarydb.items():
            cur = cache.cursor()
            cur.execute("select * from packages WHERE name = %s AND epoch = %s AND version = %s AND release = %s AND arch = %s" , (name,epoch,ver,rel,arch))
            for x in cur.fetchall():
                if (self.excludes[rep].has_key(x.pkgId)):
                    continue
                returnList.append(self.pc(self.db2class(x),rep))
        return returnList
