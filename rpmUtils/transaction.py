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
    	
        # list of flags to set for the transaction
        self.data['flags'] = []
        self.data['vsflags'] = []
        self.data['probFilterFlags'] = []


    def display(self):
        out = ""
        removed = []
        installed = []
        updated = []
        misc = []
        for (pkgInfo, mode) in self.data['packages']:
            if mode == 'u':
                updated.append(pkgInfo)
            elif mode == 'i':
                installed.append(pkgInfo)
            elif mode == 'e':
                removed.append(pkgInfo)
            else:
                misc.append(pkgInfo)

        for (n, a, e, v, r) in removed:
            out = out + "\t\t[e] %s-%s %s:%s-%s\n" % (n, a, e, v, r)

        for (n, a, e, v, r) in installed:
            out = out + "\t\t[i] %s-%s %s:%s-%s\n" % (n, a, e, v, r)        

        for (n, a, e, v, r) in updated:
            out = out + "\t\t[u] %s-%s %s:%s-%s\n" % (n, a, e, v, r)        

        for (n, a, e, v, r) in misc:
            out = out + "\t\t[wtf] %s-%s %s:%s-%s\n" % (n, a, e, v, r)                

        return out

    
# wrapper/proxy class for rpm.Transaction so we can
# instrument it, etc easily
class TransactionWrapper:
    def __init__(self):
        self.ts = rpm.TransactionSet()
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
                         'hdrFromFdno']
        self.tsflags = []

    def __getattr__(self, attr):
        if attr in self._methods:
            return self.getMethod(attr)
        else:
            raise AttributeError, attr

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
        
def initReadOnlyTransaction():
    global read_ts
    if read_ts == None:
        read_ts =  TransactionWrapper()
        # FIXME: replace with macro definition
        read_ts.pushVSFlags(-1)
    return read_ts

