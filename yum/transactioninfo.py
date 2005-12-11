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
# Written by Seth Vidal

# TODOS: make all the package relationships deal with package objects
# search by package object for TransactionData, etc.
# provide a real TransactionData.remove(txmbr) method, It should 
# remove the given txmbr and iterate to remove all those in depedent relationships
# with the given txmbr. 

from constants import *

class TransactionData:
    """Data Structure designed to hold information on a yum Transaction Set"""
    def __init__(self):
        self.flags = []
        self.vsflags = []
        self.probFilterFlags = []
        self.root = '/'
        self.pkgdict = {} # key = pkgtup, val = list of TransactionMember obj
        self.debug = 0

    def __len__(self):
        return len(self.pkgdict.values())
        
    def __iter__(self):
        if hasattr(self.getMembers(), '__iter__'):
            return self.getMembers().__iter__()
        else:
            return iter(self.getMembers())

    def debugprint(self, msg):
        if self.debug:
            print msg
    
   
    def getMembers(self, pkgtup=None):
        """takes an optional package tuple and returns all transaction members 
           matching, no pkgtup means it returns all transaction members"""
        
        if pkgtup is None:
            returnlist = []
            for key in self.pkgdict.keys():
                returnlist.extend(self.pkgdict[key])
                
            return returnlist

        if self.pkgdict.has_key(pkgtup):
            return self.pkgdict[pkgtup]
        else:
            return []
            
    def getMode(self, name=None, arch=None, epoch=None, ver=None, rel=None):
        """returns the mode of the first match from the transaction set, 
           otherwise, returns None"""

        txmbrs = self.matchNaevr(name=name, arch=arch, epoch=epoch, ver=ver, rel=rel)
        if len(txmbrs):
            return txmbrs[0].ts_state
        else:
            return None

    
    def matchNaevr(self, name=None, arch=None, epoch=None, ver=None, rel=None):
        """returns the list of packages matching the args above"""
        completelist = self.pkgdict.keys()
        removedict = {}
        returnlist = []
        returnmembers = []
        
        for pkgtup in completelist:
            (n, a, e, v, r) = pkgtup
            if name is not None:
                if name != n:
                    removedict[pkgtup] = 1
                    continue
            if arch is not None:
                if arch != a:
                    removedict[pkgtup] = 1
                    continue
            if epoch is not None:
                if epoch != e:
                    removedict[pkgtup] = 1
                    continue
            if ver is not None:
                if ver != v:
                    removedict[pkgtup] = 1
                    continue
            if rel is not None:
                if rel != r:
                    removedict[pkgtup] = 1
                    continue
        
        for pkgtup in completelist:
            if not removedict.has_key(pkgtup):
                returnlist.append(pkgtup)
        
        for matched in returnlist:
            returnmembers.extend(self.pkgdict[matched])

        return returnmembers

    def add(self, txmember):
        """add a package to the transaction"""
        
        if not self.pkgdict.has_key(txmember.pkgtup):
            self.pkgdict[txmember.pkgtup] = []
        else:
            self.debugprint("Package: %s.%s - %s:%s-%s already in ts" % txmember.pkgtup)
            for member in self.pkgdict[txmember.pkgtup]:
                if member.ts_state == txmember.ts_state:
                    self.debugprint("Package in same mode, skipping.")
                    return
        self.pkgdict[txmember.pkgtup].append(txmember)

    def remove(self, pkgtup):
        """remove a package from the transaction"""
        if not self.pkgdict.has_key(pkgtup):
            self.debugprint("Package: %s not in ts" %(pkgtup,))
            return
        for txmbr in self.pkgdict[pkgtup]:
            txmbr.po.state = None
        
        del self.pkgdict[pkgtup]
    
    def exists(self, pkgtup):
        """tells if the pkg is in the class"""
        if self.pkgdict.has_key(pkgtup):
            if len(self.pkgdict[pkgtup]) != 0:
                return 1
        
        return 0

    def isObsoleted(self, pkgtup):
        """true if the pkgtup is marked to be obsoleted"""
        if self.exists(pkgtup):
            for txmbr in self.getMembers(pkgtup=pkgtup):
                if txmbr.output_state == TS_OBSOLETED:
                    return True
        
        return False
                
    def makelists(self):
        """returns lists of transaction Member objects based on mode:
           updated, installed, erased, obsoleted, depupdated, depinstalled
           deperased"""
           
        self.removed = []
        self.installed = []
        self.updated = []
        self.obsoleted = []
        self.depremoved = []
        self.depinstalled = []
        self.depupdated = []
        
        for txmbr in self.getMembers():
            if txmbr.output_state == TS_UPDATE:
                if txmbr.isDep:
                    self.depupdated.append(txmbr)
                else:
                    self.updated.append(txmbr)
                    
            elif txmbr.output_state == TS_INSTALL or txmbr.output_state == TS_TRUEINSTALL:
                if txmbr.isDep:
                    self.depinstalled.append(txmbr)
                else:
                    self.installed.append(txmbr)
            
            elif txmbr.output_state == TS_ERASE:
                if txmbr.isDep:
                    self.depremoved.append(txmbr)
                else:
                    self.removed.append(txmbr)
                    
            elif txmbr.output_state == TS_OBSOLETED:
                self.obsoleted.append(txmbr)
                
            elif txmbr.output_state == TS_OBSOLETING:
                self.installed.append(txmbr)
                
            else:
                pass
    
            self.updated.sort()
            self.installed.sort()
            self.removed.sort()
            self.obsoleted.sort()
            self.depupdated.sort()
            self.depinstalled.sort()
            self.depremoved.sort()

    
    def addInstall(self, po):
        """adds a package as an install but in mode 'u' to the ts
           takes a packages object and returns a TransactionMember Object"""
    
        txmbr = TransactionMember(po)
        txmbr.current_state = TS_AVAILABLE
        txmbr.output_state = TS_INSTALL
        txmbr.po.state = TS_INSTALL        
        txmbr.ts_state = 'u'
        txmbr.reason = 'user'
        self.add(txmbr)
        return txmbr

    def addTrueInstall(self, po):
        """adds a package as an install
           takes a packages object and returns a TransactionMember Object"""
    
        txmbr = TransactionMember(po)
        txmbr.current_state = TS_AVAILABLE
        txmbr.output_state = TS_TRUEINSTALL
        txmbr.po.state = TS_INSTALL        
        txmbr.ts_state = 'i'
        txmbr.reason = 'user'
        self.add(txmbr)
        return txmbr
    

    def addErase(self, po):
        """adds a package as an erasure
           takes a packages object and returns a TransactionMember Object"""
    
        txmbr = TransactionMember(po)
        txmbr.current_state = TS_INSTALL
        txmbr.output_state = TS_ERASE
        txmbr.po.state = TS_INSTALL
        txmbr.ts_state = 'e'
        self.add(txmbr)
        return txmbr

    def addUpdate(self, po, oldpo=None):
        """adds a package as an update
           takes a packages object and returns a TransactionMember Object"""
    
        txmbr = TransactionMember(po)
        txmbr.current_state = TS_AVAILABLE
        txmbr.output_state = TS_UPDATE
        txmbr.po.state = TS_UPDATE        
        txmbr.ts_state = 'u'
        if oldpo:
            txmbr.relatedto.append((oldpo.pkgtup, 'updates'))
            txmbr.updates.append(oldpo)
        self.add(txmbr)
        return txmbr

    def addObsoleting(self, po, oldpo):
        """adds a package as an obsolete over another pkg
           takes a packages object and returns a TransactionMember Object"""
    
        txmbr = TransactionMember(po)
        txmbr.current_state = TS_AVAILABLE
        txmbr.output_state = TS_OBSOLETING
        txmbr.po.state = TS_OBSOLETING
        txmbr.ts_state = 'u'
        txmbr.relatedto.append((oldpo, 'obsoletes'))
        txmbr.obsoletes.append(oldpo)
        self.add(txmbr)
        return txmbr

    def addObsoleted(self, po, obsoleting_po):
        """adds a package as being obsoleted by another pkg
           takes a packages object and returns a TransactionMember Object"""
    
        txmbr = TransactionMember(po)
        txmbr.current_state = TS_INSTALL
        txmbr.output_state =  TS_OBSOLETED
        txmbr.po.state = TS_OBSOLETED
        txmbr.ts_state = None
        txmbr.relatedto.append((obsoleting_po, 'obsoletedby'))
        txmbr.obsoleted_by.append(obsoleting_po)
        self.add(txmbr)
        return txmbr


class TransactionMember:
    """Class to describe a Transaction Member (a pkg to be installed/
       updated/erased)."""
    
    def __init__(self, po):
        # holders for data
        self.po = po # package object
        self.current_state = None # where the package currently is (repo, installed)
        self.ts_state = None # what state to put it into in the transaction set
        self.output_state = None # what state to list if printing it
        self.isDep = 0
        self.reason = 'user' # reason for it to be in the transaction set
        self.process = None # 
        self.relatedto = [] # ([relatedpkgtup, relationship)]
        self.depends_on = []
        self.obsoletes = []
        self.obsoleted_by = []
        self.updates = []
        self.updated_by = []
        self.groups = [] # groups it's in
        self._poattr = ['pkgtup', 'repoid', 'name', 'arch', 'epoch', 'version',
                        'release']

        for attr in self._poattr:
            val = getattr(self.po, attr)
            setattr(self, attr, val)

    def setAsDep(self, po=None):
        """sets the transaction member as a dependency and maps the dep into the
           relationship list attribute"""
        
        self.isDep = 1
        if po:
            self.relatedto.append((po.pkgtup, 'dependson'))
            self.depends_on.append(po)

    def __cmp__(self, other):
        if self.name > other.name:
            return 1
        if self.name < other.name:
            return -1
        if self.name == other.name:
            return 0

            
    def __str__(self):
        return "%s.%s %s-%s-%s - %s" % (self.name, self.arch, self.epoch,
                                        self.version, self.release, self.ts_state)
        
    # This is the tricky part - how do we nicely setup all this data w/o going insane
    # we could make the txmember object be created from a YumPackage base object
    # we still may need to pass in 'groups', 'ts_state', 'output_state', 'reason', 'current_state'
    # and any related packages. A world of fun that will be, you betcha
    
    
    # definitions
    # current and output states are defined in constants
    # relationships are defined in constants
    # ts states are: u, i, e
    
