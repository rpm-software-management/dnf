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

import os.path
import re
import types
import logging

import rpmUtils.transaction
import rpmUtils.miscutils
import rpmUtils.arch
from misc import unique, version_tuple_to_string
import rpm

from packageSack import ListPackageSack
from constants import *
import packages
import logginglevels
import time 
import Errors

import warnings
warnings.simplefilter("ignore", Errors.YumFutureDeprecationWarning)

class Depsolve(object):
    def __init__(self):
        packages.base = self
        self._ts = None
        self._tsInfo = None
        self.dsCallback = None
        self.logger = logging.getLogger("yum.Depsolve")
        self.verbose_logger = logging.getLogger("yum.verbose.Depsolve")
    
    def doTsSetup(self):
        warnings.warn('doTsSetup() will go away in a future version of Yum.\n',
                Errors.YumFutureDeprecationWarning, stacklevel=2)
        return self._getTs()
        
    def _getTs(self):
        """setup all the transaction set storage items we'll need
           This can't happen in __init__ b/c we don't know our installroot
           yet"""
        
        if self._tsInfo != None and self._ts != None:
            return
            
        if not self.conf.installroot:
            raise Errors.YumBaseError, 'Setting up TransactionSets before config class is up'
        
        self._tsInfo = self._transactionDataFactory()
        self.initActionTs()
    
    def _getTsInfo(self):
        if not self._tsInfo:
            self._tsInfo = self._transactionDataFactory()

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
                            'repackage': rpm.RPMTRANS_FLAG_REPACKAGE}
        
        self._ts.setFlags(0) # reset everything.
        
        for flag in self.conf.tsflags:
            if ts_flags_to_rpm.has_key(flag):
                self._ts.addTsFlag(ts_flags_to_rpm[flag])
            else:
                self.logger.critical('Invalid tsflag in config file: %s', flag)

        probfilter = 0
        for flag in self.tsInfo.probFilterFlags:
            probfilter |= flag
        self._ts.setProbFilter(probfilter)

    def whatProvides(self, name, flags, version):
        """searches the packageSacks for what provides the arguments
           returns a ListPackageSack of providing packages, possibly empty"""

        self.verbose_logger.log(logginglevels.DEBUG_1, 'Searching pkgSack for dep: %s',
            name)
        # we need to check the name - if it doesn't match:
        # /etc/* bin/* or /usr/lib/sendmail then we should fetch the 
        # filelists.xml for all repos to make the searchProvides more complete.
        if name[0] == '/':
            matched = 0
            globs = ['.*bin\/.*', '^\/etc\/.*', '^\/usr\/lib\/sendmail$']
            for glob in globs:
                globc = re.compile(glob)
                if globc.match(name):
                    matched = 1
            if not matched:
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
                'Potential match for %s from %s', name, po)
            if name[0] == '/' and r_v is None:
                # file dep add all matches to the defSack
                defSack.addPackage(po)
                continue

            if po.checkPrco('provides', (name, flags, (r_e, r_v, r_r))):
                defSack.addPackage(po)
                self.verbose_logger.debug('Matched %s to require for %s', po, name)
        
        return defSack
        
    def allowedMultipleInstalls(self, po):
        """takes a packageObject, returns 1 or 0 depending on if the package 
           should/can be installed multiple times with different vers
           like kernels and kernel modules, for example"""
           
        if po.name in self.conf.installonlypkgs:
            return 1
        
        provides = po.provides_names
        if filter (lambda prov: prov in self.conf.installonlypkgs, provides):
            return 1
        
        return 0

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
            self.verbose_logger.log(logginglevels.DEBUG_3, 'Member: %s', txmbr)
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
                            '%s converted to install', txmbr.po)
                        txmbr.ts_state = 'i'
                        txmbr.output_state = TS_INSTALL

                
                self.ts.addInstall(hdr, (hdr, rpmfile), txmbr.ts_state)
                self.verbose_logger.log(logginglevels.DEBUG_1,
                    'Adding Package %s in mode %s', txmbr.po, txmbr.ts_state)
                if self.dsCallback: 
                    self.dsCallback.pkgAdded(txmbr.pkgtup, txmbr.ts_state)
            
            elif txmbr.ts_state in ['e']:
                if ts_elem.has_key((txmbr.pkgtup, txmbr.ts_state)):
                    continue
                self.ts.addErase(txmbr.po.idx)
                if self.dsCallback: self.dsCallback.pkgAdded(txmbr.pkgtup, 'e')
                self.verbose_logger.log(logginglevels.DEBUG_1,
                    'Removing Package %s', txmbr.po)
        

    def resolveDeps(self):

        CheckDeps = 1
        conflicts = 0
        missingdep = 0
        depscopy = []
        unresolveableloop = 0

        errors = []
        if self.dsCallback: self.dsCallback.start()

        while CheckDeps > 0:
            self.cheaterlookup = {} # short cache for some information we'd resolve
                                    # (needname, needversion) = pkgtup
            self.populateTs(test=1)
            if self.dsCallback: self.dsCallback.tscheck()
            deps = self.ts.check()

            
            if not deps:
                self.tsInfo.changed = False
                return (2, ['Success - deps resolved'])

            deps = unique(deps) # get rid of duplicate deps            
            if deps == depscopy:
                unresolveableloop += 1
                self.verbose_logger.log(logginglevels.DEBUG_2,
                    'Identical Loop count = %d', unresolveableloop)
                if unresolveableloop >= 2:
                    errors.append('Unable to satisfy dependencies')
                    for deptuple in deps:
                        ((name, version, release), (needname, needversion), flags, 
                          suggest, sense) = deptuple
                        if sense == rpm.RPMDEP_SENSE_REQUIRES:
                            msg = 'Package %s needs %s, this is not available.' % \
                                  (name, rpmUtils.miscutils.formatRequire(needname, 
                                                                          needversion, flags))
                        elif sense == rpm.RPMDEP_SENSE_CONFLICTS:
                            msg = 'Package %s conflicts with %s.' % \
                                  (name, rpmUtils.miscutils.formatRequire(needname, 
                                                                          needversion, flags))

                        errors.append(msg)
                    CheckDeps = 0
                    break
            else:
                unresolveableloop = 0

            depscopy = deps
            CheckDeps = 0


            # things to resolve
            self.verbose_logger.debug('# of Deps = %d', len(deps))
            depcount = 0
            for dep in deps:
                dep_start_time = time.time()
                ((name, version, release), (needname, needversion), flags, suggest, sense) = dep
                depcount += 1
                self.verbose_logger.log(logginglevels.DEBUG_2,
                    '\nDep Number: %d/%d\n', depcount, len(deps))
                if sense == rpm.RPMDEP_SENSE_REQUIRES: # requires
                    # if our packageSacks aren't here, then set them up
                    (checkdep, missing, conflict, errormsgs) = self._processReq(dep)
                    
                elif sense == rpm.RPMDEP_SENSE_CONFLICTS: # conflicts - this is gonna be short :)
                    (checkdep, missing, conflict, errormsgs) = self._processConflict(dep)
                    
                else: # wtf?
                    self.logger.critical('Unknown Sense: %d', sense)
                    continue
                
                dep_end_time = time.time()
                dep_proc_time = dep_end_time - dep_start_time
                self.verbose_logger.log(logginglevels.DEBUG_2, 'processing dep took: %f', dep_proc_time)
                
                missingdep += missing
                conflicts += conflict
                CheckDeps += checkdep
                for error in errormsgs:
                    if error not in errors:
                        errors.append(error)

            self.verbose_logger.log(logginglevels.DEBUG_1, 'miss = %d', missingdep)
            self.verbose_logger.log(logginglevels.DEBUG_1, 'conf = %d', conflicts)
            self.verbose_logger.log(logginglevels.DEBUG_1, 'CheckDeps = %d', CheckDeps)

            if CheckDeps > 0:
                if self.dsCallback: self.dsCallback.restartLoop()
                self.verbose_logger.log(logginglevels.DEBUG_1, 'Restarting Loop')
            else:
                if self.dsCallback: self.dsCallback.end()
                self.verbose_logger.log(logginglevels.DEBUG_1, 'Dependency Process ending')

            del deps

        self.tsInfo.changed = False
        if len(errors) > 0:
            return (1, errors)
        if len(self.tsInfo) > 0:
            return (2, ['Run Callback'])

    def _processReq(self, dep):
        """processes a Requires dep from the resolveDeps functions, returns a tuple
           of (CheckDeps, missingdep, conflicts, errors) the last item is an array
           of error messages"""
        
        CheckDeps = 0
        missingdep = 0
        conflicts = 0
        errormsgs = []
        
        ((name, version, release), (needname, needversion), flags, suggest, sense) = dep
        
        niceformatneed = rpmUtils.miscutils.formatRequire(needname, needversion, flags)
        self.verbose_logger.log(logginglevels.DEBUG_1, '%s requires: %s', name,
            niceformatneed)
        
        if self.dsCallback: self.dsCallback.procReq(name, niceformatneed)
        
        # is the requiring tuple (name, version, release) from an installed package?
        pkgs = []
        dumbmatchpkgs = self.rpmdb.searchNevra(name=name, ver=version, rel=release)
        for po in dumbmatchpkgs:
            if self.tsInfo.exists(po.pkgtup):
                self.verbose_logger.log(logginglevels.DEBUG_4,
                    'Skipping package already in Transaction Set: %s', po)
                continue
            
            # slightly more consistency (most of the time)
            prco_flags = rpmUtils.miscutils.flagToString(flags)
            prco_ver = rpmUtils.miscutils.stringToVersion(needversion)
            prcoformat_need = (needname, prco_flags, prco_ver)
            self.verbose_logger.log(logginglevels.DEBUG_2,
                    'Looking for %s as a requirement of %s',
                    str(prcoformat_need), po)

            if po.checkPrco('requires', (needname, prco_flags, prco_ver)):
                pkgs.append(po)

        if len(pkgs) < 1: # requiring tuple is not in the rpmdb
            txmbrs = self.tsInfo.matchNaevr(name=name, ver=version, rel=release)
            if len(txmbrs) < 1:
                self.verbose_logger.log(logginglevels.DEBUG_1,
                        'Requiring package %s-%s-%s not in transaction set'\
                        ' nor in rpmdb', name, version, release)
                errormsgs.append(msg)
                missingdep = 1
                CheckDeps = 0

            else:
                txmbr = txmbrs[0]
                self.verbose_logger.log(logginglevels.DEBUG_1,
                    'Requiring package is from transaction set')
                if txmbr.ts_state == 'e':
                    self.verbose_logger.log(logginglevels.DEBUG_2,
                            'Requiring package %s is set to be erased, ' \
                            'probably processing an old dep, restarting ' \
                            'loop early.', txmbr.name)
                    CheckDeps=1
                    missingdep=0
                    return (CheckDeps, missingdep, conflicts, errormsgs)
                    
                else:
                    self.verbose_logger.log(logginglevels.DEBUG_1, 'Resolving for requiring package: %s-%s-%s in state %s',
                        name, version, release, txmbr.ts_state)
                    self.verbose_logger.log(logginglevels.DEBUG_1, 'Resolving for requirement: %s',
                        rpmUtils.miscutils.formatRequire(needname, needversion, flags))
                    requirementTuple = (needname, flags, needversion)
                    # should we figure out which is pkg it is from the tsInfo?
                    requiringPkg = (name, version, release, txmbr.ts_state) 
                    CheckDeps, missingdep = self._requiringFromTransaction(requiringPkg, requirementTuple, errormsgs)
            
        if len(pkgs) > 0:  # requring tuple is in the rpmdb
            if len(pkgs) > 1:
                self.verbose_logger.log(logginglevels.DEBUG_2,
                    'Multiple Packages match. %s-%s-%s', name, version, release)
                for po in pkgs:
                    # if one of them is (name, arch) already in the tsInfo somewhere, 
                    # pop it out of the list
                    (n,a,e,v,r) = po.pkgtup
                    thismode = self.tsInfo.getMode(name=n, arch=a)
                    if thismode is not None:
                        self.verbose_logger.log(logginglevels.DEBUG_2,
                            '   %s already in ts %s, skipping', po, thismode)
                        pkgs.remove(po)
                        continue
                    else:
                        self.verbose_logger.log(logginglevels.DEBUG_2, '   %s',
                                po)
                    
            if len(pkgs) == 1:
                po = pkgs[0]
                self.verbose_logger.log(logginglevels.DEBUG_2,
                    'Requiring package is installed: %s', po)
            
            if len(pkgs) > 0:
                requiringPkg = pkgs[0] # take the first one, deal with the others (if there is one)
                                   # on another dep.
            else:
                self.logger.error('All pkgs in depset are also in tsInfo, this is wrong and bad')
                CheckDeps = 1
                return (CheckDeps, missingdep, conflicts, errormsgs)
            
            self.verbose_logger.log(logginglevels.DEBUG_1,
                'Resolving for installed requiring package: %s', requiringPkg)
            self.verbose_logger.log(logginglevels.DEBUG_1,
                'Resolving for requirement: %s', 
                rpmUtils.miscutils.formatRequire(needname, needversion, flags))
            
            requirementTuple = (needname, flags, needversion)

            CheckDeps, missingdep = self._requiringFromInstalled(requiringPkg,
                                                    requirementTuple, errormsgs)


        return (CheckDeps, missingdep, conflicts, errormsgs)


    def _requiringFromInstalled(self, requiringPo, requirement, errorlist):
        """processes the dependency resolution for a dep where the requiring 
           package is installed"""

        (name, arch, epoch, ver, rel) = requiringPo.pkgtup
        
        (needname, needflags, needversion) = requirement
        niceformatneed = rpmUtils.miscutils.formatRequire(needname, needversion, needflags)
        checkdeps = 0
        missingdep = 0
        
        # we must first find out why the requirement is no longer there
        # we must find out what provides/provided it from the rpmdb (if anything)
        # then check to see if that thing is being acted upon by the transaction set
        # if it is then we need to find out what is being done to it and act accordingly
        needmode = None # mode in the transaction of the needed pkg (if any)
        needpo = None
        providers = []
        
        if self.cheaterlookup.has_key((needname, needflags, needversion)):
            self.verbose_logger.log(logginglevels.DEBUG_2, 'Needed Require has already been looked up, cheating')
            cheater_tup = self.cheaterlookup[(needname, needflags, needversion)]
            providers = [cheater_tup]
        
        elif self.rpmdb.installed(name=needname):
            txmbrs = self.tsInfo.matchNaevr(name=needname)
            for txmbr in txmbrs:
                providers.append(txmbr.pkgtup)

        else:
            self.verbose_logger.log(logginglevels.DEBUG_2, 'Needed Require is not a package name. Looking up: %s', niceformatneed)
            providers = self.rpmdb.whatProvides(needname, needflags, needversion)
            
        for insttuple in providers:
            inst_str = '%s.%s %s:%s-%s' % insttuple
            (i_n, i_a, i_e, i_v, i_r) = insttuple
            self.verbose_logger.log(logginglevels.DEBUG_2,
                'Potential Provider: %s', inst_str)
            thismode = self.tsInfo.getMode(name=i_n, arch=i_a, 
                            epoch=i_e, ver=i_v, rel=i_r)
                        
            if thismode is None and i_n in self.conf.exactarchlist:
                # check for mode by the same name+arch
                thismode = self.tsInfo.getMode(name=i_n, arch=i_a)
            
            if thismode is None and i_n not in self.conf.exactarchlist:
                # check for mode by just the name
                thismode = self.tsInfo.getMode(name=i_n)
            
            if thismode is not None:
                needmode = thismode
                if self.rpmdb.installed(name=i_n, arch=i_a, ver=i_v, 
                                        epoch=i_e, rel=i_r):
                    needpo = self.rpmdb.searchPkgTuple(insttuple)[0]
                else:
                    needpo = self.getPackageObject(insttuple)

                self.cheaterlookup[(needname, needflags, needversion)] = insttuple
                self.verbose_logger.log(logginglevels.DEBUG_2, 'Mode is %s for provider of %s: %s',
                    needmode, niceformatneed, inst_str)
                break
                    
        self.verbose_logger.log(logginglevels.DEBUG_2, 'Mode for pkg providing %s: %s', 
            niceformatneed, needmode)
        
        if needmode in ['e']:
            self.verbose_logger.log(logginglevels.DEBUG_2, 'TSINFO: %s package requiring %s marked as erase',
                requiringPo, needname)
            txmbr = self.tsInfo.addErase(requiringPo)
            txmbr.setAsDep(po=needpo)
            checkdeps = 1
        
        if needmode in ['i', 'u']:
            obslist = []
            # check obsoletes first
            if self.conf.obsoletes:
                if self.up.obsoleted_dict.has_key(requiringPo.pkgtup):
                    obslist = self.up.obsoleted_dict[requiringPo.pkgtup]
                    self.verbose_logger.log(logginglevels.DEBUG_1,
                        'Looking for Obsoletes for %s', requiringPo)
                
            if len(obslist) > 0:
                po = None
                for pkgtup in obslist:
                    po = self.getPackageObject(pkgtup)
                if po:
                    for (new, old) in self.up.getObsoletesTuples(): # FIXME query the obsoleting_list now?
                        if po.pkgtup == new:
                            txmbr = self.tsInfo.addObsoleting(po, requiringPo)
                            self.tsInfo.addObsoleted(requiringPo, po)
                            txmbr.setAsDep(po=needpo)
                            self.verbose_logger.log(logginglevels.DEBUG_2, 'TSINFO: Obsoleting %s with %s to resolve dep.', 
                                requiringPo, po)
                            checkdeps = 1
                            return checkdeps, missingdep 
                
            
            # check updates second
            uplist = []                
            uplist = self.up.getUpdatesList(name=name)
            # if there's an update for the reqpkg, then update it
            
            po = None
            if len(uplist) > 0:
                if name not in self.conf.exactarchlist:
                    pkgs = self.pkgSack.returnNewestByName(name)
                    archs = {}
                    for pkg in pkgs:
                        (n,a,e,v,r) = pkg.pkgtup
                        archs[a] = pkg
                    a = rpmUtils.arch.getBestArchFromList(archs.keys())
                    po = archs[a]
                else:
                    po = self.pkgSack.returnNewestByNameArch((name,arch))[0]
                if po.pkgtup not in uplist:
                    po = None

            if po:
                for (new, old) in self.up.getUpdatesTuples():
                    if po.pkgtup == new:
                        txmbr = self.tsInfo.addUpdate(po, requiringPo)
                        txmbr.setAsDep(po=needpo)
                        self.verbose_logger.log(logginglevels.DEBUG_2, 'TSINFO: Updating %s to resolve dep.', po)
                checkdeps = 1
                
            else: # if there's no update then pass this over to requringFromTransaction()
                self.verbose_logger.log(logginglevels.DEBUG_2, 'Cannot find an update path for dep for: %s', niceformatneed)
                
                reqpkg = (name, ver, rel, None)
                return self._requiringFromTransaction(reqpkg, requirement, errorlist)
            

        if needmode is None:
            reqpkg = (name, ver, rel, None)
            if self.pkgSack is None:
                return self._requiringFromTransaction(reqpkg, requirement, errorlist)
            else:
                self.verbose_logger.log(logginglevels.DEBUG_2, 'Unresolveable requirement %s for %s',
                    niceformatneed, reqpkg[0])
                checkdeps = 0
                missingdep = 1


        return checkdeps, missingdep
        

    def _requiringFromTransaction(self, requiringPkg, requirement, errorlist):
        """processes the dependency resolution for a dep where requiring 
           package is in the transaction set"""
        
        (name, version, release, tsState) = requiringPkg
        (needname, needflags, needversion) = requirement
        checkdeps = 0
        missingdep = 0
        
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

        provSack = self.whatProvides(needname, needflags, needversion)

        # get rid of things that are already in the rpmdb - b/c it's pointless to use them here

        for pkg in provSack.returnPackages():
            if pkg.pkgtup in self.rpmdb.simplePkgList(): # is it already installed?
                self.verbose_logger.log(logginglevels.DEBUG_2, '%s is in providing packages but it is already installed, removing.', pkg)
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
                    if tspkg.po.EVR > pkg.EVR:
                        msg = 'Potential resolving package %s has newer instance in ts.' % pkg
                        self.verbose_logger.log(logginglevels.DEBUG_2, msg)
                        provSack.delPackage(pkg)
                        continue
                
                # from rpmdb
                dbpkgs = self.rpmdb.searchNevra(name=pkg.name, arch=pkg.arch)
                for dbpkg in dbpkgs:
                    if dbpkg.EVR > pkg.EVR:
                        msg = 'Potential resolving package %s has newer instance installed.' % pkg
                        self.verbose_logger.log(logginglevels.DEBUG_2, msg)
                        provSack.delPackage(pkg)
                        continue

        if len(provSack) == 0: # unresolveable
            missingdep = 1
            msg = 'Missing Dependency: %s is needed by package %s' % \
            (rpmUtils.miscutils.formatRequire(needname, needversion, needflags),
                                                                   name)
            errorlist.append(msg)
            return checkdeps, missingdep
        
        # iterate the provSack briefly, if we find the package is already in the 
        # tsInfo then just skip this run
        for pkg in provSack.returnPackages():
            (n,a,e,v,r) = pkg.pkgtup
            pkgmode = self.tsInfo.getMode(name=n, arch=a, epoch=e, ver=v, rel=r)
            if pkgmode in ['i', 'u']:
                self.verbose_logger.log(logginglevels.DEBUG_2,
                    '%s already in ts, skipping this one', n)
                checkdeps = 1
                return checkdeps, missingdep
        

        # find the best one 
        newest = provSack.returnNewestByNameArch()
        if len(newest) > 1: # there's no way this can be zero
            best = newest[0]
            for po in newest[1:]:
                if len(po.name) < len(best.name):
                    best = po
                elif len(po.name) == len(best.name):
                    # compare arch
                    arch = rpmUtils.arch.getBestArchFromList([po.arch, best.arch])
                    if arch == po.arch:
                        best = po
        elif len(newest) == 1:
            best = newest[0]
        
        if self.rpmdb.installed(po=best): # is it already installed?
            missingdep = 1
            checkdeps = 0
            msg = 'Missing Dependency: %s is needed by package %s' % (needname, name)
            errorlist.append(msg)
            return checkdeps, missingdep
        
                
            
        # FIXME - why can't we look up in the transaction set for the requiringPkg
        # and know what needs it that way and provide a more sensible dep structure in the txmbr
        inst = self.rpmdb.searchNevra(name=best.name, arch=best.arch)
        if len(inst) > 0: 
            self.verbose_logger.debug('TSINFO: Marking %s as update for %s' %(best,
                name))
            # FIXME: we should probably handle updating multiple packages...
            txmbr = self.tsInfo.addUpdate(best, inst[0])
            txmbr.setAsDep()
        else:
            self.verbose_logger.debug('TSINFO: Marking %s as install for %s', best,
                name)
            txmbr = self.tsInfo.addInstall(best)
            txmbr.setAsDep()

        checkdeps = 1
        
        return checkdeps, missingdep


    def _processConflict(self, dep):
        """processes a Conflict dep from the resolveDeps() method"""
                
        CheckDeps = 0
        missingdep = 0
        conflicts = 0
        errormsgs = []
        

        ((name, version, release), (needname, needversion), flags, suggest, sense) = dep
        
        niceformatneed = rpmUtils.miscutils.formatRequire(needname, needversion, flags)
        if self.dsCallback: self.dsCallback.procConflict(name, niceformatneed)
        
        # we should try to update out of the dep, if possible        
        # see which side of the conflict is installed and which is in the transaction Set
        needmode = self.tsInfo.getMode(name=needname)
        confmode = self.tsInfo.getMode(name=name, ver=version, rel=release)
        if confmode is None:
            confname = name
        elif needmode is None:
            confname = needname
        else:
            confname = name
            
        po = None        

        uplist = self.up.getUpdatesList(name=confname)
        
        conflict_packages = self.rpmdb.searchNevra(name=confname)
        if conflict_packages:
            confpkg = conflict_packages[0] # take the first one, probably the only one
                

            # if there's an update for the reqpkg, then update it
            if len(uplist) > 0:
                if confpkg.name not in self.conf.exactarchlist:
                    pkgs = self.pkgSack.returnNewestByName(confpkg.name)
                    archs = {}
                    for pkg in pkgs:
                        (n,a,e,v,r) = pkg.pkgtup
                        archs[a] = pkg
                    a = rpmUtils.arch.getBestArchFromList(archs.keys())
                    po = archs[a]
                else:
                    po = self.pkgSack.returnNewestByNameArch((confpkg.name,confpkg.arch))[0]
                if po.pkgtup not in uplist:
                    po = None

        if po:
            self.verbose_logger.log(logginglevels.DEBUG_2,
                'TSINFO: Updating %s to resolve conflict.', po)
            txmbr = self.tsInfo.addUpdate(po, confpkg)
            txmbr.setAsDep()
            CheckDeps = 1
            
        else:
            conf = rpmUtils.miscutils.formatRequire(needname, needversion, flags)
            CheckDeps, conflicts = self._unresolveableConflict(conf, name, errormsgs)
            self.verbose_logger.log(logginglevels.DEBUG_1, '%s conflicts: %s',
                name, conf)
        
        return (CheckDeps, missingdep, conflicts, errormsgs)

    def _unresolveableReq(self, req, name, namestate, errors):
        CheckDeps = 0
        missingdep = 1
        msg = 'Missing Dependency: %s needed for package %s (%s)' % (req, name, namestate)
        errors.append(msg)
        if self.dsCallback: self.dsCallback.unresolved(msg)
        return CheckDeps, missingdep

    def _unresolveableConflict(self, conf, name, errors):
        CheckDeps = 0
        conflicts = 1
        msg = '%s conflicts with %s' % (name, conf)
        errors.append(msg)
        return CheckDeps, conflicts


class YumDepsolver(Depsolve):
    def __init__(self):
        Depsolve.__init__(self)
        self.deps = {}
        self.path = []
        self.loops = []

    def _provideToPkg(self, req):
        best = None
        (r, f, v) = req

        for pkgtup in self.rpmdb.whatProvides(r, f, v):
            # check the rpmdb first for something providing it that's not
            # set to be removed
            txmbrs = self.tsInfo.getMembers(pkgtup)
            if not txmbrs:
                po = self.getInstalledPackageObject(pkgtup)            
                self.deps[req] = po                
                return po
            for txmbr in txmbrs:
                if txmbr.output_state not in TS_REMOVE_STATES:
                    po = self.getInstalledPackageObject(pkgtup)
                    self.deps[req] = po                
                    return po

        for po in self.whatProvides(r, f, v):
            # if we already have something to be installed which
            # does the provide then that's obviously the one we want to use.
            # this takes care of the case that we select, eg, kernel-smp
            # and then have something which requires kernel
            if self.tsInfo.getMembers(po.pkgtup):
                self.deps[req] = po
                return po
        
        for txmbr in self.tsInfo.getMembers(None, TS_INSTALL_STATES):
            if txmbr.po.checkPrco('provides', (r, f, v)):
                self.deps[req] = txmbr.po
                return txmbr.po
                
        return None # for new ts check attempt

    def _undoDepInstalls(self):
        # clean up after ourselves in the case of failures
        for txmbr in self.tsInfo:
            if txmbr.isDep:
                self.tsInfo.remove(txmbr.pkgtup)

    def prof_resolveDeps(self):
        fn = "anaconda.prof.0"
        import hotshot, hotshot.stats
        prof = hotshot.Profile(fn)
        rc = prof.runcall(self._resolveDeps)
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
        rc = prof.runcall(self._resolveDeps)
        prof.dump_stats("yumprof")
        print "done running depcheck"

        p = pstats.Stats('yumprof')
        p.strip_dirs()
        p.sort_stats('time', 'calls')
        p.print_stats(20)
        return rc

    def _mytsCheck(self):
        
        # holder object for things from the check - to be handled by resolveDeps()
        if not hasattr(self, 'dcobj'):
            self.dcobj = DepCheck()
        self.dcobj.requires = []
        self.dcobj.conficts = []

        # returns a list of tuples
        # ((name, version, release), (needname, needversion), flags, suggest, sense)


        ret = []
        for txmbr in self.tsInfo.getMembers():
            
            if self.dcobj.already_seen.has_key(txmbr):
                continue
            self.verbose_logger.log(logginglevels.INFO_2,
                                    "Checking deps for %s" %(txmbr,))
            if txmbr.output_state in (TS_INSTALL, TS_TRUEINSTALL, TS_OBSOLETING):
                ret.extend(self._checkInstall(txmbr))
            elif txmbr.output_state in (TS_UPDATE,):
                ret.extend(self._checkUpdate(txmbr))
            elif txmbr.output_state in TS_REMOVE_STATES:
                ret.extend(self._checkRemove(txmbr))
            self.dcobj.already_seen[txmbr] = 1
            
        return ret

    def _resolveDeps(self):
        CheckDeps = True
        conflicts = 0
        missingdep = 0
        depscopy = []
        unresolveableloop = 0

        errors = []
        if self.dsCallback: self.dsCallback.start()

        while CheckDeps:
            self.cheaterlookup = {} # short cache for some information we'd resolve
                                    # (needname, needversion) = pkgtup
            if self.dsCallback: self.dsCallback.tscheck()
            deps = self._mytsCheck()

            if not deps:
                # FIXME: this doesn't belong here at all...
                for txmbr in self.tsInfo.getMembers():
                    if self.allowedMultipleInstalls(txmbr.po) and \
                           txmbr.ts_state == 'u':
                        self.verbose_logger.log(logginglevels.DEBUG_2,
                                                '%s converted to install',
                                                txmbr.po)
                        txmbr.ts_state = 'i'
                        txmbr.output_state = TS_INSTALL
                
                self.tsInfo.changed = False
                return (2, ['Success - deps resolved'])

            deps = unique(deps) # get rid of duplicate deps            
            if deps == depscopy:
                unresolveableloop += 1
                self.verbose_logger.log(logginglevels.DEBUG_2,
                    'Identical Loop count = %d', unresolveableloop)
                if unresolveableloop >= 2:
                    errors.append('Unable to satisfy dependencies')
                    for deptuple in deps:
                        ((name, version, release), (needname, needversion), flags, 
                          suggest, sense) = deptuple
                        if sense == rpm.RPMDEP_SENSE_REQUIRES:
                            msg = 'Package %s-%s-%s needs %s, this is not available.' % \
                                  (name, version, release, rpmUtils.miscutils.formatRequire(needname, 
                                                                          needversion, flags))
                        elif sense == rpm.RPMDEP_SENSE_CONFLICTS:
                            msg = 'Package %s conflicts with %s.' % \
                                  (name, rpmUtils.miscutils.formatRequire(needname, 
                                                                          needversion, flags))

                        errors.append(msg)
                    CheckDeps = False
                    break
            else:
                unresolveableloop = 0

            depscopy = deps
            CheckDeps = False


            # things to resolve
            self.verbose_logger.debug('# of Deps = %d', len(deps))
            depcount = 0
            for dep in deps:
                dep_start_time = time.time()
                ((name, version, release), (needname, needversion), flags, suggest, sense) = dep
                depcount += 1
                self.verbose_logger.log(logginglevels.DEBUG_2,
                    '\nDep Number: %d/%d\n', depcount, len(deps))
                if sense == rpm.RPMDEP_SENSE_REQUIRES: # requires
                    (checkdep, missing, conflict, errormsgs) = self._processReq(dep)
                    
                elif sense == rpm.RPMDEP_SENSE_CONFLICTS: # conflicts - this is gonna be short :)
                    (checkdep, missing, conflict, errormsgs) = self._processConflict(dep)
                    
                else: # wtf?
                    self.logger.critical('Unknown Sense: %d', sense)
                    continue
                
                dep_end_time = time.time()
                dep_proc_time = dep_end_time - dep_start_time
                self.verbose_logger.log(logginglevels.DEBUG_2, 'processing dep took: %f', dep_proc_time)
                
                missingdep += missing
                conflicts += conflict
                CheckDeps |= checkdep
                for error in errormsgs:
                    if error not in errors:
                        errors.append(error)

            self.verbose_logger.log(logginglevels.DEBUG_1, 'miss = %d', missingdep)
            self.verbose_logger.log(logginglevels.DEBUG_1, 'conf = %d', conflicts)
            self.verbose_logger.log(logginglevels.DEBUG_1, 'CheckDeps = %d', CheckDeps)

            if CheckDeps:
                if self.dsCallback: self.dsCallback.restartLoop()
                self.verbose_logger.log(logginglevels.DEBUG_1, 'Restarting Loop')
            else:
                if self.dsCallback: self.dsCallback.end()
                self.verbose_logger.log(logginglevels.DEBUG_1, 'Dependency Process ending')

            del deps


        self.tsInfo.changed = False
        if len(errors) > 0:
            return (1, errors)
        if len(self.tsInfo) > 0:
            return (2, ['Run Callback'])

    resolveDeps = _resolveDeps

    def _checkInstall(self, txmbr):
        reqs = txmbr.po.returnPrco('requires')
        provs = txmbr.po.returnPrco('provides')

        flags = {"GT": rpm.RPMSENSE_GREATER,
                 "GE": rpm.RPMSENSE_EQUAL | rpm.RPMSENSE_GREATER,
                 "LT": rpm.RPMSENSE_LESS,
                 "LE": rpm.RPMSENSE_LESS | rpm.RPMSENSE_EQUAL,
                 "EQ": rpm.RPMSENSE_EQUAL,
                 None: 0 }

        # if this is an update, we should check what the old
        # requires were to make things faster
        oldreqs = []
        for oldpo in txmbr.updates:
            oldreqs.extend(oldpo.returnPrco('requires'))

        ret = []
        for req in reqs:
            if req[0].startswith('rpmlib('):
                continue
            if req in provs:
                continue
            if req in oldreqs:
                continue
            
            self.verbose_logger.log(logginglevels.DEBUG_2, "looking for %s as a requirement of %s", req, txmbr)
            dep = self.deps.get(req, None)
            if dep is None:
                dep = self._provideToPkg(req)
                if dep is None:
                    reqtuple = (req[0], version_tuple_to_string(req[2]), flags[req[1]])
                    self.dcobj.addRequires(txmbr.po, [reqtuple])
                    ret.append( ((txmbr.name, txmbr.version, txmbr.release),
                                 (req[0], version_tuple_to_string(req[2])), flags[req[1]], None,
                                 rpm.RPMDEP_SENSE_REQUIRES) )
                    continue

            # Skip filebased requires on self, etc
            if txmbr.name == dep.name:
                continue
            # FIXME: Yum doesn't need this, right?
            #if (dep.name, txmbr.name) in whiteout.whitetup:
            #   log.debug("ignoring %s>%s in whiteout" %(dep.name, txmbr.name))
            #   continue
            if self.isPackageInstalled(dep.name):
                continue
            if self.tsInfo.exists(dep.pkgtup):
                pkgs = self.tsInfo.getMembers(pkgtup=dep.pkgtup)
                member = self.bestPackagesFromList(pkgs)[0]

                #Add relationship
                found = False
                for dependspo in txmbr.depends_on:
                    if member.po == dependspo:
                        found = True
                        break
                if not found:
                    member.setAsDep(txmbr.po)
        return ret

    def _checkUpdate(self, txmbr):
        ret = self._checkInstall(txmbr)
        for oldpo in txmbr.updates:
            for this_txmbr in self.tsInfo.getMembers(oldpo.pkgtup):
                ret.extend(self._checkRemove(this_txmbr))
        # this is probably incomplete, but it does create curious results
        return ret

    def _checkRemove(self, txmbr):
        po = txmbr.po
        provs = po.returnPrco('provides')

        # get the files in the package and express them as "provides"
        files = po.filelist
        filesasprovs = map(lambda f: (f, None, (None,None,None)), files)
        provs.extend(filesasprovs)

        # if this is an update, we should check what the new package
        # provides to make things faster
        newpoprovs = {}
        for newpo in txmbr.updated_by:
            for p in newpo.provides:
                newpoprovs[p] = 1
            for f in newpo.filelist:
                newpoprovs[(f, None, (None, None, None))] = 1

        ret = []
        self._removing = []
        # iterate over the provides of the package being removed
        for prov in provs:
            if prov[0].startswith('rpmlib('): # ignore rpmlib() provides
                continue
            if prov[0].startswith("/usr/share/doc"): # XXX: ignore doc files
                continue
            if newpoprovs.has_key(prov):
                continue
            
            (r, f, v) = prov
            self.verbose_logger.log(logginglevels.DEBUG_4, "looking to see what requires %s of %s", prov, po)
            removeList = self._requiredByPkg(prov)
            
            # we have a list of all the items impacted and
            # left w/unresolved deps
            # by this remove. stick them in the ret list with their
            for po in removeList:
                flags = {"GT": rpm.RPMSENSE_GREATER,
                         "GE": rpm.RPMSENSE_EQUAL | rpm.RPMSENSE_GREATER,
                         "LT": rpm.RPMSENSE_LESS,
                         "LE": rpm.RPMSENSE_LESS | rpm.RPMSENSE_EQUAL,
                         "EQ": rpm.RPMSENSE_EQUAL,
                         None: 0 }
                f = v = None
                for (rr, rf, rv) in po.requires:
                    if rr == r:
                        f = rf
                        v = rv
                        break

                self._removing.append(po.pkgtup)
                reqtuple = (r, version_tuple_to_string(v), flags[f])
                self.dcobj.addRequires(po, [reqtuple])
                
                ret.append( ((po.name, po.version, po.release),
                             (r, version_tuple_to_string(v)),
                             flags[f], None, rpm.RPMDEP_SENSE_REQUIRES) )

        return ret

    def _requiredByPkg(self, prov):
        """check to see if anything will or does require the provide, return 
           list of requiring pkg objects if so"""
        
        # check if anything installed needs it
          # make sure installed item is not set to be removed/obsoleted
          # make sure nothing else provides the same thing just as well
        # check if anything in the ts set to be installed/updated requires it
          # make sure nothing else provides the same thing just as well
        (r, f, v) = prov
        removeList = []

        # if anything else provides this as well and is installed or
        # to be installed, then skip this whole step
        other_provider = False
        tsSack = self.tsInfo.getMembers(None, TS_INSTALL_STATES, asSack=True)        
        for provpo in self.rpmdb.searchProvides(r) + tsSack.searchProvides(r):
            if self.tsInfo.getMembers(provpo.pkgtup, TS_REMOVE_STATES): # if it's being removed in the ts, it doesn't count
                continue
            if provpo.pkgtup in self._removing: # if we're going to be removed in the ts, it doesn't count
                continue
            if not provpo.checkPrco('provides', (r, f, v)): # if it doesn't actually provide the req, it doesn't count
                continue
            other_provider = True
        
        if other_provider:
            return []

        # see what requires this provide name
        tsSack = self.tsInfo.getMembers(None, TS_INSTALL_STATES, asSack=True)
        for reqpo in self.rpmdb.searchRequires(r) + tsSack.searchRequires(r):
            self.verbose_logger.log(logginglevels.DEBUG_2, "looking at %s as a requirement of %s", r, reqpo)
            isok = False
            # ignore stuff already being removed
            if self.tsInfo.getMembers(reqpo.pkgtup, TS_REMOVE_STATES):
                continue
            # ignore stuff soon to be removed
            if reqpo.pkgtup in self._removing:
                continue

            # check to ensure that we really fulfill instpo's need for r
            if not reqpo.checkPrco('requires', (r,f,v)): 
                continue

            if provpo in removeList: # if we already found it
                continue
            
            # otherwise, add it to the removeList
            removeList.append(reqpo)
            
        return removeList
        
class DepCheck(object):
    """object that YumDepsolver uses to see what things are needed to close
       the transaction set. attributes: requires, conflicts are a list of 
       requires are conflicts in the current transaction set. Each item in the
       lists are a requires or conflicts object"""
    def __init__(self):
        self.requires = []
        self.conflicts = []
        self.already_seen = {}
        
    def addRequires(self, po, req_tuple_list):
        # fixme - do checking for duplicates or additions in here to zip things along
        reqobj = Requires(po, req_tuple_list)
        self.requires.append(reqobj)
    
    def addConflicts(self, conflict_po_list, conflict_item):
        confobj = Conflicts(conflict_po_list, conflict_item)
        self.conflicts.append(confobj)

class Requires(object):
    def __init__(self, pkg,requires):
        self.pkg = pkg # po of requiring pkg
        self.requires = requires # list of things it requires that are un-closed in the ts


class Conflicts(object):
    def __init__(self, pkglist, conflict):
        self.pkglist = pkglist # list of conflicting package objects
        self.conflict = conflict # what the conflict was between them
