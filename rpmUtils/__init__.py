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
                ver = hdr['version']
                rel = hdr['release']
                epoch = hdr['epoch']
                if epoch is None:
                    epoch = '0'

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
    
        
