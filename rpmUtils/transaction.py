#!/usr/bin/python

#
# Client code for Update Agent
# Copyright (c) 1999-2002 Red Hat, Inc.  Distributed under GPL.
#
#         Adrian Likins <alikins@redhat.com>
# Some Edits by Seth Vidal <skvidal@phy.duke.edu>
#
# a couple of classes wrapping up transactions so that we  
#    can share transactions instead of creating new ones all over
#

import rpm
import miscutils

read_ts = None
ts = None


class TransactionData:
    # simple data structure designed to transport info
    # about rpm transactions around
    def __init__(self):
        self.data = {}
        # a list of tuples of pkginfo, and mode ('e', 'i', 'u')
        # the pkgInfo is tuple of (name, arch, epoch, version, release)
        # example self.data['packages'].append((pkginfo, mode))
        self.data['packages'] = []
        # stores the reason for the package being in the transaction set
        self.reason = {} # self.reason[pkgtup] = 'user', 'dep'
            # user = user requested
            # dep = deps
            # others? ....
        # list of flags to set for the transaction
        self.data['flags'] = []
        self.data['vsflags'] = []
        self.data['probFilterFlags'] = []

    def count(self):
        """returns count of packages in transaction holder"""
        return len(self.data['packages'])
    
    def getMode(self, name=None, arch=None, epoch=None, ver=None, rel=None):
        """give back the first mode that matches the keywords, return None for
           no match."""
        completelist = []
        removedict = {}
        returnlist = []
        
        for ((n,a,e,v,r), mode) in self.data['packages']:
            completelist.append((n,a,e,v,r))
        
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
        
        for matched in returnlist:
            for (pkgtup, mode) in self.data['packages']:
                if matched == pkgtup:
                    return mode

        return None
            
            
            
    def add(self, pkgtup, mode, reason='user'):
        """add a package to the transaction"""
        
        if (pkgtup, mode) not in self.data['packages']:
            self.data['packages'].append((pkgtup, mode))
            self.reason[pkgtup] = reason
            
    def remove(self, pkgtup):
        """remove a package from the transaction"""
        
        # we're iterating the list and not including
        # the pkgs matching pkgtup
        
        newlist = []
        for (tup, mode) in self.data['packages']:
            if pkgtup != tup:
                newlist.append((tup, mode))

        if self.reason.has_key(pkgtup):
            del self.reason[pkgtup]
            
        self.data['packages'] = newlist

    def changeMode(self, pkgtup, mode):
        reason = self.reason[pkgtup]
        self.remove(pkgtup)
        self.add(pkgtup, mode, reason)
        
    def dump(self):
        """returns a list of the (pkginfo, mode) tuples"""
        return self.data['packages']
    
    def makedict(self):
        """returns a dict of the self.dump()"""
        returndict = {}
        for (pkginfo, mode) in self.dump():
            returndict[pkginfo] = mode
        
        return returndict
        
    def makelists(self):
        """returns lists of packages based on mode:
           updated, installed, erased, obsoleted, depupdated, depinstalled
           deperased"""
           
        removed = []
        installed = []
        updated = []
        obsoleted = []
        depremoved = []
        depinstalled = []
        depupdated = []
        
        for (pkgInfo, mode) in self.dump():
            if mode == 'u':
                if self.reason[pkgInfo] == 'dep':
                    depupdated.append(pkgInfo)
                else:
                    updated.append(pkgInfo)
                    
            elif mode == 'i':
                if self.reason[pkgInfo] == 'dep':
                    depinstalled.append(pkgInfo)
                else:
                    installed.append(pkgInfo)
            
            elif mode == 'e':
                if self.reason[pkgInfo] == 'dep':
                    depremoved.append(pkgInfo)
                else:
                    removed.append(pkgInfo)
            elif mode == 'o':
                obsoleted.append(pkgInfo)
            else:
                pass
    
            updated.sort()
            installed.sort()
            removed.sort()
            obsoleted.sort()
            depupdated.sort()
            depinstalled.sort()
            depremoved.sort()

        return updated, installed, removed, obsoleted, depupdated, depinstalled, depremoved
        
    def display(self):
        out = ""
        removed = []
        installed = []
        updated = []
        misc = []
        obsoleted = []
        
        for (pkgInfo, mode) in self.data['packages']:
            if mode == 'u':
                updated.append(pkgInfo)
            elif mode == 'i':
                installed.append(pkgInfo)
            elif mode == 'e':
                removed.append(pkgInfo)
            elif mode == 'o':
                obsoleted.append(pkgInfo)
            else:
                misc.append(pkgInfo)

            misc.sort()
            updated.sort()
            installed.sort()
            removed.sort()
            obsoleted.sort()
            
        for (n, a, e, v, r) in removed:
            out = out + "\t\t[e] %s.%s %s:%s-%s - %s\n" % (n, a, e, v, r, self.reason[(n, a, e, v, r)])

        for (n, a, e, v, r) in installed:
            out = out + "\t\t[i] %s.%s %s:%s-%s - %s\n" % (n, a, e, v, r, self.reason[(n, a, e, v, r)])        

        for (n, a, e, v, r) in updated:
            out = out + "\t\t[u] %s.%s %s:%s-%s - %s\n" % (n, a, e, v, r, self.reason[(n, a, e, v, r)])        

        for (n, a, e, v, r) in obsoleted:
            out = out + "\t\t[o] %s.%s %s:%s-%s - %s\n" % (n, a, e, v, r, self.reason[(n, a, e, v, r)])

        for (n, a, e, v, r) in misc:
            out = out + "\t\t[wtf] %s.%s %s:%s-%s - %s\n" % (n, a, e, v, r, self.reason[(n, a, e, v, r)])                

        return out

    
# wrapper/proxy class for rpm.Transaction so we can
# instrument it, etc easily
class TransactionWrapper:
    def __init__(self, root='/'):
        self.ts = rpm.TransactionSet(root)
        self._methods = ['dbMatch',
                         'check',
                         'order',
                         'addErase',
                         'addInstall',
                         'run',
                         'IDTXload',
                         'IDTXglob',
                         'rollback',
                         'pgpImportPubkey',
                         'pgpPrtPkts',
                         'Debug',
                         'setFlags',
                         'setVSFlags',
                         'setProbFilter',
                         'hdrFromFdno',
                         'next',
                         'clean']
        self.tsflags = []

    def __getattr__(self, attr):
        if attr in self._methods:
            return self.getMethod(attr)
        else:
            raise AttributeError, attr

    def __iter__(self):
        return self.ts
        
    def getMethod(self, method):
        # in theory, we can override this with
        # profile/etc info
        return getattr(self.ts, method)

    # push/pop methods so we dont lose the previous
    # set value, and we can potentiall debug a bit
    # easier
    def pushVSFlags(self, flags):
        self.tsflags.append(flags)
        self.ts.setVSFlags(self.tsflags[-1])

    def popVSFlags(self):
        del self.tsflags[-1]
        self.ts.setVSFlags(self.tsflags[-1])

    def addTsFlag(self, flag):
        curflags = self.ts.setFlags(0)
        self.ts.setFlags(curflags | flag)
        
    def test(self, cb, conf={}):
        """tests the ts we've setup, takes a callback function and a conf dict 
           for flags and what not"""
        #FIXME
        # I don't like this function - it should test, sure - but not
        # with this conf dict, we should be doing that beforehand and
        # we should be packing this information away elsewhere.
        self.addTsFlag(rpm.RPMTRANS_FLAG_TEST)
        if conf.has_key('diskspacecheck'):
            if conf['diskspacecheck'] == 0:
                self.ts.setProbFilter(rpm.RPMPROB_FILTER_DISKSPACE)
    
        tserrors = self.ts.run(cb.callback, '')
    
        reserrors = []
        if tserrors:
            for (descr, (etype, mount, need)) in tserrors:
                reserrors.append(descr)
        
        return reserrors
            
        
    def returnLeafNodes(self):
        """returns a list of package tuples (n,a,e,v,r) that are not required by
           any other package on the system"""
        
        req = {}
        orphan = []
    
        mi = self.dbMatch()
        if mi is None: # this is REALLY unlikely but let's just say it for the moment
            return orphan    
            
        for h in mi:
            tup = miscutils.pkgTupleFromHeader(h)    
            if not h[rpm.RPMTAG_REQUIRENAME]:
                continue
            for r in h[rpm.RPMTAG_REQUIRENAME]:
                req[r] = tup
     
     
        mi = self.dbMatch()
        if mi is None:
            return orphan
     
        for h in mi:
            preq = 0
            tup = miscutils.pkgTupleFromHeader(h)
            for p in h[rpm.RPMTAG_PROVIDES] + h[rpm.RPMTAG_FILENAMES]:
                if req.has_key(p):
                    preq = preq + 1
        
            if preq == 0:
                orphan.append(tup)
        
        return orphan

        
def initReadOnlyTransaction(root='/'):
    #global read_ts
    #if read_ts == None:
    read_ts =  TransactionWrapper(root=root)
    read_ts.pushVSFlags((rpm._RPMVSF_NOSIGNATURES|rpm._RPMVSF_NODIGESTS))
    return read_ts

