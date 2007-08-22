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


import os
import os.path
import rpm
import re
import types
import errno
import time
import glob
import fnmatch
import logging
import logging.config
from ConfigParser import ParsingError, ConfigParser
import Errors
import rpmsack
import rpmUtils.updates
import rpmUtils.arch
import rpmUtils.transaction
import comps
import config
from repos import RepoStorage
import misc
from parser import ConfigPreProcessor
import transactioninfo
import urlgrabber
from urlgrabber.grabber import URLGrabError
from packageSack import ListPackageSack
import depsolve
import plugins
import logginglevels
import yumRepo

import warnings
warnings.simplefilter("ignore", Errors.YumFutureDeprecationWarning)

from packages import parsePackages, YumAvailablePackage, YumLocalPackage, YumInstalledPackage
from constants import *
from yum.rpmtrans import RPMTransaction,SimpleCliCallBack

__version__ = '3.2.3'

class YumBase(depsolve.Depsolve):
    """This is a primary structure and base class. It houses the objects and
       methods needed to perform most things in yum. It is almost an abstract
       class in that you will need to add your own class above it for most
       real use."""
    
    def __init__(self):
        depsolve.Depsolve.__init__(self)
        self._conf = None
        self._tsInfo = None
        self._rpmdb = None
        self._up = None
        self._comps = None
        self._pkgSack = None
        self.logger = logging.getLogger("yum.YumBase")
        self.verbose_logger = logging.getLogger("yum.verbose.YumBase")
        self._repos = RepoStorage(self)

        # Start with plugins disabled
        self.disablePlugins()

        self.localPackages = [] # for local package handling

        self.mediagrabber = None

    def __del__(self):
        self.close()

    def close(self):
        if self._repos:
            self._repos.close()

    def _transactionDataFactory(self):
        """Factory method returning TransactionData object"""
        return transactioninfo.TransactionData()

    def doGenericSetup(self, cache=0):
        """do a default setup for all the normal/necessary yum components,
           really just a shorthand for testing"""
        
        self._getConfig(init_plugins=False)
        self.conf.cache = cache

    def doConfigSetup(self, fn='/etc/yum/yum.conf', root='/', init_plugins=True,
            plugin_types=(plugins.TYPE_CORE,), optparser=None, debuglevel=None,
            errorlevel=None):
        warnings.warn('doConfigSetup() will go away in a future version of Yum.\n',
                Errors.YumFutureDeprecationWarning, stacklevel=2)
                
        return self._getConfig(fn=fn, root=root, init_plugins=init_plugins,
             plugin_types=plugin_types, optparser=optparser, debuglevel=debuglevel,
             errorlevel=errorlevel)
        
    def _getConfig(self, fn='/etc/yum/yum.conf', root='/', init_plugins=True,
            plugin_types=(plugins.TYPE_CORE,), optparser=None, debuglevel=None,
            errorlevel=None,disabled_plugins=None):
        '''
        Parse and load Yum's configuration files and call hooks initialise
        plugins and logging.

        @param fn: Path to main configuration file to parse (yum.conf).
        @param root: Filesystem root to use.
        @param init_plugins: If False, plugins will not be loaded here. If
            True, plugins will be loaded if the "plugins" option is enabled in
            the configuration file.
        @param plugin_types: As per doPluginSetup()
        @param optparser: As per doPluginSetup()
        @param debuglevel: Debug level to use for logging. If None, the debug
            level will be read from the configuration file.
        @param errorlevel: Error level to use for logging. If None, the debug
            level will be read from the configuration file.
        @param disabled_plugins: Plugins to be disabled    
        '''

        if self._conf:
            return self._conf
            
        # TODO: Remove this block when we no longer support configs outside
        # of /etc/yum/
        if fn == '/etc/yum/yum.conf' and not os.path.exists(fn):
            # Try the old default
            fn = '/etc/yum.conf'

        startupconf = config.readStartupConfig(fn, root)

        
        if debuglevel != None:
            startupconf.debuglevel = debuglevel
        if errorlevel != None:
            startupconf.errorlevel = errorlevel

        self.doLoggingSetup(startupconf.debuglevel, startupconf.errorlevel)

        if init_plugins and startupconf.plugins:
            self.doPluginSetup(optparser, plugin_types, startupconf.pluginpath,
                    startupconf.pluginconfpath,disabled_plugins)

        self._conf = config.readMainConfig(startupconf)
        # run the postconfig plugin hook
        self.plugins.run('postconfig')
        self.yumvar = self.conf.yumvar

        self.getReposFromConfig()

        # who are we:
        self.conf.uid = os.geteuid()
        
        
        self.doFileLogSetup(self.conf.uid, self.conf.logfile)

        self.plugins.run('init')
        return self._conf
        

    def doLoggingSetup(self, debuglevel, errorlevel):
        '''
        Perform logging related setup.

        @param debuglevel: Debug logging level to use.
        @param errorlevel: Error logging level to use.
        '''
        logginglevels.doLoggingSetup(debuglevel, errorlevel)

    def doFileLogSetup(self, uid, logfile):
        logginglevels.setFileLog(uid, logfile)

    def getReposFromConfig(self):
        """read in repositories from config main and .repo files"""

        #FIXME this method could be a simpler

        reposlist = []
        # Check yum.conf for repositories
        for section in self.conf.cfg.sections():
            # All sections except [main] are repositories
            if section == 'main': 
                continue

            try:
                thisrepo = self.readRepoConfig(self.conf.cfg, section)
            except (Errors.RepoError, Errors.ConfigError), e:
                self.logger.warning(e)
            else:
                thisrepo.repo_config_age = self.conf.config_file_age
                reposlist.append(thisrepo)

        # Read .repo files from directories specified by the reposdir option
        # (typically /etc/yum/repos.d)
        repo_config_age = self.conf.config_file_age
        
        parser = ConfigParser()
        for reposdir in self.conf.reposdir:
            if os.path.exists(self.conf.installroot+'/'+reposdir):
                reposdir = self.conf.installroot + '/' + reposdir

            if os.path.isdir(reposdir):
                for repofn in glob.glob('%s/*.repo' % reposdir):
                    thisrepo_age = os.stat(repofn)[8]
                    if thisrepo_age > repo_config_age:
                        repo_config_age = thisrepo_age
                        
                    confpp_obj = ConfigPreProcessor(repofn, vars=self.yumvar)
                    try:
                        parser.readfp(confpp_obj)
                    except ParsingError, e:
                        msg = str(e)
                        raise Errors.ConfigError, msg

        # Check sections in the .repo files that were just slurped up
        for section in parser.sections():
            try:
                thisrepo = self.readRepoConfig(parser, section)
            except (Errors.RepoError, Errors.ConfigError), e:
                self.logger.warning(e)
            else:
                thisrepo.repo_config_age = repo_config_age
                reposlist.append(thisrepo)

        # Got our list of repo objects, add them to the repos collection
        for thisrepo in reposlist:
            try:
                self._repos.add(thisrepo)
            except Errors.RepoError, e: 
                self.logger.warning(e)
                continue

    def readRepoConfig(self, parser, section):
        '''Parse an INI file section for a repository.

        @param parser: ConfParser or similar to read INI file values from.
        @param section: INI file section to read.
        @return: YumRepository instance.
        '''
        repo = yumRepo.YumRepository(section)
        repo.populate(parser, section, self.conf)

        # Ensure that the repo name is set
        if not repo.name:
            repo.name = section
            self.logger.error('Repository %r is missing name in configuration, '
                    'using id' % section)

        # Set attributes not from the config file
        repo.basecachedir = self.conf.cachedir
        repo.yumvar.update(self.conf.yumvar)
        repo.cfg = parser

        return repo

    def disablePlugins(self):
        '''Disable yum plugins
        '''
        self.plugins = plugins.DummyYumPlugins()
    
    def doPluginSetup(self, optparser=None, plugin_types=None, searchpath=None,
            confpath=None,disabled_plugins=None):
        '''Initialise and enable yum plugins. 

        Note: _getConfig() will initialise plugins if instructed to. Only
        call this method directly if not calling _getConfig() or calling
        doConfigSetup(init_plugins=False).

        @param optparser: The OptionParser instance for this run (optional)
        @param plugin_types: A sequence specifying the types of plugins to load.
            This should be sequnce containing one or more of the
            yum.plugins.TYPE_...  constants. If None (the default), all plugins
            will be loaded.
        @param searchpath: A list of directories to look in for plugins. A
            default will be used if no value is specified.
        @param confpath: A list of directories to look in for plugin
            configuration files. A default will be used if no value is
            specified.
        @param disabled_plugins: Plugins to be disabled    
        '''
        if isinstance(plugins, plugins.YumPlugins):
            raise RuntimeError("plugins already initialised")

        self.plugins = plugins.YumPlugins(self, searchpath, optparser,
                plugin_types, confpath, disabled_plugins)

    
    def doRpmDBSetup(self):
        warnings.warn('doRpmDBSetup() will go away in a future version of Yum.\n',
                Errors.YumFutureDeprecationWarning, stacklevel=2)

        return self._getRpmDB()
    
    def _getRpmDB(self):
        """sets up a holder object for important information from the rpmdb"""

        if self._rpmdb is None:
            self.verbose_logger.debug('Reading Local RPMDB')
            self._rpmdb = rpmsack.RPMDBPackageSack(root=self.conf.installroot)
        
        return self._rpmdb

    def closeRpmDB(self):
        """closes down the instances of the rpmdb we have wangling around"""
        self._rpmdb = None
        self._ts = None
        self._tsInfo = None
        self._up = None
        self.comps = None
    
    def _deleteTs(self):
        del self._ts
        self._ts = None

    def doRepoSetup(self, thisrepo=None):
        warnings.warn('doRepoSetup() will go away in a future version of Yum.\n',
                Errors.YumFutureDeprecationWarning, stacklevel=2)

        return self._getRepos(thisrepo, True)

    def _getRepos(self, thisrepo=None, doSetup = False):
        """grabs the repomd.xml for each enabled repository and sets up 
           the basics of the repository"""
        self._getConfig() # touch the config class first

        if doSetup:
            self._repos.doSetup(thisrepo)
        return self._repos
    
    def doSackSetup(self, archlist=None, thisrepo=None):
        warnings.warn('doSackSetup() will go away in a future version of Yum.\n',
                Errors.YumFutureDeprecationWarning, stacklevel=2)

        return self._getSacks(archlist=archlist, thisrepo=thisrepo)
        
    def _getSacks(self, archlist=None, thisrepo=None):
        """populates the package sacks for information from our repositories,
           takes optional archlist for archs to include"""

        if self._pkgSack and thisrepo is None:
            self.verbose_logger.log(logginglevels.DEBUG_4,
                'skipping reposetup, pkgsack exists')
            return self._pkgSack
        
        if thisrepo is None:
            repos = self.repos.listEnabled()
        else:
            repos = self.repos.findRepos(thisrepo)
        
        self.verbose_logger.debug('Setting up Package Sacks')
        if not archlist:
            archlist = rpmUtils.arch.getArchList()
        
        archdict = {}
        for arch in archlist:
            archdict[arch] = 1
        
        self.repos.getPackageSack().setCompatArchs(archdict)
        self.repos.populateSack(which=repos)
        self._pkgSack = self.repos.getPackageSack()
        
        #FIXME - this is not very fast
        self.excludePackages()
        self._pkgSack.excludeArchs(archlist)
        
        #FIXME - this could be faster, too.
        for repo in repos:
            self.excludePackages(repo)
            self.includePackages(repo)
        self.plugins.run('exclude')
        self._pkgSack.buildIndexes()

        return self._pkgSack
    
    def _delSacks(self):
        """reset the package sacks back to zero - making sure to nuke the ones
           in the repo objects, too - where it matters"""
           
        # nuke the top layer
        
        self._pkgSack = None
           
        for repo in self.repos.repos.values():
            if hasattr(repo, '_resetSack'):
                repo._resetSack()
            else:
                warnings.warn('repo object for repo %s lacks a _resetSack method\n' +
                        'therefore this repo cannot be reset.\n',
                        Errors.YumFutureDeprecationWarning, stacklevel=2)
            
           
    def doUpdateSetup(self):
        warnings.warn('doUpdateSetup() will go away in a future version of Yum.\n',
                Errors.YumFutureDeprecationWarning, stacklevel=2)

        return self._getUpdates()
        
    def _getUpdates(self):
        """setups up the update object in the base class and fills out the
           updates, obsoletes and others lists"""
        
        if self._up:
            return self._up

        self.verbose_logger.debug('Building updates object')
        sack_pkglist = self.pkgSack.simplePkgList()
        rpmdb_pkglist = self.rpmdb.simplePkgList()        
        self._up = rpmUtils.updates.Updates(rpmdb_pkglist, sack_pkglist)
        del rpmdb_pkglist
        del sack_pkglist
        if self.conf.debuglevel >= 6:
            self._up.debug = 1
            
        if self.conf.obsoletes:
            self._up.rawobsoletes = self.pkgSack.returnObsoletes(newest=True)
            
        self._up.exactarch = self.conf.exactarch
        self._up.exactarchlist = self.conf.exactarchlist
        self._up.doUpdates()

        if self.conf.obsoletes:
            self._up.doObsoletes()

        self._up.condenseUpdates()
        return self._up
    
    def doGroupSetup(self):
        warnings.warn('doGroupSetup() will go away in a future version of Yum.\n',
                Errors.YumFutureDeprecationWarning, stacklevel=2)

        self.comps = None
        return self._getGroups()

    def _setGroups(self, val):
        if val is None:
            # if we unset the comps object, we need to undo which repos have
            # been added to the group file as well
            if self._repos:
                for repo in self._repos.listGroupsEnabled():
                    repo.groups_added = False
        self._comps = val
    
    def _getGroups(self):
        """create the groups object that will store the comps metadata
           finds the repos with groups, gets their comps data and merge it
           into the group object"""
        
        if self._comps:
            return self._comps
            
        self.verbose_logger.debug('Getting group metadata')
        reposWithGroups = []
        self.repos.doSetup()
        for repo in self.repos.listGroupsEnabled():
            if repo.groups_added: # already added the groups from this repo
                reposWithGroups.append(repo)
                continue
                
            if not repo.ready():
                raise Errors.RepoError, "Repository '%s' not yet setup" % repo
            try:
                groupremote = repo.getGroupLocation()
            except Errors.RepoMDError, e:
                pass
            else:
                reposWithGroups.append(repo)
                
        # now we know which repos actually have groups files.
        overwrite = self.conf.overwrite_groups
        self._comps = comps.Comps(overwrite_groups = overwrite)

        for repo in reposWithGroups:
            if repo.groups_added: # already added the groups from this repo
                continue
                
            self.verbose_logger.log(logginglevels.DEBUG_1,
                'Adding group file from repository: %s', repo)
            groupfile = repo.getGroups()
            try:
                self._comps.add(groupfile)
            except Errors.GroupsError, e:
                self.logger.critical('Failed to add groups file for repository: %s' % repo)
            else:
                repo.groups_added = True

        if self.comps.compscount == 0:
            raise Errors.GroupsError, 'No Groups Available in any repository'
        
        pkglist = self.rpmdb.simplePkgList()
        self._comps.compile(pkglist)
        
        return self._comps
    
    # properties so they auto-create themselves with defaults
    repos = property(fget=lambda self: self._getRepos(),
                     fset=lambda self, value: setattr(self, "_repos", value),
                     fdel=lambda self: setattr(self, "_repos", None))
    pkgSack = property(fget=lambda self: self._getSacks(),
                       fset=lambda self, value: setattr(self, "_pkgSack", value),
                       fdel=lambda self: self._delSacks())
    conf = property(fget=lambda self: self._getConfig(),
                    fset=lambda self, value: setattr(self, "_conf", value),
                    fdel=lambda self: setattr(self, "_conf", None))
    rpmdb = property(fget=lambda self: self._getRpmDB(),
                     fset=lambda self, value: setattr(self, "_rpmdb", value),
                     fdel=lambda self: setattr(self, "_rpmdb", None))
    tsInfo = property(fget=lambda self: self._getTsInfo(), 
                      fset=lambda self,value: self._setTsInfo(value), 
                      fdel=lambda self: self._delTsInfo())
    ts = property(fget=lambda self: self._getActionTs(), fdel=lambda self: self._deleteTs())
    up = property(fget=lambda self: self._getUpdates(),
                  fset=lambda self, value: setattr(self, "_up", value),
                  fdel=lambda self: setattr(self, "_up", None))
    comps = property(fget=lambda self: self._getGroups(),
                     fset=lambda self, value: self._setGroups(value),
                     fdel=lambda self: setattr(self, "_comps", None))
    
    
    def doSackFilelistPopulate(self):
        """convenience function to populate the repos with the filelist metadata
           it also is simply to only emit a log if anything actually gets populated"""
        
        necessary = False
        
        # I can't think of a nice way of doing this, we have to have the sack here
        # first or the below does nothing so...
        if self.pkgSack:
            for repo in self.repos.listEnabled():
                if repo in repo.sack.added.keys():
                    if 'filelists' in repo.sack.added[repo]:
                        continue
                    else:
                        necessary = True
                else:
                    necessary = True

        if necessary:
            msg = 'Importing additional filelist information'
            self.verbose_logger.log(logginglevels.INFO_2, msg)
            self.repos.populateSack(mdtype='filelists')
           
    def buildTransaction(self):
        """go through the packages in the transaction set, find them in the
           packageSack or rpmdb, and pack up the ts accordingly"""
        self.plugins.run('preresolve')
        (rescode, restring) = self.resolveDeps()
        self.plugins.run('postresolve', rescode=rescode, restring=restring)
        self._limit_installonly_pkgs()
        
        if self.tsInfo.changed:
            (rescode, restring) = self.resolveDeps()
            
        return rescode, restring

    def runTransaction(self, cb):
        """takes an rpm callback object, performs the transaction"""

        self.plugins.run('pretrans')

        errors = self.ts.run(cb.callback, '')
        if errors:
            raise Errors.YumBaseError, errors

        if not self.conf.keepcache:
            self.cleanUsedHeadersPackages()
        
        for i in ('ts_all_fn', 'ts_done_fn'):
            if hasattr(cb, i):
                fn = getattr(cb, i)
                if os.path.exists(fn):
                    try:
                        os.unlink(fn)
                    except (IOError, OSError), e:
                        self.logger.critical('Failed to remove transaction file %s' % fn)

        self.plugins.run('posttrans')
        
    def excludePackages(self, repo=None):
        """removes packages from packageSacks based on global exclude lists,
           command line excludes and per-repository excludes, takes optional 
           repo object to use."""
        
        # if not repo: then assume global excludes, only
        # if repo: then do only that repos' packages and excludes
        
        if not repo: # global only
            excludelist = self.conf.exclude
            repoid = None
        else:
            excludelist = repo.getExcludePkgList()
            repoid = repo.id

        if len(excludelist) == 0:
            return

        if not repo:
            self.verbose_logger.log(logginglevels.INFO_2, 'Excluding Packages in global exclude list')
        else:
            self.verbose_logger.log(logginglevels.INFO_2, 'Excluding Packages from %s',
                repo.name)
        
        exactmatch, matched, unmatched = \
           parsePackages(self._pkgSack.returnPackages(repoid), excludelist, casematch=1)

        for po in exactmatch + matched:
            self.verbose_logger.debug('Excluding %s', po)
            po.repo.sack.delPackage(po)
            
        
        self.verbose_logger.log(logginglevels.INFO_2, 'Finished')

    def includePackages(self, repo):
        """removes packages from packageSacks based on list of packages, to include.
           takes repoid as a mandatory argument."""
        
        includelist = repo.getIncludePkgList()
        
        if len(includelist) == 0:
            return
        
        pkglist = self.pkgSack.returnPackages(repo.id)
        exactmatch, matched, unmatched = \
           parsePackages(pkglist, includelist, casematch=1)
        
        self.verbose_logger.log(logginglevels.INFO_2,
            'Reducing %s to included packages only', repo.name)
        rmlist = []
        
        for po in pkglist:
            if po in exactmatch + matched:
                self.verbose_logger.debug('Keeping included package %s', po)
                continue
            else:
                rmlist.append(po)
        
        for po in rmlist:
            self.verbose_logger.debug('Removing unmatched package %s', po)
            po.repo.sack.delPackage(po)
            
        self.verbose_logger.log(logginglevels.INFO_2, 'Finished')
        
    def doLock(self, lockfile = YUM_PID_FILE):
        """perform the yum locking, raise yum-based exceptions, not OSErrors"""
        
        # if we're not root then we don't lock - just return nicely
        if self.conf.uid != 0:
            return
            
        root = self.conf.installroot
        lockfile = root + '/' + lockfile # lock in the chroot
        lockfile = os.path.normpath(lockfile) # get rid of silly preceding extra /
        
        mypid=str(os.getpid())    
        while not self._lock(lockfile, mypid, 0644):
            fd = open(lockfile, 'r')
            try: oldpid = int(fd.readline())
            except ValueError:
                # bogus data in the pid file. Throw away.
                self._unlock(lockfile)
            else:
                if oldpid == os.getpid(): # if we own the lock, we're fine
                    return
                try: os.kill(oldpid, 0)
                except OSError, e:
                    if e[0] == errno.ESRCH:
                        # The pid doesn't exist
                        self._unlock(lockfile)
                    else:
                        # Whoa. What the heck happened?
                        msg = 'Unable to check if PID %s is active' % oldpid
                        raise Errors.LockError(1, msg)
                else:
                    # Another copy seems to be running.
                    msg = 'Existing lock %s: another copy is running as pid %s.' % (lockfile, oldpid)
                    raise Errors.LockError(0, msg)
    
    def doUnlock(self, lockfile = YUM_PID_FILE):
        """do the unlock for yum"""
        
        # if we're not root then we don't lock - just return nicely
        if self.conf.uid != 0:
            return
        
        root = self.conf.installroot
        lockfile = root + '/' + lockfile # lock in the chroot
        
        self._unlock(lockfile)
        
    def _lock(self, filename, contents='', mode=0777):
        lockdir = os.path.dirname(filename)
        try:
            if not os.path.exists(lockdir):
                os.makedirs(lockdir, mode=0755)
            fd = os.open(filename, os.O_EXCL|os.O_CREAT|os.O_WRONLY, mode)    
        except OSError, msg:
            if not msg.errno == errno.EEXIST: raise msg
            return 0
        else:
            os.write(fd, contents)
            os.close(fd)
            return 1
    
    def _unlock(self, filename):
        try:
            os.unlink(filename)
        except OSError, msg:
            pass


    def verifyPkg(self, fo, po, raiseError):
        """verifies the package is what we expect it to be
           raiseError  = defaults to 0 - if 1 then will raise
           a URLGrabError if the file does not check out.
           otherwise it returns false for a failure, true for success"""

        if type(fo) is types.InstanceType:
            fo = fo.filename
            
        if not po.verifyLocalPkg():
            if raiseError:
                raise URLGrabError(-1, 'Package does not match intended download')
            else:
                return False

        ylp = YumLocalPackage(self.rpmdb.readOnlyTS(), fo)
        if ylp.pkgtup != po.pkgtup:
            if raiseError:
                raise URLGrabError(-1, 'Package does not match intended download')
            else:
                return False
        
        return True
        
        
    def verifyChecksum(self, fo, checksumType, csum):
        """Verify the checksum of the file versus the 
           provided checksum"""

        try:
            filesum = misc.checksum(checksumType, fo)
        except Errors.MiscError, e:
            raise URLGrabError(-3, 'Could not perform checksum')
            
        if filesum != csum:
            raise URLGrabError(-1, 'Package does not match checksum')
        
        return 0
            
           
    def downloadPkgs(self, pkglist, callback=None):
        def mediasort(a, b):
            # FIXME: we should probably also use the mediaid; else we
            # could conceivably ping-pong between different disc1's
            a = a.getDiscNum()
            b = b.getDiscNum()
            if a is None:
                return -1
            if b is None:
                return 1
            if a < b:
                return -1
            elif a > b:
                return 1
            return 0
        
        """download list of package objects handed to you, output based on
           callback, raise yum.Errors.YumBaseError on problems"""

        errors = {}
        def adderror(po, msg):
            errors.setdefault(po, []).append(msg)

        self.plugins.run('predownload', pkglist=pkglist)
        repo_cached = False
        remote_pkgs = []
        for po in pkglist:
            if hasattr(po, 'pkgtype') and po.pkgtype == 'local':
                continue
                    
            local = po.localPkg()
            if os.path.exists(local):
                cursize = os.stat(local)[6]
                totsize = long(po.size)
                if not po.verifyLocalPkg():
                    if po.repo.cache:
                        repo_cached = True
                        adderror(po, 'package fails checksum but caching is '
                            'enabled for %s' % po.repo.id)
                        
                    if cursize >= totsize: # otherwise keep it around for regetting
                        os.unlink(local)
                else:
                    self.verbose_logger.debug("using local copy of %s" %(po,))
                    continue
                        
            remote_pkgs.append(po)
            
            # caching is enabled and the package 
            # just failed to check out there's no 
            # way to save this, report the error and return
            if (self.conf.cache or repo_cached) and errors:
                return errors
                

        remote_pkgs.sort(mediasort)
        i = 0
        for po in remote_pkgs:
            i += 1
            checkfunc = (self.verifyPkg, (po, 1), {})
            dirstat = os.statvfs(po.repo.pkgdir)
            if (dirstat.f_bavail * dirstat.f_bsize) <= long(po.size):
                adderror(po, 'Insufficient space in download directory %s '
                        'to download' % po.repo.pkgdir)
                continue
            
            try:
                text = '(%s/%s): %s' % (i, len(remote_pkgs),
                                        os.path.basename(po.relativepath))
                mylocal = po.repo.getPackage(po,
                                   checkfunc=checkfunc,
                                   text=text,
                                   cache=po.repo.http_caching != 'none',
                                   )
            except Errors.RepoError, e:
                adderror(po, str(e))
            else:
                po.localpath = mylocal
                if errors.has_key(po):
                    del errors[po]

        self.plugins.run('postdownload', pkglist=pkglist, errors=errors)

        return errors

    def verifyHeader(self, fo, po, raiseError):
        """check the header out via it's naevr, internally"""
        if type(fo) is types.InstanceType:
            fo = fo.filename
            
        try:
            hlist = rpm.readHeaderListFromFile(fo)
            hdr = hlist[0]
        except (rpm.error, IndexError):
            if raiseError:
                raise URLGrabError(-1, 'Header is not complete.')
            else:
                return 0
                
        yip = YumInstalledPackage(hdr) # we're using YumInstalledPackage b/c
                                       # it takes headers <shrug>
        if yip.pkgtup != po.pkgtup:
            if raiseError:
                raise URLGrabError(-1, 'Header does not match intended download')
            else:
                return 0
        
        return 1
        
    def downloadHeader(self, po):
        """download a header from a package object.
           output based on callback, raise yum.Errors.YumBaseError on problems"""

        if hasattr(po, 'pkgtype') and po.pkgtype == 'local':
            return
                
        errors = {}
        local =  po.localHdr()
        repo = self.repos.getRepo(po.repoid)
        if os.path.exists(local):
            try:
                result = self.verifyHeader(local, po, raiseError=1)
            except URLGrabError, e:
                # might add a check for length of file - if it is < 
                # required doing a reget
                try:
                    os.unlink(local)
                except OSError, e:
                    pass
            else:
                po.hdrpath = local
                return
        else:
            if self.conf.cache:
                raise Errors.RepoError, \
                'Header not in local cache and caching-only mode enabled. Cannot download %s' % po.hdrpath
        
        if self.dsCallback: self.dsCallback.downloadHeader(po.name)
        
        try:
            if not os.path.exists(repo.hdrdir):
                os.makedirs(repo.hdrdir)
            checkfunc = (self.verifyHeader, (po, 1), {})
            hdrpath = repo.getHeader(po, checkfunc=checkfunc,
                    cache=repo.http_caching != 'none',
                    )
        except Errors.RepoError, e:
            saved_repo_error = e
            try:
                os.unlink(local)
            except OSError, e:
                raise Errors.RepoError, saved_repo_error
            else:
                raise
        else:
            po.hdrpath = hdrpath
            return

    def sigCheckPkg(self, po):
        '''Take a package object and attempt to verify GPG signature if required

        Returns (result, error_string) where result is
            0 - GPG signature verifies ok or verification is not required
            1 - GPG verification failed but installation of the right GPG key might help
            2 - Fatal GPG verifcation error, give up
        '''
        if hasattr(po, 'pkgtype') and po.pkgtype == 'local':
            check = self.conf.gpgcheck
            hasgpgkey = 0
        else:
            repo = self.repos.getRepo(po.repoid)
            check = repo.gpgcheck
            hasgpgkey = not not repo.gpgkey 
        
        if check:
            ts = self.rpmdb.readOnlyTS()
            sigresult = rpmUtils.miscutils.checkSig(ts, po.localPkg())
            localfn = os.path.basename(po.localPkg())
            
            if sigresult == 0:
                result = 0
                msg = ''

            elif sigresult == 1:
                if hasgpgkey:
                    result = 1
                else:
                    result = 2
                msg = 'Public key for %s is not installed' % localfn

            elif sigresult == 2:
                result = 2
                msg = 'Problem opening package %s' % localfn

            elif sigresult == 3:
                if hasgpgkey:
                    result = 1
                else:
                    result = 2
                result = 1
                msg = 'Public key for %s is not trusted' % localfn

            elif sigresult == 4:
                result = 2 
                msg = 'Package %s is not signed' % localfn
            
        else:
            result =0
            msg = ''

        return result, msg

    def cleanUsedHeadersPackages(self):
        filelist = []
        for txmbr in self.tsInfo:
            if txmbr.po.state not in TS_INSTALL_STATES:
                continue
            if txmbr.po.repoid == "installed":
                continue
            if not self.repos.repos.has_key(txmbr.po.repoid):
                continue
            
            # make sure it's not a local file
            repo = self.repos.repos[txmbr.po.repoid]
            local = False
            for u in repo.baseurl:
                if u.startswith("file:"):
                    local = True
                    break
                
            if local:
                filelist.extend([txmbr.po.localHdr()])
            else:
                filelist.extend([txmbr.po.localPkg(), txmbr.po.localHdr()])

        # now remove them
        for fn in filelist:
            if not os.path.exists(fn):
                continue
            try:
                os.unlink(fn)
            except OSError, e:
                self.logger.warning('Cannot remove %s', fn)
                continue
            else:
                self.verbose_logger.log(logginglevels.DEBUG_4,
                    '%s removed', fn)
        
    def cleanHeaders(self):
        exts = ['hdr']
        return self._cleanFiles(exts, 'hdrdir', 'header')

    def cleanPackages(self):
        exts = ['rpm']
        return self._cleanFiles(exts, 'pkgdir', 'package')

    def cleanSqlite(self):
        exts = ['sqlite', 'sqlite.bz2']
        return self._cleanFiles(exts, 'cachedir', 'sqlite')

    def cleanMetadata(self):
        exts = ['xml.gz', 'xml', 'cachecookie', 'mirrorlist.txt']
        return self._cleanFiles(exts, 'cachedir', 'metadata') 

    def _cleanFiles(self, exts, pathattr, filetype):
        filelist = []
        removed = 0
        for ext in exts:
            for repo in self.repos.listEnabled():
                repo.dirSetup()
                path = getattr(repo, pathattr)
                if os.path.exists(path) and os.path.isdir(path):
                    filelist = misc.getFileList(path, ext, filelist)

        for item in filelist:
            try:
                os.unlink(item)
            except OSError, e:
                self.logger.critical('Cannot remove %s file %s', filetype, item)
                continue
            else:
                self.verbose_logger.log(logginglevels.DEBUG_4,
                    '%s file %s removed', filetype, item)
                removed+=1
        msg = '%d %s files removed' % (removed, filetype)
        return 0, [msg]

    def doPackageLists(self, pkgnarrow='all'):
        """generates lists of packages, un-reduced, based on pkgnarrow option"""
        
        ygh = misc.GenericHolder()
        
        installed = []
        available = []
        updates = []
        obsoletes = []
        obsoletesTuples = []
        recent = []
        extras = []

        # list all packages - those installed and available, don't 'think about it'
        if pkgnarrow == 'all': 
            dinst = {}
            for po in self.rpmdb:
                dinst[po.pkgtup] = po;
            installed = dinst.values()
                        
            if self.conf.showdupesfromrepos:
                avail = self.pkgSack.returnPackages()
            else:
                avail = self.pkgSack.returnNewestByNameArch()
            
            for pkg in avail:
                if not dinst.has_key(pkg.pkgtup):
                    available.append(pkg)

        # produce the updates list of tuples
        elif pkgnarrow == 'updates':
            for (n,a,e,v,r) in self.up.getUpdatesList():
                matches = self.pkgSack.searchNevra(name=n, arch=a, epoch=e, 
                                                   ver=v, rel=r)
                if len(matches) > 1:
                    updates.append(matches[0])
                    self.verbose_logger.log(logginglevels.DEBUG_1,
                        'More than one identical match in sack for %s', 
                        matches[0])
                elif len(matches) == 1:
                    updates.append(matches[0])
                else:
                    self.verbose_logger.log(logginglevels.DEBUG_1,
                        'Nothing matches %s.%s %s:%s-%s from update', n,a,e,v,r)

        # installed only
        elif pkgnarrow == 'installed':
            installed = self.rpmdb.returnPackages()
        
        # available in a repository
        elif pkgnarrow == 'available':

            if self.conf.showdupesfromrepos:
                avail = self.pkgSack.returnPackages()
            else:
                avail = self.pkgSack.returnNewestByNameArch()
            
            self.rpmdb._make_header_dict()
            for pkg in avail:
                if not self.rpmdb._header_dict.has_key(pkg.pkgtup):
                    available.append(pkg)


        # not in a repo but installed
        elif pkgnarrow == 'extras':
            # we must compare the installed set versus the repo set
            # anything installed but not in a repo is an extra
            avail = self.pkgSack.simplePkgList()
            for po in self.rpmdb:
                if po.pkgtup not in avail:
                    extras.append(po)

        # obsoleting packages (and what they obsolete)
        elif pkgnarrow == 'obsoletes':
            self.conf.obsoletes = 1

            for (pkgtup, instTup) in self.up.getObsoletesTuples():
                (n,a,e,v,r) = pkgtup
                pkgs = self.pkgSack.searchNevra(name=n, arch=a, ver=v, rel=r, epoch=e)
                instpo = self.rpmdb.searchPkgTuple(instTup)[0] # the first one
                for po in pkgs:
                    obsoletes.append(po)
                    obsoletesTuples.append((po, instpo))
        
        # packages recently added to the repositories
        elif pkgnarrow == 'recent':
            now = time.time()
            recentlimit = now-(self.conf.recent*86400)
            ftimehash = {}
            if self.conf.showdupesfromrepos:
                avail = self.pkgSack.returnPackages()
            else:
                avail = self.pkgSack.returnNewestByNameArch()
            
            for po in avail:
                ftime = int(po.filetime)
                if ftime > recentlimit:
                    if not ftimehash.has_key(ftime):
                        ftimehash[ftime] = [po]
                    else:
                        ftimehash[ftime].append(po)

            for sometime in ftimehash.keys():
                for po in ftimehash[sometime]:
                    recent.append(po)
        
        
        ygh.installed = installed
        ygh.available = available
        ygh.updates = updates
        ygh.obsoletes = obsoletes
        ygh.obsoletesTuples = obsoletesTuples
        ygh.recent = recent
        ygh.extras = extras

        
        return ygh


        
    def findDeps(self, pkgs):
        """Return the dependencies for a given package object list, as well
           possible solutions for those dependencies.
           
           Returns the deps as a dict of dicts:
             packageobject = [reqs] = [list of satisfying pkgs]"""
        
        results = {}

        for pkg in pkgs:
            results[pkg] = {} 
            reqs = pkg.requires
            reqs.sort()
            pkgresults = results[pkg] # shorthand so we don't have to do the
                                      # double bracket thing
            
            for req in reqs:
                (r,f,v) = req
                if r.startswith('rpmlib('):
                    continue
                
                satisfiers = []

                for po in self.whatProvides(r, f, v):
                    satisfiers.append(po)

                pkgresults[req] = satisfiers
        
        return results
    
    def searchGenerator(self, fields, criteria):
        """Generator method to lighten memory load for some searches.
           This is the preferred search function to use."""
        sql_fields = []
        for f in fields:
            if RPM_TO_SQLITE.has_key(f):
                sql_fields.append(RPM_TO_SQLITE[f])
            else:
                sql_fields.append(f)

        scores = {}
        my_sets = {}
        matched_values = {}

        def __sortbyVal(x, y):
            (k, v) = x
            (k2, v2) = y
            if v > v2:
                return 1
            if v < v2:
                return -1
            if v == v2:
                return 0
        
        # go through each item in the criteria list
        # figure out if it matches and what it matches
        # tally up the scores for the pkgs
        # yield the results in order of most terms matched first
        
        for s in criteria:
            narrowed_list = []
            my_sets[s] = []
            if s.find('%') != -1:
                continue
            
            for sack in self.pkgSack.sacks.values():
                narrowed_list.extend(sack.searchPrimaryFields(sql_fields, s))
        
            for po in narrowed_list:
                tmpvalues = []
                for field in fields:
                    value = getattr(po, field)
                    if value and value.lower().find(s.lower()) != -1:
                        tmpvalues.append(value)

                if len(tmpvalues) > 0:
                    matched_values[po] = tmpvalues
                    my_sets[s].append(po)
                    
            for po in self.rpmdb:
                tmpvalues = []
                for field in fields:
                    value = getattr(po, field)
                    if value and value.lower().find(s.lower()) != -1:
                        tmpvalues.append(value)

                if len(tmpvalues) > 0:
                    matched_values[po] = tmpvalues
                    my_sets[s].append(po)
        
        for pkg in matched_values.keys():
            if scores.has_key(pkg):
                continue
            count = 0
            
            for this_set in my_sets.values():
                if pkg in this_set:
                    count+=1
            
            scores[pkg] = count

        i = scores.items()
        i.sort(__sortbyVal)
        i.reverse()
        
        for (pkg,count) in i:
            if matched_values.has_key(pkg):
                yield (pkg, matched_values[pkg])
            else:
                print pkg
            


    def searchPackages(self, fields, criteria, callback=None):
        """Search specified fields for matches to criteria
           optional callback specified to print out results
           as you go. Callback is a simple function of:
           callback(po, matched values list). It will 
           just return a dict of dict[po]=matched values list"""
        warnings.warn('searchPackages() will go away in a future version of Yum.\
                      Use searchGenerator() instead. \n',
                Errors.YumFutureDeprecationWarning, stacklevel=2)           
        matches = {}
        match_gen = self.searchGenerator(fields, criteria)
        
        for (po, matched_strings) in match_gen:
            if callback:
                callback(po, matched_strings)
            if not matches.has_key(po):
                matches[po] = []
            
            matches[po].extend(matched_strings)
        
        return matches
    
    def searchPackageProvides(self, args, callback=None):
        
        matches = {}
        for arg in args:
            if not re.match('.*[\*\?\[\]].*', arg):
                isglob = False
                if arg[0] != '/':
                    canBeFile = False
                else:
                    canBeFile = True
            else:
                isglob = True
                canBeFile = True
                
            if not isglob:
                usedDepString = True
                where = self.returnPackagesByDep(arg)
            else:
                usedDepString = False
                where = self.pkgSack.searchAll(arg, False)
            self.verbose_logger.log(logginglevels.DEBUG_1,
                'Searching %d packages', len(where))
            
            for po in where:
                self.verbose_logger.log(logginglevels.DEBUG_2,
                    'searching package %s', po)
                tmpvalues = []
                
                
                if usedDepString:
                    tmpvalues.append(arg)

                if isglob or canBeFile:
                    self.verbose_logger.log(logginglevels.DEBUG_2,
                        'searching in file entries')
                    for thisfile in po.dirlist + po.filelist + po.ghostlist:
                        if fnmatch.fnmatch(thisfile, arg):
                            tmpvalues.append(thisfile)
                
                self.verbose_logger.log(logginglevels.DEBUG_2,
                    'searching in provides entries')
                for (p_name, p_flag, (p_e, p_v, p_r)) in po.provides:
                    prov = misc.prco_tuple_to_string((p_name, p_flag, (p_e, p_v, p_r)))
                    if not usedDepString:
                        if fnmatch.fnmatch(p_name, arg) or fnmatch.fnmatch(prov, arg):
                            tmpvalues.append(prov)

                if len(tmpvalues) > 0:
                    if callback:
                        callback(po, tmpvalues)
                    matches[po] = tmpvalues
        
        # installed rpms, too
        taglist = ['filelist', 'dirnames', 'provides_names']
        for arg in args:
            if not re.match('.*[\*\?\[\]].*', arg):
                isglob = False
                if arg[0] != '/':
                    canBeFile = False
                else:
                    canBeFile = True
            else:
                isglob = True
                canBeFile = True
            
            if not isglob:
                where = self.returnInstalledPackagesByDep(arg)
                usedDepString = True
                for po in where:
                    tmpvalues = []
                    msg = 'Provides-match: %s' % arg
                    tmpvalues.append(msg)

                    if len(tmpvalues) > 0:
                        if callback:
                            callback(po, tmpvalues)
                        matches[po] = tmpvalues

            else:
                usedDepString = False
                where = self.rpmdb
                
                for po in where:
                    searchlist = []
                    tmpvalues = []
                    for tag in taglist:
                        tagdata = getattr(po, tag)
                        if tagdata is None:
                            continue
                        if type(tagdata) is types.ListType:
                            searchlist.extend(tagdata)
                        else:
                            searchlist.append(tagdata)
                    
                    for item in searchlist:
                        if fnmatch.fnmatch(item, arg):
                            tmpvalues.append(item)
                
                    if len(tmpvalues) > 0:
                        if callback:
                            callback(po, tmpvalues)
                        matches[po] = tmpvalues
            
            
        return matches

    def doGroupLists(self, uservisible=0):
        """returns two lists of groups, installed groups and available groups
           optional 'uservisible' bool to tell it whether or not to return
           only groups marked as uservisible"""
        
        
        installed = []
        available = []
        
        for grp in self.comps.groups:
            if grp.installed:
                if uservisible:
                    if grp.user_visible:
                        installed.append(grp)
                else:
                    installed.append(grp)
            else:
                if uservisible:
                    if grp.user_visible:
                        available.append(grp)
                else:
                    available.append(grp)
            
        return installed, available
    
    
    def groupRemove(self, grpid):
        """mark all the packages in this group to be removed"""
        
        txmbrs_used = []
        
        thisgroup = self.comps.return_group(grpid)
        if not thisgroup:
            raise Errors.GroupsError, "No Group named %s exists" % grpid

        thisgroup.toremove = True
        pkgs = thisgroup.packages
        for pkg in thisgroup.packages:
            txmbrs = self.remove(name=pkg)
            txmbrs_used.extend(txmbrs)
            for txmbr in txmbrs:
                txmbr.groups.append(thisgroup.groupid)
        
        return txmbrs_used

    def groupUnremove(self, grpid):
        """unmark any packages in the group from being removed"""
        

        thisgroup = self.comps.return_group(grpid)
        if not thisgroup:
            raise Errors.GroupsError, "No Group named %s exists" % grpid

        thisgroup.toremove = False
        pkgs = thisgroup.packages
        for pkg in thisgroup.packages:
            for txmbr in self.tsInfo:
                if txmbr.po.name == pkg and txmbr.po.state in TS_INSTALL_STATES:
                    try:
                        txmbr.groups.remove(grpid)
                    except ValueError:
                        self.verbose_logger.log(logginglevels.DEBUG_1,
                            "package %s was not marked in group %s", txmbr.po,
                            grpid)
                        continue
                    
                    # if there aren't any other groups mentioned then remove the pkg
                    if len(txmbr.groups) == 0:
                        self.tsInfo.remove(txmbr.po.pkgtup)
        
        
    def selectGroup(self, grpid):
        """mark all the packages in the group to be installed
           returns a list of transaction members it added to the transaction 
           set"""
        
        txmbrs_used = []
        
        if not self.comps.has_group(grpid):
            raise Errors.GroupsError, "No Group named %s exists" % grpid
            
        thisgroup = self.comps.return_group(grpid)
        
        if not thisgroup:
            raise Errors.GroupsError, "No Group named %s exists" % grpid
        
        if thisgroup.selected:
            return txmbrs_used
        
        thisgroup.selected = True
        
        pkgs = []
        if 'mandatory' in self.conf.group_package_types:
            pkgs.extend(thisgroup.mandatory_packages.keys())
        if 'default' in self.conf.group_package_types:
            pkgs.extend(thisgroup.default_packages.keys())
        if 'optional' in self.conf.group_package_types:
            pkgs.extend(thisgroup.optional_packages.keys())

        for pkg in pkgs:
            self.verbose_logger.log(logginglevels.DEBUG_2,
                'Adding package %s from group %s', pkg, thisgroup.groupid)
            try:
                txmbrs = self.install(name = pkg)
            except Errors.InstallError, e:
                self.verbose_logger.debug('No package named %s available to be installed',
                    pkg)
            else:
                txmbrs_used.extend(txmbrs)
                for txmbr in txmbrs:
                    txmbr.groups.append(thisgroup.groupid)
        
        if self.conf.enable_group_conditionals:
            for condreq, cond in thisgroup.conditional_packages.iteritems():
                if self.isPackageInstalled(cond):
                    try:
                        txmbrs = self.install(name = condreq)
                    except Errors.InstallError:
                        # we don't care if the package doesn't exist
                        continue
                    txmbrs_used.extend(txmbrs)
                    for txmbr in txmbrs:
                        txmbr.groups.append(thisgroup.groupid)
                    continue
                # Otherwise we hook into tsInfo.add
                pkgs = self.pkgSack.searchNevra(name=condreq)
                if pkgs:
                    pkgs = self.bestPackagesFromList(pkgs)
                if self.tsInfo.conditionals.has_key(cond):
                    self.tsInfo.conditionals[cond].extend(pkgs)
                else:
                    self.tsInfo.conditionals[cond] = pkgs

        return txmbrs_used

    def deselectGroup(self, grpid):
        """de-mark all the packages in the group for install"""
        
        if not self.comps.has_group(grpid):
            raise Errors.GroupsError, "No Group named %s exists" % grpid
            
        thisgroup = self.comps.return_group(grpid)
        if not thisgroup:
            raise Errors.GroupsError, "No Group named %s exists" % grpid
        
        thisgroup.selected = False
        
        for pkgname in thisgroup.packages:
        
            for txmbr in self.tsInfo:
                if txmbr.po.name == pkgname and txmbr.po.state in TS_INSTALL_STATES:
                    try: 
                        txmbr.groups.remove(grpid)
                    except ValueError:
                        self.verbose_logger.log(logginglevels.DEBUG_1,
                            "package %s was not marked in group %s", txmbr.po,
                            grpid)
                        continue
                    
                    # if there aren't any other groups mentioned then remove the pkg
                    if len(txmbr.groups) == 0:
                        self.tsInfo.remove(txmbr.po.pkgtup)

                    
        
    def getPackageObject(self, pkgtup):
        """retrieves a packageObject from a pkgtuple - if we need
           to pick and choose which one is best we better call out
           to some method from here to pick the best pkgobj if there are
           more than one response - right now it's more rudimentary."""
           
        
        # look it up in the self.localPackages first:
        for po in self.localPackages:
            if po.pkgtup == pkgtup:
                return po
                
        pkgs = self.pkgSack.searchPkgTuple(pkgtup)

        if len(pkgs) == 0:
            raise Errors.DepError, 'Package tuple %s could not be found in packagesack' % str(pkgtup)
            return None
            
        if len(pkgs) > 1: # boy it'd be nice to do something smarter here FIXME
            result = pkgs[0]
        else:
            result = pkgs[0] # which should be the only
        
            # this is where we could do something to figure out which repository
            # is the best one to pull from
        
        return result

    def getInstalledPackageObject(self, pkgtup):
        """returns a YumInstallPackage object for the pkgtup specified"""
        
        #FIXME - this should probably emit a deprecation warning telling
        # people to just use the command below
        
        po = self.rpmdb.searchPkgTuple(pkgtup)[0] # take the first one
        return po
        
    def gpgKeyCheck(self):
        """checks for the presence of gpg keys in the rpmdb
           returns 0 if no keys returns 1 if keys"""

        gpgkeyschecked = self.conf.cachedir + '/.gpgkeyschecked.yum'
        if os.path.exists(gpgkeyschecked):
            return 1
            
        myts = rpmUtils.transaction.initReadOnlyTransaction(root=self.conf.installroot)
        myts.pushVSFlags(~(rpm._RPMVSF_NOSIGNATURES|rpm._RPMVSF_NODIGESTS))
        idx = myts.dbMatch('name', 'gpg-pubkey')
        keys = idx.count()
        del idx
        del myts
        
        if keys == 0:
            return 0
        else:
            mydir = os.path.dirname(gpgkeyschecked)
            if not os.path.exists(mydir):
                os.makedirs(mydir)
                
            fo = open(gpgkeyschecked, 'w')
            fo.close()
            del fo
            return 1

    def returnPackagesByDep(self, depstring):
        """Pass in a generic [build]require string and this function will 
           pass back the packages it finds providing that dep."""
        
        results = []
        # parse the string out
        #  either it is 'dep (some operator) e:v-r'
        #  or /file/dep
        #  or packagename
        depname = depstring
        depflags = None
        depver = None
        
        if depstring[0] != '/':
            # not a file dep - look at it for being versioned
            if re.search('[>=<]', depstring):  # versioned
                try:
                    depname, flagsymbol, depver = depstring.split()
                except ValueError, e:
                    raise Errors.YumBaseError, 'Invalid versioned dependency string, try quoting it.'
                if not SYMBOLFLAGS.has_key(flagsymbol):
                    raise Errors.YumBaseError, 'Invalid version flag'
                depflags = SYMBOLFLAGS[flagsymbol]
                
        sack = self.whatProvides(depname, depflags, depver)
        results = sack.returnPackages()
        return results
        

    def returnPackageByDep(self, depstring):
        """Pass in a generic [build]require string and this function will 
           pass back the best(or first) package it finds providing that dep."""
        
        try:
            pkglist = self.returnPackagesByDep(depstring)
        except Errors.YumBaseError:
            raise Errors.YumBaseError, 'No Package found for %s' % depstring
        
        result = self._bestPackageFromList(pkglist)
        if result is None:
            raise Errors.YumBaseError, 'No Package found for %s' % depstring
        
        return result

    def returnInstalledPackagesByDep(self, depstring):
        """Pass in a generic [build]require string and this function will 
           pass back the installed packages it finds providing that dep."""
        
        results = []
        # parse the string out
        #  either it is 'dep (some operator) e:v-r'
        #  or /file/dep
        #  or packagename
        depname = depstring
        depflags = None
        depver = None
        
        if depstring[0] != '/':
            # not a file dep - look at it for being versioned
            if re.search('[>=<]', depstring):  # versioned
                try:
                    depname, flagsymbol, depver = depstring.split()
                except ValueError:
                    raise Errors.YumBaseError, 'Invalid versioned dependency string, try quoting it.'
                if not SYMBOLFLAGS.has_key(flagsymbol):
                    raise Errors.YumBaseError, 'Invalid version flag'
                depflags = SYMBOLFLAGS[flagsymbol]
                
        pkglist = self.rpmdb.whatProvides(depname, depflags, depver)
        
        for pkgtup in pkglist:
            results.append(self.getInstalledPackageObject(pkgtup))
        
        return results


    def _bestPackageFromList(self, pkglist):
        """take list of package objects and return the best package object.
           If the list is empty, return None. 
           
           Note: this is not aware of multilib so make sure you're only
           passing it packages of a single arch group."""
        
        
        if len(pkglist) == 0:
            return None
            
        if len(pkglist) == 1:
            return pkglist[0]
        
        mysack = ListPackageSack()
        mysack.addList(pkglist)
        bestlist = mysack.returnNewestByNameArch() # get rid of all lesser vers
        
        best = bestlist[0]
        for pkg in bestlist[1:]:
            if len(pkg.name) < len(best.name): # shortest name silliness
                best = pkg
                continue
            elif len(pkg.name) > len(best.name):
                continue

            # compare arch
            arch = rpmUtils.arch.getBestArchFromList([pkg.arch, best.arch])
            if arch == pkg.arch:
                best = pkg
                continue

        return best

    def bestPackagesFromList(self, pkglist, arch=None):
        """Takes a list of packages, returns the best packages.
           This function is multilib aware so that it will not compare
           multilib to singlelib packages""" 
    
        returnlist = []
        compatArchList = rpmUtils.arch.getArchList(arch)
        multiLib = []
        singleLib = []
        noarch = []
        for po in pkglist:
            if po.arch not in compatArchList:
                continue
            elif po.arch in ("noarch"):
                noarch.append(po)
            elif rpmUtils.arch.isMultiLibArch(arch=po.arch):
                multiLib.append(po)
            else:
                singleLib.append(po)
                
        # we now have three lists.  find the best package(s) of each
        multi = self._bestPackageFromList(multiLib)
        single = self._bestPackageFromList(singleLib)
        no = self._bestPackageFromList(noarch)

        # now, to figure out which arches we actually want
        # if there aren't noarch packages, it's easy. multi + single
        if no is None:
            if multi: returnlist.append(multi)
            if single: returnlist.append(single)
        # if there's a noarch and it's newer than the multilib, we want
        # just the noarch.  otherwise, we want multi + single
        elif multi:
            best = self._bestPackageFromList([multi,no])
            if best.arch == "noarch":
                returnlist.append(no)
            else:
                if multi: returnlist.append(multi)
                if single: returnlist.append(single)
        # similar for the non-multilib case
        elif single:
            best = self._bestPackageFromList([single,no])
            if best.arch == "noarch":
                returnlist.append(no)
            else:
                returnlist.append(single)
        # if there's not a multi or single lib, then we want the noarch
        else:
            returnlist.append(no)

        return returnlist


    def install(self, po=None, **kwargs):
        """try to mark for install the item specified. Uses provided package 
           object, if available. If not it uses the kwargs and gets the best
           packages from the keyword options provided 
           returns the list of txmbr of the items it installs
           
           """
        
        pkgs = []
        if po:
            if isinstance(po, YumAvailablePackage) or isinstance(po, YumLocalPackage):
                pkgs.append(po)
            else:
                raise Errors.InstallError, 'Package Object was not a package object instance'
            
        else:
            if not kwargs.keys():
                raise Errors.InstallError, 'Nothing specified to install'

            if kwargs.has_key('pattern'):
                exactmatch, matched, unmatched = \
                    parsePackages(self.pkgSack.returnPackages(),[kwargs['pattern']] , casematch=1)
                pkgs.extend(exactmatch)
                pkgs.extend(matched)

            else:
                nevra_dict = self._nevra_kwarg_parse(kwargs)

                pkgs = self.pkgSack.searchNevra(name=nevra_dict['name'],
                     epoch=nevra_dict['epoch'], arch=nevra_dict['arch'],
                     ver=nevra_dict['version'], rel=nevra_dict['release'])
                
            if pkgs:
                pkgSack = ListPackageSack(pkgs)
                pkgs = pkgSack.returnNewestByName()
                del(pkgSack)

                pkgbyname = {}
                for pkg in pkgs:
                    if not pkgbyname.has_key(pkg.name):
                        pkgbyname[pkg.name] = [ pkg ]
                    else:
                        pkgbyname[pkg.name].append(pkg)

                lst = []
                for pkgs in pkgbyname.values():
                    lst.extend(self.bestPackagesFromList(pkgs))
                pkgs = lst

        if len(pkgs) == 0:
            #FIXME - this is where we could check to see if it already installed
            # for returning better errors
            raise Errors.InstallError, 'No package(s) available to install'
        
        # FIXME - lots more checking here
        #  - install instead of erase
        #  - better error handling/reporting

        tx_return = []
        for po in pkgs:
            if self.tsInfo.exists(pkgtup=po.pkgtup):
                self.verbose_logger.log(logginglevels.DEBUG_1,
                    'Package: %s  - already in transaction set', po)
                tx_return.extend(self.tsInfo.getMembers(pkgtup=po.pkgtup))
                continue
            
            # make sure this shouldn't be passed to update:
            if self.up.updating_dict.has_key(po.pkgtup):
                txmbrs = self.update(po=po)
                tx_return.extend(txmbrs)
                continue
            
            # make sure it's not already installed
            if self.rpmdb.installed(name=po.name, arch=po.arch, epoch=po.epoch,
                    rel=po.release, ver=po.version):
                self.logger.warning('Package %s already installed and latest version', po)
                continue

            
            # make sure we're not installing a package which is obsoleted by something
            # else in the repo
            thispkgobsdict = self.up.checkForObsolete([po.pkgtup])
            if thispkgobsdict.has_key(po.pkgtup):
                obsoleting = thispkgobsdict[po.pkgtup][0]
                obsoleting_pkg = self.getPackageObject(obsoleting)
                self.install(po=obsoleting_pkg)
                continue
                
            txmbr = self.tsInfo.addInstall(po)
            tx_return.append(txmbr)
        
        return tx_return

    
    def update(self, po=None, **kwargs):
        """try to mark for update the item(s) specified. 
            po is a package object - if that is there, mark it for update,
            if possible
            else use **kwargs to match the package needing update
            if nothing is specified at all then attempt to update everything
            
            returns the list of txmbr of the items it marked for update"""
        
        # check for args - if no po nor kwargs, do them all
        # if po, do it, ignore all else
        # if no po do kwargs
        # uninstalled pkgs called for update get returned with errors in a list, maybe?

        updates = self.up.getUpdatesTuples()
        if self.conf.obsoletes:
            obsoletes = self.up.getObsoletesTuples(newest=1)
        else:
            obsoletes = []


        tx_return = []
        if not po and not kwargs.keys(): # update everything (the easy case)
            self.verbose_logger.log(logginglevels.DEBUG_2, 'Updating Everything')
            for (obsoleting, installed) in obsoletes:
                obsoleting_pkg = self.getPackageObject(obsoleting)
                installed_pkg =  self.rpmdb.searchPkgTuple(installed)[0]
                txmbr = self.tsInfo.addObsoleting(obsoleting_pkg, installed_pkg)
                self.tsInfo.addObsoleted(installed_pkg, obsoleting_pkg)
                tx_return.append(txmbr)
                
            for (new, old) in updates:
                if self.tsInfo.isObsoleted(pkgtup=old):
                    self.verbose_logger.log(logginglevels.DEBUG_2, 'Not Updating Package that is already obsoleted: %s.%s %s:%s-%s', 
                        old)
                else:
                    updating_pkg = self.getPackageObject(new)
                    updated_pkg = self.rpmdb.searchPkgTuple(old)[0]
                    txmbr = self.tsInfo.addUpdate(updating_pkg, updated_pkg)
                    tx_return.append(txmbr)
            
            return tx_return

        else:
            instpkgs = []
            availpkgs = []
            if po: # just a po
                if po.repoid == 'installed':
                    instpkgs.append(po)
                else:
                    availpkgs.append(po)
                
            else: # we have kwargs, sort them out.
                nevra_dict = self._nevra_kwarg_parse(kwargs)

                availpkgs = self.pkgSack.searchNevra(name=nevra_dict['name'],
                          epoch=nevra_dict['epoch'], arch=nevra_dict['arch'],
                        ver=nevra_dict['version'], rel=nevra_dict['release'])
                
                instpkgs = self.rpmdb.searchNevra(name=nevra_dict['name'], 
                            epoch=nevra_dict['epoch'], arch=nevra_dict['arch'], 
                            ver=nevra_dict['version'], rel=nevra_dict['release'])
            
            # for any thing specified
            # get the list of available pkgs matching it (or take the po)
            # get the list of installed pkgs matching it (or take the po)
            # go through each list and look for:
               # things obsoleting it if it is an installed pkg
               # things it updates if it is an available pkg
               # things updating it if it is an installed pkg
               # in that order
               # all along checking to make sure we:
                # don't update something that's already been obsoleted
            
            # TODO: we should search the updates and obsoletes list and
            # mark the package being updated or obsoleted away appropriately
            # and the package relationship in the tsInfo
            
            for installed_pkg in instpkgs:
                if self.up.obsoleted_dict.has_key(installed_pkg.pkgtup) and self.conf.obsoletes:
                    obsoleting = self.up.obsoleted_dict[installed_pkg.pkgtup][0]
                    obsoleting_pkg = self.getPackageObject(obsoleting)
                    # FIXME check for what might be in there here
                    txmbr = self.tsInfo.addObsoleting(obsoleting_pkg, installed_pkg)
                    self.tsInfo.addObsoleted(installed_pkg, obsoleting_pkg)
                    tx_return.append(txmbr)
            
            for available_pkg in availpkgs:
                if self.up.updating_dict.has_key(available_pkg.pkgtup):
                    updated = self.up.updating_dict[available_pkg.pkgtup][0]
                    if self.tsInfo.isObsoleted(updated):
                        self.verbose_logger.log(logginglevels.DEBUG_2, 'Not Updating Package that is already obsoleted: %s.%s %s:%s-%s', 
                            updated)
                    else:
                        updated_pkg =  self.rpmdb.searchPkgTuple(updated)[0]
                        txmbr = self.tsInfo.addUpdate(available_pkg, updated_pkg)
                        tx_return.append(txmbr)
                    
            for installed_pkg in instpkgs:
                if self.up.updatesdict.has_key(installed_pkg.pkgtup):
                    updating = self.up.updatesdict[installed_pkg.pkgtup][0]
                    updating_pkg = self.getPackageObject(updating)
                    if self.tsInfo.isObsoleted(installed_pkg.pkgtup):
                        self.verbose_logger.log(logginglevels.DEBUG_2, 'Not Updating Package that is already obsoleted: %s.%s %s:%s-%s', 
                            installed_pkg.pkgtup)
                    else:
                        txmbr = self.tsInfo.addUpdate(updating_pkg, installed_pkg)
                        tx_return.append(txmbr)

        return tx_return
        
        
    def remove(self, po=None, **kwargs):
        """try to find and mark for remove the specified package(s) -
            if po is specified then that package object (if it is installed) 
            will be marked for removal.
            if no po then look at kwargs, if neither then raise an exception"""

        if not po and not kwargs.keys():
            raise Errors.RemoveError, 'Nothing specified to remove'
        
        tx_return = []
        pkgs = []
        
        if po:
            pkgs = [po]
        else:
            nevra_dict = self._nevra_kwarg_parse(kwargs)

            pkgs = self.rpmdb.searchNevra(name=nevra_dict['name'], 
                        epoch=nevra_dict['epoch'], arch=nevra_dict['arch'], 
                        ver=nevra_dict['version'], rel=nevra_dict['release'])

        if len(pkgs) == 0: # should this even be happening?
            self.logger.warning("No package matched to remove")

        for po in pkgs:
            txmbr = self.tsInfo.addErase(po)
            tx_return.append(txmbr)
        
        return tx_return

    def _nevra_kwarg_parse(self, kwargs):
            
        returndict = {}
        
        try: returndict['name'] = kwargs['name']
        except KeyError:  returndict['name'] = None

        try: returndict['epoch'] = kwargs['epoch']
        except KeyError: returndict['epoch'] = None

        try: returndict['arch'] = kwargs['arch']
        except KeyError: returndict['arch'] = None
        
        # get them as ver, version and rel, release - if someone
        # specifies one of each then that's kinda silly.
        try: returndict['version'] = kwargs['version']
        except KeyError: returndict['version'] = None
        if returndict['version'] is None:
            try: returndict['version'] = kwargs['ver']
            except KeyError: returndict['version'] = None

        try: returndict['release'] = kwargs['release']
        except KeyError: returndict['release'] = None
        if returndict['release'] is None:
            try: release = kwargs['rel']
            except KeyError: returndict['release'] = None
        
        return returndict

    def getKeyForPackage(self, po, askcb = None, fullaskcb = None):
        """Retrieve a key for a package.  If needed, prompt for if the
        key should be imported using askcb.
        @po: Package object to retrieve the key of.
        @askcb: Callback function to use for asking for verification.  Takes
                arguments of the po, the userid for the key, and the keyid.
        @fullaskcb: Callback function to use for asking for verification
                of a key.  Differs from askcb in that it gets passed a
                dictionary so that we can expand the values passed.
        """
        
        repo = self.repos.getRepo(po.repoid)
        keyurls = repo.gpgkey
        key_installed = False

        ts = rpmUtils.transaction.TransactionWrapper(self.conf.installroot)

        for keyurl in keyurls:
            self.logger.info('Retrieving GPG key from %s' % keyurl)

            # Go get the GPG key from the given URL
            try:
                rawkey = urlgrabber.urlread(keyurl, limit=9999)
            except urlgrabber.grabber.URLGrabError, e:
                raise Errors.YumBaseError('GPG key retrieval failed: ' +
                                          str(e))

            # Parse the key
            try:
                keyinfo = misc.getgpgkeyinfo(rawkey)
                keyid = keyinfo['keyid']
                hexkeyid = misc.keyIdToRPMVer(keyid).upper()
                timestamp = keyinfo['timestamp']
                userid = keyinfo['userid']
            except ValueError, e:
                raise Errors.YumBaseError, \
                      'GPG key parsing failed: ' + str(e)

            # Check if key is already installed
            if misc.keyInstalled(ts, keyid, timestamp) >= 0:
                self.logger.info('GPG key at %s (0x%s) is already installed' % (
                    keyurl, hexkeyid))
                continue

            # Try installing/updating GPG key
            self.logger.critical('Importing GPG key 0x%s "%s" from %s' % (hexkeyid, userid, keyurl.replace("file://","")))
            rc = False
            if self.conf.assumeyes:
                rc = True
            elif fullaskcb:
                rc = fullaskcb({"po": po, "userid": userid,
                                "hexkeyid": hexkeyid, "keyurl": keyurl})
            elif askcb:
                rc = askcb(po, userid, hexkeyid)

            if not rc:
                raise Errors.YumBaseError, "Not installing key"
            
            # Import the key
            result = ts.pgpImportPubkey(misc.procgpgkey(rawkey))
            if result != 0:
                raise Errors.YumBaseError, \
                      'Key import failed (code %d)' % result
            self.logger.info('Key imported successfully')
            key_installed = True

            if not key_installed:
                raise Errors.YumBaseError, \
                      'The GPG keys listed for the "%s" repository are ' \
                      'already installed but they are not correct for this ' \
                      'package.\n' \
                      'Check that the correct key URLs are configured for ' \
                      'this repository.' % (repo.name)

        # Check if the newly installed keys helped
        result, errmsg = self.sigCheckPkg(po)
        if result != 0:
            self.logger.info("Import of key(s) didn't help, wrong key(s)?")
            raise Errors.YumBaseError, errmsg
    def _limit_installonly_pkgs(self):
        if self.conf.installonly_limit < 1 :
            return 
            
        toremove = []
        for instpkg in self.conf.installonlypkgs:
            for m in self.tsInfo.getMembers():
                if (m.name == instpkg or instpkg in m.po.provides_names) \
                       and m.ts_state in ('i', 'u'):
                    installed = self.rpmdb.searchNevra(name=m.name)
                    if len(installed) >= self.conf.installonly_limit - 1: # since we're adding one
                        numleft = len(installed) - self.conf.installonly_limit + 1
                        (curv, curr) = misc.get_running_kernel_version_release()
                        
                        installed.sort(packages.comparePoEVR)
                        for po in installed:
                            if (po.version, po.release) == (curv, curr): 
                                # don't remove running
                                continue
                            if numleft == 0:
                                break
                            toremove.append(po)
                            numleft -= 1
                        
        map(lambda x: self.tsInfo.addErase(x), toremove)

    def processTransaction(self, callback=None,rpmTestDisplay=None, rpmDisplay=None):
        '''
        Process the current Transaction
        - Download Packages
        - Check GPG Signatures.
        - Run Test RPM Transaction
        - Run RPM Transaction
        
        callback.event method is called at start/end of each process.
        
        @param callback: callback object (must have an event method)
        @param rpmTestDisplay: Name of display class to use in RPM Test Transaction 
        @param rpmDisplay: Name of display class to use in RPM Transaction 
        '''
        
        action = "Download Packages"
        if callback: callback.event(action=action, state="Start")
        pkgs = self._downloadPackages()
        if callback: callback.event(action=action, state="End")
        action = "Checking Signatures"
        if callback: callback.event(action=action, state="Start")
        self._checkSignatures(pkgs)
        if callback: callback.event(action=action, state="End")
        action = "Test Transaction"
        if callback: callback.event(action=action, state="Start")
        self._doTestTransaction(display=rpmTestDisplay)
        if callback: callback.event(action=action, state="End")
        action = "Run Transaction"
        if callback: callback.event(action=action, state="Start")
        self._doTransaction(display=rpmDisplay)
        if callback: callback.event(action=action, state="End")
    
    def _downloadPackages(self):
        ''' Download the need packages in the Transaction '''
        # This can be overloaded by a subclass.    
        dlpkgs = map(lambda x: x.po, filter(lambda txmbr:
                                            txmbr.ts_state in ("i", "u"),
                                            self.tsInfo.getMembers()))
           
        try:
            probs = self.downloadPkgs(dlpkgs)

        except IndexError:
            raise yum.Errors.YumBaseError, ["Unable to find a suitable mirror."]
        if len(probs.keys()) > 0:
            errstr = ["Errors were encountered while downloading packages."]
            for key in probs.keys():
                errors = yum.misc.unique(probs[key])
                for error in errors:
                    errstr.append("%s: %s" %(key, error))

            raise yum.Errors.YumDownloadError, errstr
        return dlpkgs

    def _checkSignatures(self,pkgs):
        ''' The the signatures of the downloaded packages '''
        # This can be overloaded by a subclass.    
        for po in pkgs:
            result, errmsg = self.sigCheckPkg(po)
            if result == 0:
                # Verified ok, or verify not req'd
                continue            
            elif result == 1:
               self.getKeyForPackage(po, self._askForGPGKeyImport)
            else:
                raise yum.Errors.YumGPGCheckError, errmsg

        return 0
        
    def _askForGPGKeyImport(self, po, userid, hexkeyid):
        ''' 
        Ask for GPGKeyImport 
        This need to be overloaded in a subclass to make GPG Key import work
        '''
        return False

    def _doTestTransaction(self,display=None):
        ''' Do the RPM test transaction '''
        # This can be overloaded by a subclass.    
        if self.conf.rpm_check_debug:
            self.verbose_logger.log(logginglevels.INFO_2, 
                 'Running rpm_check_debug')
            msgs = self._run_rpm_check_debug()
            if msgs:
                retmsgs = ['ERROR with rpm_check_debug vs depsolve:']
                retmsgs.extend(msgs) 
                retmsgs.append('Please report this error in bugzilla')
                raise yum.Errors.YumRPMCheckError,retmsgs
        
        tsConf = {}
        for feature in ['diskspacecheck']: # more to come, I'm sure
            tsConf[feature] = getattr( self.conf, feature )
        #
        testcb = RPMTransaction(self, test=True)
        # overwrite the default display class
        if display:
            testcb.display = display
        # clean out the ts b/c we have to give it new paths to the rpms 
        del self.ts
  
        self.initActionTs()
        # save our dsCallback out
        dscb = self.dsCallback
        self.dsCallback = None # dumb, dumb dumb dumb!
        self.populateTs( keepold=0 ) # sigh
        tserrors = self.ts.test( testcb, conf=tsConf )
        del testcb
  
        if len( tserrors ) > 0:
            errstring =  'Test Transaction Errors: '
            for descr in tserrors:
                 errstring += '  %s\n' % descr 
            raise yum.Errors.YumTestTransactionError, errstring 

        del self.ts
        # put back our depcheck callback
        self.dsCallback = dscb


    def _doTransaction(self,display=None):
        ''' do the RPM Transaction '''
        # This can be overloaded by a subclass.    
        self.initActionTs() # make a new, blank ts to populate
        self.populateTs( keepold=0 ) # populate the ts
        self.ts.check() # required for ordering
        self.ts.order() # order
        cb = RPMTransaction(self,display=SimpleCliCallBack)
        # overwrite the default display class
        if display:
            cb.display = display
        self.runTransaction( cb=cb )

        
