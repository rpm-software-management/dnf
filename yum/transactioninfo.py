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
# Written by Seth Vidal

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
    
    def exists(self, pkgtup):
        """tells if the pkg is in the class"""
        if self.pkgdict.has_key(pkgtup):
            if len(self.pkgdict[pkgtup]) != 0:
                return 1
        
        return 0

    def makelists(self):
        """returns lists of transaction Member objects based on mode:
           updated, installed, erased, obsoleted, depupdated, depinstalled
           deperased"""
           
        removed = []
        installed = []
        updated = []
        obsoleted = []
        depremoved = []
        depinstalled = []
        depupdated = []
        
        for txmbr in self.getMembers():
            if txmbr.output_state == 'updating':
                if txmbr.isDep:
                    depupdated.append(txmbr)
                else:
                    updated.append(txmbr)
                    
            elif txmbr.output_state == 'installing':
                if txmbr.isDep:
                    depinstalled.append(txmbr)
                else:
                    installed.append(txmbr)
            
            elif txmbr.output_state == 'erasing':
                if txmbr.isDep:
                    depremoved.append(txmbr)
                else:
                    removed.append(txmbr)
                    
            elif txmbr.output_state == 'obsoleted':
                obsoleted.append(txmbr)
                
            elif txmbr.output_state == 'obsoleting':
                installed.append(txmbr)
                
            else:
                pass
    
            updated.sort()
            installed.sort()
            removed.sort()
            obsoleted.sort()
            depupdated.sort()
            depinstalled.sort()
            depremoved.sort()

        return updated, installed, removed, obsoleted, depupdated, depinstalled, depremoved
    
    def addInstall(self, po):
        """adds a package as an install but in mode 'u' to the ts
           takes a packages object and returns a TransactionMember Object"""
    
        txmbr = TransactionMember()
        txmbr.pkgtup = po.pkgtup()
        txmbr.current_state = 'repo'
        txmbr.output_state = 'installing'
        txmbr.ts_state = 'u'
        txmbr.reason = 'user'
        txmbr.name = po.name
        txmbr.arch = po.arch
        txmbr.epoch = po.epoch
        txmbr.ver = po.version
        txmbr.rel = po.release
        txmbr.repoid = po.repoid
        self.add(txmbr)
        return txmbr

    def addTrueInstall(self, po):
        """adds a package as an install
           takes a packages object and returns a TransactionMember Object"""
    
        txmbr = TransactionMember()
        txmbr.pkgtup = po.pkgtup()
        txmbr.current_state = 'repo'
        txmbr.output_state = 'installing'
        txmbr.ts_state = 'i'
        txmbr.reason = 'user'
        txmbr.name = po.name
        txmbr.arch = po.arch
        txmbr.epoch = po.epoch
        txmbr.ver = po.version
        txmbr.rel = po.release
        txmbr.repoid = po.repoid
        self.add(txmbr)
        return txmbr
    

    def addErase(self, po):
        """adds a package as an erasure
           takes a packages object and returns a TransactionMember Object"""
    
        txmbr = TransactionMember()
        txmbr.pkgtup = po.pkgtup()
        txmbr.current_state = 'installed'
        txmbr.output_state = 'erasing'
        txmbr.ts_state = 'e'
        txmbr.name = po.name
        txmbr.arch = po.arch
        txmbr.epoch = po.epoch
        txmbr.ver = po.version
        txmbr.rel = po.release
        txmbr.repoid = po.repoid
        self.add(txmbr)
        return txmbr

    def addUpdate(self, po, oldpo=None):
        """adds a package as an update
           takes a packages object and returns a TransactionMember Object"""
    
        txmbr = TransactionMember()
        txmbr.pkgtup = po.pkgtup()
        txmbr.current_state = 'repo'
        txmbr.output_state = 'updating'
        txmbr.ts_state = 'u'
        txmbr.name = po.name
        txmbr.arch = po.arch
        txmbr.epoch = po.epoch
        txmbr.ver = po.version
        txmbr.rel = po.release
        txmbr.repoid = po.repoid
        if oldpo:
            txmbr.relatedto.append((oldpo.pkgtup(), 'updates'))
        self.add(txmbr)
        return txmbr

    def addObsoleting(self, po, oldpo):
        """adds a package as an obsolete over another pkg
           takes a packages object and returns a TransactionMember Object"""
    
        txmbr = TransactionMember()
        txmbr.pkgtup = po.pkgtup()
        txmbr.current_state = 'repo'
        txmbr.output_state = 'obsoleting'
        txmbr.ts_state = 'u'
        txmbr.name = po.name
        txmbr.arch = po.arch
        txmbr.epoch = po.epoch
        txmbr.ver = po.version
        txmbr.rel = po.release
        txmbr.repoid = po.repoid
        txmbr.relatedto.append((oldpo.pkgtup(), 'obsoletes'))
        self.add(txmbr)
        return txmbr

    def addObsoleted(self, po, obsoleting_po):
        """adds a package as being obsoleted by another pkg
           takes a packages object and returns a TransactionMember Object"""
    
        txmbr = TransactionMember()
        txmbr.pkgtup = po.pkgtup()
        txmbr.current_state = 'installed'
        txmbr.output_state = 'obsoleted'
        txmbr.ts_state = None
        txmbr.name = po.name
        txmbr.arch = po.arch
        txmbr.epoch = po.epoch
        txmbr.ver = po.version
        txmbr.rel = po.release
        txmbr.repoid = po.repoid
        txmbr.relatedto.append((obsoleting_po.pkgtup(), 'obsoletedby'))
        self.add(txmbr)
        return txmbr


class TransactionMember:
    """Class to describe a Transaction Member (a pkg to be installed/
       updated/erased)."""
    
    def __init__(self):
        # holders for data
        self.pkgtup = None # package tuple
        self.current_state = None # where the package currently is (repo, installed)
        self.ts_state = None # what state to put it into in the transaction set
        self.output_state = None # what state to list if printing it
        self.isDep = 0
        self.reason = 'user' # reason for it to be in the transaction set
        self.repoid = None # repository id (if any)
        self.name = None
        self.arch = None
        self.epoch = None
        self.ver = None
        self.rel = None
        self.process = None # 
        self.relatedto = [] # ([relatedpkgtup, relationship)]
        self.groups = [] # groups it's in
        self.pkgid = None # pkgid from the package, if it has one, so we can find it
        self.repoid = None
    
    def setAsDep(self, pkgtup=None):
        """sets the transaction member as a dependency and maps the dep into the
           relationship list attribute"""
        
        self.isDep = 1
        if pkgtup:
            self.relatedto.append((pkgtup, 'dependson'))

    def __str__(self):
        return "%s.%s %s-%s-%s - %s" % (self.name, self.arch, self.epoch, self.ver, self.rel, self.ts_state)
        
    # This is the tricky part - how do we nicely setup all this data w/o going insane
    # we could make the txmember object be created from a YumPackage base object
    # we still may need to pass in 'groups', 'ts_state', 'output_state', 'reason', 'current_state'
    # and any related packages. A world of fun that will be, you betcha
    
    
    # things to define:
    # types of relationships
    # types of reasons
    # ts, current and output states
    
    # output states are:
    # update, install, remove, obsoleted
    
    # ts states are: u, i, e
    
    # current_states are:
    # installed, repo
    
    #relationships:
    # obsoletedby, updates, obsoletes, updatedby, 
    # dependencyof, dependson
    
