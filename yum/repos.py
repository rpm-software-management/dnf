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
import os
import os.path
import failover    
from urlgrabber.grabber import URLGrabber

class RepoStorage:
    """This class contains multiple repositories and core configuration data
       about them."""
       
    def __init__(self):
        self.repos = {} # list of repos by repoid pointing a repo object 
                        # of repo options/misc data
    
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
        """return list of repo ids for enabled repos"""
        returnlist = []
        for repo in self.repos.values():
            if repo.enabled:
                returnlist.append(repo)
                
        return returnlist


        
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
        
    def __cmp__(self, other):
        if self.id > other.id:
            return 1
        elif self.id < other.id:
            return -1
        else:
            return 0

    def __str__(self):
        return self.id
        
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
        # FIXME this should do things with our proxy and keepalive info here
        # too
        if self.failmeth == 'roundrobin':
            mgclass = urlgrabber.mirror.MGRandomOrder
        else:
            mgclass = urlgrabber.mirror.MirrorGroup
            
        self.grabfunc = URLGrabber(keepalive=self.keepalive, 
                                   bandwidth=self.bandwidth,
                                   retry=self.retries,
                                   throttle=self.throttle)
        self.grab = mgclass(self.grabfunc, self.urls)

        # now repo.grab.urlgrab('relativepath/some.file') should do the right thing
        
        
    def remoteGroups(self):
        return os.path.join(self.baseURL(), self.groupsfilename)
    
    def localGroups(self):
        return os.path.join(self.cache, self.groupsfilename)

    def remoteMetadata(self):
        return os.path.join(self.baseURL(), 'repodata/repomd.xml')
        
    def baseURL(self):
        return self.failover.get_serverurl()
        
    def failed(self):
        self.failover.server_failed()

    def _retrieveMD(self, url, local):
        """base function to retrieve data from the remote url"""
        
    def getRepoXML(self, cache=0):
        """retrieve/check/read in repomd.xml from the repository"""
        pass
        
    def getPrimaryXML(self, cache=0):
        pass
    
    def getFileListsXML(self, cache=0):
        pass    

    def getOtherXML(self, cache=0):
        pass    
    
