#!/usr/bin/python -t
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
# Parts Copyright 2007 Red Hat, Inc


import rpm
import os
import fcntl
import time
import logging
import types
import sys
from yum.constants import *


class NoOutputCallBack:
    def __init__(self):
        pass
        
    def event(self, package, action, te_current, te_total, ts_current, ts_total):
        """
        @param package: A yum package object or simple string of a package name
        @param action: A yum.constant transaction set state or in the obscure 
                       rpm repackage case it could be the string 'repackaging'
        @param te_current: current number of bytes processed in the transaction
                           element being processed
        @param te_total: total number of bytes in the transaction element being
                         processed
        @param ts_current: number of processes completed in whole transaction
        @param ts_total: total number of processes in the transaction.
        """
        # this is where a progress bar would be called
        
        pass

    def scriptout(self, package, msgs):
        """package is the package.  msgs is the messages that were
        output (if any)."""
        pass

    def errorlog(self, msg):
        """takes a simple error msg string"""
        
        pass

    def filelog(self, package, action):
        # check package object type - if it is a string - just output it
        """package is the same as in event() - a package object or simple string
           action is also the same as in event()"""
        pass
        
class RPMBaseCallback:
    '''
    Base class for a RPMTransaction display callback class
    '''
    def __init__(self):
        self.action = { TS_UPDATE : 'Updating', 
                        TS_ERASE: 'Erasing',
                        TS_INSTALL: 'Installing', 
                        TS_TRUEINSTALL : 'Installing',
                        TS_OBSOLETED: 'Obsoleted',
                        TS_OBSOLETING: 'Installing',
                        TS_UPDATED: 'Cleanup',
                        'repackaging': 'Repackaging'}
        self.fileaction = { TS_UPDATE: 'Updated', 
                            TS_ERASE: 'Erased',
                            TS_INSTALL: 'Installed', 
                            TS_TRUEINSTALL: 'Installed', 
                            TS_OBSOLETED: 'Obsoleted',
                            TS_OBSOLETING: 'Installed',
                            TS_UPDATED: 'Cleanup'}   
        self.logger = logging.getLogger('yum.filelogging.RPMInstallCallback')        
        
    def event(self, package, action, te_current, te_total, ts_current, ts_total):
        """
        @param package: A yum package object or simple string of a package name
        @param action: A yum.constant transaction set state or in the obscure 
                       rpm repackage case it could be the string 'repackaging'
        @param te_current: Current number of bytes processed in the transaction
                           element being processed
        @param te_total: Total number of bytes in the transaction element being
                         processed
        @param ts_current: number of processes completed in whole transaction
        @param ts_total: total number of processes in the transaction.
        """
        raise NotImplementedError()

    def scriptout(self, package, msgs):
        """package is the package.  msgs is the messages that were
        output (if any)."""
        pass

    def errorlog(self, msg):
        # FIXME this should probably dump to the filelog, too
        print >> sys.stderr, msg

    def filelog(self, package, action):
        # check package object type - if it is a string - just output it
        msg = '%s: %s' % (self.fileaction[action], package)
        self.logger.info(msg)
            

class SimpleCliCallBack(RPMBaseCallback):
    def __init__(self):
        RPMBaseCallback.__init__(self)
        self.lastmsg = None
        self.lastpackage = None # name of last package we looked at
        
    def event(self, package, action, te_current, te_total, ts_current, ts_total):
        # this is where a progress bar would be called
        msg = '%s: %s %s/%s [%s/%s]' % (self.action[action], package, 
                                   te_current, te_total, ts_current, ts_total)
        if msg != self.lastmsg:
            print msg
        self.lastmsg = msg
        self.lastpackage = package

    def scriptout(self, package, msgs):
        if msgs:
            print msgs,

class RPMTransaction:
    def __init__(self, base, test=False, display=NoOutputCallBack):
        if not callable(display):
            self.display = display
        else:
            self.display = display() # display callback
        self.base = base # base yum object b/c we need so much
        self.test = test # are we a test?
        
        self.filehandles = {}
        self.total_actions = 0
        self.total_installed = 0
        self.complete_actions = 0
        self.installed_pkg_names = []
        self.total_removed = 0
        self.logger = logging.getLogger('yum.filelogging.RPMInstallCallback')
        self.filelog = False

        self._setupOutputLogging()

    def _setupOutputLogging(self):
        # UGLY... set up the transaction to record output from scriptlets
        (r, w) = os.pipe()
        # need fd objects, and read should be non-blocking
        self._readpipe = os.fdopen(r, 'r')
        fcntl.fcntl(self._readpipe.fileno(), fcntl.F_SETFL,
                    fcntl.fcntl(self._readpipe.fileno(),
                                fcntl.F_GETFL) | os.O_NONBLOCK)
        self._writepipe = os.fdopen(w, 'w')
        self.base.ts.ts.scriptFd = self._writepipe.fileno()
        rpm.setVerbosity(rpm.RPMLOG_INFO)
        rpm.setLogFile(self._writepipe)

    def _shutdownOutputLogging(self):
        # reset rpm bits from reording output
        rpm.setVerbosity(rpm.RPMLOG_NOTICE)
        rpm.setLogFile(sys.stderr)
        try:
            self._writepipe.close()
        except:
            pass

    def _scriptOutput(self):
        try:
            out = self._readpipe.read()
            return out
        except IOError:
            pass

    def __del__(self):
        self._shutdownOutputLogging()
        
    def _dopkgtup(self, hdr):
        tmpepoch = hdr['epoch']
        if tmpepoch is None: epoch = '0'
        else: epoch = str(tmpepoch)

        return (hdr['name'], hdr['arch'], epoch, hdr['version'], hdr['release'])

    def _makeHandle(self, hdr):
        handle = '%s:%s.%s-%s-%s' % (hdr['epoch'], hdr['name'], hdr['version'],
          hdr['release'], hdr['arch'])

        return handle
    
    def ts_done(self, package, action):
        """writes out the portions of the transaction which have completed"""
        
        if self.test: return
    
        if not hasattr(self, '_ts_done'):
            # need config variable to put this in a better path/name
            te_fn = '%s/transaction-done.%s' % (self.base.conf.persistdir, self._ts_time)
            self.ts_done_fn = te_fn
            try:
                self._ts_done = open(te_fn, 'w')
            except (IOError, OSError), e:
                self.display.errorlog('could not open ts_done file: %s' % e)
                return
        
        # walk back through self._te_tuples
        # make sure the package and the action make some kind of sense
        # write it out and pop(0) from the list
        
        # make sure we have a list to work from - rpm seems to be throwing us
        # some curveballs
        if len(self._te_tuples) == 0:
            msg = 'extra callback for package %s in state %d' % (package, action)
            self.display.errorlog(msg)
            return

        (t,e,n,v,r,a) = self._te_tuples[0] # what we should be on

        # make sure we're in the right action state
        msg = 'ts_done state is %s %s should be %s %s' % (package, action, t, n)
        if action in TS_REMOVE_STATES:
            if t != 'erase':
                self.display.errorlog(msg)
        if action in TS_INSTALL_STATES:
            if t != 'install':
                self.display.errorlog(msg)
                
        # check the pkg name out to make sure it matches
        if type(package) in types.StringTypes:
            name = package
        else:
            name = package.name
        
        if n != name:
            msg = 'ts_done name in te is %s should be %s' % (n, package)
            self.display.errorlog(msg)

        # hope springs eternal that this isn't wrong
        msg = '%s %s:%s-%s-%s.%s\n' % (t,e,n,v,r,a)

        self._ts_done.write(msg)
        self._ts_done.flush()
        self._te_tuples.pop(0)
    
    def ts_all(self):
        """write out what our transaction will do"""
        
        # save the transaction elements into a list so we can run across them
        if not hasattr(self, '_te_tuples'):
            self._te_tuples = []

        for te in self.base.ts:
            n = te.N()
            a = te.A()
            v = te.V()
            r = te.R()
            e = te.E()
            if e is None:
                e = '0'
            if te.Type() == 1:
                t = 'install'
            elif te.Type() == 2:
                t = 'erase'
            else:
                t = te.Type()
            
            # save this in a list            
            self._te_tuples.append((t,e,n,v,r,a))

        # write to a file
        self._ts_time = time.strftime('%Y-%m-%d.%H:%M.%S')
        tsfn = '%s/transaction-all.%s' % (self.base.conf.persistdir, self._ts_time)
        self.ts_all_fn = tsfn
        try:
            # fixme - we should probably be making this elsewhere but I'd
            # rather that the transaction not fail so we do it here, anyway
            if not os.path.exists(self.base.conf.persistdir):
                os.makedirs(self.base.conf.persistdir) # make the dir, just in case
            
            fo = open(tsfn, 'w')
        except (IOError, OSError), e:
            self.display.errorlog('could not open ts_all file: %s' % e)
            return
        

        for (t,e,n,v,r,a) in self._te_tuples:
            msg = "%s %s:%s-%s-%s.%s\n" % (t,e,n,v,r,a)
            fo.write(msg)
        fo.flush()
        fo.close()
    
    def callback( self, what, bytes, total, h, user ):
        if what == rpm.RPMCALLBACK_TRANS_START:
            self._transStart( bytes, total, h )
        elif what == rpm.RPMCALLBACK_TRANS_PROGRESS:
            self._transProgress( bytes, total, h )
        elif what == rpm.RPMCALLBACK_TRANS_STOP:
            self._transStop( bytes, total, h )
        elif what == rpm.RPMCALLBACK_INST_OPEN_FILE:
            return self._instOpenFile( bytes, total, h )
        elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            self._instCloseFile(  bytes, total, h )
        elif what == rpm.RPMCALLBACK_INST_PROGRESS:
            self._instProgress( bytes, total, h )
        elif what == rpm.RPMCALLBACK_UNINST_START:
            self._unInstStart( bytes, total, h )
        elif what == rpm.RPMCALLBACK_UNINST_PROGRESS:
            self._unInstProgress( bytes, total, h )
        elif what == rpm.RPMCALLBACK_UNINST_STOP:
            self._unInstStop( bytes, total, h )
        elif what == rpm.RPMCALLBACK_REPACKAGE_START:
            self._rePackageStart( bytes, total, h )
        elif what == rpm.RPMCALLBACK_REPACKAGE_STOP:
            self._rePackageStop( bytes, total, h )
        elif what == rpm.RPMCALLBACK_REPACKAGE_PROGRESS:
            self._rePackageProgress( bytes, total, h )
        elif what == rpm.RPMCALLBACK_CPIO_ERROR:
            self._cpioError(bytes, total, h)
        elif what == rpm.RPMCALLBACK_UNPACK_ERROR:
            self._unpackError(bytes, total, h)
    
    
    def _transStart(self, bytes, total, h):
        if bytes == 6:
            self.total_actions = total
            if self.test: return

            self.ts_all() # write out what transaction will do

    def _transProgress(self, bytes, total, h):
        pass
        
    def _transStop(self, bytes, total, h):
        pass

    def _instOpenFile(self, bytes, total, h):
        self.lastmsg = None
        hdr = None
        if h is not None:
            hdr, rpmloc = h
            handle = self._makeHandle(hdr)
            fd = os.open(rpmloc, os.O_RDONLY)
            self.filehandles[handle]=fd
            self.total_installed += 1
            self.complete_actions += 1
            self.installed_pkg_names.append(hdr['name'])
            return fd
        else:
            self.display.errorlog("Error: No Header to INST_OPEN_FILE")
            
    def _instCloseFile(self, bytes, total, h):
        hdr = None
        if h is not None:
            hdr, rpmloc = h
            handle = self._makeHandle(hdr)
            os.close(self.filehandles[handle])
            fd = 0
            if self.test: return
            
            pkgtup = self._dopkgtup(hdr)
            txmbrs = self.base.tsInfo.getMembers(pkgtup=pkgtup)
            for txmbr in txmbrs:
                self.display.filelog(txmbr.po, txmbr.output_state)
                self.display.scriptout(txmbr.po, self._scriptOutput())
                self.ts_done(txmbr.po, txmbr.output_state)
                
                
    
    def _instProgress(self, bytes, total, h):
        if h is not None:
            # If h is a string, we're repackaging.
            # Why the RPMCALLBACK_REPACKAGE_PROGRESS flag isn't set, I have no idea
            if type(h) == type(""):
                self.display.event(h, 'repackaging',  bytes, total,
                                self.complete_actions, self.total_actions)

            else:
                hdr, rpmloc = h
                pkgtup = self._dopkgtup(hdr)
                txmbrs = self.base.tsInfo.getMembers(pkgtup=pkgtup)
                for txmbr in txmbrs:
                    action = txmbr.output_state
                    self.display.event(txmbr.po, action, bytes, total,
                                self.complete_actions, self.total_actions)
    def _unInstStart(self, bytes, total, h):
        pass
        
    def _unInstProgress(self, bytes, total, h):
        pass
    
    def _unInstStop(self, bytes, total, h):
        self.total_removed += 1
        self.complete_actions += 1
        if h not in self.installed_pkg_names:
            self.display.filelog(h, TS_ERASE)
            action = TS_ERASE
        else:
            action = TS_UPDATED                    
        
        self.display.event(h, action, 100, 100, self.complete_actions,
                            self.total_actions)
        self.display.scriptout(h, self._scriptOutput())
        
        if self.test: return # and we're done
        self.ts_done(h, action)
        
        
    def _rePackageStart(self, bytes, total, h):
        pass
        
    def _rePackageStop(self, bytes, total, h):
        pass
        
    def _rePackageProgress(self, bytes, total, h):
        pass
        
    def _cpioError(self, bytes, total, h):
        (hdr, rpmloc) = h
        pkgtup = self._dopkgtup(hdr)
        txmbrs = self.base.tsInfo.getMembers(pkgtup=pkgtup)
        for txmbr in txmbrs:
            msg = "Error in cpio payload of rpm package %s" % txmbr.po
            self.display.errorlog(msg)
            # FIXME - what else should we do here? raise a failure and abort?
    
    def _unpackError(self, bytes, total, h):
        (hdr, rpmloc) = h
        pkgtup = self._dopkgtup(hdr)
        txmbrs = self.base.tsInfo.getMembers(pkgtup=pkgtup)
        for txmbr in txmbrs:
            msg = "Error unpacking rpm package %s" % txmbr.po
            self.display.errorlog(msg)
            # FIXME - should we raise? I need a test case pkg to see what the
            # right behavior should be
                
