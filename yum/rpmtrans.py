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
import sys
import logging
from yum.constants import *

from i18n import _

class NoOutputCallBack:
    def __init__(self):
        pass
        
    def event(self, package, action, te_current, te_total, ts_current, ts_total):
        """package is a yum package object or simple string of a package name
           action is a yum.constant transaction set state or in the obscure 
              rpm repackage case it could be the string 'repackaging'
           te_current: current number of bytes processed in the transaction
                       element being processed
           te_total: total number of bytes in the transaction element being processed
           ts_current: number of processes completed in whole transaction
           ts_total: total number of processes in the transaction.
        """
        # this is where a progress bar would be called
        
        pass
    def errorlog(self, msg):
        """takes a simple error msg string"""
        
        pass

    def filelog(self, package, action):
        # check package object type - if it is a string - just output it
        """package is the same as in event() - a package object or simple string
           action is also the same as in event()"""
        pass
        

class SimpleCliCallBack:
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
        self.lastmsg = None
        self.logger = logging.getLogger('yum.filelogging.RPMInstallCallback')        
        self.lastpackage = None # name of last package we looked at
        
    def event(self, package, action, te_current, te_total, ts_current, ts_total):
        # this is where a progress bar would be called
        msg = '%s: %s %s/%s [%s/%s]' % (self.action[action], package, 
                                   te_current, te_total, ts_current, ts_total)
        if msg != self.lastmsg:
            print msg
        self.lastmsg = msg
        self.lastpackage = package
        
        
    def errorlog(self, msg):
        print >> sys.stderr, msg

    def filelog(self, package, action):
        # check package object type - if it is a string - just output it
        msg = '%s: %s' % (self.fileaction[action], package)
        self.logger.info(msg)

class RPMTransaction:
    def __init__(self, tsInfo, display=NoOutputCallBack):
        self.display = display()
        self.tsInfo = tsInfo

        self.filehandles = {}
        self.total_actions = 0
        self.total_installed = 0
        self.complete_actions = 0
        self.installed_pkg_names = []
        self.total_removed = 0
        self.logger = logging.getLogger('yum.filelogging.RPMInstallCallback')
        self.filelog = False

    def _dopkgtup(self, hdr):
        tmpepoch = hdr['epoch']
        if tmpepoch is None: epoch = '0'
        else: epoch = str(tmpepoch)

        return (hdr['name'], hdr['arch'], epoch, hdr['version'], hdr['release'])

    def _makeHandle(self, hdr):
        handle = '%s:%s.%s-%s-%s' % (hdr['epoch'], hdr['name'], hdr['version'],
          hdr['release'], hdr['arch'])

        return handle
        
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
            self.unpackError(bytes, total, h)
    
    
    def _transStart(self, bytes, total, h):
        if bytes == 6:
            self.total_actions = total
    
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
            self.display.errorlog(_("Error: No Header to INST_OPEN_FILE"))
    def _instCloseFile(self, bytes, total, h):
        hdr = None
        if h is not None:
            hdr, rpmloc = h
            handle = self._makeHandle(hdr)
            os.close(self.filehandles[handle])
            fd = 0

            pkgtup = self._dopkgtup(hdr)
            txmbrs = self.tsInfo.getMembers(pkgtup=pkgtup)
            for txmbr in txmbrs:
                self.display.filelog(txmbr.po, txmbr.output_state)
    
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
                txmbrs = self.tsInfo.getMembers(pkgtup=pkgtup)
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

    def _rePackageStart(self, bytes, total, h):
        pass
        
    def _rePackageStop(self, bytes, total, h):
        pass
        
    def _rePackageProgress(self, bytes, total, h):
        pass
        
    def _cpioError(self, bytes, total, h):
        (hdr, rpmloc) = h
        pkgtup = self._dopkgtup(hdr)
        txmbrs = self.tsInfo.getMembers(pkgtup=pkgtup)
        for txmbr in txmbrs:
            self.display.errorlog("Error in cpio payload of rpm package %s" % txmbr.po)
            # FIXME - what else should we do here? raise a failure and abort?
    
    def _unpackError(self, bytes, total, h):
        (hdr, rpmloc) = h
        pkgtup = self._dopkgtup(hdr)
        txmbrs = self.tsInfo.getMembers(pkgtup=pkgtup)
        for txmbr in txmbrs:
            self.display.errorlog("Error unpacking rpm package %s" % txmbr.po)
            # FIXME - should we raise? I need a test case pkg to see what the
            # right behavior should be
                
