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



import os
import os.path
import types

import Errors
from urlgrabber.grabber import URLGrabber
import urlgrabber.mirror
from urlgrabber.grabber import URLGrabError
from repomd import repoMDObject
from repomd import mdErrors
from repomd import packageSack
from packages import YumAvailablePackage
import mdcache

class YumPackageSack(repomd.packageSack.PackageSack):
    """imports/handles package objects from an mdcache dict object"""
    def __init__(self, packageClass):
        repomd.packageSack.PackageSack.__init__(self)
        self.pc = packageClass
        self.added = {}
        
    def addDict(self, repoid, datatype, datadict, callback=None):
        total = len(datadict.keys())
        if datatype == 'primary':
            for pkgid in datadict.keys():
                pkgdict = datadict[pkgid]
                po = self.pc()
                po.importFromDict(pkgdict, repoid)
                self._addToDictAsList(self.pkgsByID, pkgid, po)
                self.addPackage(po)
            
            if not self.added.has_key(repoid):
                self.added[repoid] = []
            self.added[repoid].append('primary')
            
        elif datatype == 'filelists':
            if self.added.has_key(repoid):
                if 'primary' not in self.added[repoid]:
                    raise Errors.RepoError, '%s md for %s imported before primary' \
                           % (datatype, repoid)
                           
            for pkgid in datadict.keys():
                pkgdict = datadict[pkgid]
                if self.pkgsByID.has_key(pkgid):
                    for po in self.pkgsByID[pkgid]:
                        po.importFromDict(pkgdict, repoid)

            self.added[repoid].append(datatype)
        else:
            # umm, wtf?
            pass
            
class RepoStorage:
    """This class contains multiple repositories and core configuration data
       about them."""
       
    def __init__(self):
        self.repos = {} # list of repos by repoid pointing a repo object 
                        # of repo options/misc data
        self.pkgSack = YumPackageSack(YumAvailablePackage)
        self.callback = None # progress callback used for populateSack() for importing the xml files
        self.cache = 0
        
    def add(self, repoid):
        if self.repos.has_key(repoid):
            raise Errors.RepoError, 'Repository %s already added, not adding again' % (repoid)
        thisrepo = Repository(repoid)
        self.repos[repoid] = thisrepo
        
        return thisrepo

    def delete(self, repoid):
        if self.repos.has_key(repoid):
            del self.repos[repoid]
            
    def sort(self):
        repolist = self.repos.values()
        repolist.sort()
        return repolist
        
    def getRepo(self, repoid):
        try:
            return self.repos[repoid]
        except KeyError, e:
            raise Errors.RepoError, \
                'Error getting repository data for %s, repository not found' % (repoid)

    def disableRepo(self, repoid):
        """disable a repository from use"""
        thisrepo = self.getRepo(repoid)
        thisrepo.disable()
            
    def enableRepo(self, repoid):
        """disable a repository from use"""
        thisrepo = self.getRepo(repoid)
        thisrepo.enable()
            
    def listEnabled(self):
        """return list of enabled repo objects"""
        returnlist = []
        for repo in self.repos.values():
            if repo.enabled:
                returnlist.append(repo)

        return returnlist

    def listGroupsEnabled(self):
        """return a list of repo objects that have groups enabled"""
        returnlist = []
        for repo in self.repos.values():
            if repo.enablegroups:
                returnlist.append(repo)

        return returnlist

    def setCache(self, cacheval):
        """set's cache value in all repos"""
        self.cache = cacheval
        for repo in self.repos.values():
            repo.cache = cacheval

    def setProgressBar(self, obj):
        """set's the progress bar for downloading files from repos"""
        
        for repo in self.repos.values():
            repo.callback = obj
            repo.setupGrab()

    def setFailureCallback(self, obj):
        """set's the failure callback for all repos"""
        
        for repo in self.repos.values():
            repo.failure_obj = obj
            repo.setupGrab()
            
                
    def populateSack(self, which='enabled', with='primary', callback=None):
        """This populates the package sack from the repositories, two optional 
           arguments: which='repoid, enabled, all'
                      with='primary, filelists, other, all'"""

        if not callback:
            callback = self.callback
        myrepos = []
        if which == 'enabled':
            myrepos = self.listEnabled()
        elif which == 'all':
            myrepos = self.repos.values()
        else:
            if type(which) == types.ListType:
                for repo in which:
                    repobj = self.getRepo(repo)
                    myrepos.append(repobj)
            elif type(which) == types.StringType:
                repobj = self.getRepo(which)
                myrepos.append(repobj)

        if with == 'all':
            data = ['primary', 'filelists', 'other']
        else:
            data = [ with ]
        
        for repo in myrepos:
            if not hasattr(repo, 'cacheHandler'):
                repo.cacheHandler = mdcache.RepodataParser(storedir=repo.cachedir, callback=callback)
            for item in data:
                if item == 'primary':
                    xml = repo.getPrimaryXML()
                    (ctype, csum) = repo.repoXML.primaryChecksum()
                    repo.cacheHandler.getPrimary(xml, csum)
                    data = repo.cacheHandler.repodata['metadata']
                    self.pkgSack.addDict(repo.id, item, data, callback) 
                elif item == 'filelists':
                    xml = repo.getFileListsXML()
                    (ctype, csum) = repo.repoXML.filelistsChecksum()
                    repo.cacheHandler.getFileLists(xml, csum)
                    data = repo.cacheHandler.repodata['filelists']
                    self.pkgSack.addDict(repo.id, item, data, callback) 
                elif item == 'other':
                    xml = repo.getOtherXML()
                    (ctype, csum) = repo.repoXML.otherChecksum()
                    repo.cacheHandler.getOtherdata(xml, csum)
                    data = repo.cacheHandler.repodata['otherdata']
                    self.pkgSack.addDict(repo.id, item, data, callback)
                else:
                    # how odd, just move along
                    continue
                

                
        
        
class Repository:
    """this is an actual repository object"""       

    def __init__(self, repoid):
        self.id = repoid
        self.name = repoid # name is repoid until someone sets it to a real name
        # some default (ish) things
        self.urls = []
        self.gpgcheck = 0
        self.enabled = 1
        self.enablegroups = 1  
        self.groupsfilename = 'yumgroups.xml' # something some freaks might 
                                              # eventually want
        self.setkeys = []
        self.repoMDFile = 'repodata/repomd.xml'
        self.repoXML = None
        self.cache = 0
        self.callback = None # callback for the grabber
        self.failure_obj = None
        
        # throw in some stubs for things that will be set by the config class
        self.cachedir = ""
        self.pkgdir = ""
        self.hdrdir = ""        
        # holder for stuff we've grabbed
        self.retrieved = { 'primary':0, 'filelists':0, 'other':0, 'groups':0 }

        
    def __cmp__(self, other):
        if self.id > other.id:
            return 1
        elif self.id < other.id:
            return -1
        else:
            return 0

    def __str__(self):
        return self.id

    def _checksum(self, sumtype, file, CHUNK=2**16):
        """takes filename, hand back Checksum of it
           sumtype = md5 or sha
           filename = /path/to/file
           CHUNK=65536 by default"""
           
        # chunking brazenly lifted from Ryan Tomayko
        try:
            if type(file) is not types.StringType:
                fo = file # assume it's a file-like-object
            else:           
                fo = open(file, 'r', CHUNK)
                
            if sumtype == 'md5':
                import md5
                sum = md5.new()
            elif sumtype == 'sha':
                import sha
                sum = sha.new()
            else:
                raise Errors.RepoError, 'Error Checksumming file, wrong \
                                         checksum type %s' % sumtype
            chunk = fo.read
            while chunk: 
                chunk = fo.read(CHUNK)
                sum.update(chunk)
    
            if type(file) is types.StringType:
                fo.close()
                del fo
                
            return sum.hexdigest()
        except (EnvironmentError, IOError, OSError):
            raise Errors.RepoError, 'Error opening file for checksum'
        
    def dump(self):
        string = 'repo: %s\n' % self.id
        for attr in dir(self):
            if attr not in ['id', 'set', 'unset', 'setFailover',
                            'remoteGroups', 'remoteMetadata', 'localGroups',
                            'baseURL', 'failed', 'repomd', '__str__', '__init__',
                            '__doc__', '__module__', '__cmp__', 'dump', 'enable',
                            'disable']:
                
                string = string + '%s = %s\n' % (attr, getattr(self, attr))
        
        return string
    
    def enable(self):
        self.set('enabled', 1)
    
    def disable(self):
        self.set('enabled', 0)
        
                
    def set(self, key, value):
        """sets a generic attribute of this repository"""
        self.setkeys.append(key)
        setattr(self, key, value)
        
    def unset(self, key):
        """delete an attribute of this repository"""
        self.setkeys.remove(key)
        delattr(self, key)
   
    def listSetKeys(self):
        return setkeys
        
    def setupGrab(self):
        """sets up the grabber functions with the already stocked in urls for
           the mirror groups"""

        # FIXME this should do things with our proxy info too
        if self.failovermethod == 'roundrobin':
            mgclass = urlgrabber.mirror.MGRandomOrder
        else:
            mgclass = urlgrabber.mirror.MirrorGroup
            
        self.grabfunc = URLGrabber(keepalive=self.keepalive, 
                                   bandwidth=self.bandwidth,
                                   retry=self.retries,
                                   throttle=self.throttle,
                                   progress_obj=self.callback,
                                   failure_callback=self.failure_obj)
                                   #reget='simple')
                                   
        self.grab = mgclass(self.grabfunc, self.urls)

    def dirSetup(self):
        """make the necessary dirs, if possible, raise on failure"""
        for dir in [self.cachedir, self.hdrdir, self.pkgdir]:
            if self.cache == 0:
                if os.path.exists(dir) and os.path.isdir(dir):
                    continue
                else:
                    try:
                        os.makedirs(dir, mode=0755)
                    except OSError, e:
                        raise Errors.RepoError, \
                            "Error making cache directory: %s error was: %s" % (dir, e)
            else:
                if not os.path.exists(dir):
                    raise Errors.RepoError, \
                        "Cannot access repository dir %s" % dir
 

    def get(self, url=None, relative=None, local=None, start=None, end=None,
            copy_local=0, checkfunc=None):
        """retrieve file from the mirrorgroup for the repo
           relative to local, optionally get range from
           start to end, also optionally retrieve from a specific baseurl"""
           
        # if local or relative is None: raise an exception b/c that shouldn't happen
        # if url is not None - then do a grab from the complete url - not through
        # the mirror, raise errors as need be
        # if url is None do a grab via the mirror group/grab for the repo
        # return the path to the local file

        if local is None or relative is None:
            raise Errors.RepoError, \
                  "get request for Repo %s, gave no source or dest" % self.id
                  
        if self.failure_obj:
            (f_func, f_args, f_kwargs) = self.failure_obj
            f_kwargs['relative'] = relative
            self.failure_obj = (f_func, f_args, f_kwargs)
        
        if self.cache == 1:
            if os.path.exists(local):
                return local
            else: # ain't there - raise
                raise Errors.RepoError, \
                    "Caching enabled but no local cache of %s from %s" % (local,
                           self)
        
        if url is not None:
            ug = URLGrabber(keepalive = self.keepalive, 
                            bandwidth = self.bandwidth,
                            retry = self.retries,
                            throttle = self.throttle,
                            progres_obj = self.callback,
                            copy_local = copy_local,
                            failure_callback = self.failure_obj,
                            checkfunc = checkfunc)
            
            remote = url + '/' + relative

            try:
                result = ug.urlgrab(remote, local,
                                    range = (start, end), 
                                    retry = self.retries,
                                    copy_local = copy_local,
                                    failure_callback = self.failure_obj,
                                    checkfunc = checkfunc)
            except URLGrabError, e:
                raise Errors.RepoError, \
                    "failed to retrieve %s from %s\nerror was %s" % (relative, self.id, e)
              
        else:
            try:
                result = self.grab.urlgrab(relative, local, range=(start, end),
                                           copy_local=copy_local,
                                           checkfunc=checkfunc)
            except URLGrabError, e:
                raise Errors.RepoError, "failure: %s from %s: %s" % (relative, self.id, e)
                
        return result
           
        
    def getRepoXML(self):
        """retrieve/check/read in repomd.xml from the repository"""

        remote = self.repoMDFile
        local = self.cachedir + '/repomd.xml'
        
        if self.cache == 1:
            if not os.path.exists(local):
                raise Errors.RepoError, 'Cannot find repomd.xml file for %s' % (self)
            else:
                result = local
        else:
            try:
                result = self.get(relative=remote, local=local, copy_local=1)
            except URLGrabError, e:
                raise Errors.RepoError, 'Error downloading file %s: %s' % (local, e)

        try:
            self.repoXML = repoMDObject.RepoMD(self.id, result)
        except mdErrors.RepoMDError, e:
            raise Errors.RepoError, 'Error importing repomd.xml from %s: %s' % (self, e)

    
    def _checkMD(self, fn, mdtype):
        """check the metadata type against its checksum"""
        
        csumDict = { 'primary' : self.repoXML.primaryChecksum,
                     'filelists' : self.repoXML.filelistsChecksum,
                     'other' : self.repoXML.otherChecksum,
                     'group' : self.repoXML.groupChecksum }
                     
        csumMethod = csumDict[mdtype]
        
        (r_ctype, r_csum) = csumMethod() # get the remote checksum
        
        try:
            l_csum = self._checksum(r_ctype, fn) # get the local checksum
        except Errors.RepoError, e:
            raise URLGrabError(-3, 'Error performing checksum')
            
        if l_csum == r_csum: 
            return 1
        else:
            raise URLGrabError(-1, 'Metadata file does not match checksum')
        

        
    def _retrieveMD(self, mdtype):
        """base function to retrieve metadata files from the remote url
           returns the path to the local metadata file of a 'mdtype'
           mdtype can be 'primary', 'filelists', 'other' or 'group'."""
        locDict = { 'primary' : self.repoXML.primaryLocation,
                    'filelists' : self.repoXML.filelistsLocation,
                    'other' : self.repoXML.otherLocation,
                    'group' : self.repoXML.groupLocation }
        
        locMethod = locDict[mdtype]
        
        (r_base, remote) = locMethod()
        fname = os.path.basename(remote)
        local = self.cachedir + '/' + fname

        if self.retrieved.has_key(mdtype):
            if self.retrieved[mdtype]: # got it, move along
                return local

        if self.cache == 1:
            if os.path.exists(local):
                try:
                    self._checkMD(local, mdtype)
                except URLGrabError, e:
                    raise Errors.RepoError, \
                        "Caching enabled and local cache: %s does not match checksum" % local
                else:
                    return local
                    
            else: # ain't there - raise
                raise Errors.RepoError, \
                    "Caching enabled but no local cache of %s from %s" % (local,
                           self)
                           
        if os.path.exists(local):
            try:
                self._checkMD(local, mdtype)
            except URLGrabError, e:
                pass
            else:
                self.retrieved[mdtype] = 1
                return local # it's the same return the local one

        try:
            checkfunc = (self._checkMD, (mdtype,), {})
            local = self.get(relative=remote, local=local, copy_local=1, checkfunc=checkfunc)
        except URLGrabError, e:
            raise Errors.RepoError, \
                "Could not retrieve %s matching remote checksum from %s" % (local, self)
        else:
            self.retrieved[mdtype] = 1
            return local

    
    def getPrimaryXML(self):
        """this gets you the path to the primary.xml file, retrieving it if we 
           need a new one"""

        return self._retrieveMD('primary')
        
    
    def getFileListsXML(self):
        """this gets you the path to the filelists.xml file, retrieving it if we 
           need a new one"""

        return self._retrieveMD('filelists')

    def getOtherXML(self):
        return self._retrieveMD('other')

    def getGroups(self):
        """gets groups and returns group file path for the repository, if there 
           is none it returns None"""
        try:
            file = self._retrieveMD('group')
        except URLGrabError:
            file = None
        
        return file
        
        
    

