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
import rpm
import re
import fnmatch
import types
import errno
import time
import sre_constants

import Errors
import rpmUtils
import rpmUtils.updates
import rpmUtils.transaction
import rpmUtils.arch
import groups
from urlgrabber.grabber import URLGrabError
import depsolve

from packages import parsePackages, YumLocalPackage, YumInstalledPackage
from repomd import mdErrors

class YumBase(depsolve.Depsolve):
    """This is a primary structure and base class. It houses the objects and
       methods needed to perform most things in yum. It is almost an abstract
       class in that you will need to add your own class above it for most
       real use."""
    
    def __init__(self):
        depsolve.Depsolve.__init__(self)
        self.localdbimported = 0
        
    def doTsSetup(self):
        """setup all the transaction set storage items we'll need
           This can't happen in __init__ b/c we don't know our installroot
           yet"""
        if not self.conf.getConfigOption('installroot'):
            raise Errors.YumBaseError, 'Setting up TransactionSets before config class is up'
        
        installroot = self.conf.getConfigOption('installroot')
        self.read_ts = rpmUtils.transaction.initReadOnlyTransaction(root=installroot)
        self.tsInfo = rpmUtils.transaction.TransactionData()
        self.rpmdb = rpmUtils.RpmDBHolder()
        self.initActionTs()
        
    def doRpmDBSetup(self):
        """sets up a holder object for important information from the rpmdb"""
        
        if not self.localdbimported:
            self.log(3, 'Reading Local RPMDB')
            self.rpmdb.addDB(self.read_ts)
            self.localdbimported = 1

    def closeRpmDB(self):
        """closes down the instances of the rpmdb we have wangling around"""
        if hasattr(self, 'rpmdb'):
            del self.rpmdb
            
        if hasattr(self, 'ts'):
            del self.ts.ts
            del self.ts
        if hasattr(self, 'read_ts'):
            del self.read_ts.ts
            del self.read_ts

    def doSackSetup(self, archlist=None):
        """populates the package sacks for information from our repositories,
           takes optional archlist for archs to include"""
           
        self.log(3, 'Setting up Package Sacks')
        if not archlist:
            archlist = rpmUtils.arch.getArchList()

        archdict = {}
        for arch in archlist:
            archdict[arch] = 1

        self.repos.pkgSack.compatarchs = archdict
        self.repos.populateSack()
        self.pkgSack = self.repos.pkgSack
        self.excludePackages()
        for repo in self.repos.listEnabled():
            self.excludePackages(repo)
            self.includePackages(repo)
        self.pkgSack.buildIndexes()
        
    def doUpdateSetup(self):
        """setups up the update object in the base class and fills out the
           updates, obsoletes and others lists"""
        
        if hasattr(self, 'up'):
            return
            
        self.log(3, 'Building updates object')
        #FIXME - add checks for the other pkglists to see if we should
        # raise an error
        self.up = rpmUtils.updates.Updates(self.rpmdb.getPkgList(),
                                           self.pkgSack.simplePkgList())
        if self.conf.getConfigOption('debuglevel') >= 6:
            self.up.debug = 1
            
        if self.conf.getConfigOption('obsoletes'):
            self.up.rawobsoletes = self.pkgSack.returnObsoletes()
            
        self.up.exactarch = self.conf.getConfigOption('exactarch')
        self.up.doUpdates()

        if self.conf.getConfigOption('obsoletes'):
            self.up.doObsoletes()

        self.up.condenseUpdates()
        
    
    def doGroupSetup(self):
        """create the groups object that will store the comps metadata
           finds the repos with groups, gets their comps data and merge it
           into the group object"""
        
        self.log(3, 'Getting group metadata')
        reposWithGroups = []
        for repo in self.repos.listGroupsEnabled():
            if repo.repoXML is None:
                raise Errors.RepoError, "Repository '%s' not yet setup" % repo
            try:
                groupremote = repo.repoXML.groupLocation()
            except mdErrors.RepoMDError, e:
                pass
            else:
                reposWithGroups.append(repo)
        # now we know which repos actually have groups files.

        self.doRpmDBSetup()
        pkgtuples = self.rpmdb.getPkgList()
        overwrite = self.conf.getConfigOption('overwrite_groups')
        self.groupInfo = groups.Groups_Info(pkgtuples, overwrite_groups = overwrite)

        for repo in reposWithGroups:
            self.log(4, 'Adding group file from repository: %s' % repo)
            groupfile = repo.getGroups()
            try:
                self.groupInfo.add(groupfile)
            except Errors.GroupsError, e:
                self.errorlog(0, 'Failed to add groups file for repository: %s' % repo)

        if self.groupInfo.compscount == 0:
            raise Errors.GroupsError, 'No Groups Available in any repository'

        self.groupInfo.compileGroups()


    def buildTransaction(self):
        """go through the packages in the transaction set, find them in the
           packageSack or rpmdb, and pack up the ts accordingly"""
        #FIXME - dup this function out into cli.py to add callbacks for
        # the depresolution process
        # callbacks should be:
        # - each package added to ts
        # - each dep processed
        # - each restart of dep resolution loop
        (rescode, restring) = self.resolveDeps()
        return rescode, restring

    def excludePackages(self, repo=None):
        """removes packages from packageSacks based on global exclude lists,
           command line excludes and per-repository excludes, takes optional 
           repo object to use."""
        
        # if not repo: then assume global excludes, only
        # if repo: then do only that repos' packages and excludes
        
        if not repo: # global only
            excludelist = self.conf.getConfigOption('exclude')
            repoid = None
        else:
            excludelist = repo.excludes
            repoid = repo.id

        if len(excludelist) == 0:
            return
        
        if not repo:
            self.log(2, 'Excluding Packages in global exclude list')
        else:
            self.log(2, 'Excluding Packages from %s' % repo.name)
            
        exactmatch, matched, unmatched = \
           parsePackages(self.pkgSack.returnPackages(repoid), excludelist)
        
        for po in exactmatch + matched:
            self.log(3, 'Excluding %s' % po)
            self.pkgSack.delPackage(po)
        
        self.log(2, 'Finished')

    def includePackages(self, repo):
        """removes packages from packageSacks based on list of packages, to include.
           takes repoid as a mandatory argument."""
        
        includelist = repo.includepkgs
        
        if len(includelist) == 0:
            return
        
        pkglist = self.pkgSack.returnPackages(repo.id)
        exactmatch, matched, unmatched = \
           parsePackages(pkglist, includelist)
        
        self.log(2, 'Reducing %s to included packages only' % repo.name)
        rmlist = []
        
        for po in pkglist:
            if po in exactmatch + matched:
                self.log(3, 'Keeping included package %s' % po)
                continue
            else:
                rmlist.append(po)
        
        for po in rmlist:
            self.log(3, 'Removing unmatched package %s' % po)
            self.pkgSack.delPackage(po)
            
        self.log(2, 'Finished')
        
    def excludeNonCompatArchs(self):
        """runs through the whole packageSack and excludes any arch not compatible
           with the system"""
        
        self.log(2, 'Excluding Incompatible Archs')
        archlist = ['src'] # source rpms are allowed
        archlist.extend(rpmUtils.arch.getArchList())
        
        for po in self.pkgSack.returnPackages():
            if po.arch not in archlist:
                self.log(3, 'Arch Excluding %s' % po)
                self.pkgSack.delPackage(po)
        self.log(2, 'Finished')
        
        
        
    def doLock(self, lockfile):
        """perform the yum locking, raise yum-based exceptions, not OSErrors"""
        
        # if we're not root then we don't lock - just return nicely
        if self.conf.getConfigOption('uid') != 0:
            return
        
        mypid=str(os.getpid())    
        while not self._lock(lockfile, mypid, 0644):
            fd = open(lockfile, 'r')
            try: oldpid = int(fd.readline())
            except ValueError:
                # bogus data in the pid file. Throw away.
                self._unlock(lockfile)
            else:
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
                    msg = 'Existing lock %s: another copy is running. Aborting.' % lockfile
                    raise Errors.LockError(0, msg)
    
    def doUnlock(self, lockfile):
        """do the unlock for yum"""
        
        # if we're not root then we don't lock - just return nicely
        if self.conf.getConfigOption('uid') != 0:
            return
        self._unlock(lockfile)
        
    def _lock(self, filename, contents='', mode=0777):
        try:
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

        for (csumtype, csum, csumid) in po.checksums:
            if csumid:
                checksum = csum
                checksumType = csumtype
                break
        try:
            self.verifyChecksum(fo, checksumType, checksum)
        except URLGrabError, e:
            if raiseError:
                raise
            else:
                return 0

        ylp = YumLocalPackage(self.read_ts, fo)
        if ylp.pkgtup() != po.pkgtup():
            if raiseError:
                raise URLGrabError(-1, 'Package does not match intended download')
            else:
                return 0
        
        return 1
        
        
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
        """download list of package objects handed to you, output based on
           callback, raise yum.Errors.YumBaseError on problems"""

        errors = {}
        for po in pkglist:
            if hasattr(po, 'pkgtype') and po.pkgtype == 'local':
                continue
                    
            local = po.localPkg()
            if os.path.exists(local):
                try:
                    result = self.verifyPkg(local, po, raiseError=1)
                except URLGrabError, e:
                    os.unlink(local)
                else:
                    if result:
                        continue
                    else:
                        os.unlink(local)

            repo = self.repos.getRepo(po.repoid)
            remote = po.returnSimple('relativepath')
            checkfunc = (self.verifyPkg, (po, 1), {})

            try:
                mylocal = repo.get(relative=remote, local=local, checkfunc=checkfunc)
            except Errors.RepoError, e:
                if not errors.has_key(po):
                    errors[po] = []
                errors[po].append(str(e))
            else:
                po.localpath = mylocal
                if errors.has_key(po):
                    del errors[po]

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
        if yip.pkgtup() != po.pkgtup():
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
        start = po.returnSimple('hdrstart')
        end = po.returnSimple('hdrend')
        repo = self.repos.getRepo(po.repoid)
        remote = po.returnSimple('relativepath')
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
                'Header not in local cache and caching-only mode enabled. Cannot download %s' % remote
        
        if self.dsCallback: self.dsCallback.downloadHeader(po.name)
        
        try:
            checkfunc = (self.verifyHeader, (po, 1), {})
            hdrpath = repo.get(relative=remote, local=local, start=start, 
                               end=end, checkfunc=checkfunc, copy_local=1)
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

    def sigCheckPkgs(self, pkgs):
        """takes a list of package objects, checks their sig/checksums, returns
           a list of failures"""
        errorlist = []
        for po in pkgs:
            if hasattr(po, 'pkgtype') and po.pkgtype == 'local':
                check = self.conf.gpgcheck
            else:
                repo = self.repos.getRepo(po.repoid)
                check = repo.gpgcheck
                
            if check:
                result = rpmUtils.miscutils.checkSig(self.read_ts, po.localPkg())
                localfn = po.localPkg()
                
                msg = ''
                if result == 0:
                    continue
                elif result == 1:
                    msg = 'public key not available for %s' % localfn
                elif result == 2:
                    msg = 'problem opening package %s' % localfn
                elif result == 3:
                    msg = 'untrusted public key for %s' % localfn
                elif result == 4:
                    msg = 'unsigned package %s' % localfn
                
                errorlist.append(msg)
            
        return errorlist
        
    
        
    def cleanHeaders(self):
        filelist = []
        ext = 'hdr'
        removed = 0
        for repo in self.repos.listEnabled():
            repo.dirSetup()
            path = repo.hdrdir
            filelist = misc.getFileList(path, ext, filelist)
            
        for hdr in filelist:
            try:
                os.unlink(hdr)
            except OSError, e:
                self.errorlog(0, 'Cannot remove header %s' % hdr)
                continue
            else:
                self.log(7, 'Header %s removed' % hdr)
                removed+=1
        msg = '%d headers removed' % removed
        return 0, [msg]

            
    def cleanPackages(self):
        filelist = []
        ext = 'rpm'
        removed = 0
        for repo in self.repos.listEnabled():
            repo.dirSetup()
            path = repo.pkgdir
            filelist = misc.getFileList(path, ext, filelist)
            
        for pkg in filelist:
            try:
                os.unlink(pkg)
            except OSError, e:
                self.errorlog(0, 'Cannot remove package %s' % pkg)
                continue
            else:
                self.log(7, 'Package %s removed' % pkg)
                removed+=1
        
        msg = '%d packages removed' % removed
        return 0, [msg]

    def cleanPickles(self):
        filelist = []
        ext = 'pickle'
        removed = 0
        for repo in self.repos.listEnabled():
            repo.dirSetup()
            path = repo.cachedir
            filelist = misc.getFileList(path, ext, filelist)
            
        for item in filelist:
            try:
                os.unlink(item)
            except OSError, e:
                self.errorlog(0, 'Cannot remove cache file %s' % item)
                continue
            else:
                self.log(7, 'Cache file %s removed' % item)
                removed+=1
        msg = '%d cache files removed' % removed
        return 0, [msg]
    

    def cleanMetadata(self):
        filelist = []
        exts = ['xml.gz', 'xml']
        
        removed = 0
        for ext in exts:
            for repo in self.repos.listEnabled():
                repo.dirSetup()
                path = repo.cachedir
                filelist = misc.getFileList(path, ext, filelist)
            
        for item in filelist:
            try:
                os.unlink(item)
            except OSError, e:
                self.errorlog(0, 'Cannot remove metadata file %s' % item)
                continue
            else:
                self.log(7, 'metadata file %s removed' % item)
                removed+=1
        msg = '%d metadata files removed' % removed
        return 0, [msg]
        
    def sortPkgObj(self, pkg1 ,pkg2):
        """sorts a list of package tuples by name"""
        if pkg1.name > pkg2.name:
            return 1
        elif pkg1.name == pkg2.name:
            return 0
        else:
            return -1
    
    def doPackageLists(self, pkgnarrow='all'):
        """generates lists of packages, un-reduced, based on pkgnarrow option"""
        
        ygh = misc.GenericHolder()
        
        installed = []
        available = []
        updates = []
        obsoletes = []
        recent = []
        extras = []

        # list all packages - those installed and available, don't 'think about it'
        if pkgnarrow == 'all': 
            self.doRepoSetup()
            self.doRpmDBSetup()
            inst = self.rpmdb.getPkgList()
            for hdr in self.rpmdb.getHdrList():
                po = YumInstalledPackage(hdr)
                installed.append(po)

            if self.conf.showdupesfromrepos:
                avail = self.pkgSack.returnPackages()
            else:
                avail = self.pkgSack.returnNewestByNameArch()

            for pkg in avail:
                pkgtup = (pkg.name, pkg.arch, pkg.epoch, pkg.version, pkg.release)
                if pkgtup not in inst:
                    available.append(pkg)

        # produce the updates list of tuples
        elif pkgnarrow == 'updates':
            self.doRepoSetup()
            self.doRpmDBSetup()
            self.doUpdateSetup()
            for (n,a,e,v,r) in self.up.getUpdatesList():
                matches = self.pkgSack.searchNevra(name=n, arch=a, epoch=e, 
                                                   ver=v, rel=r)
                if len(matches) > 1:
                    updates.append(matches[0])
                    self.log(4, 'More than one identical match in sack for %s' % matches[0])
                elif len(matches) == 1:
                    updates.append(matches[0])
                else:
                    self.log(4, 'Nothing matches %s.%s %s:%s-%s from update' % (n,a,e,v,r))

        # installed only
        elif pkgnarrow == 'installed':
            self.doRpmDBSetup()
            for hdr in self.rpmdb.getHdrList():
                po = YumInstalledPackage(hdr)
                installed.append(po)
        
        # available in a repository
        elif pkgnarrow == 'available':
            self.doRepoSetup()
            self.doRpmDBSetup()
            inst = self.rpmdb.getPkgList()
            if self.conf.showdupesfromrepos:
                avail = self.pkgSack.returnPackages()
            else:
                avail = self.pkgSack.returnNewestByNameArch()

            for pkg in avail:
                pkgtup = (pkg.name, pkg.arch, pkg.epoch, pkg.version, pkg.release)
                if pkgtup not in inst:
                    available.append(pkg)

        # not in a repo but installed
        elif pkgnarrow == 'extras':
            # we must compare the installed set versus the repo set
            # anything installed but not in a repo is an extra
            self.doRepoSetup()
            self.doRpmDBSetup()
            avail = self.pkgSack.simplePkgList()
            for hdr in self.rpmdb.getHdrList():
                po = YumInstalledPackage(hdr)
                if po.pkgtup() not in avail:
                    extras.append(po)

        # obsoleting packages (and what they obsolete)
        elif pkgnarrow == 'obsoletes':
            self.doRepoSetup()
            self.doRpmDBSetup()
            self.conf.setConfigOption('obsoletes', 1)
            self.doUpdateSetup()

            for pkgtup in self.up.getObsoletesList():
                (n,a,e,v,r) = pkgtup
                pkgs = self.pkgSack.searchNevra(name=n, arch=a, ver=v, rel=r, epoch=e)
                for po in pkgs:
                    obsoletes.append(po)
        
        # packages recently added to the repositories
        elif pkgnarrow == 'recent':
            now = time.time()
            recentlimit = now-(self.conf.recent*86400)
            ftimehash = {}
            self.doRepoSetup()
            if self.conf.showdupesfromrepos:
                avail = self.pkgSack.returnPackages()
            else:
                avail = self.pkgSack.returnNewestByNameArch()
            
            for po in avail:
                ftime = int(po.returnSimple('filetime'))
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
        ygh.recent = recent
        ygh.extras = extras
        
        return ygh

    def _refineSearchPattern(self, arg):
        """Takes a search string from the cli for Search or Provides
           and cleans it up so it doesn't make us vomit"""
           
        if re.match('.*[\*,\[,\],\{,\},\?,\+].*', arg):
            restring = fnmatch.translate(arg)
        else:
            restring = arg
        
        return restring
        
    def searchPackages(self, fields, criteria, callback=None):
        """Search specified fields for matches to criteria
           optional callback specified to print out results
           as you go. Callback is a simple function of:
           callback(po, matched values list). It will 
           just return a dict of dict[po]=matched values list"""
        
        self.doRepoSetup()
        self.doRpmDBSetup()
        matches = {}
        for string in criteria:
            restring = self._refineSearchPattern(string)
            
            try: crit_re = re.compile(restring, flags=re.I)
            except sre_constants.error, e:
                raise Errors.MiscError, \
                 'Search Expression: %s is an invalid Regular Expression.\n' % string
                  
            for po in self.pkgSack:
                tmpvalues = []
                for field in fields:
                    value = po.returnSimple(field)
                    if crit_re.search(value):
                        tmpvalues.append(value)
                if len(tmpvalues) > 0:
                    if callback:
                        callback(po, tmpvalues)
                    matches[po] = tmpvalues
        
        # do the same for installed pkgs
        for hdr in self.rpmdb.getHdrList(): # this is more expensive so this is the  top op
            po = YumInstalledPackage(hdr)
            tmpvalues = []
            for string in criteria:
                restring = self._refineSearchPattern(string)
                
                try: crit_re = re.compile(restring, flags=re.I)
                except sre_constants.error, e:
                    raise Errors.MiscError, \
                     'Search Expression: %s is an invalid Regular Expression.\n' % string

                for field in fields:
                    value = po.returnSimple(field)
                    if type(value) is types.ListType: # this is annoying
                        value = str(value)
                    if crit_re.search(value):
                        tmpvalues.append(value)
            if len(tmpvalues) > 0:
                if callback:
                    callback(po, tmpvalues)
                matches[po] = tmpvalues
        
        return matches
    
    def searchPackageProvides(self, args, callback=None):
        
        self.doRepoSetup()
        self.doRpmDBSetup()
        matches = {}
        
        # search pkgSack - fully populate the worthwhile metadata to search
        # if it even vaguely matches
        for arg in args:
            matched = 0
            globs = ['.*bin\/.*', '.*\/etc\/.*', '^\/usr\/lib\/sendmail$']
            for glob in globs:
                globc = re.compile(glob)
                if globc.match(arg):
                    matched = 1
            if not matched:
                self.log(2, 'Importing Additional filelist information for packages')
                self.repos.populateSack(with='filelists')

        for arg in args:
            restring = self._refineSearchPattern(arg)
            try: arg_re = re.compile(restring, flags=re.I)
            except sre_constants.error, e:
                raise Errors.MiscError, \
                 'Search Expression: %s is an invalid Regular Expression.\n' % arg
            
            for po in self.pkgSack:
                tmpvalues = []
                for filetype in po.returnFileTypes():
                    for fn in po.returnFileEntries(ftype=filetype):
                        if arg_re.search(fn):
                            tmpvalues.append(fn)

                for (p_name, p_flag, (p_e, p_v, p_r)) in po.returnPrco('provides'):
                    if arg_re.search(p_name):
                        prov = po.prcoPrintable((p_name, p_flag, (p_e, p_v, p_r)))
                        tmpvalues.append(prov)

                if len(tmpvalues) > 0:
                    if callback:
                        callback(po, tmpvalues)
                    matches[po] = tmpvalues
        
        # installed rpms, too
        taglist = ['filenames', 'dirnames', 'provides']
        arg_re = []
        for arg in args:
            restring = self._refineSearchPattern(arg)

            try: reg = re.compile(restring, flags=re.I)
            except sre_constants.error, e:
                raise Errors.MiscError, \
                 'Search Expression: %s is an invalid Regular Expression.\n' % arg
            
            arg_re.append(reg)

        for hdr in self.rpmdb.getHdrList():
            po = YumInstalledPackage(hdr)
            tmpvalues = []
            searchlist = []
            for tag in taglist:
                tagdata = po.returnSimple(tag)
                if tagdata is None:
                    continue
                if type(tagdata) is types.ListType:
                    searchlist.extend(tagdata)
                else:
                    searchlist.append(tagdata)
            
            for reg in arg_re:
                for item in searchlist:
                    if reg.search(item):
                        tmpvalues.append(item)

            del searchlist

            if len(tmpvalues) > 0:
                if callback:
                    callback(po, tmpvalues)
                matches[po] = tmpvalues
            
            
        return matches

    def doGroupLists(self, uservisible=0):
        """returns two lists of groups, installed groups and available groups
           optional 'uservisible' bool to tell it whether or not to return
           only groups marked as uservisible"""
        
        if uservisible:
            availgroups = self.groupInfo.visible_groups
        else:
            availgroups = self.groupInfo.grouplist
        
        installed = []
        available = []
        
        for group in availgroups:
            if self.groupInfo.isGroupInstalled(group):
                installed.append(group)
            else:
                available.append(group)

        installed.sort()
        available.sort()
        
        return installed, available
        
    def getPackageObject(self, pkgtup):
        """retrieves a packageObject from a pkgtuple - if we need
           to pick and choose which one is best we better call out
           to some method from here to pick the best pkgobj if there are
           more than one response - right now it's more rudimentary."""
           
        
        (n,a,e,v,r) = pkgtup
        
        # look it up in the self.localPackages first:
        for po in self.localPackages:
            if po.pkgtup() == pkgtup:
                return po
                
        pkgs = self.pkgSack.searchNevra(name=n, arch=a, epoch=e, ver=v, rel=r)

        if len(pkgs) == 0:
            raise Errors.DepError, 'Package tuple %s could not be found in packagesack' % pkgtup
            return None
            
        if len(pkgs) > 1: # boy it'd be nice to do something smarter here FIXME
            result = pkgs[0]
        else:
            result = pkgs[0] # which should be the only
        
            # this is where we could do something to figure out which repository
            # is the best one to pull from
        
        return result
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
            fo = open(gpgkeyschecked, 'w')
            fo.close()
            del fo
            return 1

