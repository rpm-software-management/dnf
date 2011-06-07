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
        self._methods = ['check',
                         'order',
                         'addErase',
                         'addInstall',
                         'run',
                         'pgpImportPubkey',
                         'pgpPrtPkts',
                         'problems',
                         'setFlags',
                         'setVSFlags',
                         'setProbFilter',
                         'hdrFromFdno',
                         'next',
                         'clean']
        self.tsflags = []
        self.open = True

    def __del__(self):
        # Automatically close the rpm transaction when the reference is lost
        self.close()

    def close(self):
        if self.open:
            self.ts.closeDB()
            self.ts = None
            self.open = False

    def dbMatch(self, *args, **kwds):
        if 'patterns' in kwds:
            patterns = kwds.pop('patterns')
        else:
            patterns = []

        mi = self.ts.dbMatch(*args, **kwds)
        for (tag, tp, pat) in patterns:
            mi.pattern(tag, tp, pat)
        return mi

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

    def getTsFlags(self):
        curflags = self.ts.setFlags(0)
        self.ts.setFlags(curflags)
        return curflags
    
    def isTsFlagSet(self, flag):
        val = self.getTsFlags()
        return bool(flag & val)

    def setScriptFd(self, fd):
        self.ts.scriptFd = fd.fileno()
        
#    def addProblemFilter(self, filt):
#        curfilter = self.ts.setProbFilter(0)
#        self.ts.setProbFilter(cutfilter | filt)    
        
    def test(self, cb, conf={}):
        """tests the ts we've setup, takes a callback function and a conf dict 
           for flags and what not"""
    
        origflags = self.getTsFlags()
        self.addTsFlag(rpm.RPMTRANS_FLAG_TEST)
        # FIXME GARBAGE - remove once this is reimplemented elsehwere
        # KEEPING FOR API COMPLIANCE ONLY
        if conf.get('diskspacecheck') == 0:
            self.ts.setProbFilter(rpm.RPMPROB_FILTER_DISKSPACE)
        tserrors = self.ts.run(cb.callback, '')
        self.ts.setFlags(origflags)
    
        reserrors = []
        if tserrors:
            for (descr, (etype, mount, need)) in tserrors:
                reserrors.append(descr)
        
        return reserrors
            
        
    def returnLeafNodes(self, headers=False):
        """returns a list of package tuples (n,a,e,v,r) that are not required by
           any other package on the system
           If headers is True then it will return a list of (header, index) tuples
           """
        
        req = {}
        orphan = []
    
        mi = self.dbMatch()
        if mi is None: # this is REALLY unlikely but let's just say it for the moment
            return orphan    
            
        # prebuild the req dict
        for h in mi:
            if h['name'] == 'gpg-pubkey':
                continue
            if not h[rpm.RPMTAG_REQUIRENAME]:
                continue
            tup = miscutils.pkgTupleFromHeader(h)    
            for r in h[rpm.RPMTAG_REQUIRENAME]:
                if r not in req:
                    req[r] = set()
                req[r].add(tup)
     
     
        mi = self.dbMatch()
        if mi is None:
            return orphan

        def _return_all_provides(hdr):
            """ Return all the provides, via yield. """
            # These are done one by one, so that we get lazy loading
            for prov in hdr[rpm.RPMTAG_PROVIDES]:
                yield prov
            for prov in hdr[rpm.RPMTAG_FILENAMES]:
                yield prov

        for h in mi:
            if h['name'] == 'gpg-pubkey':
                continue
            preq = 0
            tup = miscutils.pkgTupleFromHeader(h)
            for p in _return_all_provides(h):
                if p in req:
                    # Don't count a package that provides its require
                    s = req[p]
                    if len(s) > 1 or tup not in s:
                        preq = preq + 1
                        break

            if preq == 0:
                if headers:
                    orphan.append((h, mi.instance()))
                else:
                    orphan.append(tup)
        
        return orphan

        
def initReadOnlyTransaction(root='/'):
    read_ts =  TransactionWrapper(root=root)
    read_ts.pushVSFlags((rpm._RPMVSF_NOSIGNATURES|rpm._RPMVSF_NODIGESTS))
    return read_ts

