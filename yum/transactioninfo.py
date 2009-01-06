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

"""
Classes and functions for manipulating a transaction to be passed
to rpm.
"""

from constants import *
from packageSack import PackageSack
from packages import YumInstalledPackage
from sqlitesack import YumAvailablePackageSqlite
import Errors
import warnings

class TransactionData:
    """Data Structure designed to hold information on a yum Transaction Set"""
    def __init__(self):
        self.flags = []
        self.vsflags = []
        self.probFilterFlags = []
        self.root = '/'
        self.pkgdict = {} # key = pkgtup, val = list of TransactionMember obj
        self._namedict = {} # name -> list of TransactionMember obj
        self._unresolvedMembers = set()
        self.debug = 0
        self.changed = False
        self.installonlypkgs = []
        
        self.conditionals = {} # key = pkgname, val = list of pos to add

        self.rpmdb = None
        self.pkgSack = None
        self.pkgSackPackages = 0
        self.localSack = PackageSack()

        # lists of txmbrs in their states - just placeholders
        self.instgroups = []
        self.removedgroups = []
        self.removed = []
        self.installed = []
        self.updated = []
        self.obsoleted = []
        self.depremoved = []
        self.depinstalled = []
        self.depupdated = []
        
    def __len__(self):
        return len(self.pkgdict)
        
    def __iter__(self):
        if hasattr(self.getMembers(), '__iter__'):
            return self.getMembers().__iter__()
        else:
            return iter(self.getMembers())

    def debugprint(self, msg):
        if self.debug:
            print msg

    def getMembersWithState(self, pkgtup=None, output_states=None):
        return filter(lambda p: p.output_state in output_states,
                      self.getMembers(pkgtup))

    def getMembers(self, pkgtup=None):
        """takes an optional package tuple and returns all transaction members 
           matching, no pkgtup means it returns all transaction members"""
        
        returnlist = []

        if pkgtup is None:
            for members in self.pkgdict.itervalues():
                returnlist.extend(members)            
        elif self.pkgdict.has_key(pkgtup):
            returnlist.extend(self.pkgdict[pkgtup])
        return returnlist
            
    # The order we resolve things in _matters_, so for sanity sort the list
    # otherwise .i386 can be different to .x86_64 etc.
    def getUnresolvedMembers(self):
        return list(sorted(self._unresolvedMembers))

    def markAsResolved(self, txmbr):
        self._unresolvedMembers.discard(txmbr)

    def resetResolved(self, hard=False):
        if hard or len(self) < len(self._unresolvedMembers):
            self._unresolvedMembers.clear()
            self._unresolvedMembers.update(self.getMembers())
            return True
        return False

    def getMode(self, name=None, arch=None, epoch=None, ver=None, rel=None):
        """returns the mode of the first match from the transaction set, 
           otherwise, returns None"""

        txmbrs = self.matchNaevr(name=name, arch=arch, epoch=epoch, ver=ver, rel=rel)
        if not len(txmbrs):
            return None
        states = []
        for txmbr in txmbrs:
            states.append(txmbr.ts_state)
        
        if 'u' in states:
            return 'u'
        elif 'i' in states:
            return 'i'
        else:
            return states[0]
            

    
    def matchNaevr(self, name=None, arch=None, epoch=None, ver=None, rel=None):
        """returns the list of packages matching the args above"""
        if name is None:
            txmbrs = self.getMembers()
        else:
            txmbrs = self._namedict.get(name, [])

        result = []

        for txmbr in txmbrs:
            (n, a, e, v, r) = txmbr.pkgtup
            if name is not None and name != n:
                continue
            if arch is not None and arch != a:
                continue
            if epoch is not None and epoch != e:
                continue
            if ver is not None and ver != v:
                continue
            if rel is not None and rel != r:
                continue
            result.append(txmbr)

        return result

    def _isLocalPackage(self, txmember):
        # Is this the right criteria?
        # FIXME: This is kinda weird, we really want all local pkgs to be in a
        # special pkgsack before this point ... so that "yum up ./*.rpm" works.
        #  Also FakePackage() sets it off ... which is confusing and not what
        # happens IRL.
        return txmember.ts_state in ('u', 'i') and not isinstance(txmember.po, (YumInstalledPackage, YumAvailablePackageSqlite))

    def _allowedMultipleInstalls(self, po):
        """takes a packageObject, returns 1 or 0 depending on if the package 
           should/can be installed multiple times with different vers
           like kernels and kernel modules, for example"""
           
        if po.name in self.installonlypkgs:
            return True
        
        provides = po.provides_names
        if filter (lambda prov: prov in self.installonlypkgs, provides):
            return True
        
        return False
        
    def add(self, txmember):
        """add a package to the transaction"""
        
        for oldpo in txmember.updates:
            self.addUpdated(oldpo, txmember.po)

        if not self.pkgdict.has_key(txmember.pkgtup):
            self.pkgdict[txmember.pkgtup] = []
        else:
            self.debugprint("Package: %s.%s - %s:%s-%s already in ts" % txmember.pkgtup)
            for member in self.pkgdict[txmember.pkgtup]:
                if member.ts_state == txmember.ts_state:
                    self.debugprint("Package in same mode, skipping.")
                    return
        self.pkgdict[txmember.pkgtup].append(txmember)
        self._namedict.setdefault(txmember.name, []).append(txmember)
        self.changed = True
        if self._isLocalPackage(txmember):
            self.localSack.addPackage(txmember.po)
        elif isinstance(txmember.po, YumAvailablePackageSqlite):
            self.pkgSackPackages += 1

        if self.conditionals.has_key(txmember.name):
            for pkg in self.conditionals[txmember.name]:
                if self.rpmdb.contains(po=pkg):
                    continue
                for condtxmbr in self.install_method(po=pkg):
                    condtxmbr.setAsDep(po=txmember.po)

        self._unresolvedMembers.add(txmember)

    def remove(self, pkgtup):
        """remove a package from the transaction"""
        if not self.pkgdict.has_key(pkgtup):
            self.debugprint("Package: %s not in ts" %(pkgtup,))
            return
        for txmbr in self.pkgdict[pkgtup]:
            txmbr.po.state = None
            if self._isLocalPackage(txmbr):
                self.localSack.delPackage(txmbr.po)
            elif isinstance(txmbr.po, YumAvailablePackageSqlite):
                self.pkgSackPackages -= 1
            self._namedict[txmbr.name].remove(txmbr)
            self._unresolvedMembers.add(txmbr)
        
        del self.pkgdict[pkgtup]
        if not self._namedict[pkgtup[0]]:
            del self._namedict[pkgtup[0]]
        self.changed = True        
    
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
           
        self.instgroups = []
        self.removedgroups = []
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
                if txmbr.groups:
                    for g in txmbr.groups:
                        if g not in self.instgroups:
                            self.instgroups.append(g)
                if txmbr.isDep:
                    self.depinstalled.append(txmbr)
                else:
                    self.installed.append(txmbr)
            
            elif txmbr.output_state == TS_ERASE:
                for g in txmbr.groups:
                    if g not in self.instgroups:
                        self.removedgroups.append(g)
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
        self.instgroups.sort()
        self.removedgroups.sort()

    
    def addInstall(self, po):
        """adds a package as an install but in mode 'u' to the ts
           takes a packages object and returns a TransactionMember Object"""

        if self._allowedMultipleInstalls(po):
           return self.addTrueInstall(po)
    
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
        
        if self._allowedMultipleInstalls(po):
           return self.addTrueInstall(po)
            
        txmbr = TransactionMember(po)
        txmbr.current_state = TS_AVAILABLE
        txmbr.output_state = TS_UPDATE
        txmbr.po.state = TS_UPDATE        
        txmbr.ts_state = 'u'
        if oldpo:
            txmbr.relatedto.append((oldpo, 'updates'))
            txmbr.updates.append(oldpo)
            
        self.add(txmbr)
        return txmbr

    def addUpdated(self, po, updating_po):
        """adds a package as being updated by another pkg
           takes a packages object and returns a TransactionMember Object"""
    
        txmbr = TransactionMember(po)
        txmbr.current_state = TS_INSTALL
        txmbr.output_state =  TS_UPDATED
        txmbr.po.state = TS_UPDATED
        txmbr.ts_state = None
        txmbr.relatedto.append((updating_po, 'updatedby'))
        txmbr.updated_by.append(updating_po)
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


    def setDatabases(self, rpmdb, pkgSack):
        self.rpmdb = rpmdb
        self.pkgSack = pkgSack

    def getNewProvides(self, name, flag=None, version=(None, None, None)):
        """return dict { packages -> list of matching provides }
        searches in packages to be installed"""
        result = { }
        if self.pkgSackPackages:
            for pkg, hits in self.pkgSack.getProvides(name, flag, version).iteritems():
                if self.getMembersWithState(pkg.pkgtup, TS_INSTALL_STATES):
                    result[pkg] = hits
        result.update(self.localSack.getProvides(name, flag, version))
        return result

    def getOldProvides(self, name, flag=None, version=(None, None, None)):
        """return dict { packages -> list of matching provides }
        searches in packages already installed and not going to be removed"""
        result = { }
        for pkg, hits in self.rpmdb.getProvides(name, flag, version).iteritems():
            if not self.getMembersWithState(pkg.pkgtup, TS_REMOVE_STATES):
                result[pkg] = hits
        return result

    def getProvides(self, name, flag=None, version=(None, None, None)):
        """return dict { packages -> list of matching provides }"""
        result = self.getOldProvides(name, flag, version)
        result.update(self.getNewProvides(name, flag, version))
        return result

    def getNewRequires(self, name, flag=None, version=(None, None, None)):
        """return dict { packages -> list of matching provides }
        searches in packages to be installed"""
        result = { }
        if self.pkgSackPackages:
            for pkg, hits in self.pkgSack.getRequires(name, flag, version).iteritems():
                if self.getMembersWithState(pkg.pkgtup, TS_INSTALL_STATES):
                    result[pkg] = hits
        result.update(self.localSack.getRequires(name, flag, version))
        return result


    def getOldRequires(self, name, flag=None, version=(None, None, None)):
        """return dict { packages -> list of matching provides }
        searches in packages already installed and not going to be removed"""
        result = { }
        for pkg, hits in self.rpmdb.getRequires(name, flag, version).iteritems():
            if not self.getMembersWithState(pkg.pkgtup, TS_REMOVE_STATES):
                result[pkg] = hits
        return result

    def getRequires(self, name, flag=None, version=(None, None, None)):
        """return dict { packages -> list of matching provides }"""
        result = self.getOldRequires(name, flag, version)
        result.update(self.getNewRequires(name, flag, version))
        return result

class ConditionalTransactionData(TransactionData):
    """A transaction data implementing conditional package addition"""
    def __init__(self):
        warnings.warn("ConditionalTransactionData will go away in a future "
                      "version of Yum.", Errors.YumFutureDeprecationWarning)
        TransactionData.__init__(self)

class SortableTransactionData(TransactionData):
    """A transaction data implementing topological sort on it's members"""
    def __init__(self):
        # Cache of sort
        self._sorted = []
        # Current dependency path
        self.path = []
        # List of loops
        self.loops = []
        TransactionData.__init__(self)

    def _visit(self, txmbr):
        self.path.append(txmbr.name)
        txmbr.sortColour = TX_GREY
        for po in txmbr.depends_on:
            vertex = self.getMembers(pkgtup=po.pkgtup)[0]
            if vertex.sortColour == TX_GREY:
                self._doLoop(vertex.name)
            if vertex.sortColour == TX_WHITE:
                self._visit(vertex)
        txmbr.sortColour = TX_BLACK
        self._sorted.insert(0, txmbr.pkgtup)

    def _doLoop(self, name):
        self.path.append(name)
        loop = self.path[self.path.index(self.path[-1]):]
        if len(loop) > 2:
            self.loops.append(loop)

    def add(self, txmember):
        txmember.sortColour = TX_WHITE
        TransactionData.add(self, txmember)
        self._sorted = []

    def remove(self, pkgtup):
        TransactionData.remove(self, pkgtup)
        self._sorted = []

    def sort(self):
        if self._sorted:
            return self._sorted
        self._sorted = []
        # loop over all members
        for txmbr in self.getMembers():
            if txmbr.sortColour == TX_WHITE:
                self.path = [ ]
                self._visit(txmbr)
        self._sorted.reverse()
        return self._sorted

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
        self.relatedto = [] # ([relatedpkg, relationship)]
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
            self.relatedto.append((po, 'dependson'))
            self.depends_on.append(po)

    def __cmp__(self, other):
        result = cmp(self.name, other.name)
        if not result:
            return cmp(id(self), id(other))
        return result

    def __hash__(self):
        return object.__hash__(self)
            
    def __str__(self):
        return "%s.%s %s-%s-%s - %s" % (self.name, self.arch, self.epoch,
                                        self.version, self.release, self.ts_state)

    def __repr__(self):
        return "<%s : %s (%s)>" % (self.__class__.__name__, str(self),hex(id(self))) 
        
    # This is the tricky part - how do we nicely setup all this data w/o going insane
    # we could make the txmember object be created from a YumPackage base object
    # we still may need to pass in 'groups', 'ts_state', 'output_state', 'reason', 'current_state'
    # and any related packages. A world of fun that will be, you betcha
    
    
    # definitions
    # current and output states are defined in constants
    # relationships are defined in constants
    # ts states are: u, i, e
