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
        

    def __len__(self):
        return len(self.pkgdict.values())
    
    def getMode(self, name=None, arch=None, epoch=None, ver=None, rel=None):
        """give back the first mode that matches the keywords, return None for
           no match."""

        return None
        
    def add(self, pkgtup):
        """add a package to the transaction"""
            
    def remove(self, pkgtup):
        """remove a package from the transaction"""
    
    def exists(self, pkgtup):
        """tells if the pkg is in the class"""
        if self.pkgdict.has_key(pkgtup):
            if len(self.pkgdict[pkgtup]) != 0:
                return 1
        
        return 0



class TransactionMember:
    """Class to describe a Transaction Member (a pkg to be installed/
       updated/erased)."""
    
    def __init__(self):
        # holders for data
        self.pkgtup = None # package tuple
        self.current_state = None # where the package currently is (repo, installed)
        self.ts_state = None # what state to put it into in the transaction set
        self.output_state = None # what state to list if printing it
        self.reason = None # reason for it to be in the transaction set
        self.repoid = None # repository id (if any)
        self.name = None
        self.arch = None
        self.epoch = None
        self.ver = None
        self.rel = None
        self.process = None # 
        self.relatedto = [] # ([relatedpkg, relationship)]
        self.groups = [] # groups it's in
        self.pkgid = None # pkgid from the package, if it has one, so we can find it
        
