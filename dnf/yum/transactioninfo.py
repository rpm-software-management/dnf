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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
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
import Errors
import warnings
import misc

import hawkey

class TransactionData:
    """Data Structure designed to hold information on a yum Transaction Set"""
    def __init__(self, prob_filter_flags=None):
        self.probFilterFlags = []
        if prob_filter_flags:
            self.probFilterFlags = prob_filter_flags[:]
        self.pkgdict = {} # key = pkgtup, val = list of TransactionMember obj
        self._namedict = {} # name -> list of TransactionMember obj
        self.installonlypkgs = []
        self.state_counter = 0
        self.conditionals = {} # key = pkgname, val = list of pos to add

        self.selector_installs = []
        self.upgrade_all = False

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
        self.reinstalled = []
        self.downgraded = []
        self.failed = []

    def __len__(self):
        return len(self.pkgdict) + len(self.selector_installs)

    def __iter__(self):
        if hasattr(self.getMembers(), '__iter__'):
            return self.getMembers().__iter__()
        else:
            return iter(self.getMembers())

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
        elif pkgtup in self.pkgdict:
            returnlist.extend(self.pkgdict[pkgtup])
        return returnlist

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
            if arch is None and epoch is None and ver is None and rel is None:
                return txmbrs[:]

        result = []

        for txmbr in txmbrs:
            (n, a, e, v, r) = txmbr.pkgtup
            # Name is done above
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

    def deselect(self, pattern):
        """ Remove these packages from the transaction. This is more user
            orientated than .remove(). Used from kickstart/install -blah. """

        #  We don't have a returnPackages() here, so just try the "simple"
        # specifications. Pretty much 100% hit rate on kickstart.
        txmbrs = self.matchNaevr(pattern)
        if not txmbrs:
            na = pattern.rsplit('.', 2)
            if len(na) == 2:
                txmbrs = self.matchNaevr(na[0], na[1])

        if not txmbrs:
            if self.pkgSack is None:
                pkgs = []
            else:
                pkgs = self.pkgSack.returnPackages(patterns=[pattern])
            if not pkgs:
                pkgs = self.rpmdb.returnPackages(patterns=[pattern])

            for pkg in pkgs:
                txmbrs.extend(self.getMembers(pkg.pkgtup))
                #  Now we need to do conditional group packages, so they don't
                # get added later on. This is hacky :(
                for req, cpkgs in self.conditionals.iteritems():
                    if pkg in cpkgs:
                        cpkgs.remove(pkg)
                        self.conditionals[req] = cpkgs

        for txmbr in txmbrs:
            self.remove(txmbr.pkgtup)
        return txmbrs

    def _allowedMultipleInstalls(self, po):
        """takes a packageObject, returns 1 or 0 depending on if the package
           should/can be installed multiple times with different vers
           like kernels and kernel modules, for example"""

        if po.name in self.installonlypkgs:
            return True
        return False # :hawkey

        provides = po.provides_names
        if filter (lambda prov: prov in self.installonlypkgs, provides):
            return True

        return False

    def add(self, txmember):
        """add a package to the transaction"""

        if txmember.pkgtup not in self.pkgdict:
            self.pkgdict[txmember.pkgtup] = []
        else:
            for member in self.pkgdict[txmember.pkgtup]:
                if member.ts_state == txmember.ts_state:
                    return
        self.pkgdict[txmember.pkgtup].append(txmember)
        self._namedict.setdefault(txmember.name, []).append(txmember)
        self.state_counter += 1

    def remove(self, pkgtup):
        """remove a package from the transaction"""
        if pkgtup not in self.pkgdict:
            return
        for txmbr in self.pkgdict[pkgtup]:
            txmbr.po.state = None
            self._namedict[txmbr.name].remove(txmbr)

        del self.pkgdict[pkgtup]
        if not self._namedict[pkgtup[0]]:
            del self._namedict[pkgtup[0]]
        self.state_counter += 1

    def exists(self, pkgtup):
        """tells if the pkg is in the class"""
        if pkgtup in self.pkgdict:
            if len(self.pkgdict[pkgtup]) != 0:
                return 1

        return 0

    def makelists(self, include_reinstall=False, include_downgrade=False):
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
        self.reinstalled = []
        self.downgraded = []
        self.failed = []

        for txmbr in self.getMembers():
            if txmbr.output_state == TS_UPDATE:
                if txmbr.isDep:
                    self.depupdated.append(txmbr)
                else:
                    self.updated.append(txmbr)

            elif txmbr.output_state == TS_INSTALL:
                if include_reinstall and txmbr.reinstall:
                    self.reinstalled.append(txmbr)
                    continue

                if include_downgrade and txmbr.downgrades:
                    self.downgraded.append(txmbr)
                    continue

                if txmbr.groups:
                    for g in txmbr.groups:
                        if g not in self.instgroups:
                            self.instgroups.append(g)
                if txmbr.isDep:
                    self.depinstalled.append(txmbr)
                else:
                    self.installed.append(txmbr)

            elif txmbr.output_state == TS_ERASE:
                if include_downgrade and txmbr.downgraded_by:
                    continue

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
            elif txmbr.output_state == TS_FAILED:
                self.failed.append(txmbr)

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
        self.reinstalled.sort()
        self.downgraded.sort()
        self.failed.sort()

    def addInstall(self, po):
        """adds a package as an install but in mode 'u' to the ts
           takes a packages object and returns a TransactionMember Object"""

        txmbr = TransactionMember(po)
        txmbr.output_state = TS_INSTALL
        txmbr.po.state = TS_INSTALL
        txmbr.ts_state = 'i'
        self.add(txmbr)
        return txmbr

    def add_selector_install(self, sltr):
        self.selector_installs.append(sltr)

    def addErase(self, po):
        """adds a package as an erasure
           takes a packages object and returns a TransactionMember Object"""

        txmbr = TransactionMember(po)
        txmbr.output_state = TS_ERASE
        txmbr.po.state = TS_INSTALL
        txmbr.ts_state = 'e'
        self.add(txmbr)
        return txmbr

    def addUpdate(self, po, oldpo=None):
        """adds a package as an update
           takes a packages object and returns a TransactionMember Object"""

        if self._allowedMultipleInstalls(po):
            return self.addInstall(po)

        txmbr = TransactionMember(po)
        txmbr.output_state = TS_UPDATE
        txmbr.po.state = TS_UPDATE
        txmbr.ts_state = 'u'
        if oldpo:
            txmbr.updates.append(oldpo)
            self._addUpdated(oldpo, po)

        self.add(txmbr)
        return txmbr

    def addDowngrade(self, po, oldpo=None):
        """adds a package as an downgrade takes a packages object and returns
           a pair of TransactionMember Objects"""

        atxmbr = self.addInstall(po)

        if oldpo:
            itxmbr = self.addErase(oldpo)
            itxmbr.downgraded_by.append(po)
            atxmbr.downgrades.append(oldpo)
        return atxmbr

    # deprecated
    def _addUpdated(self, po, updating_po):
        """adds a package as being updated by another pkg
           takes a packages object and returns a TransactionMember Object
        """

        txmbr = TransactionMember(po)
        txmbr.output_state =  TS_UPDATED
        txmbr.po.state = TS_UPDATED
        txmbr.ts_state = 'ud'
        self.add(txmbr)
        return txmbr

class TransactionMember:
    """Class to describe a Transaction Member (a pkg to be installed/
       updated/erased)."""

    def __init__(self, po):
        # holders for data
        self.po = po # package object
        self.ts_state = None # what state to put it into in the transaction set
        self.output_state = None # what state to list if printing it
        self.isDep = 0
        self.reason = 'unknown' # reason for it to be in the transaction set
        self.process = None #  I think this is used nowhere by nothing - skv 2010/11/03
        self.depends_on = []
        self.obsoletes = []
        self.obsoleted_by = []
        self.updates = []
        self.downgrades = []
        self.downgraded_by = []
        self.reinstall = False
        self.groups = [] # groups it's in
        self._poattr = ['pkgtup', 'reponame', 'name', 'arch', 'evr']

        for attr in self._poattr:
            val = getattr(self.po, attr)
            setattr(self, attr, val)

        return # :hawkey
        if po.from_system:
            #  We want to load these so that we can auto hardlink in the same
            # new values. Because of the hardlinks it should be really cheap
            # to load them ... although it's still a minor hack.
            po.yumdb_info.get('from_repo')
            po.yumdb_info.get('releasever')
            po.yumdb_info.get('changed_by')

    def __cmp__(self, other):
        return cmp(self.po, other.po)

    def __hash__(self):
        return object.__hash__(self)

    def __str__(self):
        return "%s.%s %s - %s" % (self.name, self.arch, self.evr,
                                  self.ts_state)
    def __repr__(self):
        return "<%s : %s (%s)>" % (self.__class__.__name__, str(self),hex(id(self)))

    def propagated_reason(self, yumdb):
        if self.reason == "user":
            return self.reason
        previously = None
        if self.updates:
            updated = self.updates[0]
            previously =  yumdb.get_package(updated).get('reason')
        elif self.downgrades:
            downgraded = self.downgrades[0]
            previously = yumdb.get_package(downgraded).get('reason')
        if previously:
            return previously
        return self.reason
