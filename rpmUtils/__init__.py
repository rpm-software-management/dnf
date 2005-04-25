#!/usr/bin/python -tt

import rpm
import miscutils
import exceptions
import oldUtils


class RpmUtilsError(exceptions.Exception):
    def __init__(self, args=None):
        exceptions.Exception.__init__(self)
        self.args = args

    

# useful functions
def getHeadersByKeyword(ts, **kwargs):
    """return list of headers from the rpmdb matching a keyword
        ex: getHeadersByKeyword(name='foo', version='1', release='1')
    """
    lst = []
    # lifted from up2date - way to easy and useful NOT to steal - thanks adrian
    mi = ts.dbMatch()
    if kwargs.has_key('epoch'):
        del(kwargs['epoch']) # epochs don't work here for None/0/'0' reasons
        
    keywords = len(kwargs.keys())
    for hdr in mi:
        match = 0
        for keyword in kwargs.keys():
            if hdr[keyword] == kwargs[keyword]:
                match += 1
        if match == keywords:
            lst.append(hdr)
    del mi
    return lst
        
def getIndexesByKeyword(ts, **kwargs):
    """return list of headers Indexes from the rpmdb matching a keyword
        ex: getHeadersByKeyword(name='foo', version='1', release='1')
    """
    # THIS IS EXCRUCIATINGLY SLOW
    lst = []
    mi = ts.dbMatch()
    for keyword in kwargs.keys():
        mi.pattern(keyword, rpm.RPMMIRE_GLOB, kwargs[keyword])

    # we really shouldnt be getting multiples here, but what the heck
    for h in mi:
        instance = mi.instance()
        lst.append(instance)
    del mi
    return lst

class RpmDBHolder:
    def __init__(self):
        self.pkglists = []
        
    def addDB(self, ts):
        self.ts = ts
        self.match_on_index = 0
        
        try:
            mi = self.ts.dbMatch(0, 1)
            hdr = mi.next()
        except (TypeError, StopIteration), e:
            self.match_on_index = 0
        else:
            self.match_on_index = 1
            
        self.indexdict = {}
        
        mi = self.ts.dbMatch()
        for hdr in mi:
            pkgtuple = self._hdr2pkgTuple(hdr)
            if not self.indexdict.has_key(pkgtuple):
                self.indexdict[pkgtuple] = []
            else:
                continue
            self.indexdict[pkgtuple].append(mi.instance())
            self.pkglists.append(pkgtuple)
        del mi
        
    def _hdr2pkgTuple(self, hdr):
        name = hdr['name']
        arch = hdr['arch']
        ver = str(hdr['version']) # convert these to strings to be sure
        rel = str(hdr['release'])
        epoch = hdr['epoch']
        if epoch is None:
            epoch = '0'
        else:
            epoch = str(epoch)
    
        return (name, arch, epoch, ver, rel)
    
    def getPkgList(self):
        return self.pkglists
    
    def getHdrList(self):
        hdrlist = []
        mi = self.ts.dbMatch()
        if mi:
            for hdr in mi:
                hdrlist.append(hdr)

        del mi
        return hdrlist
            
    def getNameArchPkgList(self):
        lst = []
        for (name, arch, epoch, ver, rel) in self.pkglists:
            lst.append((name, arch))
        
        return miscutils.unique(lst)
        
        
    def getNamePkgList(self):
        lst = []
        for (name, arch, epoch, ver, rel) in self.pkglists:
            lst.append(name)
            
        return miscutils.unique(lst)

    def returnNewestbyNameArch(self):
        """returns the newest set of pkgs based on 'name and arch'"""
        highdict = {}
        for (n, a, e, v, r) in self.pkglists:
            if not highdict.has_key((n, a)):
                highdict[(n, a)] = (e, v, r)
            else:
                (e2, v2, r2) = highdict[(n, a)]
                rc = miscutils.compareEVR((e,v,r), (e2, v2, r2))
                if rc > 0:
                    highdict[(n, a)] = (e, v, r)
                    
        returns = []
        for (n, a) in highdict.keys():
            (e, v, r) = highdict[(n, a)]
            returns.append((n, a, e, v ,r))
            
        return returns
        
    def returnNewestbyName(self):
        """returns the newest set of pkgs based on name"""
        highdict = {}
        for (n, a, e, v, r) in self.pkglists:
            if not highdict.has_key(n):
                highdict[n] = (a, e, v, r)
            else:
                (a2, e2, v2, r2) = highdict[n]
                rc = miscutils.compareEVR((e,v,r), (e2, v2, r2))
                if rc > 0:
                    highdict[n] = (a, e, v, r)
                    
        returns = []
        for n in highdict.keys():
            (a, e, v, r) = highdict[n]
            returns.append((n, a, e, v ,r))
            
        return returns
    
    def installed(self, name=None, arch=None, epoch=None, ver=None, rel=None):
        if len(self.returnTupleByKeyword(name=name, arch=arch, epoch=epoch, ver=ver, rel=rel)) > 0:
            return 1
        return 0

    
    def returnTupleByKeyword(self, name=None, arch=None, epoch=None, ver=None, rel=None):
        """return a list of pkgtuples based on name, arch, epoch, ver and/or rel 
           matches."""
        
        completelist = self.getPkgList()
        removedict = {}
        returnlist = []
        
        for pkgtup in completelist:
            (n, a, e, v, r) = pkgtup
            if name is not None:
                if name != n:
                    removedict[pkgtup] = 1
                    continue
            if arch is not None:
                if arch != a:
                    removedict[pkgtup] = 1
                    continue
            if epoch is not None:
                if epoch != e:
                    removedict[pkgtup] = 1
                    continue
            if ver is not None:
                if ver != v:
                    removedict[pkgtup] = 1
                    continue
            if rel is not None:
                if rel != r:
                    removedict[pkgtup] = 1
                    continue
                    
        for pkgtup in completelist:
            if not removedict.has_key(pkgtup):
                returnlist.append(pkgtup)
        
        return returnlist

    def returnHeaderByTuple(self, pkgtuple):
        """returns a list of header(s) based on the pkgtuple provided"""
        (n, a, e, v, r) = pkgtuple
        
        if not self.match_on_index:
            lst = getHeadersByKeyword(self.ts, name=n, arch=a, epoch=e, version=v, 
                                  release=r)
            return lst
        else:
            idxs = self.returnIndexByTuple(pkgtuple)
            idx = idxs[0]
            mi = self.ts.dbMatch(0, idx)
            hdr = mi.next()
            return [hdr]

        
    def returnIndexByTuple(self, pkgtuple):
        return self.indexdict[pkgtuple]
    
    def whatProvides(self, provname, provflag, provver):
        """uses the ts in this class to return a list of pkgtuples that match
           the provide"""
        
        matches = []
        checkfileprov = 0
        
        if provname[0] == '/':
            checkfileprov = 1
            matchingFileHdrs = self.ts.dbMatch('basenames', provname)
            matchingHdrs = self.ts.dbMatch('provides', provname)            
        else:
            matchingHdrs = self.ts.dbMatch('provides', provname)

        # now we have the list of pkgs installed in the rpmdb that
        # have a the provname matching, now we need to find out
        # if any/all of them match the flag/ver set
        
        if checkfileprov and matchingFileHdrs.count() > 0:
            for matchhdr in matchingFileHdrs:
                pkgtuple = self._hdr2pkgTuple(matchhdr)
                matches.append(pkgtuple)
            del matchingFileHdrs
            return miscutils.unique(matches)

        if provflag in [0, None] or provver is None: # if we've got no ver or flag
                                                     # for comparison then they all match
            for matchhdr in matchingHdrs:
                pkgtuple = self._hdr2pkgTuple(matchhdr)
                matches.append(pkgtuple)
            del matchingHdrs
            return miscutils.unique(matches)
        
        for matchhdr in matchingHdrs:
            (pkg_n, pkg_a, pkg_e, pkg_v, pkg_r) = self._hdr2pkgTuple(matchhdr)
            pkgtuple = (pkg_n, pkg_a, pkg_e, pkg_v, pkg_r)
            # break the provver up into e-v-r (e:v-r)
            (prov_e, prov_v, prov_r) = miscutils.stringToVersion(provver)
            provtuple = (provname, provflag, (prov_e, prov_v, prov_r))
            # find the provide in the header 
            providelist = self._providesList(matchhdr)
            for (name, flag, ver) in providelist:
                if name != provname: # definitely not
                    continue

                match_n = name
                match_a = pkg_a # you got a better idea?
                if ver is not None:
                    (match_e, match_v, match_r) = miscutils.stringToVersion(ver)
                else:
                    match_e = pkg_e
                    match_v = pkg_v
                    match_r = pkg_r
                    
                matchtuple = (match_n, match_a, match_e, match_v, match_r)
                # This provides matches if the version is in the requested
                # range or the providing package provides the resource
                # without a version (meaning that it matches all EVR) 
                if miscutils.rangeCheck(provtuple, matchtuple) or (match_v == None):
                    matches.append(pkgtuple)
        del matchingHdrs
        return miscutils.unique(matches)
            
    def _providesList(self, hdr):
        lst = []
        names = hdr[rpm.RPMTAG_PROVIDENAME]
        flags = hdr[rpm.RPMTAG_PROVIDEFLAGS]
        vers = hdr[rpm.RPMTAG_PROVIDEVERSION]
        if names is not None:
            lst = zip(names, flags, vers)
        return miscutils.unique(lst)

