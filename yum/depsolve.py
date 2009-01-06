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

"""
Depedancy resolution module for yum.
"""

import os.path
import types
import logging

import rpmUtils.transaction
import rpmUtils.miscutils
import rpmUtils.arch
from rpmUtils.arch import archDifference, isMultiLibArch, getBestArch
import misc
from misc import unique, version_tuple_to_string
import rpm

from packageSack import ListPackageSack
from constants import *
import packages
import logginglevels
import Errors
import warnings
warnings.simplefilter("ignore", Errors.YumFutureDeprecationWarning)
from operator import itemgetter

from yum import _

try:
    assert max(2, 4) == 4
except:
    # Python-2.4.x doesn't have min/max ... *sigh*
        def min(x, *args): 
            for y in args:
                if x > y: x = y
            return x
        def max(x, *args):
            for y in args:
                if x < y: x = y
            return x
flags = {"GT": rpm.RPMSENSE_GREATER,
         "GE": rpm.RPMSENSE_EQUAL | rpm.RPMSENSE_GREATER,
         "LT": rpm.RPMSENSE_LESS,
         "LE": rpm.RPMSENSE_LESS | rpm.RPMSENSE_EQUAL,
         "EQ": rpm.RPMSENSE_EQUAL,
         None: 0 }

class Depsolve(object):

    """
    Dependency resolving class.
    """

    def __init__(self):
        packages.base = self
        self._ts = None
        self._tsInfo = None
        self.dsCallback = None
        self.logger = logging.getLogger("yum.Depsolve")
        self.verbose_logger = logging.getLogger("yum.verbose.Depsolve")

        self.path = []
        self.loops = []

        self.installedFileRequires = None
        self.installedUnresolvedFileRequires = None

    def doTsSetup(self):
        warnings.warn(_('doTsSetup() will go away in a future version of Yum.\n'),
                Errors.YumFutureDeprecationWarning, stacklevel=2)
        return self._getTs()
        
    def _getTs(self, remove_only=False):
        """setup all the transaction set storage items we'll need
           This can't happen in __init__ b/c we don't know our installroot
           yet"""
        
        if self._tsInfo != None and self._ts != None:
            if not remove_only and self._tsInfo.pkgSack is None:
                self._tsInfo.setDatabases(self.rpmdb, self.pkgSack)
            return
            
        if not self.conf.installroot:
            raise Errors.YumBaseError, _('Setting up TransactionSets before config class is up')
        
        self._getTsInfo(remove_only)
        self.initActionTs()
    
    def _getTsInfo(self, remove_only=False):
        """ remove_only param. says if we are going to do _only_ remove(s) in
            the transaction. If so we don't need to setup the remote repos. """
        if self._tsInfo is None:
            self._tsInfo = self._transactionDataFactory()
            if remove_only:
                pkgSack = None
            else:
                pkgSack = self.pkgSack
            self._tsInfo.setDatabases(self.rpmdb, pkgSack)
            self._tsInfo.installonlypkgs = self.conf.installonlypkgs # this kinda sucks
            # this REALLY sucks, sadly (needed for group conditionals)
            self._tsInfo.install_method = self.install
            self._tsInfo.update_method = self.update
            self._tsInfo.remove_method = self.remove
        return self._tsInfo

    def _setTsInfo(self, value):
        self._tsInfo = value

    def _delTsInfo(self):
        self._tsInfo = None
        
    def _getActionTs(self):
        if not self._ts:
            self.initActionTs()
        return self._ts
        

    def initActionTs(self):
        """sets up the ts we'll use for all the work"""
        
        self._ts = rpmUtils.transaction.TransactionWrapper(self.conf.installroot)
        ts_flags_to_rpm = { 'noscripts': rpm.RPMTRANS_FLAG_NOSCRIPTS,
                            'notriggers': rpm.RPMTRANS_FLAG_NOTRIGGERS,
                            'nodocs': rpm.RPMTRANS_FLAG_NODOCS,
                            'test': rpm.RPMTRANS_FLAG_TEST,
                            'justdb': rpm.RPMTRANS_FLAG_JUSTDB,
                            'repackage': rpm.RPMTRANS_FLAG_REPACKAGE}
        
        self._ts.setFlags(0) # reset everything.
        
        for flag in self.conf.tsflags:
            if ts_flags_to_rpm.has_key(flag):
                self._ts.addTsFlag(ts_flags_to_rpm[flag])
            else:
                self.logger.critical(_('Invalid tsflag in config file: %s'), flag)

        probfilter = 0
        for flag in self.tsInfo.probFilterFlags:
            probfilter |= flag
        self._ts.setProbFilter(probfilter)

    def whatProvides(self, name, flags, version):
        """searches the packageSacks for what provides the arguments
           returns a ListPackageSack of providing packages, possibly empty"""

        self.verbose_logger.log(logginglevels.DEBUG_1, _('Searching pkgSack for dep: %s'),
            name)
        # we need to check the name - if it doesn't match:
        # /etc/* bin/* or /usr/lib/sendmail then we should fetch the 
        # filelists.xml for all repos to make the searchProvides more complete.
        if name[0] == '/':
            if not misc.re_primary_filename(name):
                self.doSackFilelistPopulate()
            
        pkgs = self.pkgSack.searchProvides(name)
        
        
        if flags == 0:
            flags = None
        if type(version) in (types.StringType, types.NoneType, types.UnicodeType):
            (r_e, r_v, r_r) = rpmUtils.miscutils.stringToVersion(version)
        elif type(version) in (types.TupleType, types.ListType): # would this ever be a ListType?
            (r_e, r_v, r_r) = version
        
        defSack = ListPackageSack() # holder for items definitely providing this dep
        
        for po in pkgs:
            self.verbose_logger.log(logginglevels.DEBUG_2,
                _('Potential match for %s from %s'), name, po)
            if name[0] == '/' and r_v is None:
                # file dep add all matches to the defSack
                defSack.addPackage(po)
                continue

            if po.checkPrco('provides', (name, flags, (r_e, r_v, r_r))):
                defSack.addPackage(po)
                self.verbose_logger.debug(_('Matched %s to require for %s'), po, name)
        
        return defSack
        
    def allowedMultipleInstalls(self, po):
        """takes a packageObject, returns 1 or 0 depending on if the package 
           should/can be installed multiple times with different vers
           like kernels and kernel modules, for example"""
           
        if po.name in self.conf.installonlypkgs:
            return True
        
        provides = po.provides_names
        if filter (lambda prov: prov in self.conf.installonlypkgs, provides):
            return True
        
        return False

    def populateTs(self, test=0, keepold=1):
        """take transactionData class and populate transaction set"""

        if self.dsCallback: self.dsCallback.transactionPopulation()
        ts_elem = {}
        
        if self.ts.ts is None:
            self.initActionTs()
            
        if keepold:
            for te in self.ts:
                epoch = te.E()
                if epoch is None:
                    epoch = '0'
                pkginfo = (te.N(), te.A(), epoch, te.V(), te.R())
                if te.Type() == 1:
                    mode = 'i'
                elif te.Type() == 2:
                    mode = 'e'
                
                ts_elem[(pkginfo, mode)] = 1
                
        for txmbr in self.tsInfo.getMembers():
            self.verbose_logger.log(logginglevels.DEBUG_3, _('Member: %s'), txmbr)
            if txmbr.ts_state in ['u', 'i']:
                if ts_elem.has_key((txmbr.pkgtup, 'i')):
                    continue
                rpmfile = txmbr.po.localPkg()
                if os.path.exists(rpmfile):
                    hdr = txmbr.po.returnHeaderFromPackage()
                else:
                    self.downloadHeader(txmbr.po)
                    hdr = txmbr.po.returnLocalHeader()

                if txmbr.ts_state == 'u':
                    if self.allowedMultipleInstalls(txmbr.po):
                        self.verbose_logger.log(logginglevels.DEBUG_2,
                            _('%s converted to install'), txmbr.po)
                        txmbr.ts_state = 'i'
                        txmbr.output_state = TS_INSTALL

                
                self.ts.addInstall(hdr, (hdr, rpmfile), txmbr.ts_state)
                self.verbose_logger.log(logginglevels.DEBUG_1,
                    _('Adding Package %s in mode %s'), txmbr.po, txmbr.ts_state)
                if self.dsCallback: 
                    self.dsCallback.pkgAdded(txmbr.pkgtup, txmbr.ts_state)
            
            elif txmbr.ts_state in ['e']:
                if ts_elem.has_key((txmbr.pkgtup, txmbr.ts_state)):
                    continue
                self.ts.addErase(txmbr.po.idx)
                if self.dsCallback: self.dsCallback.pkgAdded(txmbr.pkgtup, 'e')
                self.verbose_logger.log(logginglevels.DEBUG_1,
                    _('Removing Package %s'), txmbr.po)

    def _processReq(self, po, requirement):
        """processes a Requires dep from the resolveDeps functions, returns a tuple
           of (CheckDeps, missingdep, conflicts, errors) the last item is an array
           of error messages"""
        
        errormsgs = []

        needname, flags, needversion = requirement
        niceformatneed = rpmUtils.miscutils.formatRequire(needname, needversion, flags)
        self.verbose_logger.log(logginglevels.DEBUG_1, _('%s requires: %s'), po, niceformatneed)
        if self.dsCallback: self.dsCallback.procReq(po.name, niceformatneed)

        try:    
            if po.repo.id != "installed":
                CheckDeps, missingdep = self._requiringFromTransaction(po, requirement, errormsgs)
            else:
                CheckDeps, missingdep = self._requiringFromInstalled(po, requirement, errormsgs)
    
            # Check packages with problems
            if missingdep:
                self.po_with_problems.add((po,self._working_po,errormsgs[-1]))
            
    
        except Errors.DepError,e:
            # FIXME: This is a hack, it don't solve the problem
            # of tries to update to a package the have been removed from the
            # pkgSack because of dep problems.
            # The real solution is to remove the package from the updates, when
            # it is remove from the pkgSack
            self.po_with_problems.add((po,self._working_po,str(e)))
            CheckDeps = 1
            missingdep = 0

        return (CheckDeps, missingdep, errormsgs)

    @staticmethod
    def _prco_req_nfv2req(rn, rf, rv):
        return (rn, flags[rf], version_tuple_to_string(rv))

    def _prco_req2req(self, req):
        return self._prco_req_nfv2req(req[0], req[1], req[2])
            
    def _requiringFromInstalled(self, requiringPo, requirement, errorlist):
        """processes the dependency resolution for a dep where the requiring 
           package is installed"""

        checkdeps = 0
        missingdep = 0
        
        if self.tsInfo.getMembersWithState(requiringPo.pkgtup, TS_REMOVE_STATES):
            return checkdeps, missingdep

        name, arch, epoch, ver, rel = requiringPo.pkgtup

        needname, needflags, needversion = requirement
        niceformatneed = rpmUtils.miscutils.formatRequire(needname, needversion, needflags)


        # we must first find out why the requirement is no longer there
        # we must find out what provides/provided it from the rpmdb (if anything)
        # then check to see if that thing is being acted upon by the transaction set
        # if it is then we need to find out what is being done to it and act accordingly
        needmode = None # mode in the transaction of the needed pkg (if any)
        needpo = None
        providers = []
        
        if self.cheaterlookup.has_key((needname, needflags, needversion)):
            self.verbose_logger.log(logginglevels.DEBUG_2, _('Needed Require has already been looked up, cheating'))
            cheater_po = self.cheaterlookup[(needname, needflags, needversion)]
            providers = [cheater_po]
        
        elif self.rpmdb.contains(name=needname):
            txmbrs = self.tsInfo.matchNaevr(name=needname)
            for txmbr in txmbrs:
                providers.append(txmbr.po)

        else:
            self.verbose_logger.log(logginglevels.DEBUG_2, _('Needed Require is not a package name. Looking up: %s'), niceformatneed)
            providers = self.rpmdb.getProvides(needname, needflags, needversion)

        for inst_po in providers:
            inst_str = '%s.%s %s:%s-%s' % inst_po.pkgtup
            (i_n, i_a, i_e, i_v, i_r) = inst_po.pkgtup
            self.verbose_logger.log(logginglevels.DEBUG_2,
                _('Potential Provider: %s'), inst_str)
            thismode = self.tsInfo.getMode(name=i_n, arch=i_a, 
                            epoch=i_e, ver=i_v, rel=i_r)

            if thismode is None and i_n in self.conf.exactarchlist:
                # check for mode by the same name+arch
                thismode = self.tsInfo.getMode(name=i_n, arch=i_a)
            
            if thismode is None and i_n not in self.conf.exactarchlist:
                # check for mode by just the name
                thismode = self.tsInfo.getMode(name=i_n)

            # if this package is being obsoleted, it's just like if it's
            # being upgraded as far as checking for other providers
            if thismode is None:
                if filter(lambda x: x.obsoleted_by,
                          self.tsInfo.matchNaevr(i_n, i_a, i_e, i_v, i_r)):
                    thismode = 'u'

            if thismode is not None:
                needmode = thismode

                self.cheaterlookup[(needname, needflags, needversion)] = inst_po
                self.verbose_logger.log(logginglevels.DEBUG_2, _('Mode is %s for provider of %s: %s'),
                    needmode, niceformatneed, inst_str)
                break
                    
        self.verbose_logger.log(logginglevels.DEBUG_2, _('Mode for pkg providing %s: %s'), 
            niceformatneed, needmode)

        if needmode in ['e']:
            self.verbose_logger.log(logginglevels.DEBUG_2, _('TSINFO: %s package requiring %s marked as erase'),
                requiringPo, needname)
            txmbr = self.tsInfo.addErase(requiringPo)
            txmbr.setAsDep(po=inst_po)
            checkdeps = 1
        
        if needmode in ['i', 'u']:
            length = len(self.tsInfo)
            self.update(name=name, epoch=epoch, version=ver, release=rel,
                        requiringPo=requiringPo)
            txmbrs = self.tsInfo.getMembersWithState(requiringPo.pkgtup, TS_REMOVE_STATES)
            if len(self.tsInfo) != length and txmbrs:
                if txmbrs[0].output_state == TS_OBSOLETED:
                    self.verbose_logger.log(logginglevels.DEBUG_2, _('TSINFO: Obsoleting %s with %s to resolve dep.'),
                                            requiringPo, txmbrs[0].obsoleted_by[0])
                else:
                    self.verbose_logger.log(logginglevels.DEBUG_2, _('TSINFO: Updating %s to resolve dep.'), requiringPo)
                    # If the requirement is still there, try and solve it again
                    # so we don't lose it
                    for pkg in txmbrs[0].updated_by:
                        if requirement in map(self._prco_req2req, pkg.returnPrco('requires')):
                            return True, missingdep + self._requiringFromTransaction(pkg, requirement, errorlist)[1]
                checkdeps = True
                return checkdeps, missingdep
            self.verbose_logger.log(logginglevels.DEBUG_2, _('Cannot find an update path for dep for: %s'), niceformatneed)
            return self._requiringFromTransaction(requiringPo, requirement, errorlist)
            

        if needmode is None:
            reqpkg = (name, ver, rel, None)
            if self.pkgSack is None:
                return self._requiringFromTransaction(requiringPo, requirement, errorlist)
            else:
                prob_pkg = "%s (%s)" % (requiringPo,requiringPo.repoid)
                msg = _('Unresolvable requirement %s for %s') % (niceformatneed,
                                                               prob_pkg)
                self.verbose_logger.log(logginglevels.DEBUG_2, msg)
                checkdeps = 0
                missingdep = 1
                errorlist.append(msg)

        return checkdeps, missingdep
        
    def _quickWhatProvides(self, name, flags, version):
        if self._last_req is None:
            return False

        if flags == 0:
            flags = None
        if type(version) in (types.StringType, types.NoneType, types.UnicodeType):
            (r_e, r_v, r_r) = rpmUtils.miscutils.stringToVersion(version)
        elif type(version) in (types.TupleType, types.ListType): # would this ever be a ListType?
            (r_e, r_v, r_r) = version
        
        # Quick lookup, lots of reqs for one pkg:
        po = self._last_req
        if po.checkPrco('provides', (name, flags, (r_e, r_v, r_r))):
            self.verbose_logger.debug(_('Quick matched %s to require for %s'), po, name)
            return True
        return False
        
    def _requiringFromTransaction(self, requiringPo, requirement, errorlist):
        """processes the dependency resolution for a dep where requiring 
           package is in the transaction set"""
        
        (name, arch, epoch, version, release) = requiringPo.pkgtup
        (needname, needflags, needversion) = requirement
        checkdeps = 0
        missingdep = 0
        upgraded = {}

        #~ - if it's not available from some repository:
        #~     - mark as unresolveable.
        #
        #~ - if it's available from some repo:
        #~    - if there is an another version of the package currently installed then
        #        - if the other version is marked in the transaction set
        #           - if it's marked as erase
        #              - mark the dep as unresolveable
         
        #           - if it's marked as update or install
        #              - check if the version for this requirement:
        #                  - if it is higher 
        #                       - mark this version to be updated/installed
        #                       - remove the other version from the transaction set
        #                       - tell the transaction set to be rebuilt
        #                  - if it is lower
        #                       - mark the dep as unresolveable
        #                   - if they are the same
        #                       - be confused but continue

        if self._quickWhatProvides(needname, needflags, needversion):
            return checkdeps, missingdep

        provSack = self.whatProvides(needname, needflags, needversion)
        # get rid of things that are already in the rpmdb - b/c it's pointless to use them here

        for pkg in provSack.returnPackages():
            if self.rpmdb.contains(po=pkg): # is it already installed?
                self.verbose_logger.log(logginglevels.DEBUG_2, _('%s is in providing packages but it is already installed, removing.'), pkg)
                provSack.delPackage(pkg)
                continue

            # we need to check to see, if we have anything similar to it (name-wise)
            # installed or in the ts, and this isn't a package that allows multiple installs
            # then if it's newer, fine - continue on, if not, then we're unresolveable
            # cite it and exit

            tspkgs = []
            if not self.allowedMultipleInstalls(pkg):
                # from ts
                tspkgs = self.tsInfo.matchNaevr(name=pkg.name, arch=pkg.arch)
                for tspkg in tspkgs:
                    if tspkg.po.verGT(pkg):
                        msg = _('Potential resolving package %s has newer instance in ts.') % pkg
                        self.verbose_logger.log(logginglevels.DEBUG_2, msg)
                        provSack.delPackage(pkg)
                        continue
                    elif tspkg.po.verLT(pkg):
                        upgraded.setdefault(pkg.pkgtup, []).append(tspkg.pkgtup)
                
                # from rpmdb
                dbpkgs = self.rpmdb.searchNevra(name=pkg.name, arch=pkg.arch)
                for dbpkg in dbpkgs:
                    if dbpkg.verGT(pkg):
                        msg = _('Potential resolving package %s has newer instance installed.') % pkg
                        self.verbose_logger.log(logginglevels.DEBUG_2, msg)
                        provSack.delPackage(pkg)
                        continue

        if len(provSack) == 0: # unresolveable
            missingdep = 1
            prob_pkg = "%s (%s)" % (requiringPo,requiringPo.repoid)
            msg = _('Missing Dependency: %s is needed by package %s') % \
            (rpmUtils.miscutils.formatRequire(needname, needversion, needflags),
                                                                   prob_pkg)
            errorlist.append(msg)
            return checkdeps, missingdep
        
        # iterate the provSack briefly, if we find the package is already in the 
        # tsInfo then just skip this run
        for pkg in provSack.returnPackages():
            (n,a,e,v,r) = pkg.pkgtup
            pkgmode = self.tsInfo.getMode(name=n, arch=a, epoch=e, ver=v, rel=r)
            if pkgmode in ['i', 'u']:
                self.verbose_logger.log(logginglevels.DEBUG_2,
                    _('%s already in ts, skipping this one'), pkg)
                # FIXME: Remove this line, if it is not needed ?
                # checkdeps = 1
                self._last_req = pkg
                return checkdeps, missingdep

        # find the best one 

        # try updating the already install pkgs
        for pkg in provSack.returnNewestByName():
            results = self.update(requiringPo=requiringPo, name=pkg.name,
                                  epoch=pkg.epoch, version=pkg.version,
                                  rel=pkg.rel)
            for txmbr in results:
                if pkg == txmbr.po:
                    checkdeps = True
                    self._last_req = pkg
                    return checkdeps, missingdep

        # find out which arch of the ones we can choose from is closest
        # to the arch of the requesting pkg
        newest = provSack.returnNewestByNameArch()
        if len(newest) > 1: # there's no way this can be zero
                            
            pkgresults = self._compare_providers(newest, requiringPo)
            # take the first one...
            best = pkgresults[0][0]                   
                
        elif len(newest) == 1:
            best = newest[0]
        
        
        if self.rpmdb.contains(po=best): # is it already installed?
            missingdep = 1
            checkdeps = 0
            prob_pkg = "%s (%s)" % (requiringPo,requiringPo.repoid)
            msg = _('Missing Dependency: %s is needed by package %s') % (needname, prob_pkg)
            errorlist.append(msg)
            return checkdeps, missingdep
        
                
            
        # FIXME - why can't we look up in the transaction set for the requiringPkg
        # and know what needs it that way and provide a more sensible dep structure in the txmbr
        inst = self.rpmdb.searchNevra(name=best.name, arch=best.arch)
        if len(inst) > 0: 
            self.verbose_logger.debug(_('TSINFO: Marking %s as update for %s') %(best,
                requiringPo))
            # FIXME: we should probably handle updating multiple packages...
            txmbr = self.tsInfo.addUpdate(best, inst[0])
            txmbr.setAsDep(po=requiringPo)
            txmbr.reason = "dep"
            self._last_req = best
        else:
            self.verbose_logger.debug(_('TSINFO: Marking %s as install for %s'), best,
                requiringPo)
            # FIXME: Don't we want .install() here, so obsoletes get done?
            txmbr = self.tsInfo.addInstall(best)
            txmbr.setAsDep(po=requiringPo)
            self._last_req = best

            # if we had other packages with this name.arch that we found
            # before, they're not going to be installed anymore, so we
            # should mark them to be re-checked
            if upgraded.has_key(best.pkgtup):
                map(lambda x: self.tsInfo.remove(x), upgraded[best.pkgtup])

        checkdeps = 1
        
        return checkdeps, missingdep


    def _processConflict(self, po, conflict, conflicting_po):
        """processes a Conflict dep from the resolveDeps() method"""

        CheckDeps = True
        errormsgs = []

        needname, flags, needversion = conflict
        (name, arch, epoch, ver, rel) = po.pkgtup

        niceformatneed = rpmUtils.miscutils.formatRequire(needname, needversion, flags)
        if self.dsCallback: self.dsCallback.procConflict(name, niceformatneed)

        length = len(self.tsInfo)
        if flags & rpm.RPMSENSE_LESS:
            self.update(name=conflicting_po.name)
            txmbrs = self.tsInfo.getMembersWithState(conflicting_po.pkgtup, TS_REMOVE_STATES)
            if len(self.tsInfo) != length and txmbrs:
                return CheckDeps, errormsgs
        elif flags & rpm.RPMSENSE_GREATER:
            self.update(name=name)
            txmbrs = self.tsInfo.getMembersWithState(po.pkgtup, TS_REMOVE_STATES)
            if len(self.tsInfo) != length and txmbrs:
                return CheckDeps, errormsgs

        self.update(name=conflicting_po.name)
        txmbrs = self.tsInfo.getMembersWithState(conflicting_po.pkgtup, TS_REMOVE_STATES)
        if len(self.tsInfo) != length and txmbrs:
            return CheckDeps, errormsgs
        self.update(name=name)
        txmbrs = self.tsInfo.getMembersWithState(po.pkgtup, TS_REMOVE_STATES)
        if len(self.tsInfo) != length and txmbrs:
            return CheckDeps, errormsgs

        msg = '%s conflicts with %s' % (name, conflicting_po.name)
        errormsgs.append(msg)
        self.verbose_logger.log(logginglevels.DEBUG_1, msg)
        CheckDeps = False
        self.po_with_problems.add((po,None,errormsgs[-1]))
        return CheckDeps, errormsgs

    def _undoDepInstalls(self):
        # clean up after ourselves in the case of failures
        for txmbr in self.tsInfo:
            if txmbr.isDep:
                self.tsInfo.remove(txmbr.pkgtup)

    def prof_resolveDeps(self):
        fn = "anaconda.prof.0"
        import hotshot, hotshot.stats
        prof = hotshot.Profile(fn)
        rc = prof.runcall(self.resolveDeps)
        prof.close()
        print "done running depcheck"
        stats = hotshot.stats.load(fn)
        stats.strip_dirs()
        stats.sort_stats('time', 'calls')
        stats.print_stats(20)
        return rc

    def cprof_resolveDeps(self):
        import cProfile, pstats
        prof = cProfile.Profile()
        rc = prof.runcall(self.resolveDeps)
        prof.dump_stats("yumprof")
        print "done running depcheck"

        p = pstats.Stats('yumprof')
        p.strip_dirs()
        p.sort_stats('time')
        p.print_stats(20)
        return rc

    def resolveDeps(self):

        if not len(self.tsInfo):
            return (0, [_('Success - empty transaction')])

        self.po_with_problems = set()
        self._working_po = None
        self._last_req = None
        self.tsInfo.resetResolved(hard=False)

        CheckDeps = True
        CheckRemoves = False
        CheckInstalls = False

        missingdep = 0
        errors = []

        if self.dsCallback: self.dsCallback.start()

        while True:

            CheckDeps = True

            # check Requires
            while CheckDeps:
                self.cheaterlookup = {}
                if self.dsCallback: self.dsCallback.tscheck()
                CheckDeps, checkinstalls, checkremoves, missing = self._resolveRequires(errors)
                CheckInstalls |= checkinstalls
                CheckRemoves |= checkremoves


            # check global FileRequires
            if CheckRemoves:
                CheckRemoves = False
                for po, dep in self._checkFileRequires():
                    (checkdep, missing, errormsgs) = self._processReq(po, dep)
                    CheckDeps |= checkdep
                    errors += errormsgs

                if CheckDeps:
                    if self.dsCallback: self.dsCallback.restartLoop()
                    self.verbose_logger.log(logginglevels.DEBUG_1, _('Restarting Loop'))
                    continue

            # check Conflicts
            if CheckInstalls:
                CheckInstalls = False
                for conflict in self._checkConflicts():
                    (checkdep, errormsgs) = self._processConflict(*conflict)
                    CheckDeps |= checkdep
                    errors += errormsgs
                    if checkdep:
                        break # The next conflict might be the same pkg

                if CheckDeps:
                    if self.dsCallback: self.dsCallback.restartLoop()
                    self.verbose_logger.log(logginglevels.DEBUG_1, _('Restarting Loop'))
                    continue

            break

        # FIXME: this doesn't belong here at all...
        for txmbr in self.tsInfo.getMembers():
            if self.allowedMultipleInstalls(txmbr.po) and \
                   txmbr.ts_state == 'u':
                self.verbose_logger.log(logginglevels.DEBUG_2,
                                        _('%s converted to install'),
                                        txmbr.po)
                txmbr.ts_state = 'i'
                txmbr.output_state = TS_INSTALL

        if self.dsCallback: self.dsCallback.end()
        self.verbose_logger.log(logginglevels.DEBUG_1, _('Dependency Process ending'))

        self.tsInfo.changed = False
        if len(errors) > 0:
            errors = unique(errors)
            for po,wpo,err in self.po_with_problems:
                self.verbose_logger.info(_("%s from %s has depsolving problems") % (po,po.repoid))
                self.verbose_logger.info("  --> %s" % (err))
            return (1, errors)

        if len(self.tsInfo) > 0:
            if not len(self.tsInfo):
                return (0, [_('Success - empty transaction')])
            return (2, [_('Success - deps resolved')])

    def _resolveRequires(self, errors):
        any_missing = False
        CheckDeps = False
        CheckInstalls = False
        CheckRemoves = False
        # we need to check the opposite of install and remove for regular
        # tsInfo members vs removed members
        for txmbr in self.tsInfo.getUnresolvedMembers():

            if self.dsCallback and txmbr.ts_state:
                self.dsCallback.pkgAdded(txmbr.pkgtup, txmbr.ts_state)
            self.verbose_logger.log(logginglevels.DEBUG_2,
                                    _("Checking deps for %s") %(txmbr,))

            # store the primary po we currently are working on 
            # so we can store it in self.po_with_problems.
            # it is useful when an update is breaking an require of an installed package
            # then we want to know who is causing the problem, not just who is having the problem. 
            if not txmbr.updates and txmbr.relatedto:
                self._working_po = txmbr.relatedto[0][0]
            else:
                self._working_po = txmbr.po
           
            if (txmbr.output_state in TS_INSTALL_STATES) == (txmbr.po.state != None):
                thisneeds = self._checkInstall(txmbr)
                CheckInstalls = True
            else:
                thisneeds = self._checkRemove(txmbr)
                CheckRemoves = True

            missing_in_pkg = False
            for po, dep in thisneeds:
                (checkdep, missing, errormsgs) = self._processReq(po, dep)
                CheckDeps |= checkdep
                errors += errormsgs
                missing_in_pkg |= missing

            if not missing_in_pkg:
                self.tsInfo.markAsResolved(txmbr)

            any_missing |= missing_in_pkg

        return CheckDeps, CheckInstalls, CheckRemoves, any_missing

    @staticmethod
    def _sort_reqs(pkgtup1, pkgtup2):
        """ Sort the requires for a package from most "narrow" to least,
            this tries to ensure that if we have two reqs like
            "libfoo = 1.2.3-4" and "foo-api" (which is also provided by
            libxyz-foo) that we'll get just libfoo.
            There are other similar cases this "handles"."""

        mapper = {'EQ' : 1, 'LT' : 2, 'LE' : 3, 'GT' : 4, 'GE' : 5,
                  None : 99}
        ret = mapper.get(pkgtup1[1], 10) - mapper.get(pkgtup2[1], 10)
        if ret:
            return ret

        # This is pretty magic, basically we want an explicit:
        #
        #  Requires: foo
        #
        # ...to happen before the implicit:
        #
        #  Requires: libfoo.so.0()
        #
        # ...because sometimes the libfoo.so.0() is provided by multiple
        # packages. Do we need more magic for other implicit deps. here?
        def _req_name2val(name):
            if (name.startswith("lib") and
                (name.endswith("()") or name.endswith("()(64bit)"))):
                return 99 # Processes these last
            return 0
        return _req_name2val(pkgtup1[0]) - _req_name2val(pkgtup2[0])

    def _checkInstall(self, txmbr):
        txmbr_reqs = txmbr.po.returnPrco('requires')
        txmbr_provs = set(txmbr.po.returnPrco('provides'))

        # if this is an update, we should check what the old
        # requires were to make things faster
        oldreqs = []
        for oldpo in txmbr.updates:
            oldreqs.extend(oldpo.returnPrco('requires'))
        oldreqs = set(oldreqs)

        ret = []
        for req in sorted(txmbr_reqs, cmp=self._sort_reqs):
            if req[0].startswith('rpmlib('):
                continue
            if req in txmbr_provs:
                continue
            if req in oldreqs and self.rpmdb.getProvides(*req):
                continue
            
            self.verbose_logger.log(logginglevels.DEBUG_2, _("looking for %s as a requirement of %s"), req, txmbr)
            provs = self.tsInfo.getProvides(*req)
            if not provs:
                ret.append( (txmbr.po, self._prco_req2req(req)) )
                continue

            #Add relationship
            for po in provs:
                if txmbr.name == po.name:
                    continue
                for member in self.tsInfo.getMembersWithState(
                    pkgtup=po.pkgtup, output_states=TS_INSTALL_STATES):
                    member.relatedto.append((txmbr.po, 'dependson'))

        return ret

    def _checkRemove(self, txmbr):
        po = txmbr.po
        provs = po.returnPrco('provides')

        # if this is an update, we should check what the new package
        # provides to make things faster
        newpoprovs = {}
        for newpo in txmbr.updated_by:
            for p in newpo.provides:
                newpoprovs[p] = 1
        ret = []
        
        # iterate over the provides of the package being removed
        # and see what's actually going away
        for prov in provs:
            if prov[0].startswith('rpmlib('): # ignore rpmlib() provides
                continue
            if newpoprovs.has_key(prov):
                continue
            # FIXME: This is probably the best place to fix the postfix rename
            # problem long term (post .21) ... see compare_providers.
            for pkg, hits in self.tsInfo.getRequires(*prov).iteritems():
                for rn, rf, rv in hits:
                    if not self.tsInfo.getProvides(rn, rf, rv):
                        ret.append( (pkg, self._prco_req_nfv2req(rn, rf, rv)) )
        return ret

    def _checkFileRequires(self):
        fileRequires = set()
        reverselookup = {}
        ret = []

        # generate list of file requirement in rpmdb
        if self.installedFileRequires is None:
            self.installedFileRequires = {}
            self.installedUnresolvedFileRequires = set()
            resolved = set()
            for pkg in self.rpmdb.returnPackages():
                for name, flag, evr in pkg.requires:
                    if not name.startswith('/'):
                        continue
                    self.installedFileRequires.setdefault(pkg, []).append(name)
                    if name not in resolved:
                        dep = self.rpmdb.getProvides(name, flag, evr)
                        resolved.add(name)
                        if not dep:
                            self.installedUnresolvedFileRequires.add(name)

        # get file requirements from packages not deleted
        for po, files in self.installedFileRequires.iteritems():
            if not self._tsInfo.getMembersWithState(po.pkgtup, output_states=TS_REMOVE_STATES):
                fileRequires.update(files)
                for filename in files:
                    reverselookup.setdefault(filename, []).append(po)

        fileRequires -= self.installedUnresolvedFileRequires

        # get file requirements from new packages
        for txmbr in self._tsInfo.getMembersWithState(output_states=TS_INSTALL_STATES):
            for name, flag, evr in txmbr.po.requires:
                if name.startswith('/'):
                    # check if file requires was already unresolved in update
                    if name in self.installedUnresolvedFileRequires:
                        already_broken = False
                        for oldpo in txmbr.updates:
                            if oldpo.checkPrco('requires', (name, None, (None, None, None))):
                                already_broken = True
                                break
                        if already_broken:
                            continue
                    fileRequires.add(name)
                    reverselookup.setdefault(name, []).append(txmbr.po)

        # check the file requires
        for filename in fileRequires:
            if not self.tsInfo.getOldProvides(filename) and not self.tsInfo.getNewProvides(filename):
                for po in reverselookup[filename]:
                    ret.append( (po, (filename, 0, '')) )

        return ret


    def _checkConflicts(self):
        ret = [ ]
        for po in self.rpmdb.returnPackages():
            if self.tsInfo.getMembersWithState(po.pkgtup, output_states=TS_REMOVE_STATES):
                continue
            for conflict in po.returnPrco('conflicts'):
                (r, f, v) = conflict
                for conflicting_po in self.tsInfo.getNewProvides(r, f, v):
                    if conflicting_po.pkgtup[0] == po.pkgtup[0] and conflicting_po.pkgtup[2:] == po.pkgtup[2:]:
                        continue
                    ret.append( (po, self._prco_req_nfv2req(r, f, v),
                                 conflicting_po) )
        for txmbr in self.tsInfo.getMembersWithState(output_states=TS_INSTALL_STATES):
            po = txmbr.po
            for conflict in txmbr.po.returnPrco('conflicts'):
                (r, f, v) = conflict
                for conflicting_po in self.tsInfo.getProvides(r, f, v):
                    if conflicting_po.pkgtup[0] == po.pkgtup[0] and conflicting_po.pkgtup[2:] == po.pkgtup[2:]:
                        continue
                    ret.append( (po, self._prco_req_nfv2req(r, f, v),
                                 conflicting_po) )
        return ret


    def isPackageInstalled(self, pkgname):
        installed = False
        if self.rpmdb.contains(name=pkgname):
            installed = True

        lst = self.tsInfo.matchNaevr(name = pkgname)
        for txmbr in lst:
            if txmbr.output_state in TS_INSTALL_STATES:
                return True
        if installed and len(lst) > 0:
            # if we get here, then it was installed, but it's in the tsInfo
            # for an erase or obsoleted --> not going to be installed at end
            return False
        return installed
    _isPackageInstalled = isPackageInstalled

    def _compare_providers(self, pkgs, reqpo):
        """take the list of pkgs and score them based on the requesting package
           return a dictionary of po=score"""
        self.verbose_logger.log(logginglevels.DEBUG_4,
              _("Running compare_providers() for %s") %(str(pkgs)))

        
        def _common_prefix_len(x, y, minlen=2):
            num = min(len(x), len(y))
            for off in range(num):
                if x[off] != y[off]:
                    return max(off, minlen)
            return max(num, minlen)

        def _common_sourcerpm(x, y):
            if not hasattr(x, 'sourcerpm'):
                return False
            if not hasattr(y, 'sourcerpm'):
                return False
            return x.sourcerpm == y.sourcerpm

        def _compare_arch_distance(x, y, req_compare_arch):
            # take X and Y package objects
            # determine which has a closer archdistance to compare_arch
            # if they are equal to compare_arch, compare which is closer to the 
            # running arch
            # return the package which is closer or None for equal, or equally useless
            
            x_dist = archDifference(req_compare_arch, x.arch)
            if isMultiLibArch(): # only go to the next one if we're multilib - 
                if x_dist == 0: # can't really use best's arch anyway...
                    self.verbose_logger.log(logginglevels.DEBUG_4,
                        _("better arch in po %s") %(y))
                    return y # just try the next one - can't be much worse

            y_dist = archDifference(req_compare_arch, y.arch)
            if y_dist > 0 and x_dist > y_dist:
                self.verbose_logger.log(logginglevels.DEBUG_4,
                    _("better arch in po %s") %(y))

                return y
            if y_dist == x_dist:
                return None
            return x
            
        pkgresults = {}
        ipkgresults = {}

        for pkg in pkgs:
            pkgresults[pkg] = 0
            if self.rpmdb.contains(pkg.name):
                ipkgresults[pkg] = 0

        #  This is probably only for "renames". What happens is that pkgA-1 gets
        # obsoleted by pkgB but pkgB requires pkgA-2, now _if_ the pkgA txmbr
        # gets processed before pkgB then we'll process the "checkRemove" of
        # pkgA ... so any deps. on pkgA-1 will look for a new provider, one of
        # which is pkgA-2 in that case we want to choose that pkg over any
        # others. This works for multiple cases too, but who'd do that right?:)
        #  FIXME: A good long term. fix here is to just not get into this
        # problem, but that's too much for .21. This is much safer.
        if ipkgresults:
            pkgresults = ipkgresults
            pkgs = ipkgresults.keys()
            
        # go through each pkg and compare to others
        # if it is same skip it
        # if the pkg is obsoleted by any other of the packages
        # then add  -1024 to its score
        # don't need to look for mutual obsoletes b/c each package
        # is evaluated against all the others, so mutually obsoleting
        # packages will have their scores diminished equally
        
        # compare the arch vs each other pkg
        #   give each time it returns with a better arch a +5

        # look for common source vs the reqpo - give a +10 if it has it

        # look for common_prefix_len - add the length*2 to the score
        
        # add the negative of the length of the name to the score
        
        for po in pkgs:
            for nextpo in pkgs:
                if po == nextpo:
                    continue
                obsoleted = False
                for obs in nextpo.obsoletes:
                    if po.inPrcoRange('provides', obs):
                        obsoleted = True
                                
                        self.verbose_logger.log(logginglevels.DEBUG_4,
                            _("%s obsoletes %s") % (po, nextpo))

                    if obsoleted:
                        pkgresults[po] -= 1024
                        break
                
                if reqpo:
                    arches = (reqpo.arch, getBestArch())
                else:
                    arches = (getBestArch())
                
                for thisarch in arches:
                    res = _compare_arch_distance(po, nextpo, thisarch)
                    if not res:
                        continue
                    self.verbose_logger.log(logginglevels.DEBUG_4,                   
                       _('archdist compared %s to %s on %s\n  Winner: %s' % (po, nextpo, thisarch, res)))

                    if res == po:
                        pkgresults[po] += 5

            if _common_sourcerpm(po, reqpo):
                self.verbose_logger.log(logginglevels.DEBUG_4,
                    _('common sourcerpm %s and %s' % (po, reqpo)))
                pkgresults[po] += 20
            if reqpo:
                cpl = _common_prefix_len(po.name, reqpo.name)
                if cpl > 2:
                    self.verbose_logger.log(logginglevels.DEBUG_4,
                        _('common prefix of %s between %s and %s' % (cpl, po, reqpo)))
                
                    pkgresults[po] += cpl*2
            
            pkgresults[po] += (len(po.name)*-1)

        bestorder = sorted(pkgresults.items(), key=itemgetter(1), reverse=True)
        self.verbose_logger.log(logginglevels.DEBUG_4,
                _('Best Order: %s' % str(bestorder)))

        return bestorder
                                    
       


class DepCheck(object):
    """object that YumDepsolver uses to see what things are needed to close
       the transaction set. attributes: requires, conflicts are a list of 
       requires are conflicts in the current transaction set. Each item in the
       lists are a requires or conflicts object"""
    def __init__(self):
        self.requires = []
        self.conflicts = []

    def addRequires(self, po, req_tuple_list):
        # fixme - do checking for duplicates or additions in here to zip things along
        reqobj = Requires(po, req_tuple_list)
        self.requires.append(reqobj)
    
    def addConflicts(self, conflict_po_list, conflict_item):
        confobj = Conflicts(conflict_po_list, conflict_item)
        self.conflicts.append(confobj)

class Requires(object):

    """
    A pure data class for holding a package and the list of things it
    requires.
    """

    def __init__(self, pkg,requires):
        self.pkg = pkg # po of requiring pkg
        self.requires = requires # list of things it requires that are un-closed in the ts


class Conflicts(object):

    """
    A pure data class for holding a package and the list of things it
    conflicts.
    """

    def __init__(self, pkglist, conflict):
        self.pkglist = pkglist # list of conflicting package objects
        self.conflict = conflict # what the conflict was between them
