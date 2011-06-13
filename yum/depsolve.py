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
Dependency resolution module for yum.
"""

import os.path
import types
import logging

import rpmUtils.transaction
import rpmUtils.miscutils
from rpmUtils.arch import archDifference, canCoinstall
import misc
from misc import unique, version_tuple_to_string
from transactioninfo import TransactionMember
import rpm

from packageSack import ListPackageSack
from constants import *
import packages
import logginglevels
import Errors
import warnings
warnings.simplefilter("ignore", Errors.YumFutureDeprecationWarning)

from yum import _, _rpm_ver_atleast

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
        self._ts = None
        self._tsInfo = None
        self.dsCallback = None
        # Callback-style switch, default to legacy (hdr, file) mode
        self.use_txmbr_in_callback = False
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
        # This is only in newer rpm.org releases
        if hasattr(rpm, 'RPMTRANS_FLAG_NOCONTEXTS'):
            ts_flags_to_rpm['nocontexts'] = rpm.RPMTRANS_FLAG_NOCONTEXTS
        
        self._ts.setFlags(0) # reset everything.
        
        for flag in self.conf.tsflags:
            if flag in ts_flags_to_rpm:
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
        defSack = ListPackageSack(self.pkgSack.searchProvides((name, flags, version)))
        return defSack
        
    def allowedMultipleInstalls(self, po):
        """takes a packageObject, returns 1 or 0 depending on if the package 
           should/can be installed multiple times with different vers
           like kernels and kernel modules, for example"""

        iopkgs = set(self.conf.installonlypkgs)
        if po.name in iopkgs:
            return True
        
        for prov in po.provides_names:
            if prov in iopkgs:
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
                if (txmbr.pkgtup, 'i') in ts_elem:
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

                # New-style callback with just txmbr instead of full headers?
                if self.use_txmbr_in_callback:
                    cbkey = txmbr
                else:
                    cbkey = (hdr, rpmfile)
                
                self.ts.addInstall(hdr, cbkey, txmbr.ts_state)
                self.verbose_logger.log(logginglevels.DEBUG_1,
                    _('Adding Package %s in mode %s'), txmbr.po, txmbr.ts_state)
                if self.dsCallback:
                    dscb_ts_state = txmbr.ts_state
                    if dscb_ts_state == 'u' and txmbr.downgrades:
                        dscb_ts_state = 'd'
                    self.dsCallback.pkgAdded(txmbr.pkgtup, dscb_ts_state)
            
            elif txmbr.ts_state in ['e']:
                if (txmbr.pkgtup, txmbr.ts_state) in ts_elem:
                    continue
                self.ts.addErase(txmbr.po.idx)
                if self.dsCallback:
                    if txmbr.downgraded_by:
                        continue
                    self.dsCallback.pkgAdded(txmbr.pkgtup, 'e')
                self.verbose_logger.log(logginglevels.DEBUG_1,
                    _('Removing Package %s'), txmbr.po)

    def _dscb_procReq(self, po, niceformatneed):
        """ Call the callback for processing requires, call the nicest one
            available. """
        if not self.dsCallback:
            return

        if hasattr(self.dsCallback, 'procReqPo'):
            self.dsCallback.procReqPo(po, niceformatneed)
        else:
            self.dsCallback.procReq(po.name, niceformatneed)

    def _processReq(self, po, requirement):
        """processes a Requires dep from the resolveDeps functions, returns a tuple
           of (CheckDeps, missingdep, conflicts, errors) the last item is an array
           of error messages"""
        
        errormsgs = []

        needname, flags, needversion = requirement
        niceformatneed = rpmUtils.miscutils.formatRequire(needname, needversion, flags)
        self.verbose_logger.log(logginglevels.DEBUG_1, _('%s requires: %s'), po, niceformatneed)
        self._dscb_procReq(po, niceformatneed)

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
            
    def _err_missing_requires(self, reqPo, reqTup):
        if hasattr(self.dsCallback, 'format_missing_requires'):
            msg = self.dsCallback.format_missing_requires(reqPo, reqTup)
            if msg is not None: # PK
                return self.dsCallback.format_missing_requires(reqPo, reqTup)
        (needname, needflags, needversion) = reqTup
        ui_req = rpmUtils.miscutils.formatRequire(needname, needversion,
                                                  needflags)
        return _('%s requires %s') % (reqPo, ui_req)

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
        
        if (needname, needflags, needversion) in self.cheaterlookup:
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
            self._working_po = inst_po # store the last provider
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

        if needmode in ['ud']: # the thing it needs is being updated or obsoleted away 
            # try to update the requiring package in hopes that all this problem goes away :(
            self.verbose_logger.log(logginglevels.DEBUG_2, _('Trying to update %s to resolve dep'), requiringPo)
            # if the required pkg was updated, not obsoleted, then try to
            # only update the requiring po
            origobs = self.conf.obsoletes
            self.conf.obsoletes = 0
            txmbrs = self.update(po=requiringPo, requiringPo=requiringPo)
            self.conf.obsoletes = origobs
            if not txmbrs:
                txmbrs = self.update(po=requiringPo, requiringPo=requiringPo)
                if not txmbrs:
                    msg = self._err_missing_requires(requiringPo, requirement)
                    self.verbose_logger.log(logginglevels.DEBUG_2, _('No update paths found for %s. Failure!'), requiringPo)
                    return self._requiringFromTransaction(requiringPo, requirement, errorlist)
            checkdeps = 1

        if needmode in ['od']: # the thing it needs is being updated or obsoleted away 
            # try to update the requiring package in hopes that all this problem goes away :(
            self.verbose_logger.log(logginglevels.DEBUG_2, _('Trying to update %s to resolve dep'), requiringPo)
            txmbrs = self.update(po=requiringPo, requiringPo=requiringPo)
            if not txmbrs:
                msg = self._err_missing_requires(requiringPo, requirement)
                self.verbose_logger.log(logginglevels.DEBUG_2, _('No update paths found for %s. Failure!'), requiringPo)
                return self._requiringFromTransaction(requiringPo, requirement, errorlist)
            checkdeps = 1

            
        if needmode in ['e']:
            self.verbose_logger.log(logginglevels.DEBUG_2, _('TSINFO: %s package requiring %s marked as erase'),
                requiringPo, needname)
            txmbrs = self.remove(po=requiringPo)
            for txmbr in txmbrs:
                txmbr.setAsDep(po=inst_po)
            checkdeps = 1
        
        if needmode in ['i', 'u']:
            newupdates = self.update(name=name, epoch=epoch, version=ver, release=rel,
                                     requiringPo=requiringPo)
            txmbrs = self.tsInfo.getMembersWithState(requiringPo.pkgtup, TS_REMOVE_STATES)
            if newupdates and txmbrs:
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
                msg = self._err_missing_requires(requiringPo, requirement)
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
                tspkgs = self.tsInfo.matchNaevr(name=pkg.name)
                for tspkg in tspkgs:
                    if not canCoinstall(pkg.arch, tspkg.po.arch): # a comparable arch
                        if tspkg.po.verGT(pkg):
                            msg = _('Potential resolving package %s has newer instance in ts.') % pkg
                            self.verbose_logger.log(logginglevels.DEBUG_2, msg)
                            provSack.delPackage(pkg)
                            continue
                        elif tspkg.po.verLT(pkg):
                            upgraded.setdefault(pkg.pkgtup, []).append(tspkg.pkgtup)
                
                # from rpmdb
                dbpkgs = self.rpmdb.searchNevra(name=pkg.name)
                for dbpkg in dbpkgs:
                    if dbpkg.verGT(pkg) and not canCoinstall(pkg.arch, dbpkg.arch):
                        msg = _('Potential resolving package %s has newer instance installed.') % pkg
                        self.verbose_logger.log(logginglevels.DEBUG_2, msg)
                        provSack.delPackage(pkg)
                        continue

        if len(provSack) == 0: # unresolveable
            missingdep = 1
            msg = self._err_missing_requires(requiringPo, requirement)
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
                self._last_req = pkg
                return checkdeps, missingdep

        # find the best one 

        # try updating the already install pkgs
        results = []
        for pkg in provSack.returnNewestByName():
            tresults = self.update(requiringPo=requiringPo, name=pkg.name,
                                   epoch=pkg.epoch, version=pkg.version,
                                   rel=pkg.rel)
            #  Note that this does "interesting" things with multilib. We can
            # have say A.i686 and A.x86_64, and if we hit "A.i686" first,
            # .update() will actually update "A.x86_64" which will then fail
            # the pkg == txmbr.po test below, but then they'll be nothing to
            # update when we get around to A.x86_64 ... so this entire loop
            # fails.
            #  Keeping results through the loop and thus. testing each pkg
            # against all txmbr's from previous runs "fixes" this.
            results.extend(tresults)
            for txmbr in results:
                if pkg == txmbr.po:
                    checkdeps = True
                    self._last_req = pkg
                    return checkdeps, missingdep

        pkgs = provSack.returnPackages()
        if len(pkgs) == 1: # Minor opt.
            best = pkgs[0]
        else:
            #  Always do compare providers for multiple pkgs, it deals with
            # newest etc. ... so no need to do NewestNameArch() ... and it
            # stops compare_providers from being clever.
            pkgresults = self._compare_providers(pkgs, requiringPo)
            best = pkgresults[0][0]
        
        if self.rpmdb.contains(po=best): # is it already installed?
            missingdep = 1
            checkdeps = 0
            msg = self._err_missing_requires(requiringPo, requirement)
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
            checkdeps = True
            self._last_req = best
        else:
            self.verbose_logger.debug(_('TSINFO: Marking %s as install for %s'), best,
                requiringPo)
            reqtuple = misc.string_to_prco_tuple(needname + str(needflags) + needversion)
            txmbrs = self.install(best, provides_for=reqtuple)
            for txmbr in txmbrs:
                txmbr.setAsDep(po=requiringPo)
                txmbr.reason = "dep"
                self._last_req = txmbr.po

                # if we had other packages with this name.arch that we found
                # before, they're not going to be installed anymore, so we
                # should mark them to be re-checked
                if txmbr.pkgtup in upgraded:
                    map(self.tsInfo.remove, upgraded[txmbr.pkgtup])
            if not txmbrs:
                missingdep = 1
                checkdeps = 0
                msg = self._err_missing_requires(requiringPo, requirement)
                errorlist.append(msg)
            else:
                checkdeps = 1
        
        return checkdeps, missingdep

    def _dscb_procConflict(self, po, niceformatneed):
        """ Call the callback for processing requires, call the nicest one
            available. """
        if not self.dsCallback:
            return

        if hasattr(self.dsCallback, 'procConflictPo'):
            self.dsCallback.procConflictPo(po, niceformatneed)
        else:
            self.dsCallback.procConflict(po.name, niceformatneed)

    def _processConflict(self, po, conflict, conflicting_po):
        """processes a Conflict dep from the resolveDeps() method"""

        CheckDeps = True
        errormsgs = []

        needname, flags, needversion = conflict
        (name, arch, epoch, ver, rel) = po.pkgtup

        niceformatneed = rpmUtils.miscutils.formatRequire(needname, needversion, flags)
        self._dscb_procConflict(po, niceformatneed)

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

        msg = '%s conflicts with %s' % (name, str(conflicting_po))
        errormsgs.append(msg)
        self.verbose_logger.log(logginglevels.DEBUG_1, msg)
        CheckDeps = False
        # report the conflicting po, so skip-broken can remove it
        self.po_with_problems.add((po,conflicting_po,errormsgs[-1]))
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

    def resolveDeps(self, full_check=True, skipping_broken=False):

        if not len(self.tsInfo):
            return (0, [_('Success - empty transaction')])

        self.po_with_problems = set()
        self._working_po = None
        self._last_req = None
        self.tsInfo.resetResolved(hard=False)

        CheckDeps = True
        CheckRemoves = full_check
        CheckInstalls = full_check

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
            self._working_po = None # reset the working po
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
            self._working_po = None # reset the working po
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

        if self.dsCallback:
            if not self.conf.skip_broken:
                self.dsCallback.end()
            elif not skipping_broken and not errors:
                self.dsCallback.end()
        self.verbose_logger.log(logginglevels.DEBUG_1, _('Dependency Process ending'))

        self.tsInfo.changed = False
        if len(errors) > 0:
            errors = unique(errors)
            #  We immediately display this in cli, so don't show it twice.
            # Plus skip-broken can get here N times. Might be worth keeping
            # around for debugging?
            done = set() # Same as the unique above
            for po,wpo,err in self.po_with_problems:
                if (po,err) in done:
                    continue
                done.add((po, err))
                self.verbose_logger.log(logginglevels.DEBUG_4,
                    "SKIPBROKEN: %s from %s has depsolving problems" % (po, po.repoid))
                err = err.replace('\n', '\n  --> ')
                self.verbose_logger.log(logginglevels.DEBUG_4,"SKIPBROKEN:  --> %s" % err)
            return (1, errors)

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
                dscb_ts_state = txmbr.ts_state
                if txmbr.downgrades:
                    dscb_ts_state = 'd'
                if dscb_ts_state == 'u' and txmbr.reinstall:
                    dscb_ts_state = 'r'
                if dscb_ts_state == 'u':
                    if txmbr.output_state == TS_OBSOLETING:
                        dscb_ts_state = 'o'
                    elif not txmbr.updates:
                        dscb_ts_state = 'i'
                self.dsCallback.pkgAdded(txmbr.pkgtup, dscb_ts_state)
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
                if txmbr.downgraded_by: # Don't try to chain remove downgrades
                    msg = self._err_missing_requires(po, dep)
                    self.verbose_logger.log(logginglevels.DEBUG_2, msg)
                    errors.append(msg)
                    self.po_with_problems.add((po,self._working_po,errors[-1]))
                    missing_in_pkg = 1
                    continue

                (checkdep, missing, errormsgs) = self._processReq(po, dep)
                CheckDeps |= checkdep
                errors += errormsgs
                missing_in_pkg |= missing

            if not missing_in_pkg:
                self.tsInfo.markAsResolved(txmbr)

            any_missing |= missing_in_pkg

        return CheckDeps, CheckInstalls, CheckRemoves, any_missing

    @staticmethod
    def _sort_req_key(pkgtup):
        """ Get a sort key for a package requires from most "narrow" to least,
            this tries to ensure that if we have two reqs like
            "libfoo = 1.2.3-4" and "foo-api" (which is also provided by
            libxyz-foo) that we'll get just libfoo.
            There are other similar cases this "handles"."""

        mapper = {'EQ' : 1, 'LT' : 2, 'LE' : 3, 'GT' : 4, 'GE' : 5, None : 99}
        flagscore = mapper.get(pkgtup[1], 10)

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

        namescore = 0
        if pkgtup[0].startswith("lib") and \
                (pkgtup[0].endswith("()") or pkgtup[0].endswith("()(64bit)")):
            namescore = 99 # Processes these last

        return (flagscore, namescore)

    def _checkInstall(self, txmbr):
        txmbr_reqs = txmbr.po.returnPrco('requires')

        # if this is an update, we should check what the old
        # requires were to make things faster
        oldreqs = []
        for oldpo in txmbr.updates:
            oldreqs.extend(oldpo.returnPrco('requires'))
        oldreqs = set(oldreqs)

        ret = []
        for req in sorted(txmbr_reqs, key=self._sort_req_key):
            if req[0].startswith('rpmlib('):
                continue
            if req in oldreqs:
                continue
            
            self.verbose_logger.log(logginglevels.DEBUG_2, _("looking for %s as a requirement of %s"), req, txmbr)
            provs = self.tsInfo.getProvides(*req)
            #  The self provides should mostly be caught before here now, but
            # at least config() crack still turns up, it's not that
            # expensive to just do it, and we really don't want "false positive"
            # requires for compare_providers().
            if not provs and not txmbr.po.inPrcoRange('provides', req):
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
        for newpo in txmbr.updated_by + txmbr.obsoleted_by:
            for p in newpo.provides:
                newpoprovs[p] = 1
        ret = []
        
        # iterate over the provides of the package being removed
        # and see what's actually going away
        for prov in provs:
            if prov[0].startswith('rpmlib('): # ignore rpmlib() provides
                continue
            if prov in newpoprovs:
                continue
            # FIXME: This is probably the best place to fix the postfix rename
            # problem long term (post .21) ... see compare_providers.
            for pkg, hits in self.tsInfo.getRequires(*prov).iteritems():
                # See the docs, this is to make groupremove "more useful".
                if (self.conf.groupremove_leaf_only and txmbr.groups and
                    txmbr.output_state == TS_ERASE):
                    cb = self.dsCallback
                    if cb and hasattr(cb, 'groupRemoveReq'):
                        cb.groupRemoveReq(pkg, hits)
                    #  We don't undo anything else here ... hopefully that's
                    # fine.
                    self.tsInfo.remove(txmbr.pkgtup)
                    return []

                for hit in hits:
                    # See if the update solves the problem...
                    found = False
                    for newpo in txmbr.updated_by:
                        if newpo.checkPrco('provides', hit):
                            found = True
                            break
                    if found: continue
                    for newpo in txmbr.obsoleted_by:
                        if newpo.checkPrco('provides', hit):
                            found = True
                            break
                    if found: continue

                    # It doesn't, so see what else might...
                    rn, rf, rv = hit
                    if not self.tsInfo.getProvides(rn, rf, rv):
                        ret.append( (pkg, self._prco_req_nfv2req(rn, rf, rv)) )
        return ret

    def _checkFileRequires(self):
        fileRequires = set()
        nfileRequires = set() # These need to be looked up in the rpmdb.
        reverselookup = {}
        ret = []

        # generate list of file requirement in rpmdb
        if self.installedFileRequires is None:
            self.installedFileRequires, \
              self.installedUnresolvedFileRequires, \
              self.installedFileProviders = self.rpmdb.fileRequiresData()

        # get file requirements from packages not deleted
        todel = []
        for pkgtup, files in self.installedFileRequires.iteritems():
            if self._tsInfo.getMembersWithState(pkgtup, output_states=TS_REMOVE_STATES):
                todel.append(pkgtup)
            else:
                fileRequires.update(files)
                for filename in files:
                    reverselookup.setdefault(filename, []).append(pkgtup)
        for pkgtup in todel:
            del self.installedFileRequires[pkgtup]

        fileRequires -= self.installedUnresolvedFileRequires

        # get file requirements from new packages
        for txmbr in self._tsInfo.getMembersWithState(output_states=TS_INSTALL_STATES):
            for name, flag, evr in txmbr.po.requires:
                if name.startswith('/'):
                    pt = txmbr.po.pkgtup
                    self.installedFileRequires.setdefault(pt, []).append(name)
                    # check if file requires was already unresolved in update
                    if name in self.installedUnresolvedFileRequires:
                        already_broken = False
                        for oldpo in txmbr.updates:
                            if oldpo.checkPrco('requires', (name, None, (None, None, None))):
                                already_broken = True
                                break
                        if already_broken:
                            continue
                    if name not in fileRequires:
                        nfileRequires.add(name)
                    fileRequires.add(name)
                    reverselookup.setdefault(name, []).append(txmbr.po.pkgtup)

        todel = []
        for fname in self.installedFileProviders:
            niFP_fname = []
            for pkgtup in self.installedFileProviders[fname]:
                if self._tsInfo.getMembersWithState(pkgtup, output_states=TS_REMOVE_STATES):
                    continue
                niFP_fname.append(pkgtup)

            if not niFP_fname:
                todel.append(fname)
                continue

            self.installedFileProviders[fname] = niFP_fname
        for fname in todel:
            del self.installedFileProviders[fname]

        # check the file requires
        iFP = self.installedFileProviders
        for filename in fileRequires:
            # In theory we need this to be:
            #
            # nprov, filename in iFP (or new), oprov
            #
            # ...this keeps the cache exactly the same as the non-cached data.
            # However that also means that we'll always need the filelists, so
            # we do:
            #
            # filename in iFP (if found return), oprov (if found return),
            # nprov
            #
            # ...this means we'll always get the same _result_ (as we only need
            # to know if _something_ provides), but our cache will be off on
            # what does/doesn't provide the file.
            if filename in self.installedFileProviders:
                continue

            oprov = self.tsInfo.getOldProvides(filename)
            if oprov:
                iFP.setdefault(filename, []).extend([po.pkgtup for po in oprov])
                continue

            nprov = self.tsInfo.getNewProvides(filename)
            if nprov:
                iFP.setdefault(filename, []).extend([po.pkgtup for po in nprov])
                continue 

            for pkgtup in reverselookup[filename]:
                po = self.tsInfo.getMembersWithState(pkgtup, TS_INSTALL_STATES)
                if po:
                    po = po[0].po # Should only have one
                else:
                    po = self.getInstalledPackageObject(pkgtup)
                ret.append( (po, (filename, 0, '')) )

        self.rpmdb.transactionCacheFileRequires(self.installedFileRequires, 
                                        self.installedUnresolvedFileRequires,
                                        self.installedFileProviders,
                                        ret)

        return ret

    def _checkConflicts(self):
        ret = [ ]
        cpkgs = []
        for po in self.rpmdb.returnConflictPackages():
            if self.tsInfo.getMembersWithState(po.pkgtup, output_states=TS_REMOVE_STATES):
                continue
            conflicts = po.returnPrco('conflicts')
            if not conflicts: # We broke this due to dbMatch() usage.
                continue
            cpkgs.append(po)
            for conflict in conflicts:
                (r, f, v) = conflict
                for conflicting_po in self.tsInfo.getNewProvides(r, f, v):
                    if conflicting_po.pkgtup[0] == po.pkgtup[0] and conflicting_po.pkgtup[2:] == po.pkgtup[2:]:
                        continue
                    ret.append( (po, self._prco_req_nfv2req(r, f, v),
                                 conflicting_po) )
        for txmbr in self.tsInfo.getMembersWithState(output_states=TS_INSTALL_STATES):
            po = txmbr.po
            done = False
            for conflict in txmbr.po.returnPrco('conflicts'):
                if not done:
                    cpkgs.append(txmbr.po)
                    done = True
                (r, f, v) = conflict
                for conflicting_po in self.tsInfo.getProvides(r, f, v):
                    if conflicting_po.pkgtup[0] == po.pkgtup[0] and conflicting_po.pkgtup[2:] == po.pkgtup[2:]:
                        continue
                    ret.append( (po, self._prco_req_nfv2req(r, f, v),
                                 conflicting_po) )

        if _rpm_ver_atleast((4, 9, 0)):
            return ret # Don't need the conflicts cache anymore

        self.rpmdb.transactionCacheConflictPackages(cpkgs)
        return ret

    def isPackageInstalled(self, pkgname):
        lst = self.tsInfo.matchNaevr(name = pkgname)
        for txmbr in lst:
            if txmbr.output_state in TS_INSTALL_STATES:
                return True

        if len(lst) > 0:
            # if we get here then it's in the tsInfo for an erase or obsoleted
            #  --> not going to be installed
            return False

        if not self.rpmdb.contains(name=pkgname):
            return False

        return True
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
            if self.arch.multilib: # only go to the next one if we're multilib - 
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

        #  Actual start of _compare_providers().

        # Do a NameArch filtering, based on repo. __cmp__
        unique_nevra_pkgs = {}
        for pkg in pkgs:
            if (pkg.pkgtup in unique_nevra_pkgs and
                unique_nevra_pkgs[pkg.pkgtup].repo <= pkg.repo):
                continue
            unique_nevra_pkgs[pkg.pkgtup] = pkg
        pkgs = unique_nevra_pkgs.values()
            
        pkgresults = {}

        for pkg in pkgs:
            pkgresults[pkg] = 0
        
        # hand this off to our plugins
        self.plugins.run("compare_providers", providers_dict=pkgresults, 
                                      reqpo=reqpo)
        
        for pkg in pkgresults.keys():
            rpmdbpkgs = self.rpmdb.searchNevra(name=pkg.name)
            if rpmdbpkgs:
                #  We only want to count things as "installed" if they are
                # older than what we are comparing, because this then an update
                # so we give preference. If they are newer then obsoletes/etc.
                # could play a part ... this probably needs a better fix.
                newest = sorted(rpmdbpkgs)[-1]
                if newest.verLT(pkg):
                    # give pkgs which are updates just a SLIGHT edge
                    # we should also make sure that any pkg
                    # we are giving an edge to is not obsoleted by
                    # something else in the transaction. :(
                    # there are many ways I hate this - this is but one
                    pkgresults[pkg] += 5
                elif newest.verEQ(pkg):
                    #  We get here from bestPackagesFromList(), give a giant
                    # bump to stuff that is already installed.
                    pkgresults[pkg] += 1000
                elif newest.verGT(pkg):
                    # if the version we're looking at is older than what we have installed
                    # score it down like we would an obsoleted pkg
                    pkgresults[pkg] -= 1024
            else:
                # just b/c they're not installed pkgs doesn't mean they should
                # be ignored entirely. Just not preferred
                pass

        pkgs = pkgresults.keys()
            
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
        
        
        lpos = {}
        for po in pkgs:
            for nextpo in pkgs:
                if po == nextpo:
                    continue

                #  If this package isn't the latest version of said package,
                # treat it like it's obsoleted. The problem here is X-1
                # accidentally provides FOO, so you release X-2 without the
                # provide, but X-1 is still picked over a real provider.
                if po.name not in lpos:
                    lpos[po.name] = self.pkgSack.returnNewestByName(po.name)[:1]
                if not lpos[po.name] or not po.verEQ(lpos[po.name][0]):
                    pkgresults[po] -= 1024

                obsoleted = False
                if po.obsoletedBy([nextpo]):
                    obsoleted = True
                    pkgresults[po] -= 1024
                                
                    self.verbose_logger.log(logginglevels.DEBUG_4,
                        _("%s obsoletes %s") % (nextpo, po))

                if reqpo:
                    arches = (reqpo.arch, self.arch.bestarch)
                else:
                    arches = (self.arch.bestarch,)
                
                for thisarch in arches:
                    res = _compare_arch_distance(po, nextpo, thisarch)
                    if not res:
                        continue
                    self.verbose_logger.log(logginglevels.DEBUG_4,                   
                       _('archdist compared %s to %s on %s\n  Winner: %s' % (po, nextpo, thisarch, res)))

                    if res == po:
                        pkgresults[po] += 5

            # End of O(N*N): for nextpo in pkgs:
            if _common_sourcerpm(po, reqpo):
                self.verbose_logger.log(logginglevels.DEBUG_4,
                    _('common sourcerpm %s and %s' % (po, reqpo)))
                pkgresults[po] += 20
            if self.isPackageInstalled(po.base_package_name):
                self.verbose_logger.log(logginglevels.DEBUG_4,
                    _('base package %s is installed for %s' % (po.base_package_name, po)))
                pkgresults[po] += 5 # Same as before - - but off of base package name
            if reqpo:
                cpl = _common_prefix_len(po.name, reqpo.name)
                if cpl > 2:
                    self.verbose_logger.log(logginglevels.DEBUG_4,
                        _('common prefix of %s between %s and %s' % (cpl, po, reqpo)))
                
                    pkgresults[po] += cpl*2
                
        #  If we have more than one "best", see what would happen if we picked
        # each package ... ie. what things do they require that _aren't_ already
        # installed/to-be-installed. In theory this can screw up due to:
        #   pkgA => requires pkgX
        #   pkgB => requires pkgY, requires pkgZ
        # ...but pkgX requires 666 other things. Going recursive is
        # "non-trivial" though, python != prolog. This seems to do "better"
        # from simple testing though.
        bestnum = max(pkgresults.values())
        rec_depsolve = {}
        for po in pkgs:
            if pkgresults[po] != bestnum:
                continue
            rec_depsolve[po] = 0
        if len(rec_depsolve) > 1:
            for po in rec_depsolve:
                fake_txmbr = TransactionMember(po)

                #  Note that this is just requirements, so you could also have
                # 4 requires for a single package. This might be fixable, if
                # needed, but given the above it's probably better to leave it
                # like this.
                reqs = self._checkInstall(fake_txmbr)
                rec_depsolve[po] = len(reqs)

            bestnum = min(rec_depsolve.values())
            self.verbose_logger.log(logginglevels.DEBUG_4,
                                    _('requires minimal: %d') % bestnum)
            for po in rec_depsolve:
                if rec_depsolve[po] == bestnum:
                    self.verbose_logger.log(logginglevels.DEBUG_4,
                            _(' Winner: %s') % po)
                    pkgresults[po] += 1
                else:
                    num = rec_depsolve[po]
                    self.verbose_logger.log(logginglevels.DEBUG_4,
                            _(' Loser(with %d): %s') % (num, po))

        #  We don't want to decide to use a "shortest first", if something else
        # has told us to pick something else. But we want to pick between
        # multiple "best" packages. So we spike all the best packages (so
        # only those can win) and then bump them down by package name length.
        bestnum = max(pkgresults.values())
        for po in pkgs:
            if pkgresults[po] != bestnum:
                continue
            pkgresults[po] += 1000
            pkgresults[po] += (len(po.name)*-1)

        bestorder = sorted(pkgresults.items(),
                           key=lambda x: (x[1], x[0]), reverse=True)
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
