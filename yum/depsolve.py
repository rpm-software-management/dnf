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


class Depsolve:
    def __init__(self, YumBaseClass):
        """takes an rpmUtils.transaction.TransactionData object"""
        base = YumBaseClass
        self.base = base
        self.tsInfo = base.tsInfo
        #self.excludelists = base.conf.getConfigOption
        self.installonly = base.conf.getConfigOption('installonlypkgs')
        self.installroot = base.conf.getConfigOption('installroot')thanks
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
        result = None
        if len(pkgs) == 0:
            # oh hell, how did this happen, we should raise or return None
            pass
        elif len(pkgs) > 1: # boy it'd be nice to do something smarter here FIXME
            result = pkgs[0]
        else:
            result = pkgs[0] # which should be the only
            
        return result            
    
    def getHeader(self, po)
        """takes a package tup and returns the header for the package"""
        # this whole function should probably be moved to somewhere else
        # as it is useful outside of here

        rel = po.returnSimple('relativepath')
        pkgname = os.path.basename(rel)
        hdrname = pkgname[:-4] + '.hdr'
        url = po.returnSimple('basepath')
        start = po.returnSimple('hdrstart')
        end = po.returnSimple('hdrend')
        repoid = po.returnSimple('repoid')
        repo = self.base.repos.getRepo(po.returnSimple('repoid'))
        localfile = repo.hdrdir + '/' + hdrname
        hdrpath = repo.get(url=url, relative=rel, local=localfile, 
                           range=(start, end))
        # need a function to open a hdr-range header and return it

        return hdr                                   
    def getProvidesNames(self, po):
        """takes a package object returns a list of providesNames"""
        
        provnames = []
        prov = po.returnPrco('provides')
        
        for (name, flag, vertup) in prov:
            provname.append(name)

        return provnames
    
    def populateTs(self):
        """take transactionData class and populate transaction set"""
        for (pkginfo, mode) in self.tsInfo.dump():
            (n, a, e, v, r) = pkginfo
            if mode in ['u', 'i']:
                po = self.getPackageObject(pkginfo)
                hdr = self.getHeader(po)
                loc = po.returnSimple('relativepath')
                provides = self.getProvidesNames(po)
                if mode == 'u':
                    if n in self.installonly or 'kernel-modules' in provides:
                        self.tsInfo.changeMode(pkginfo, 'i')
                        self.ts.addInstall(hdr, (hdr, loc), 'i')
                    else:
                        self.ts.addInstall(hdr, (hdr, loc), 'u')
                if mode == 'i':
                    self.ts.addInstall(hdr, (hdr, loc), 'i')                                            

            elif mode in ['e']:
                indexes = rpmUtils.getIndexesByKeyword(self.base.ts, name=n,
                          arch=a, epoch=e, version=v, release=r)
                for idx in indexes:
                    self.ts.addErase(idx)                          
                
        
    def resolvedeps(self, rpmDBInfo):
        #self == tsnevral
        #populate ts
        #depcheck
        #parse deps, if they exist, change nevral pkg states
        #die if:
        #    no suggestions
        #    conflicts
        #return 0 and a message if all is fine
        #return 1 and a list of error messages if shit breaks
        CheckDeps = 1
        conflicts = 0
        unresolvable = 0
        
        # this does a quick dep check with adding all the archs
        # keeps mem usage small in the easy/quick case
        _ts = self.populateTs(addavailable = 0)
        deps = _ts.check()
        if not deps:
            log(5, 'Quick Check only')
            return (0, 'Success - deps resolved')
        del deps
        del _ts
        log(5, 'Long Check')
        depscopy = []
        unresolveableloop = 0
        while CheckDeps==1 or conflicts != 1 or unresolvable != 1:
            errors=[]
            _ts = self.populateTs(addavailable = 1)
            deps = _ts.check()
            if deps == depscopy:
                unresolveableloop = unresolveableloop + 1
                log(5, 'looping count = %d' % unresolveableloop)
                if unresolveableloop >= 3:
                    errors.append('Unable to satisfy dependencies')
                    for ((name, version, release), (reqname, reqversion), flags, suggest, sense) in deps:
                        errors.append('Package %s needs %s, this is not available.' % (name, rpmUtils.formatRequire(reqname, reqversion, flags)))
            else:
                unresolveableloop = 0
                           
            depscopy = deps
            
            CheckDeps = 0
            if not deps:
                return (0, 'Success - deps resolved')
            log (3, '# of Deps = %d' % len(deps))
            for ((name, version, release), (reqname, reqversion),
                                flags, suggest, sense) in deps:
                log (4, 'debug dep: %s req %s - %s - %s' % (name, reqname, reqversion, sense))
                if sense == rpm.RPMDEP_SENSE_REQUIRES:
                    if suggest:
                        (header, sugname) = suggest
                        log(4, '%s wants %s' % (name, sugname))
                        (name, arch) = self.nafromloc(sugname)
                        archlist = self.bestArchsByVersion(name)
                        bestarch = archwork.bestarch(archlist)
                        pkghdr = self.getHeader(name, bestarch)
                        provides = rpmUtils.getProvides(pkghdr)
                        if reqname in provides:                                                                
                            log(3, _('bestarch = %s for %s') % (bestarch, name))
                        else:
                            log(3, _('bestarch %s does not provide resetting to arch %s') % (bestarch, arch))
                            bestarch = arch
                        self.setPkgState(name, bestarch, 'ud')
                        log(4, 'Got dep: %s, %s' % (name,bestarch))
                        CheckDeps = 1
                    else:
                        log(5, 'No suggestion for %s needing %s' % (name, reqname))
                        if self.exists(reqname):
                            if self.state(reqname) in ('e', 'ed'):
                                # this is probably an erase depedency
                                archlist = archwork.availablearchs(rpmDBInfo,name)
                                arch = archwork.bestarch(archlist)
                                ((e, v, r, a, l, i), s)=rpmDBInfo._get_data(name,arch)
                                self.add((name,e,v,r,a,l,i),'ed')
                                log(4, 'Got Erase Dep: %s, %s' %(name,a))
                            else:
                                archlist = self.bestArchsByVersion(reqname)
                                if len(archlist) > 0:
                                    arch = archwork.bestarch(archlist)
                                    if self.state(reqname, arch) not in ['ud','u','i']:
                                        self.setPkgState(reqname, arch, 'ud')
                                        log(4, 'Got Extra Dep: %s, %s' %(reqname,arch))
                                    else:
                                        log(4, '%s already to be installed/upgraded, trying to upgrade the requiring pkg' % (reqname))
                                        if self.exists(name):
                                            archlist = self.bestArchsByVersion(name)
                                            if len(archlist) > 0:
                                                arch = archwork.bestarch(archlist)
                                                self.setPkgState(name, arch, 'ud')
                                                log(4, 'Upgrading %s, %s' % (name, arch))
                                else:
                                    unresolvable = 1
                                    log(4, 'unresolvable - %s needs %s' % (name, rpmUtils.formatRequire(reqname, reqversion, flags)))
                                    if clientStuff.nameInExcludes(reqname):
                                        errors.append('Package %s needs %s that has been excluded.' % (name, reqname))
                                    else:
                                        errors.append('Package %s needs %s, this is not available.)' % (name, rpmUtils.formatRequire(reqname, reqversion, flags)))
                            CheckDeps=1
                        else:
                            # this is horribly ugly but I have to find some way to see if what it needed is provided
                            # by what we are removing - if it is then remove it -otherwise its a real dep problem - move along
                            if reqname[0] == '/':
                                whatprovides = _ts.dbMatch('basenames', reqname)
                            else:
                                whatprovides = _ts.dbMatch('provides', reqname)

                            if whatprovides and whatprovides.count() != 0:
                                log(5, 'Found some provides for %s' % (reqname))
                                for provhdr in whatprovides:
                                    if self.state(provhdr[rpm.RPMTAG_NAME],provhdr[rpm.RPMTAG_ARCH]) in ['e','ed']:
                                        ((e,v,r,a,l,i),s)=rpmDBInfo._get_data(name)
                                        self.add((name,e,v,r,a,l,i),'ed')
                                        log(4, 'Got Erase Dep: %s, %s' %(name, a))
                                        CheckDeps=1
                                    else:
                                    # help us obi-wan - you're our only hope!
                                        log(4, 'Cannot find a resolution attempting update out of loop on %s' % (name))
                                        if self.exists(name):
                                            archlist = self.bestArchsByVersion(name)
                                            if len(archlist) > 0:
                                                arch = archwork.bestarch(archlist)
                                                self.setPkgState(name, arch, 'ud')
                                                log(4, 'Upgrading %s, %s' % (name, arch))                                
                                        else:
                                        # it's as if a thousand dependencies cried out and were suddenly silenced!
                                            unresolvable = 1
                                            if clientStuff.nameInExcludes(reqname):
                                                errors.append('Package %s needs %s that has been excluded.' % (name, reqname))
                                            else:
                                                errors.append('Package %s needs %s, this is not available.' % (name, rpmUtils.formatRequire(reqname, reqversion, flags)))
                            else:
                                # help us obi-wan - you're our only hope!
                                log(4, 'Cannot find a resolution attempting update out of loop on %s' % (name))
                                if self.exists(name):
                                    archlist = self.bestArchsByVersion(name)
                                    if len(archlist) > 0:
                                        arch = archwork.bestarch(archlist)
                                        self.setPkgState(name, arch, 'ud')
                                        log(4, 'Upgrading %s, %s' % (name, arch))                                
                                else:
                                    # it's as if a thousand dependencies cried out and were suddenly silenced!
                                    unresolvable = 1
                                    if clientStuff.nameInExcludes(reqname):
                                        errors.append('Package %s needs %s that has been excluded.' % (name, reqname))
                                    else:
                                        errors.append('Package %s needs %s, this is not available.' % (name, rpmUtils.formatRequire(reqname, reqversion, flags)))
                                        
                elif sense == rpm.RPMDEP_SENSE_CONFLICTS:
                    # much more shit should happen here. specifically:
                    # if you have a conflict b/t two pkgs, try to upgrade the reqname pkg. - see if that solves the problem
                    # also something like a "this isn't our fault and we can't help it, continue on" should happen.like in anaconda
                    # more even than the below should happen here - but its getting closer - I need to flesh out all the horrible
                    # states it could be in.
                    log(4, 'conflict: %s %s %s' % (name, reqname, reqversion))
                    if rpmDBInfo.exists(reqname) and self.exists(reqname) and self.state(reqname) not in ('i','iu','u','ud'):
                        archlist = archwork.availablearchs(rpmDBInfo,reqname)
                        arch = archwork.bestarch(archlist)
                        (e1, v1, r1) = rpmDBInfo.evr(reqname,arch)
                        (e2, v2, r2) = self.evr(reqname,arch)
                        rc = rpmUtils.compareEVR((e1,v1,r1), (e2,v2,r2))
                        if rc<0:
                            log(4, 'conflict: setting %s to upgrade' % (reqname))
                            self.setPkgState(reqname, arch, 'ud')
                            CheckDeps=1
                        else:
                            errors.append('conflict between %s and %s' % (name, reqname))
                            conflicts=1
                    else:
                        errors.append('conflict between %s and %s' % (name, reqname))
                        conflicts=1
            log(4, 'Restarting Dependency Loop')
            log.write(2, '.')
            sys.stdout.flush()
            del _ts
            del deps
            if len(errors) > 0:
                return(1, errors)
