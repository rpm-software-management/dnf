"""
resolvedeps.py
ideas:
     
  - possibly require functions to:
     - resolve requires: whatProvides('somestring')
     - resolve conflicts: whatConflicts('somestring')
     - archresolution - which arch is best
     - get headers
     - progress callback
     - error report
     - output

  - info it will need:
     - install-only lists
     - exclude lists

    
"""
import os
import os.path

import rpmUtils.transaction
import rpmUtils.miscutils
import rpmUtils.arch
import rpm

from metadata.packageSack import ListPackageSack
from Errors import DepError
import packages

class Depsolve:
    def __init__(self):
        packages.base = self
        self.initActionTs()
    
    def initActionTs(self):
        """sets up the ts we'll use for all the work"""
        self.ts = rpmUtils.transaction.TransactionWrapper() # deal with flags, etc

    def whatProvides(self, req):
        """tells you what provides the requested string"""
        
    def whatConflicts(self, pkgtup):
        """tells you what packages conflict with the requested pkg"""

    def getPackageObject(self, pkgtup):
        """retrieves the packageObject from a pkginfo tuple - if we need
           to pick and choose which one is best we better call out
           to some method from here to pick the best pkgobj if there are
           more than one response - right now it's more rudimentary"""
           
        (n,a,e,v,r) = pkgtup
        pkgs = self.pkgSack.searchNevra(name=n, arch=a, epoch=e, ver=v, rel=r)

        if len(pkgs) == 0:
            raise DepError, 'Package tuple %s could not be found in packagesack' % pkgtup
            return None
            
        if len(pkgs) > 1: # boy it'd be nice to do something smarter here FIXME
            result = pkgs[0]
        else:
            result = pkgs[0] # which should be the only
        
        return result
    
    def populateTs(self, test=0):
        """take transactionData class and populate transaction set"""

        ts_elem = []
        for te in self.ts:
            epoch = te.E()
            if epoch is None:
                epoch = '0'
            pkginfo = (te.N(), te.A(), epoch, te.V(), te.R())
            if te.Type() == 1:
                mode = 'i'
            elif te.Type() == 2:
                mode = 'e'
            
            ts_elem.append((pkginfo, mode))
        
        for (pkginfo, mode) in self.tsInfo.dump():
            (n, a, e, v, r) = pkginfo
            if mode in ['u', 'i']:
                if (pkginfo, 'i') in ts_elem:
                    continue
                po = self.getPackageObject(pkginfo)
                hdr = po.getHeader()
                rpmfile = po.localPkg()
                if test:
                    provides = po.getProvidesNames()
                else:
                    provides = []
                if mode == 'u':
                    if n in self.conf.getConfigOption('installonlypkgs') or 'kernel-modules' in provides:
                        self.tsInfo.changeMode(pkginfo, 'i')
                        self.ts.addInstall(hdr, (hdr, rpmfile), 'i')
                        self.log(4, 'Adding Package %s in mode i' % po)
                    else:
                        self.ts.addInstall(hdr, (hdr, rpmfile), 'u')
                        self.log(4, 'Adding Package %s in mode u' % po)
                if mode == 'i':
                    self.ts.addInstall(hdr, (hdr, rpmfile), 'i')
                    self.log(4, 'Adding Package %s in mode i' % po)
            elif mode in ['e']:
                if (pkginfo, mode) in ts_elem:
                    continue
                indexes = rpmUtils.getIndexesByKeyword(self.read_ts, name=str(n),
                          arch=str(a), epoch=str(e), version=str(v), release=str(r))
                for idx in indexes:
                    self.ts.addErase(idx)
                    self.log(4, 'Removing Package %s-%s-%s.%s' % (n, v, r, a))
        
    def resolveDeps(self):
        CheckDeps = 1
        conflicts = 0
        missingdep = 0
        depscopy = []
        unresolveableloop = 0
        self.cheaterlookup = {}
        errors = []

        while CheckDeps == 1 and (missingdep == 0 or conflicts == 1):
            self.populateTs(test=1)
            deps = self.ts.check()

            if not deps:
                return (2, ['Success - deps resolved'])
            
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
                        missingdep = 1
            else:
                unresolveableloop = 0

            depscopy = deps
            CheckDeps = 0


            # things to resolve
            self.log (3, '# of Deps = %d' % len(deps))
            
            for dep in deps:
                ((name, version, release), (needname, needversion), flags, suggest, sense) = dep
                if sense == rpm.RPMDEP_SENSE_REQUIRES:
                    (CheckDeps, missingdep, conflicts, errormsgs) = self._processReq(dep)
                elif sense == rpm.RPMDEP_SENSE_CONFLICTS:
                    (CheckDeps, missingdep, conflicts, errormsgs) = self._processConflict(dep)
                else:
                    self.errorlog(0, 'Unknown Sense: %d' (sense))
                    continue
                    
                for error in errormsgs:
                    errors.append(error)

            if CheckDeps:
                self.log(2, 'Restarting Dependency Process with new changes')
            else:
                self.log(4, 'Dependency Process ending')

            del deps

        if len(errors) > 0:
            return(1, errors)
        if self.tsInfo.count() > 0:
            return(2, ['Run Callback'])

    def _processReq(self, dep):
        """processes a Requires dep from the resolveDeps functions, returns a tuple
           of (CheckDeps, missingdep, conflicts, errors) the last item is an array
           of error messages"""
        
        CheckDeps = 0
        missingdep = 0
        conflicts = 0
        errormsgs = []
        
        ((name, version, release), (needname, needversion), flags, suggest, sense) = dep
        self.log(4, '%s requires: %s' % (name, rpmUtils.miscutils.formatRequire(needname, needversion, flags)))
        
        pkgs = self.rpmdb.returnTupleByKeyword(name=name, ver=version, rel=release)
        
        if len(pkgs) > 0:
            # the requiring package is installed, that means the item needed is in
            # a package that is either being updated or erased/obsoleted
            # check what state the needed item/package is in:
            # if it's being upgraded then mark the requiring package to be upgraded too
            # if it's being erased then mark the requiring package to be erased
            self.log(5, 'installed pkg: %s-%s-%s' % (name, version, release))
            needmode = self.tsInfo.getMode(name=needname)
            
            # if the needmode is None then what the package needs is not in our tsInfo
            # and may very well be a virtual dep (kernel-drm = 4.3.0, for example)
            # therefore we need to find what provides that virtual dep
            # if it is a package that we have in our tsInfo, then treat as below
            if needmode is None:
                # need a function to tell if anything in the rpmdb provides
                   # needname = needversion 
                # take the prco matching function from the metadata
                pass

            pkg = pkgs[0] #take the first one
            po = None
            if needmode in ['e']:
                for pkg in pkgs:
                    (n,a,e,v,r) = pkg
                    self.log(5, '%s package requiring %s marked as erase' % (n, needname))
                    self.tsInfo.add(pkg, 'e', 'dep')
                    CheckDeps = 1
            if needmode in ['i', 'u']:
                self.log(5, 'needed packaged marked as update')
                (n,a,e,v,r) = pkg
                if not self.conf.getConfigOption('exactarch'):
                    pkgs = self.pkgSack.returnNewestByName(n)
                    archs = []
                    for pkg in pkgs:
                        (n,e,v,r,a) = pkg.returnNevraTuple()
                        archs.append(a)
                    a = rpmUtils.arch.getBestArchFromList(archs)
                    po = self.pkgSack.returnNewestByNameArch((n,a))
                else:
                    po = self.pkgSack.returnNewestByNameArch((n,a))

                if po:
                    (n,e,v,r,a) = po.returnNevraTuple()
                    self.tsInfo.add((n,a,e,v,r), 'u', 'dep')
                    CheckDeps = 1

        else:
            # we need to find the package from the repositories
            pkgs = self.pkgSack.searchProvides(needname)
            if flags == 0:
                flags = None
            (r_e, r_v, r_r) = rpmUtils.miscutils.stringToVersion(needversion)
            defSack = ListPackageSack() # list of items definitely providing this requirment
            for po in pkgs:
                self.log(5, 'Potential match %s to %s' % (needname, po))
                if po.checkPrco('provides', (needname, flags, (r_e, r_v, r_r))):
                    # first one? <shrug>
                    defSack.addPkg(po)
                    self.log(3, 'Matched %s to require for %s' % (po, name))
            
            # iterate the defSack briefly, if we find the package is already in the 
            # tsInfo then just skip this run
            for pkg in defSack.returnPackages():
                (n,e,v,r,a) = pkg.returnNevraTuple()
                pkgmode = self.tsInfo.getMode(name=n, arch=a, epoch=e, ver=v, rel=r)
                if pkgmode in ['i', 'u']:
                    self.log(5, '%s already in ts, skipping this one' % (n))
                    CheckDeps = 1
                    return (CheckDeps, missingdep, conflicts, errormsgs)
                    
            #self.bestPackageFromList(defSack, reqtup) # useful function to have
            newest = defSack.returnNewestByNameArch()
            if len(newest) > 1:
                best = newest[0]
                for po in newest[1:]:
                    if len(po.name) < len(best.name):
                        best = po
                    elif len(po.name) == len(best.name):
                        # compare arch
                        arch = rpmUtils.arch.getBestArchFromList([po.arch, best.arch])
                        if arch == po.arch:
                            best = po
            else:
                best = newest[0]

            (n, e, v, r, a) = best.returnNevraTuple() # this is stupid the po should be emitting matching tuple types                    
            self.tsInfo.add((n, a, e, v, r), 'i', 'dep')
            self.log(3, 'Best of providing: %s to require for %s' % (best, name))
            CheckDeps=1
                
        # find out if the req package is in the tsInfo
        # if it is, check which mode
        # if i or u then we're installing or updating something - find it in the repos
        # if e or ed then we're removing
        # if it is not in the tsInfo, check what provides what it is requiring
        # if the package that provides what we're requiring is in the tsInfo or the rpmdb
        # if it is in both and the rpmdb one is a different version, try to change versions
        # on the requiring package
        return (CheckDeps, missingdep, conflicts, errormsgs)
        
    def _processConflict(self, dep):
        """processes a Conflict dep from the resolveDeps() method"""
                
        CheckDeps = 0
        missingdep = 0
        conflicts = 0
        errormsgs = []

        msg = '%s conflicts: %s' % (name, rpmUtils.miscutils.formatRequire(needname, needversion, flags))
        self.log(4, '%s', msg)
        conflicts = 1
        errormsgs.append(msg)
        
            
        return (CheckDeps, missingdep, conflicts, errormsgs)
