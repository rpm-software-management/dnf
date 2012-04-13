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

import re
import fnmatch
import types
import logging
import misc

import Errors
from packageSack import MetaSack

from weakref import proxy as weakref

class _wrap_ayum_getKeyForRepo:
    """ This is a wrapper for calling YumBase.getKeyForRepo() because
        otherwise we take a real reference through the bound method and
        that is d00m (this applies to YumBase and RepoStorage, hence why
        we have a seperate class).
        A "better" fix might be to explicitly pass the YumBase instance to
        the callback ... API change! """
    def __init__(self, ayum, ca=False):
        self.ayum = weakref(ayum)
        self.ca = ca
    def __call__(self, repo, callback=None):
        if self.ca:
            return self.ayum.getCAKeyForRepo(repo, callback)
        return self.ayum.getKeyForRepo(repo, callback)

class RepoStorage:
    """This class contains multiple repositories and core configuration data
       about them."""
       
    def __init__(self, ayum):
        self.repos = {} # list of repos by repoid pointing a repo object 
                        # of repo options/misc data
        self.callback = None # progress callback used for populateSack() for importing the xml files
        self.cache = 0
        self.pkgSack = MetaSack()
        self.logger = logging.getLogger("yum.RepoStorage")

        self._setup = False

        self.ayum = weakref(ayum)
        # callbacks for handling gpg key imports for repomd.xml sig checks
        # need to be set from outside of the repos object to do anything
        # even quasi-useful
        # defaults to what is probably sane-ish
        self.gpg_import_func = _wrap_ayum_getKeyForRepo(ayum)
        self.gpgca_import_func = _wrap_ayum_getKeyForRepo(ayum, ca=True)
        self.confirm_func = None

        # This allow listEnabled() to be O(1) most of the time.
        self._cache_enabled_repos = []
        self.quick_enable_disable = {}

    def doSetup(self, thisrepo = None):
        
        self.ayum.plugins.run('prereposetup')
        
        if thisrepo is None:
            repos = self.listEnabled()
        else:
            repos = self.findRepos(thisrepo)

        if len(repos) < 1:
            self.logger.debug('No Repositories Available to Set Up')

        for repo in repos:
            repo.setup(self.ayum.conf.cache, self.ayum.mediagrabber,
                   gpg_import_func = self.gpg_import_func, confirm_func=self.confirm_func,
                   gpgca_import_func = self.gpgca_import_func)
            # if we come back from setup NOT enabled then mark as disabled
            # so nothing else touches us
            if not repo.enabled:
                self.disableRepo(repo.id)
                
        self._setup = True
        self.ayum.plugins.run('postreposetup')
        
    def __str__(self):
        return str(self.repos.keys())

    def __del__(self):
        self.close()

    def close(self):
        for repo in self.repos.values():
            repo.close()

    def add(self, repoobj):
        if repoobj.id in self.repos:
            raise Errors.DuplicateRepoError, 'Repository %s is listed more than once in the configuration' % (repoobj.id)
        self.repos[repoobj.id] = repoobj
        if hasattr(repoobj, 'quick_enable_disable'):
            self.quick_enable_disable.update(repoobj.quick_enable_disable)
            repoobj.quick_enable_disable = self.quick_enable_disable
        else:
            self._cache_enabled_repos = None
        #  At least pulp reuses RepoStorage but doesn't have a "real" YumBase()
        # so we can't guarantee new YumBase() attrs. exist.
        if not hasattr(self.ayum, '_override_sigchecks'):
            repoobj._override_sigchecks = False
        else:
            repoobj._override_sigchecks = self.ayum._override_sigchecks

    def delete(self, repoid):
        if repoid in self.repos:
            thisrepo = self.repos[repoid]
            thisrepo.close()
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
        if misc.re_glob(repoid) or repoid.find(',') != -1:
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
        if misc.re_glob(repoid) or repoid.find(',') != -1:
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

        if (self._cache_enabled_repos is not None and
            not self.quick_enable_disable):
            return self._cache_enabled_repos

        returnlist = []
        for repo in self.repos.values():
            if repo.isEnabled():
                returnlist.append(repo)

        returnlist.sort()

        if self._cache_enabled_repos is not None:
            self._cache_enabled_repos = returnlist
            self.quick_enable_disable.clear()
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
        
        self._cachedir = cachedir
        for repo in self.repos.values():
            repo.old_base_cache_dir = repo.basecachedir
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


    def populateSack(self, which='enabled', mdtype='metadata', callback=None, cacheonly=0):
        """
        This populates the package sack from the repositories, two optional 
        arguments:
            - which='repoid, enabled, all'
            - mdtype='metadata, filelists, otherdata, all'
        """

        if not self._setup:
            self.doSetup()

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

        if mdtype == 'all':
            data = ['metadata', 'filelists', 'otherdata']
        else:
            data = [ mdtype ]
         
        for repo in myrepos:
            sack = repo.getPackageSack()
            try:
                sack.populate(repo, mdtype, callback, cacheonly)
            except Errors.RepoError, e:
                if mdtype in ['all', 'metadata'] and repo.skip_if_unavailable:
                    self.disableRepo(repo.id)
                else:
                    raise
            else:
                self.pkgSack.addSack(repo.id, sack)


class Repository:
    """this is an actual repository object"""       

    def __init__(self, repoid):
        self.id = repoid
        self.quick_enable_disable = {}
        self.disable()
        self._xml2sqlite_local = False

    def __cmp__(self, other):
        """ Sort base class repos. by alphanumeric on their id, also
            see __cmp__ in YumRepository(). """
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
        
    def __del__(self):
        self.close()

    def close(self):
        pass

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
        self.quick_enable_disable[self.id] = True
                    
    def disable(self):
        self.setAttribute('enabled', 0)
        self.quick_enable_disable[self.id] = False

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

