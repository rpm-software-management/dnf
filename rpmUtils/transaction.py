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
    read_ts =  TransactionWrapper(root=root)
    read_ts.pushVSFlags((rpm._RPMVSF_NOSIGNATURES|rpm._RPMVSF_NODIGESTS))
    return read_ts

