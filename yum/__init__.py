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
import errno
import Errors

import rpmUtils
import rpmUtils.transaction
import groups
from urlgrabber.grabber import URLGrabError
import depsolve

from packages import parsePackages
from repomd import mdErrors

class YumBase(depsolve.Depsolve):
    """This is a primary structure and base class. It houses the objects and
       methods needed to perform most things in yum. It is almost an abstract
       class in that you will need to add your own class above it for most
       real use."""
    
    def __init__(self):
        depsolve.Depsolve.__init__(self)

        
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
        self.log(3, 'Reading Local RPMDB')
        self.rpmdb.addDB(self.read_ts)

    def doSackSetup(self):
        """populates the package sacks for information from our repositories"""
        self.log(3, 'Setting up Package Sacks')
        self.repos.populateSack()
        self.pkgSack = self.repos.pkgSack
        self.excludePackages()
        self.excludeNonCompatArchs()
        for repo in self.repos.listEnabled():
            self.excludePackages(repo)

    def doUpdateSetup(self):
        """setups up the update object in the base class and fills out the
           updates, obsoletes and others lists"""
        
        self.log(3, 'Building updates object')
        #FIXME - add checks for the other pkglists to see if we should
        # raise an error
        self.up = rpmUtils.updates.Updates(self.rpmdb.getPkgList(),
                                           self.pkgSack.simplePkgList())
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
        
        pkgtuples = self.rpmdb.getPkgList()
        overwrite = self.conf.getConfigOption('overwrite_groups')
        self.groupInfo = groups.Groups_Info(pkgtuples, overwrite_groups = overwrite)

        for repo in reposWithGroups:
            groupfile = repo.getGroups()
            self.groupInfo.add(groupfile)

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
            self.log(2, 'Excluding Packages')
            excludelist = self.conf.getConfigOption('exclude')
            repoid = None
        else:
            self.log(2, 'Excluding Packages from %s' % repo.name)
            excludelist = repo.excludes
            repoid = repo.id

        if len(excludelist) == 0:
            return
        exactmatch, matched, unmatched = \
           parsePackages(self.pkgSack.returnPackages(repoid), excludelist)
        
        for po in exactmatch + matched:
            self.log(3, 'Excluding %s' % po)
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
        
    def includePackages(self, repoid):
        """removes packages from packageSacks based on list of packages, to include.
           takes repoid as a mandatory argument."""
        
        # if includepkgs is not set for that repo then return w/no changes
        # otherwise remove all pkgs in the packageSack for that repo that
        # do not match the includepkgs
        
        
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
        
    
    def verifyChecksum(self, file, checksumType, csum):
        """Verify the checksum of the file versus the 
           provided checksum"""

        try:
            filesum = misc.checksum(checksumType, file)
        except Errors.MiscError, e:
            raise URLGrabError(-3, 'Could not perform checksum')
            
        if filesum != csum:
            raise URLGrabError(-2, 'Package does not match checksum')
        
        return 0
            
           
    def downloadPkgs(self, pkglist, callback=None):
        """download list of package objects handed to you, output based on
           callback, raise yum.Errors.YumBaseError on problems"""

        errors = {}
        for po in pkglist:
            for (csumtype, csum, csumid) in po.checksums:
                if csumid:
                    checksum = csum
                    checksumType = csumtype
                    break
            
            local =  po.localPkg()
            repo = self.repos.getRepo(po.repoid)
            remote = po.returnSimple('relativepath')
            if os.path.exists(local):
                try:
                    result = self.verifyChecksum(local, checksumType, checksum)
                except URLGrabError, e:
                    os.unlink(local)
                else:
                    if result == 0:
                        continue
                    else:
                        os.unlink(local)
            
            checkfunc = (self.verifyChecksum, (checksumType, csum), {})

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

    def sigCheckPkgs(self, pkgs):
        """takes a list of package objects, checks their sig/checksums, returns
           a list of failures"""
        errorlist = []
        for po in pkgs:
            repo = self.repos.getRepo(po.repoid)
            if repo.gpgcheck:
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
    
