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
    def __init__(self, YumBaseClass):
        """takes an rpmUtils.transaction.TransactionData object"""
        base = YumBaseClass
        self.base = base
        packages.base = base
        self.tsInfo = base.tsInfo
        #self.excludelists = base.conf.getConfigOption
        self.installonly = base.conf.getConfigOption('installonlypkgs')
        self.installroot = base.conf.getConfigOption('installroot')
        self.ts = rpmUtils.transaction.TransactionWrapper() # FIXME - specify installroot?
        self.pkgSack = base.pkgSack
        
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
        for (pkginfo, mode) in self.tsInfo.dump():
            (n, a, e, v, r) = pkginfo
            if mode in ['u', 'i']:
                po = self.getPackageObject(pkginfo)
                hdr = po.getHeader()
                loc = po.returnSimple('relativepath')
                provides = po.getProvidesNames()
                if mode == 'u':
                    if n in self.installonly or 'kernel-modules' in provides:
                        self.tsInfo.changeMode(pkginfo, 'i')
                        self.ts.addInstall(hdr, (hdr, loc), 'i')
                        self.base.log(5, 'Adding Package %s in mode i' % po)
                    else:
                        self.ts.addInstall(hdr, (hdr, loc), 'u')
                        self.base.log(5, 'Adding Package %s in mode u' % po)
                if mode == 'i':
                    self.ts.addInstall(hdr, (hdr, loc), 'i')                                            
                    self.base.log(5, 'Adding Package %s in mode i' % po)
            elif mode in ['e']:
                indexes = rpmUtils.getIndexesByKeyword(self.base.ts, name=n,
                          arch=a, epoch=e, version=v, release=r)
                for idx in indexes:
                    self.ts.addErase(idx)                          
                    self.base.log(5, 'Adding Package %s-%s-%s.%s in mode i' % (n, v, r, a))
        
    def resolvedeps(self):
        CheckDeps = 1
        conflicts = 0
        unresolvable = 0
        depscopy = []
        unresolveableloop = 0
        while CheckDeps==1 or conflicts != 1 or unresolvable != 1:
            errors=[]
            self.populateTs()
            deps = self.ts.check()
            if deps == depscopy:
                unresolveableloop = unresolveableloop + 1
                self.base.log(5, 'looping count = %d' % unresolveableloop)
                if unresolveableloop >= 2:
                    errors.append('Unable to satisfy dependencies')
                    for deptuple in deps:
                        ((name, version, release), (reqname, reqversion), flags, 
                          suggest, sense) = deptuple
                        msg = 'Package %s needs %s, this is not available.' % \
                              (name, rpmUtils.miscutils.formatRequire(reqname, 
                                                            reqversion, flags))
                        errors.append(msg)
            else:
                unresolveableloop = 0
                           
            depscopy = deps
            
            CheckDeps = 0
            if not deps:
                return (0, 'Success - deps resolved')
            self.base.log (3, '# of Deps = %d' % len(deps))
            for ((name, version, release), (reqname, reqversion),
                                flags, suggest, sense) in deps:
                self.base.log (4, 'debug dep: %s req %s - %s - %s' % (name, reqname, reqversion, sense))
                if sense == rpm.RPMDEP_SENSE_REQUIRES:
                    # silly silly silly easy case
                    self.base.log(4, '%s requires: %s' % (name, rpmUtils.miscutils.formatRequire(reqname, reqversion, flags)))
                    pkgs = self.base.pkgSack.searchProvides(reqname)
                    if flags == 0:
                        flags = None
                    (r_e, r_v, r_r) = rpmUtils.miscutils.stringToVersion(reqversion)
                    for po in pkgs:
                        if po.checkPrco('provides', (reqname, flags, (r_e, r_v, r_r))):
                            # first one? <shrug>
                            (n, e, v, r, a) = po.returnNevraTuple() # this is stupid the po should be emitting matching tuple types
                            pkgtup = (n, a, e, v, r)
                            self.tsInfo.add(pkgtup, 'u', 'dep')
                            break

                elif sense == rpm.RPMDEP_SENSE_CONFLICTS:
                    self.base.log(4, '%s conflicts: %s' % (name, rpmUtils.miscutils.formatRequire(reqname, reqversion, flags)))
            self.base.log(4, 'Restarting Dependency Process with new changes')
            self.base.log.write(2, '.')
            del deps
            self.ts.clean()
            if len(errors) > 0:
                return(1, errors)
