#!/usr/bin/python -tt

import rpm
import miscutils
import exceptions


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
    for keyword in kwargs.keys():
        mi.pattern(keyword, rpm.RPMMIRE_GLOB, kwargs[keyword])

    # we really shouldnt be getting multiples here, but what the heck
    for h in mi:
        #print "%s-%s-%s.%s" % ( h['name'], h['version'], h['release'], h['arch'])
        lst.append(h)
                                                                                                        
    return lst
        
def getIndexesByKeyword(ts, **kwargs):
    """return list of headers Indexes from the rpmdb matching a keyword
        ex: getHeadersByKeyword(name='foo', version='1', release='1')
    """
    lst = []
    mi = ts.dbMatch()
    for keyword in kwargs.keys():
        mi.pattern(keyword, rpm.RPMMIRE_GLOB, kwargs[keyword])

    # we really shouldnt be getting multiples here, but what the heck
    for h in mi:
        instance = mi.instance()
        lst.append(instance)
                                                                                                        
    return lst

class RpmDBHolder:
    def __init__(self):
        self.pkglists = []
        
    def addDB(self, ts):
        self.ts = ts
        mi = ts.dbMatch()
        if mi is not None:
            for hdr in mi:
                name = hdr['name']
                arch = hdr['arch']
                ver = str(hdr['version']) # convert these to strings to be sure
                rel = str(hdr['release'])
                epoch = hdr['epoch']
                if epoch is None:
                    epoch = '0'
                else:
                    epoch = str(epoch)
                    
                pkgtuple = (name, arch, epoch, ver, rel)                
                self.pkglists.append(pkgtuple)
                
    def getPkgList(self):
        return self.pkglists
        
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
        lst = getHeadersByKeyword(self.ts, name=n, arch=a, epoch=e, version=v, 
                                  release=r)
        return lst
        
        
