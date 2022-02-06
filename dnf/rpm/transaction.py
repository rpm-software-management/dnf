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

from __future__ import absolute_import
from __future__ import unicode_literals
from dnf.i18n import _
import logging
import rpm

_logger = logging.getLogger('dnf')
read_ts = None
ts = None

# wrapper/proxy class for rpm.Transaction so we can
# instrument it, etc easily
class TransactionWrapper(object):
    def __init__(self, root='/'):
        self.ts = rpm.TransactionSet(root)
        self._methods = ['check',
                         'order',
                         'addErase',
                         'addInstall',
                         'addReinstall',
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

    def dbCookie(self):
        # dbCookie() does not support lazy opening of rpm database.
        # The following line opens the database if it is not already open.
        if self.ts.openDB() != 0:
            _logger.error(_('The openDB() function cannot open rpm database.'))
            return ''

        cookie = self.ts.dbCookie()
        if not cookie:
            _logger.error(_('The dbCookie() function did not return cookie of rpm database.'))
            return ''

        return cookie

    def __getattr__(self, attr):
        if attr in self._methods:
            return self.getMethod(attr)
        else:
            raise AttributeError(attr)

    def __iter__(self):
        return self.ts

    def getMethod(self, method):
        # in theory, we can override this with
        # profile/etc info
        return getattr(self.ts, method)

    # push/pop methods so we don't lose the previous
    # set value, and we can potentially debug a bit
    # easier
    def pushVSFlags(self, flags):
        self.tsflags.append(flags)
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

    def test(self, cb, conf={}):
        """tests the ts we've setup, takes a callback function and a conf dict
           for flags and what not"""

        origflags = self.getTsFlags()
        self.addTsFlag(rpm.RPMTRANS_FLAG_TEST)
        # FIXME GARBAGE - remove once this is reimplemented elsewhere
        # KEEPING FOR API COMPLIANCE ONLY
        if conf.get('diskspacecheck') == 0:
            self.ts.setProbFilter(rpm.RPMPROB_FILTER_DISKSPACE)
        tserrors = self.ts.run(cb.callback, '')
        self.ts.setFlags(origflags)

        reserrors = []
        if tserrors is not None:
            for (descr, (etype, mount, need)) in tserrors:
                reserrors.append(descr)
            if not reserrors:
                reserrors.append(_('Errors occurred during test transaction.'))

        return reserrors

def initReadOnlyTransaction(root='/'):
    read_ts =  TransactionWrapper(root=root)
    read_ts.pushVSFlags((rpm._RPMVSF_NOSIGNATURES|rpm._RPMVSF_NODIGESTS))
    return read_ts
