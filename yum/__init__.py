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
import errno
import Errors

import rpmUtils
import rpmUtils.transaction
import depsolve

class YumBase(depsolve.Depsolve):
    """This is a primary structure and base class. It houses the objects and
       methods needed to perform most things in yum. It is almost an abstract
       class in that you will need to add your own class above it for most
       real use."""
    
    def __init__(self):
        depsolve.Depsolve.__init__(self)
        self.read_ts = rpmUtils.transaction.initReadOnlyTransaction()
        self.tsInfo = rpmUtils.transaction.TransactionData()
        self.rpmdb = rpmUtils.RpmDBHolder()

    def doRpmDBSetup(self):
        """sets up a holder object for important information from the rpmdb"""
        
        self.rpmdb.addDB(self.read_ts)

    def doSackSetup(self):
        """populates the package sacks for information from our repositories"""
        self.repos.populateSack()
        self.pkgSack = self.repos.pkgSack


    def doUpdateSetup(self):
        """setups up the update object in the base class and fills out the
           updates, obsoletes and others lists"""
        
        #FIXME - add checks for the other pkglists to see if we should
        # raise an error
        self.up = rpmUtils.updates.Updates(self.rpmdb.getPkgList(),
                                           self.pkgSack.simplePkgList())
                                       
        self.up.exactarch = self.conf.getConfigOption('exactarch')
        self.up.doUpdates()
        self.up.condenseUpdates()
        
        
    def buildTransaction(self):
        """go through the packages in the transaction set, find them in the
           packageSack or rpmdb, and pack up the ts accordingly"""
        (rescode, restring) = self.resolveDeps()
        return rescode, restring
    
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
        
    def downloadPkgs(self, pkglist, callback=None):
        """download list of package objects handed to you, output based on
           callback, raise yum.Errors.YumBaseError on problems"""

        #downloading
        # build up list of things needed to download
        # get po for each item
        # pass list of po to downloader method
        # download
        # checksum from po.checksums
        # if we get an error we can't surmount exit and go away

        errors = {}
        for po in pkglist:
            for (csumtype, csum, csumid) in po.checksums:
                if csumid:
                    checksum = csum
                    checksumType = csumtype
                    break
            repo = self.repos.getRepo(po.repoid)
            remote = po.returnSimple('relativepath')
            rpmfn = os.path.basename(remote)
            local = repo.pkgdir + '/' + rpmfn
            rpmgood = 0
            retrycount = 0
            while not rpmgood and retrycount < self.conf.getConfigOption('retries'):
                try:
                    mylocal = repo.get(relative=remote, local=local)
                except Errors.RepoError, e:
                    errors[po] = e
                    retrycount+=1
                else: # no errors doing the download, check the checksum
                    filesum = misc.checksum(checksumType, local)
                    if filesum != checksum:
                        retrycount+=1
                        self.errorlog(0, 'Package %s does not match checksum, removing' % mylocal)
                        os.unlink(mylocal)
                        continue
                    
                    if errors.has_key(po):
                        del errors[po]
                    rpmgood=1
                
            
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
        
