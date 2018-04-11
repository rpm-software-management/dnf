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
import dnf.transaction
import dnf.util
import rpm
import os
import logging
import sys
import tempfile
import traceback


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

logger = logging.getLogger('dnf')


class TransactionDisplay(object):

    def __init__(self):
        pass

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
        """msgs is the messages that were output (if any)."""
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


class LoggingTransactionDisplay(ErrorTransactionDisplay):
    '''
    Base class for a RPMTransaction display callback class
    '''
    def __init__(self):
        super(LoggingTransactionDisplay, self).__init__()
        self.rpm_logger = logging.getLogger('dnf.rpm')

    def error(self, message):
        super(LoggingTransactionDisplay, self).error(message)
        self.rpm_logger.error(message)

    def filelog(self, package, action):
        action_str = dnf.transaction.FILE_ACTIONS[action]
        msg = '%s: %s' % (action_str, package)
        self.rpm_logger.info(msg)


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
        self.filelog = False

        self._setupOutputLogging(base.conf.rpmverbosity)
        self._te_list = []
        # Index in _te_list of the transaction element being processed (for use
        # in callbacks)
        self._te_index = 0

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
        # reset rpm bits from reording output
        rpm.setVerbosity(rpm.RPMLOG_NOTICE)
        rpm.setLogFile(sys.stderr)
        try:
            self._writepipe.close()
        except:
            pass

    def _scriptOutput(self):
        try:
            out = self._readpipe.read()
            if not out:
                return None
            return out
        except IOError:
            pass

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
            return tsi.pkg, tsi.action, tsi

        te = self._te_list[self._te_index]
        te_nevra = dnf.util._te_nevra(te)
        for tsi in self.base.transaction:
            if tsi.action == libdnf.transaction.TransactionItemAction_REINSTALL:
                # skip REINSTALL in order to return REINSTALLED
                continue
            if str(tsi) == te_nevra:
                return tsi.pkg, tsi.action, tsi

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
            _, _, tsi = self._extract_cbkey(key)
            for display in self.displays:
                display.filelog(tsi.pkg, tsi.action)

    def _instOpenFile(self, key):
        self.lastmsg = None
        pkg, _, _ = self._extract_cbkey(key)
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
        _, _, tsi = self._extract_cbkey(key)
        self.fd.close()
        self.fd = None

        if self.test or not self.trans_running:
            return

        if tsi.state == libdnf.transaction.TransactionItemState_UNKNOWN:
            tsi.state = libdnf.transaction.TransactionItemState_DONE

        for display in self.displays:
            display.filelog(tsi.pkg, tsi.action)
        self._scriptout()

        if self.complete_actions == self.total_actions:
            # RPM doesn't explicitly report when post-trans phase starts
            action = dnf.transaction.TRANS_POST
            for display in self.displays:
                display.progress(None, action, None, None, None, None)

    def _instProgress(self, amount, total, key):
        _, _, tsi = self._extract_cbkey(key)
        for display in self.displays:
            display.progress(
                tsi.pkg, tsi.action, amount, total, self.complete_actions,
                self.total_actions)

    def _uninst_start(self, key):
        self.total_removed += 1

    def _uninst_progress(self, amount, total, key):
        _, _, tsi = self._extract_cbkey(key)
        for display in self.displays:
            display.progress(
                tsi.pkg, tsi.action, amount, total, self.complete_actions,
                self.total_actions)

    def _unInstStop(self, key):
        _, _, tsi = self._extract_cbkey(key)

        if tsi.state == libdnf.transaction.TransactionItemState_UNKNOWN:
            tsi.state = libdnf.transaction.TransactionItemState_DONE

        for display in self.displays:
            display.filelog(tsi.pkg, tsi.action)

        if self.test:
            return

        self._scriptout()

    def _cpioError(self, key):
        # In the case of a remove, we only have a name, not a tsi:
        pkg, _, _ = self._extract_cbkey(key)
        msg = "Error in cpio payload of rpm package %s" % pkg
        for display in self.displays:
            display.error(msg)

    def _unpackError(self, key):
        pkg, _, tsi = self._extract_cbkey(key)
        msg = "Error unpacking rpm package %s" % pkg
        for display in self.displays:
            display.error(msg)
        tsi.state = libdnf.transaction.TransactionItemState_ERROR

    def _scriptError(self, amount, total, key):
        # "amount" carries the failed scriptlet tag,
        # "total" carries fatal/non-fatal status
        scriptlet_name = rpm.tagnames.get(amount, "<unknown>")

        pkg, _, _ = self._extract_cbkey(key)
        if pkg is not None:
            name = pkg.name
        elif dnf.util.is_string_type(key):
            name = key
        else:
            name = 'None'

        msg = ("Error in %s scriptlet in rpm package %s" % (scriptlet_name, name))

        for display in self.displays:
            display.error(msg)

    def _script_start(self, key):
        # TODO: this doesn't fit into libdnf TransactionItem use cases
        action = dnf.transaction.PKG_SCRIPTLET
        if key is None and self._te_list == []:
            pkg = 'None'
        else:
            pkg, _, _ = self._extract_cbkey(key)
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
