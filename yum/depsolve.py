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
import rpm

from Errors import DepError
import packages

class Depsolve:
    def __init__(self):
        packages.base = self
        self.ts = rpmUtils.transaction.TransactionWrapper() # FIXME - specify installroot?
        
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
    
    def populateTs(self):
        """take transactionData class and populate transaction set"""
        ts_elem = []
        for te in self.ts:
            pkginfo = (te.N(), te.A(), te.V(), te.E(), te.R())
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
                loc = po.returnSimple('relativepath')
                provides = po.getProvidesNames()
                if mode == 'u':
                    if n in self.conf.getConfigOption('installonlypkgs') or 'kernel-modules' in provides:
                        self.tsInfo.changeMode(pkginfo, 'i')
                        self.ts.addInstall(hdr, (hdr, loc), 'i')
                        self.log(5, 'Adding Package %s in mode i' % po)
                    else:
                        self.ts.addInstall(hdr, (hdr, loc), 'u')
                        self.log(5, 'Adding Package %s in mode u' % po)
                if mode == 'i':
                    self.ts.addInstall(hdr, (hdr, loc), 'i')                                            
                    self.log(5, 'Adding Package %s in mode i' % po)
            elif mode in ['e']:
                if (pkginfo, mode) in ts_elem:
                    continue
                indexes = rpmUtils.getIndexesByKeyword(self.read_ts, name=n,
                          arch=a, epoch=e, version=v, release=r)
                for idx in indexes:
                    self.ts.addErase(idx)
                    self.log(5, 'Adding Package %s-%s-%s.%s in mode i' % (n, v, r, a))
        
    def resolveDeps(self):
        CheckDeps = 1
        conflicts = 0
        missingdep = 0
        depscopy = []
        unresolveableloop = 0
        self.cheaterlookup = {}
        errors = []
        
        while CheckDeps == 1 and (missingdep == 0 or conflicts == 1):
            self.populateTs()
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
                (CheckDeps, missingdep, conflicts, errormsgs) = self._processDep(dep)
                for error in errormsgs:
                    errors.append(error)

            if CheckDeps:
                self.log(4, 'Restarting Dependency Process with new changes')
            else:
                self.log(4, 'Dependency Process ending')

            del deps

        if len(errors) > 0:
            return(1, errors)
        if self.tsInfo.count() > 0:
            return(2, ['Run Callback'])

    def _processDep(self, dep):
        """processes a dependency from the resolveDeps functions, returns a tuple
           of (CheckDeps, missingdep, conflicts, errors) the last item is an array
           of error messages"""
        
        CheckDeps = 0
        missingdep = 0
        conflicts = 0
        errormsgs = []
        
        ((name, version, release), (needname, needversion), flags, suggest, sense) = dep

        if sense == rpm.RPMDEP_SENSE_REQUIRES:
            self.log(4, '%s requires: %s' % (name, rpmUtils.miscutils.formatRequire(needname, needversion, flags)))
            if self.rpmdb.installed(name=name, ver=version, rel=release):
                # the requiring package is installed, that means the item needed is in
                # a package that is either being updated or erased/obsoleted
                # check what state the needed item/package is in:
                # if it's being upgraded then mark the requiring package to be upgraded too
                # if it's being erased then mark the requiring package to be erased
                print 'it is installed %s-%s-%s' % (name, version, release)
                pass
            pkgs = self.pkgSack.searchProvides(needname)
            if flags == 0:
                flags = None
            (r_e, r_v, r_r) = rpmUtils.miscutils.stringToVersion(needversion)
            for po in pkgs:
                self.log(5, 'Potential match %s to %s' % (needname, po))
                if po.checkPrco('provides', (needname, flags, (r_e, r_v, r_r))):
                    # first one? <shrug>
                    (n, e, v, r, a) = po.returnNevraTuple() # this is stupid the po should be emitting matching tuple types
                    
                    ### Why am I getting a po back and then just using the pkgtup info from it
                    # why not just store the po itself in the tsInfo, and dispense with all these lookups
                    self.tsInfo.add((n, a, e, v, r), 'u', 'dep')
                    self.log(3, 'Matched %s to require for %s' % (po, name))
                    CheckDeps=1
                    
            # find out if the req package is in the tsInfo
            # if it is, check which mode
            # if i or u then we're installing or updating something - find it in the repos
            # if e or ed then we're removing
            # if it is not in the tsInfo, check what provides what it is requiring
            # if the package that provides what we're requiring is in the tsInfo or the rpmdb
            # if it is in both and the rpmdb one is a different version, try to change versions
            # on the requiring package
        

        elif sense == rpm.RPMDEP_SENSE_CONFLICTS:
            msg = '%s conflicts: %s' % (name, rpmUtils.miscutils.formatRequire(needname, needversion, flags))
            self.log(4, '%s', msg)
            conflicts = 1
            errormsgs.append(msg)
            
        else:
            self.log(4, 'Unknown Sense: %d' (sense))
            
        return (CheckDeps, missingdep, conflicts, errormsgs)
