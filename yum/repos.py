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
import re
import fnmatch
import types

import Errors
from packageSack import MetaSack
from packages import YumAvailablePackage

_is_fnmatch_pattern = re.compile(r"[*?[]").search

class RepoStorage:
    """This class contains multiple repositories and core configuration data
       about them."""
       
    def __init__(self):
        self.repos = {} # list of repos by repoid pointing a repo object 
                        # of repo options/misc data
        self.callback = None # progress callback used for populateSack() for importing the xml files
        self.cache = 0
        self.pkgSack = MetaSack()

        
    def __str__(self):
        return str(self.repos.keys())
    

    def add(self, repoobj):
        if self.repos.has_key(repoobj.id):
            raise Errors.DuplicateRepoError, 'Repository %s is listed more than once in the configuration' % (repoobj.id)
        self.repos[repoobj.id] = repoobj
        

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

    def findRepos(self,pattern):
        """find all repositories matching fnmatch `pattern`"""

        result = []
        
        for item in pattern.split(','):
            item = item.strip()
            match = re.compile(fnmatch.translate(item)).match
            for name,repo in self.repos.items():
                if match(name):
                    result.append(repo)
        return result
        
    def disableRepo(self, repoid):
        """disable a repository from use
        
        fnmatch wildcards may be used to disable a group of repositories.
        returns repoid of disabled repos as list
        """
        repos = []
        if _is_fnmatch_pattern(repoid) or repoid.find(',') != -1:
            for repo in self.findRepos(repoid):
                repos.append(repo.id)
                repo.disable()
        else:
            thisrepo = self.getRepo(repoid)
            repos.append(thisrepo.id)
            thisrepo.disable()
        
        return repos
        
    def enableRepo(self, repoid):
        """enable a repository for use
        
        fnmatch wildcards may be used to enable a group of repositories.
        returns repoid of enables repos as list
        """
        repos = []
        if _is_fnmatch_pattern(repoid) or repoid.find(',') != -1:
            for repo in self.findRepos(repoid):
                repos.append(repo.id)
                repo.enable()
        else:
            thisrepo = self.getRepo(repoid)
            repos.append(thisrepo.id)
            thisrepo.enable()
        
        return repos
        
    def listEnabled(self):
        """return list of enabled repo objects"""
        returnlist = []
        for repo in self.repos.values():
            if repo.isEnabled():
                returnlist.append(repo)

        return returnlist

    def listGroupsEnabled(self):
        """return a list of repo objects that have groups enabled"""
        returnlist = []
        for repo in self.listEnabled():
            if repo.enablegroups:
                returnlist.append(repo)

        return returnlist

    def setCache(self, cacheval):
        """sets cache value in all repos"""
        self.cache = cacheval
        for repo in self.repos.values():
            repo.cache = cacheval

    def setCacheDir(self, cachedir):
        """sets the cachedir value in all repos"""

        for repo in self.repos.values():
            repo.basecachedir = cachedir

    def setProgressBar(self, obj):
        """sets the progress bar for downloading files from repos"""
        
        for repo in self.repos.values():
            repo.setCallback(obj)

    def setFailureCallback(self, obj):
        """sets the failure callback for all repos"""
        
        for repo in self.repos.values():
            repo.setFailureObj(obj)

    def setMirrorFailureCallback(self, obj):
        """sets the failure callback for all mirrors"""
        
        for repo in self.repos.values():
            repo.setMirrorFailureObj(obj)

    def setInterruptCallback(self, callback):
        for repo in self.repos.values():
            repo.setInterruptCallback(callback)

    def getPackageSack(self):
        return self.pkgSack


    def populateSack(self, which='enabled', with='metadata', callback=None, cacheonly=0):
        """This populates the package sack from the repositories, two optional 
           arguments: which='repoid, enabled, all'
                      with='metadata, filelists, otherdata, all'"""

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
                    if isinstance(repo, Repository):
                        myrepos.append(repo)
                    else:
                        repobj = self.getRepo(repo)
                        myrepos.append(repobj)
            elif type(which) == types.StringType:
                repobj = self.getRepo(which)
                myrepos.append(repobj)

        if with == 'all':
            data = ['metadata', 'filelists', 'otherdata']
        else:
            data = [ with ]
         
        for repo in myrepos:
            sack = repo.getPackageSack()
            sack.populate(repo, with, callback, cacheonly)
            self.pkgSack.addSack(repo.id, sack)


class Repository:
    """this is an actual repository object"""       

    def __init__(self, repoid):
        self.id = repoid
        self.disable()

    def __cmp__(self, other):
        if self.id > other.id:
            return 1
        elif self.id < other.id:
            return -1
        else:
            return 0

    def __str__(self):
        return self.id

    def __hash__(self):
        return hash(self.id)
        
    def setAttribute(self, key, value):
        """sets a generic attribute of this repository"""
        setattr(self, key, value)

    def getAttribute(self, key):
        return getattr(self, key, None)

    def isEnabled(self):
        enabled = self.getAttribute('enabled')
        return enabled is not None and enabled

    def enable(self):
        self.setAttribute('enabled', 1)
                    
    def disable(self):
        self.setAttribute('enabled', 0)

    def getExcludePkgList(self):
        excludeList = self.getAttribute('exclude')
        return excludeList or []

    def getIncludePkgList(self):
        includeList = self.getAttribute('includepkgs')
        return includeList or []

    # Abstract interface
    def ready(self):
        raise NotImplementedError()

    def getGroupLocation(self):
        raise NotImplementedError()
 
    def getPackageSack(self):
        raise NotImplementedError()

    def setup(self, cache):
        raise NotImplementedError()
                    
    def setCallback(self, callback):
        raise NotImplementedError()

    def setFailureObj(self, obj):
        raise NotImplementedError()

    def setMirrorFailureObj(self, obj):
        raise NotImplementedError()

    def getPackage(self, package, checkfunc = None, text = None, cache = True):
        raise NotImplementedError()

    def getHeader(self, package, checkfunc = None, reget = 'simple', cache = True):
        raise NotImplementedError()

