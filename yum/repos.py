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
from metadata import repoMDObject
from metadata import mdErrors
from metadata import packageSack
from metadata import packageObject
from packages import YumAvailablePackage

class RepoStorage:
    """This class contains multiple repositories and core configuration data
       about them."""
       
    def __init__(self):
        self.repos = {} # list of repos by repoid pointing a repo object 
                        # of repo options/misc data
        self.pkgSack = packageSack.XMLPackageSack(YumAvailablePackage)
        self.callback = None # progress callback used for populateSack()
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
        
        # FIXME !!!!
        # MAybe worth looking at using excludelist here
        # pop open another packageSack, fill it with packages
        # matching the exclude list as we go. Use it to check 
        # for excluded packages without having to remove them from
        # a usable set in case someone wants to re-include them later.
        for repo in myrepos:
            for item in data:
                if item == 'primary':
                    xml = repo.getPrimaryXML(cache=self.cache)
                elif item == 'filelists':
                    xml = repo.getFileListsXML(cache=self.cache)
                elif item == 'other':
                    xml = repo.getOtherXML(cache=self.cache)
                else:
                    # how odd, just move along
                    continue
                self.pkgSack.addFile(repo.id, xml, callback)
                    

                
        
        
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
        
        # throw in some stubs for things that will be set by the config class
        self.cache = ""
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
        except EnvironmentError:
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
                                   throttle=self.throttle)
                                   
        # FIXME - needs a failure callback and it needs  to specify it
        self.grab = mgclass(self.grabfunc, self.urls)

        
    def remoteGroups(self):
        return os.path.join(self.baseURL(), self.groupsfilename)
    
    def localGroups(self):
        return os.path.join(self.cache, self.groupsfilename)

    def baseURL(self):
        return self.failover.get_serverurl()
        
    def failed(self):
        self.failover.server_failed()

    def dirSetup(self, cache=0):
        """make the necessary dirs, if possible, raise on failure"""
        for dir in [self.cache, self.hdrdir, self.pkgdir]:
            if not cache:
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
            copy_local=0):
        """retrieve file from the mirrorgroup for the repo
           relative to local, optionally get range from
           start to end, also optionally retrieve from a specific baseurl"""
           
        # if local or relative is None: raise an exception b/c that shouldn't happen
        # if url is not None - then do a grab from the complete url - not through
        # the mirror, raise errors as need be
        # if url is None do a grab via the mirror group/grab for the repo
        # return the path to the local file

        # FIXME we need a failure callback!!!
        if local is None or relative is None:
            raise Errors.RepoError, \
                  "get request for Repo %s, gave no source or dest" % self.id
        if url is not None:
            ug = URLGrabber(keepalive=self.keepalive, 
                       bandwidth=self.bandwidth,
                       retry=self.retries,
                       throttle=self.throttle)
            remote=url + '/' + relative
            try:           
                result = ug.urlgrab(remote, local, range=(start, end), 
                                    copy_local=copy_local)
            except URLGrabError, e:
                raise Errors.RepoError, \
                    "failed to retrieve %s from %s\nerror was %s" % (relative, self.id, e)
              
            # setup a grabber and use it - same general rules
        else:
            try:
                result = self.grab.urlgrab(relative, local, range=(start, end),
                                           copy_local=copy_local)
            except URLGrabError, e:
                raise "failed to retrieve %s from %s\nerror was %s" % (relative, self.id, e)
                
        return result
           
        
    def getRepoXML(self, cache=0):
        """retrieve/check/read in repomd.xml from the repository"""

        remote = self.repoMDFile
        local = self.cache + '/repomd.xml'
        if cache:
            if not os.path.exists(local):
                raise Errors.RepoError, 'Cannot find repomd.xml file for %s' % (self)
        else:
            try:
                local = self.get(relative=remote, local=local, copy_local=1)
            except URLGrabError, e:
                raise Errors.RepoError, 'Error downloading file %s: %s' % (local, e)

        try:
            self.repoXML = repoMDObject.RepoMD(self.id, local)
        except mdErrors.RepoMDError, e:
            raise Errors.RepoError, 'Error importing repomd.xml from %s: %s' % (self, e)

        
    def _retrieveMD(self, mdtype, cache=0):
        """base function to retrieve data from the remote url"""
        locDict = { 'primary' : self.repoXML.primaryLocation,
                    'filelists' : self.repoXML.filelistsLocation,
                    'other' : self.repoXML.otherLocation,
                    'group' : self.repoXML.groupLocation }
        
        csumDict = { 'primary' : self.repoXML.primaryChecksum,
                     'filelists' : self.repoXML.filelistsChecksum,
                     'other' : self.repoXML.otherChecksum,
                     'group' : self.repoXML.groupChecksum }
                     
        locMethod = locDict[mdtype]
        csumMethod = csumDict[mdtype]
        
        (r_base, remote) = locMethod()
        fname = os.path.basename(remote)
        local = self.cache + '/' + fname

        if self.retrieved[mdtype]: # got it, move along
            return local

        if cache: # cached - just go
            if os.path.exists(local):
                return local
            else: # ain't there - raise
                raise Errors.RepoError, \
                    "Caching enabled but no local cache of %s from %s" % (local,
                           self)
                           
        (r_ctype, r_csum) = csumMethod() # get the remote checksum
        
        if os.path.exists(local): 
            l_csum = self._checksum(r_ctype, local) # get the local checksum
            if l_csum == r_csum: 
                self.retrieved[mdtype] = 1
                return local # it's the same return the local one

        try:        
            local = self.get(relative=remote, local=local, copy_local=1)
        except URLGrabError, e:
            raise

        self.retrieved[mdtype] = 1
        return local

    
    def getPrimaryXML(self, cache=0):
        """this gets you the path to the primary.xml file, retrieving it if we 
           need a new one"""

        return self._retrieveMD('primary', cache)
        
    
    def getFileListsXML(self, cache=0):
        """this gets you the path to the filelists.xml file, retrieving it if we 
           need a new one"""

        return self._retrieveMD('filelists', cache)

    def getOtherXML(self, cache=0):
        return self._retrieveMD('other', cache)

    def getGroups(self, cache=0):
        """gets groups and returns group file path for the repository, if there 
           is none it returns None"""
        try:
            file = self._retrieveMD('group', cache)
        except URLGrabError:
            file = None
        
        return file
        
        
    

