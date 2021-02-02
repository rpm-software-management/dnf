# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# Copyright 2005 Duke University
# Parts Copyright 2007 Red Hat, Inc

from __future__ import print_function, absolute_import
from __future__ import unicode_literals

import libdnf.transaction

from dnf.i18n import _, ucd
import dnf.callback
import dnf.transaction
import dnf.util
import rpm
import os
import logging
import sys
import tempfile
import traceback
import warnings


# TODO: merge w/ libdnf
# transaction set states
TS_UPDATE = 10
TS_INSTALL = 20
TS_ERASE = 40
TS_OBSOLETED = 50
TS_OBSOLETING = 60
TS_AVAILABLE = 70
TS_UPDATED = 90
TS_FAILED = 100

TS_INSTALL_STATES = [TS_INSTALL, TS_UPDATE, TS_OBSOLETING]
TS_REMOVE_STATES = [TS_ERASE, TS_OBSOLETED, TS_UPDATED]

RPM_ACTIONS_SET = {libdnf.transaction.TransactionItemAction_INSTALL,
                   libdnf.transaction.TransactionItemAction_DOWNGRADE,
                   libdnf.transaction.TransactionItemAction_DOWNGRADED,
                   libdnf.transaction.TransactionItemAction_OBSOLETE,
                   libdnf.transaction.TransactionItemAction_OBSOLETED,
                   libdnf.transaction.TransactionItemAction_UPGRADE,
                   libdnf.transaction.TransactionItemAction_UPGRADED,
                   libdnf.transaction.TransactionItemAction_REMOVE,
                   libdnf.transaction.TransactionItemAction_REINSTALLED}

logger = logging.getLogger('dnf')


def _add_deprecated_action(name):
    """
    Wrapper to return a deprecated action constant
    while printing a deprecation warning.
    """
    @property
    def _func(self):
        msg = "%s.%s is deprecated. Use dnf.callback.%s instead." \
            % (self.__class__.__name__, name, name)
        warnings.warn(msg, DeprecationWarning, stacklevel=2)
        value = getattr(dnf.callback, name)
        return value
    return _func


class TransactionDisplay(object):
    # :api

    def __init__(self):
        # :api
        pass

    # use constants from dnf.callback which are the official API
    PKG_CLEANUP = _add_deprecated_action("PKG_CLEANUP")
    PKG_DOWNGRADE = _add_deprecated_action("PKG_DOWNGRADE")
    PKG_REMOVE = _add_deprecated_action("PKG_REMOVE")
    PKG_ERASE = PKG_REMOVE
    PKG_INSTALL = _add_deprecated_action("PKG_INSTALL")
    PKG_OBSOLETE = _add_deprecated_action("PKG_OBSOLETE")
    PKG_REINSTALL = _add_deprecated_action("PKG_REINSTALL")
    PKG_UPGRADE = _add_deprecated_action("PKG_UPGRADE")
    PKG_VERIFY = _add_deprecated_action("PKG_VERIFY")
    TRANS_PREPARATION = _add_deprecated_action("TRANS_PREPARATION")
    PKG_SCRIPTLET = _add_deprecated_action("PKG_SCRIPTLET")
    TRANS_POST = _add_deprecated_action("TRANS_POST")

    def progress(self, package, action, ti_done, ti_total, ts_done, ts_total):
        """Report ongoing progress on a transaction item. :api

        :param package: a package being processed
        :param action: the action being performed
        :param ti_done: number of processed bytes of the transaction
           item being processed
        :param ti_total: total number of bytes of the transaction item
           being processed
        :param ts_done: number of actions processed in the whole
           transaction
        :param ts_total: total number of actions in the whole
           transaction

        """
        pass

    def scriptout(self, msgs):
        """Hook for reporting an rpm scriptlet output.

        :param msgs: the scriptlet output
        """
        pass

    def error(self, message):
        """Report an error that occurred during the transaction. :api"""
        pass

    def filelog(self, package, action):
        # check package object type - if it is a string - just output it
        """package is the same as in progress() - a package object or simple
           string action is also the same as in progress()"""
        pass

    def verify_tsi_package(self, pkg, count, total):
        # TODO: replace with verify_tsi?
        self.progress(pkg, dnf.transaction.PKG_VERIFY, 100, 100, count, total)


class ErrorTransactionDisplay(TransactionDisplay):

    """An RPMTransaction display that prints errors to standard output."""

    def error(self, message):
        super(ErrorTransactionDisplay, self).error(message)
        dnf.util._terminal_messenger('print', message, sys.stderr)


class LoggingTransactionDisplay(TransactionDisplay):
    '''
    Base class for a RPMTransaction display callback class
    '''
    def __init__(self):
        super(LoggingTransactionDisplay, self).__init__()
        self.rpm_logger = logging.getLogger('dnf.rpm')

    def error(self, message):
        self.rpm_logger.error(message)

    def filelog(self, package, action):
        action_str = dnf.transaction.FILE_ACTIONS[action]
        msg = '%s: %s' % (action_str, package)
        self.rpm_logger.log(dnf.logging.SUBDEBUG, msg)

    def scriptout(self, msgs):
        if msgs:
            self.rpm_logger.info(ucd(msgs))


class RPMTransaction(object):
    def __init__(self, base, test=False, displays=()):
        if not displays:
            displays = [ErrorTransactionDisplay()]
        self.displays = displays
        self.base = base
        self.test = test  # are we a test?
        self.trans_running = False
        self.fd = None
        self.total_actions = 0
        self.total_installed = 0
        self.complete_actions = 0
        self.installed_pkg_names = set()
        self.total_removed = 0

        self._setupOutputLogging(base.conf.rpmverbosity)
        self._te_list = []
        # Index in _te_list of the transaction element being processed (for use
        # in callbacks)
        self._te_index = 0
        self._tsi_cache = None

    def _setupOutputLogging(self, rpmverbosity="info"):
        # UGLY... set up the transaction to record output from scriptlets
        io_r = tempfile.NamedTemporaryFile()
        self._readpipe = io_r
        self._writepipe = open(io_r.name, 'w+b')
        self.base._ts.setScriptFd(self._writepipe)
        rpmverbosity = {'critical' : 'crit',
                        'emergency' : 'emerg',
                        'error' : 'err',
                        'information' : 'info',
                        'warn' : 'warning'}.get(rpmverbosity, rpmverbosity)
        rpmverbosity = 'RPMLOG_' + rpmverbosity.upper()
        if not hasattr(rpm, rpmverbosity):
            rpmverbosity = 'RPMLOG_INFO'
        rpm.setVerbosity(getattr(rpm, rpmverbosity))
        rpm.setLogFile(self._writepipe)

    def _shutdownOutputLogging(self):
        # reset rpm bits from recording output
        rpm.setVerbosity(rpm.RPMLOG_NOTICE)
        rpm.setLogFile(sys.stderr)
        try:
            self._writepipe.close()
        except:
            pass

    def _scriptOutput(self):
        try:
            # XXX ugly workaround of problem which started after upgrading glibc
            # from glibc-2.27-32.fc28.x86_64 to glibc-2.28-9.fc29.x86_64
            # After this upgrade nothing is read from _readpipe, so every
            # posttrans and postun scriptlet output is lost. The problem
            # only occurs when using dnf-2, dnf-3 is OK.
            # I did not find the root cause of this error yet.
            self._readpipe.seek(self._readpipe.tell())
            out = self._readpipe.read()
            if not out:
                return None
            return out
        except IOError:
            pass

    def messages(self):
        messages = self._scriptOutput()
        if messages:
            for line in messages.splitlines():
                yield ucd(line)

    def _scriptout(self):
        msgs = self._scriptOutput()
        for display in self.displays:
            display.scriptout(msgs)
        self.base.history.log_scriptlet_output(msgs)

    def __del__(self):
        self._shutdownOutputLogging()

    def _extract_cbkey(self, cbkey):
        """Obtain the package related to the calling callback."""

        if hasattr(cbkey, "pkg"):
            tsi = cbkey
            return [tsi]

        te = self._te_list[self._te_index]
        te_nevra = dnf.util._te_nevra(te)
        if self._tsi_cache:
            if str(self._tsi_cache[0]) == te_nevra:
                return self._tsi_cache
        items = []
        for tsi in self.base.transaction:
            if tsi.action not in RPM_ACTIONS_SET:
                # skip REINSTALL in order to return REINSTALLED, or REASON_CHANGE to avoid crash
                continue
            if str(tsi) == te_nevra:
                items.append(tsi)
        if items:
            self._tsi_cache = items
            return items
        raise RuntimeError("TransactionItem not found for key: %s" % cbkey)

    def callback(self, what, amount, total, key, client_data):
        try:
            if isinstance(key, str):
                key = ucd(key)
            if what == rpm.RPMCALLBACK_TRANS_START:
                self._transStart(total)
            elif what == rpm.RPMCALLBACK_TRANS_STOP:
                pass
            elif what == rpm.RPMCALLBACK_TRANS_PROGRESS:
                self._trans_progress(amount, total)
            elif what == rpm.RPMCALLBACK_ELEM_PROGRESS:
                # This callback type is issued every time the next transaction
                # element is about to be processed by RPM, before any other
                # callbacks are issued.  "amount" carries the index of the element.
                self._elemProgress(key, amount)
            elif what == rpm.RPMCALLBACK_INST_OPEN_FILE:
                return self._instOpenFile(key)
            elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
                self._instCloseFile(key)
            elif what == rpm.RPMCALLBACK_INST_START:
                self._inst_start(key)
            elif what == rpm.RPMCALLBACK_INST_STOP:
                self._inst_stop(key)
            elif what == rpm.RPMCALLBACK_INST_PROGRESS:
                self._instProgress(amount, total, key)
            elif what == rpm.RPMCALLBACK_UNINST_START:
                self._uninst_start(key)
            elif what == rpm.RPMCALLBACK_UNINST_STOP:
                self._unInstStop(key)
            elif what == rpm.RPMCALLBACK_UNINST_PROGRESS:
                self._uninst_progress(amount, total, key)
            elif what == rpm.RPMCALLBACK_CPIO_ERROR:
                self._cpioError(key)
            elif what == rpm.RPMCALLBACK_UNPACK_ERROR:
                self._unpackError(key)
            elif what == rpm.RPMCALLBACK_SCRIPT_ERROR:
                self._scriptError(amount, total, key)
            elif what == rpm.RPMCALLBACK_SCRIPT_START:
                self._script_start(key)
            elif what == rpm.RPMCALLBACK_SCRIPT_STOP:
                self._scriptStop()
        except Exception:
            exc_type, exc_value, exc_traceback = sys.exc_info()
            except_list = traceback.format_exception(exc_type, exc_value, exc_traceback)
            logger.critical(''.join(except_list))

    def _transStart(self, total):
        self.total_actions = total
        if self.test: return
        self.trans_running = True
        self._te_list = list(self.base._ts)

    def _trans_progress(self, amount, total):
        action = dnf.transaction.TRANS_PREPARATION
        for display in self.displays:
            display.progress('', action, amount + 1, total, 1, 1)

    def _elemProgress(self, key, index):
        self._te_index = index
        self.complete_actions += 1
        if not self.test:
            transaction_list = self._extract_cbkey(key)
            for display in self.displays:
                display.filelog(transaction_list[0].pkg, transaction_list[0].action)

    def _instOpenFile(self, key):
        self.lastmsg = None
        transaction_list = self._extract_cbkey(key)
        pkg = transaction_list[0].pkg
        rpmloc = pkg.localPkg()
        try:
            self.fd = open(rpmloc)
        except IOError as e:
            for display in self.displays:
                display.error("Error: Cannot open file %s: %s" % (rpmloc, e))
        else:
            if self.trans_running:
                self.total_installed += 1
                self.installed_pkg_names.add(pkg.name)
            return self.fd.fileno()

    def _instCloseFile(self, key):
        self.fd.close()
        self.fd = None

    def _inst_start(self, key):
        pass

    def _inst_stop(self, key):
        if self.test or not self.trans_running:
            return

        self._scriptout()

        if self.complete_actions == self.total_actions:
            # RPM doesn't explicitly report when post-trans phase starts
            action = dnf.transaction.TRANS_POST
            for display in self.displays:
                display.progress(None, action, None, None, None, None)

    def _instProgress(self, amount, total, key):
        transaction_list = self._extract_cbkey(key)
        pkg = transaction_list[0].pkg
        action = transaction_list[0].action
        for display in self.displays:
            display.progress(pkg, action, amount, total, self.complete_actions, self.total_actions)

    def _uninst_start(self, key):
        self.total_removed += 1

    def _uninst_progress(self, amount, total, key):
        transaction_list = self._extract_cbkey(key)
        pkg = transaction_list[0].pkg
        action = transaction_list[0].action
        for display in self.displays:
            display.progress(pkg, action, amount, total, self.complete_actions, self.total_actions)

    def _unInstStop(self, key):
        if self.test:
            return

        self._scriptout()

    def _cpioError(self, key):
        transaction_list = self._extract_cbkey(key)
        msg = "Error in cpio payload of rpm package %s" % transaction_list[0].pkg
        for display in self.displays:
            display.error(msg)

    def _unpackError(self, key):
        transaction_list = self._extract_cbkey(key)
        msg = "Error unpacking rpm package %s" % transaction_list[0].pkg
        for display in self.displays:
            display.error(msg)

    def _scriptError(self, amount, total, key):
        # "amount" carries the failed scriptlet tag,
        # "total" carries fatal/non-fatal status
        scriptlet_name = rpm.tagnames.get(amount, "<unknown>")

        transaction_list = self._extract_cbkey(key)
        name = transaction_list[0].pkg.name

        msg = ("Error in %s scriptlet in rpm package %s" % (scriptlet_name, name))

        for display in self.displays:
            display.error(msg)

    def _script_start(self, key):
        # TODO: this doesn't fit into libdnf TransactionItem use cases
        action = dnf.transaction.PKG_SCRIPTLET
        if key is None and self._te_list == []:
            pkg = 'None'
        else:
            transaction_list = self._extract_cbkey(key)
            pkg = transaction_list[0].pkg
        complete = self.complete_actions if self.total_actions != 0 and self.complete_actions != 0 \
            else 1
        total = self.total_actions if self.total_actions != 0 and self.complete_actions != 0 else 1
        for display in self.displays:
            display.progress(pkg, action, 100, 100, complete, total)

    def _scriptStop(self):
        self._scriptout()

    def verify_tsi_package(self, pkg, count, total):
        for display in self.displays:
            display.verify_tsi_package(pkg, count, total)
