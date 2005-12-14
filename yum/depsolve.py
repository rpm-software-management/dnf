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

import os
import os.path
import re
import types

import rpmUtils.transaction
import rpmUtils.miscutils
import rpmUtils.arch
from misc import unique
import rpm

from repomd.packageSack import ListPackageSack
from repomd.mdErrors import PackageSackError
from Errors import DepError, RepoError
from constants import *
import packages

class Depsolve:
    def __init__(self):
        packages.base = self
        self.dsCallback = None
    
    def initActionTs(self):
        """sets up the ts we'll use for all the work"""
        
        self.ts = rpmUtils.transaction.TransactionWrapper(self.conf.installroot)
        ts_flags_to_rpm = { 'noscripts': rpm.RPMTRANS_FLAG_NOSCRIPTS,
                            'notriggers': rpm.RPMTRANS_FLAG_NOTRIGGERS,
                            'nodocs': rpm.RPMTRANS_FLAG_NODOCS,
                            'test': rpm.RPMTRANS_FLAG_TEST,
                            'repackage': rpm.RPMTRANS_FLAG_REPACKAGE}
        
        self.ts.setFlags(0) # reset everything.
        
        for flag in self.conf.tsflags:
            if ts_flags_to_rpm.has_key(flag):
                self.ts.addTsFlag(ts_flags_to_rpm[flag])
            else:
                self.errorlog(0, 'Invalid tsflag in config file: %s' % flag)

    def whatProvides(self, name, flags, version):
        """searches the packageSacks for what provides the arguments
           returns a ListPackageSack of providing packages, possibly empty"""

        self.log(4, 'Searching pkgSack for dep: %s' % name)
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
                self.log(2, 'Importing Additional filelist information for dependency resolution')
                self.repos.populateSack(with='filelists')
                
        pkgs = self.pkgSack.searchProvides(name)
        if flags == 0:
            flags = None
        

        if type(version) in (types.StringType, types.NoneType):
            (r_e, r_v, r_r) = rpmUtils.miscutils.stringToVersion(version)
        elif type(version) in (types.TupleType, types.ListType): # would this ever be a ListType?
            (r_e, r_v, r_r) = version
        
        defSack = ListPackageSack() # holder for items definitely providing this dep
        
        for po in pkgs:
            self.log(5, 'Potential match for %s from %s' % (name, po))
            if name[0] == '/' and r_v is None:
                # file dep add all matches to the defSack
                defSack.addPackage(po)
                continue

            if po.checkPrco('provides', (name, flags, (r_e, r_v, r_r))):
                defSack.addPackage(po)
                self.log(3, 'Matched %s to require for %s' % (po, name))
        
        return defSack
        
    def allowedMultipleInstalls(self, po):
        """takes a packageObject, returns 1 or 0 depending on if the package 
           should/can be installed multiple times with different vers
           like kernels and kernel modules, for example"""
           
        if po.name in self.conf.installonlypkgs:
            return 1
        
        provides = po.getProvidesNames()
        if filter (lambda prov: prov in self.conf.installonlypkgs, provides):
            return 1
        
        return 0

    def handleKernelModule(self, txmbr):
        """Figure out what special magic needs to be done to install/upgrade
           this kernel module."""

        def getKernelReqs(hdr):
            kernels = ["kernel-%s" % a for a in rpmUtils.arch.arches.keys()]
            reqs = []
            names = hdr[rpm.RPMTAG_REQUIRENAME]
            flags = hdr[rpm.RPMTAG_REQUIREFLAGS]
            ver =   hdr[rpm.RPMTAG_REQUIREVERSION]
            if names is not None:
                reqs = zip(names, flags, ver)
            return filter(lambda r: r[0] in kernels, reqs)

        kernelReqs = getKernelReqs(txmbr.po.returnLocalHeader())
        instPkgs = self.rpmdb.returnTupleByKeyword(name=txmbr.po.name)
        for pkg in instPkgs:
            hdr = self.rpmdb.returnHeaderByTuple(pkg)[0]
            instKernelReqs = getKernelReqs(hdr)
            
            for r in kernelReqs:
                if r in instKernelReqs:
                    # we know that an incoming kernel module requires the
                    # same kernel as an already installed module of the
                    # same name.  "Upgrade" this module instead of install
                    po = packages.YumInstalledPackage(hdr)
                    self.tsInfo.addErase(po)
                    self.log(4, 'Removing kernel module %s upgraded to %s' %
                             (po, txmbr.po))
                    break
       

    def populateTs(self, test=0, keepold=1):
        """take transactionData class and populate transaction set"""

        if self.dsCallback: self.dsCallback.transactionPopulation()
        ts_elem = {}
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
            self.log(6, 'Member: %s' % txmbr)
            if txmbr.ts_state in ['u', 'i']:
                if ts_elem.has_key((txmbr.pkgtup, 'i')):
                    continue
                self.downloadHeader(txmbr.po)
                hdr = txmbr.po.returnLocalHeader()
                rpmfile = txmbr.po.localPkg()
                
                if txmbr.ts_state == 'u':
                    if txmbr.po.name.startswith("kernel-module-"):
                        self.handleKernelModule(txmbr)
                    if self.allowedMultipleInstalls(txmbr.po):
                        self.log(5, '%s converted to install' % (txmbr.po))
                        txmbr.ts_state = 'i'
                        txmbr.output_state = TS_INSTALL

                
                self.ts.addInstall(hdr, (hdr, rpmfile), txmbr.ts_state)
                self.log(4, 'Adding Package %s in mode %s' % (txmbr.po, txmbr.ts_state))
                if self.dsCallback: 
                    self.dsCallback.pkgAdded(txmbr.pkgtup, txmbr.ts_state)
            
            elif txmbr.ts_state in ['e']:
                if ts_elem.has_key((txmbr.pkgtup, txmbr.ts_state)):
                    continue
                indexes = self.rpmdb.returnIndexByTuple(txmbr.pkgtup)
                for idx in indexes:
                    self.ts.addErase(idx)
                    if self.dsCallback: self.dsCallback.pkgAdded(txmbr.pkgtup, 'e')
                    self.log(4, 'Removing Package %s' % txmbr.po)
        

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
                return (2, ['Success - deps resolved'])

            deps = unique(deps) # get rid of duplicate deps            
            if deps == depscopy:
                unresolveableloop += 1
                self.log(5, 'Identical Loop count = %d' % unresolveableloop)
                if unresolveableloop >= 2:
                    errors.append('Unable to satisfy dependencies')
                    for deptuple in deps:
                        ((name, version, release), (needname, needversion), flags, 
                          suggest, sense) = deptuple
                        msg = 'Package %s needs %s, this is not available.' % \
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
            self.log (3, '# of Deps = %d' % len(deps))
            depcount = 0
            for dep in deps:
                ((name, version, release), (needname, needversion), flags, suggest, sense) = dep
                depcount += 1
                self.log(5, '\nDep Number: %d/%d\n' % (depcount, len(deps)))
                if sense == rpm.RPMDEP_SENSE_REQUIRES: # requires
                    # if our packageSacks aren't here, then set them up
                    if not hasattr(self, 'pkgSack'):
                        self.doRepoSetup()
                        self.doSackSetup()
                    (checkdep, missing, conflict, errormsgs) = self._processReq(dep)
                    
                elif sense == rpm.RPMDEP_SENSE_CONFLICTS: # conflicts - this is gonna be short :)
                    (checkdep, missing, conflict, errormsgs) = self._processConflict(dep)
                    
                else: # wtf?
                    self.errorlog(0, 'Unknown Sense: %d' (sense))
                    continue

                missingdep += missing
                conflicts += conflict
                CheckDeps += checkdep
                for error in errormsgs:
                    if error not in errors:
                        errors.append(error)

            self.log(4, 'miss = %d' % missingdep)
            self.log(4, 'conf = %d' % conflicts)
            self.log(4, 'CheckDeps = %d' % CheckDeps)

            if CheckDeps > 0:
                if self.dsCallback: self.dsCallback.restartLoop()
                self.log(4, 'Restarting Loop')
            else:
                if self.dsCallback: self.dsCallback.end()
                self.log(4, 'Dependency Process ending')

            del deps
            

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
        self.log(4, '%s requires: %s' % (name, niceformatneed))
        
        if self.dsCallback: self.dsCallback.procReq(name, niceformatneed)
        
        # is the requiring tuple (name, version, release) from an installed package?
        pkgs = []
        dumbmatchpkgs = self.rpmdb.returnTupleByKeyword(name=name, ver=version, rel=release)
        for pkgtuple in dumbmatchpkgs:
            self.log(6, 'Calling rpmdb.returnHeaderByTuple on %s.%s %s:%s-%s' % pkgtuple)
            hdrs = self.rpmdb.returnHeaderByTuple(pkgtuple)
            for hdr in hdrs:
                po = packages.YumInstalledPackage(hdr)
                if self.tsInfo.exists(po.pkgtup):
                    self.log(7, 'Skipping package already in Transaction Set: %s' % po)
                    continue
                if niceformatneed in po.requiresList():
                    pkgs.append(po)

        if len(pkgs) < 1: # requiring tuple is not in the rpmdb
            txmbrs = self.tsInfo.matchNaevr(name=name, ver=version, rel=release)
            if len(txmbrs) < 1:
                msg = 'Requiring package %s-%s-%s not in transaction set \
                                  nor in rpmdb' % (name, version, release)
                self.log(4, msg)
                errormsgs.append(msg)
                missingdep = 1
                CheckDeps = 0

            else:
                txmbr = txmbrs[0]
                self.log(4, 'Requiring package is from transaction set')
                if txmbr.ts_state == 'e':
                    msg = 'Requiring package %s is set to be erased,' % txmbr.name +\
                           'probably processing an old dep, restarting loop early.'
                    self.log(5, msg)
                    CheckDeps=1
                    missingdep=0
                    return (CheckDeps, missingdep, conflicts, errormsgs)
                    
                else:
                    self.log(4, 'Resolving for requiring package: %s-%s-%s in state %s' %
                                (name, version, release, txmbr.ts_state))
                    self.log(4, 'Resolving for requirement: %s' % 
                        rpmUtils.miscutils.formatRequire(needname, needversion, flags))
                    requirementTuple = (needname, flags, needversion)
                    # should we figure out which is pkg it is from the tsInfo?
                    requiringPkg = (name, version, release, txmbr.ts_state) 
                    CheckDeps, missingdep = self._requiringFromTransaction(requiringPkg, requirementTuple, errormsgs)
            
        if len(pkgs) > 0:  # requring tuple is in the rpmdb
            if len(pkgs) > 1:
                self.log(5, 'Multiple Packages match. %s-%s-%s' % (name, version, release))
                for po in pkgs:
                    # if one of them is (name, arch) already in the tsInfo somewhere, 
                    # pop it out of the list
                    (n,a,e,v,r) = po.pkgtup
                    thismode = self.tsInfo.getMode(name=n, arch=a)
                    if thismode is not None:
                        self.log(5, '   %s already in ts %s, skipping' % (po, thismode))
                        pkgs.remove(po)
                        continue
                    else:
                        self.log(5, '   %s' % po)
                    
            if len(pkgs) == 1:
                po = pkgs[0]
                self.log(5, 'Requiring package is installed: %s' % po)
            
            if len(pkgs) > 0:
                requiringPkg = pkgs[0] # take the first one, deal with the others (if there is one)
                                   # on another dep.
            else:
                self.errorlog(1, 'All pkgs in depset are also in tsInfo, this is wrong and bad')
                CheckDeps = 1
                return (CheckDeps, missingdep, conflicts, errormsgs)
            
            self.log(4, 'Resolving for installed requiring package: %s' % requiringPkg)
            self.log(4, 'Resolving for requirement: %s' % 
                rpmUtils.miscutils.formatRequire(needname, needversion, flags))
            
            requirementTuple = (needname, flags, needversion)
            
            CheckDeps, missingdep = self._requiringFromInstalled(requiringPkg.pkgtup,
                                                    requirementTuple, errormsgs)


        return (CheckDeps, missingdep, conflicts, errormsgs)


    def _requiringFromInstalled(self, requiringPkg, requirement, errorlist):
        """processes the dependency resolution for a dep where the requiring 
           package is installed"""
        
        # FIXME - should we think about dealing exclusively in package objects?
           
        (name, arch, epoch, ver, rel) = requiringPkg
        requiringPo = self.getInstalledPackageObject(requiringPkg)
        
        (needname, needflags, needversion) = requirement
        niceformatneed = rpmUtils.miscutils.formatRequire(needname, needversion, needflags)
        checkdeps = 0
        missingdep = 0
        
        # we must first find out why the requirement is no longer there
        # we must find out what provides/provided it from the rpmdb (if anything)
        # then check to see if that thing is being acted upon by the transaction set
        # if it is then we need to find out what is being done to it and act accordingly
        rpmdbNames = self.rpmdb.getNamePkgList()
        needmode = None # mode in the transaction of the needed pkg (if any)
        needpkgtup = None
        providers = []
        
        if self.cheaterlookup.has_key((needname, needflags, needversion)):
            self.log(5, 'Needed Require has already been looked up, cheating')
            cheater_tup = self.cheaterlookup[(needname, needflags, needversion)]
            providers = [cheater_tup]
        
        elif needname in rpmdbNames:
            txmbrs = self.tsInfo.matchNaevr(name=needname)
            for txmbr in txmbrs:
                providers.append(txmbr.pkgtup)

        else:
            self.log(5, 'Needed Require is not a package name. Looking up: %s' % niceformatneed)
            providers = self.rpmdb.whatProvides(needname, needflags, needversion)
            
        for insttuple in providers:
            inst_str = '%s.%s %s:%s-%s' % insttuple
            (i_n, i_a, i_e, i_v, i_r) = insttuple
            self.log(5, 'Potential Provider: %s' % inst_str)
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
                needpkgtup = insttuple
                self.cheaterlookup[(needname, needflags, needversion)] = insttuple
                self.log(5, 'Mode is %s for provider of %s: %s' % 
                            (needmode, niceformatneed, inst_str))
                break
                    
        self.log(5, 'Mode for pkg providing %s: %s' % (niceformatneed, needmode))
        
        if needmode in ['e']:
            self.log(5, 'TSINFO: %s package requiring %s marked as erase' %
                            (requiringPo, needname))
            txmbr = self.tsInfo.addErase(requiringPo)
            
            needpo = None
            if needpkgtup:
                needpo = self.getInstalledPackageObject(needpkgtup)
            
            txmbr.setAsDep(po=needpo)
            checkdeps = 1
        
        if needmode in ['i', 'u']:
            self.doUpdateSetup()
            obslist = []
            # check obsoletes first
            if self.conf.obsoletes:
                if self.up.obsoleted_dict.has_key(requiringPo.pkgtup):
                    obslist = self.up.obsoleted_dict[requiringPo.pkgtup]
                    self.log(4, 'Looking for Obsoletes for %s' % requiringPo)
                
            if len(obslist) > 0:
                po = None
                for pkgtup in obslist:
                    po = self.getPackageObject(pkgtup)
                if po:
                    for (new, old) in self.up.getObsoletesTuples(): # FIXME query the obsoleting_list now?
                        if po.pkgtup == new:
                            txmbr = self.tsInfo.addObsoleting(po, requiringPo)
                            self.tsInfo.addObsoleted(requiringPo, po)
                            needpo = None
                            if needpkgtup:
                                needpo = self.getInstalledPackageObject(needpkgtup)
                            txmbr.setAsDep(po=needpo)
                            self.log(5, 'TSINFO: Obsoleting %s with %s to resolve dep.' % (requiringPo, po))
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
                        needpo = None
                        if needpkgtup:
                            needpo = self.getInstalledPackageObject(needpkgtup)
                        txmbr.setAsDep(po=needpo)
                        
                        self.log(5, 'TSINFO: Updating %s to resolve dep.' % po)
                checkdeps = 1
                
            else: # if there's no update then pass this over to requringFromTransaction()
                self.log(5, 'Cannot find an update path for dep for: %s' % niceformatneed)
                
                reqpkg = (name, ver, rel, None)
                return self._requiringFromTransaction(reqpkg, requirement, errorlist)
            

        if needmode is None:
            reqpkg = (name, ver, rel, None)
            if hasattr(self, 'pkgSack'):
                return self._requiringFromTransaction(reqpkg, requirement, errorlist)
            else:
                self.log(5, 'Unresolveable requirement %s for %s' % (niceformatneed, reqpkg_print))
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
            if pkg.pkgtup in self.rpmdb.getPkgList(): # is it already installed?
                self.log(5, '%s is in providing packages but it is already installed, removing.' % pkg)
                provSack.delPackage(pkg)
                continue

            # we need to check to see, if we have anything similar to it (name-wise)
            # installed or in the ts, and this isn't a package that allows multiple installs
            # then if it's newer, fine - continue on, if not, then we're unresolveable
            # cite it and exit
        
            tspkgs = []
            if not self.allowedMultipleInstalls(pkg):
                (n, a, e, v, r) = pkg.pkgtup
                
                # from ts
                tspkgs = self.tsInfo.matchNaevr(name=pkg.name, arch=pkg.arch)
                for tspkg in tspkgs:
                    (tn, ta, te, tv, tr) = tspkg.pkgtup
                    rc = rpmUtils.miscutils.compareEVR((e, v, r), (te, tv, tr))
                    if rc < 0:
                        msg = 'Potential resolving package %s has newer instance in ts.' % pkg
                        self.log(5, msg)
                        provSack.delPackage(pkg)
                        continue
                
                # from rpmdb
                dbpkgs = self.rpmdb.returnTupleByKeyword(name=pkg.name, arch=pkg.arch)
                for dbpkgtup in dbpkgs:
                    (dn, da, de, dv, dr) = dbpkgtup
                    rc = rpmUtils.miscutils.compareEVR((e, v, r), (de, dv, dr))
                    if rc < 0:
                        msg = 'Potential resolving package %s has newer instance installed.' % pkg
                        self.log(5, msg)
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
                self.doUpdateSetup()
                self.log(5, '%s already in ts, skipping this one' % (n))
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
        
        if best.pkgtup in self.rpmdb.getPkgList(): # is it already installed?
            missingdep = 1
            checkdeps = 0
            msg = 'Missing Dependency: %s is needed by package %s' % (needname, name)
            errorlist.append(msg)
            return checkdeps, missingdep
        
                
            
        # FIXME - why can't we look up in the transaction set for the requiringPkg
        # and know what needs it that way and provide a more sensible dep structure in the txmbr
        if (best.name, best.arch) in self.rpmdb.getNameArchPkgList():
            self.log(3, 'TSINFO: Marking %s as update for %s' % (best, name))
            txmbr = self.tsInfo.addUpdate(best)
            txmbr.setAsDep()
        else:
            self.log(3, 'TSINFO: Marking %s as install for %s' % (best, name))
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
        self.doUpdateSetup()
        uplist = self.up.getUpdatesList(name=confname)
        
        conftuple = self.rpmdb.returnTupleByKeyword(name=confname)
        if conftuple:
            (confname, confarch, confepoch, confver, confrel) = conftuple[0] # take the first one, probably the only one
                

            # if there's an update for the reqpkg, then update it
            if len(uplist) > 0:
                if confname not in self.conf.exactarchlist:
                    pkgs = self.pkgSack.returnNewestByName(confname)
                    archs = {}
                    for pkg in pkgs:
                        (n,a,e,v,r) = pkg.pkgtup
                        archs[a] = pkg
                    a = rpmUtils.arch.getBestArchFromList(archs.keys())
                    po = archs[a]
                else:
                    po = self.pkgSack.returnNewestByNameArch((confname,confarch))[0]
                if po.pkgtup not in uplist:
                    po = None

        if po:
            self.log(5, 'TSINFO: Updating %s to resolve conflict.' % po)
            txmbr = self.tsInfo.addUpdate(po)
            txmbr.setAsDep()
            CheckDeps = 1
            
        else:
            conf = rpmUtils.miscutils.formatRequire(needname, needversion, flags)
            CheckDeps, conflicts = self._unresolveableConflict(conf, name, errormsgs)
            self.log(4, '%s conflicts: %s' % (name, conf))
        
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
