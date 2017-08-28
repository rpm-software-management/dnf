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
from dnf.i18n import _, ucd
import dnf.transaction
import dnf.util
import rpm
import os
import logging
import sys
import tempfile
import traceback


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
    # per-package events
    PKG_CLEANUP = 1
    PKG_DOWNGRADE = 2
    PKG_ERASE = 3
    PKG_INSTALL = 4
    PKG_OBSOLETE = 5
    PKG_REINSTALL = 6
    PKG_UPGRADE = 7
    PKG_VERIFY = 8
    TRANS_PREPARATION = 9
    PKG_SCRIPTLET = 10
    # transaction-wide events
    TRANS_POST = 11

    ACTION_FROM_OP_TYPE = {
        dnf.transaction.DOWNGRADE : PKG_DOWNGRADE,
        dnf.transaction.ERASE     : PKG_ERASE,
        dnf.transaction.INSTALL   : PKG_INSTALL,
        dnf.transaction.REINSTALL : PKG_REINSTALL,
        dnf.transaction.UPGRADE   : PKG_UPGRADE
        }

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
        self.progress(pkg, self.PKG_VERIFY, 100, 100, count, total)


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
        self.action = {self.PKG_CLEANUP: _('Cleanup'),
                       self.PKG_DOWNGRADE: _('Downgrading'),
                       self.PKG_ERASE: _('Erasing'),
                       self.PKG_INSTALL: _('Installing'),
                       self.PKG_OBSOLETE: _('Obsoleting'),
                       self.PKG_REINSTALL: _('Reinstalling'),
                       self.PKG_UPGRADE: _('Upgrading'),
                       self.PKG_VERIFY: _('Verifying'),
                       self.TRANS_PREPARATION: _('Preparing'),
                       self.PKG_SCRIPTLET: _('Running scriptlet')}
        self.fileaction = {self.PKG_CLEANUP: 'Cleanup',
                           self.PKG_DOWNGRADE: 'Downgraded',
                           self.PKG_ERASE: 'Erased',
                           self.PKG_INSTALL: 'Installed',
                           self.PKG_OBSOLETE: 'Obsoleted',
                           self.PKG_REINSTALL: 'Reinstalled',
                           self.PKG_UPGRADE:  'Upgraded',
                           self.PKG_VERIFY: 'Verified',
                           self.TRANS_PREPARATION: 'Preparing',
                           self.PKG_SCRIPTLET: 'Running scriptlet'}
        self.rpm_logger = logging.getLogger('dnf.rpm')

    def error(self, message):
        super(LoggingTransactionDisplay, self).error(message)
        self.rpm_logger.error(message)

    def filelog(self, package, action):
        # If the action is not in the fileaction list then dump it as a string
        # hurky but, sadly, not much else
        process = self.fileaction[action]
        if process is None:
            return
        msg = '%s: %s' % (process, package)
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

        if isinstance(cbkey, dnf.transaction.TransactionItem):
            # Easy, tsi is provided by the callback (only happens on installs)
            return cbkey._active, cbkey._active_history_state, cbkey

        # We don't have the tsi, let's look it up (only happens on erasures)
        obsoleted = obsoleted_state = obsoleted_tsi = None
        if self._te_list == []:
            if isinstance(cbkey, str):
                obsoleted = cbkey
        else:
            te = self._te_list[self._te_index]
            te_nevra = dnf.util._te_nevra(te)
            for tsi in self.base.transaction:
                # only walk the tsis once. prefer finding an erase over an obsoleted
                # package:
                if tsi.erased is not None and str(tsi.erased) == te_nevra:
                    return tsi.erased, tsi._erased_history_state, tsi
                if tsi.installed is not None and str(tsi.installed) == te_nevra:
                    return tsi.installed, tsi._installed_history_state, tsi
                for o in tsi.obsoleted:
                    if str(o) == te_nevra:
                        obsoleted = o
                        obsoleted_state = tsi._obsoleted_history_state
                        obsoleted_tsi = tsi
        return obsoleted, obsoleted_state, obsoleted_tsi

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
                self._elemProgress(amount)
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
        action = TransactionDisplay.TRANS_PREPARATION
        for display in self.displays:
            display.progress('', action, amount + 1, total, 1, 1)

    def _elemProgress(self, index):
        self._te_index = index
        self.complete_actions += 1

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
        pkg, state, tsi = self._extract_cbkey(key)
        self.fd.close()
        self.fd = None

        if self.test or not self.trans_running:
            return

        action = TransactionDisplay.ACTION_FROM_OP_TYPE[tsi.op_type]
        for display in self.displays:
            display.filelog(pkg, action)
        self._scriptout()
        pid = self.base.history.pkg2pid(pkg)
        self.base.history.trans_data_pid_end(pid, state)

        if self.complete_actions == self.total_actions:
            # RPM doesn't explicitly report when post-trans phase starts
            action = TransactionDisplay.TRANS_POST
            for display in self.displays:
                display.progress(None, action, None, None, None, None)

    def _instProgress(self, amount, total, key):
        pkg, _, tsi = self._extract_cbkey(key)
        action = TransactionDisplay.ACTION_FROM_OP_TYPE[tsi.op_type]
        for display in self.displays:
            display.progress(
                pkg, action, amount, total, self.complete_actions,
                self.total_actions)

    def _uninst_start(self, key):
        self.total_removed += 1

    def _uninst_progress(self, amount, total, key):
        pkg, state, _ = self._extract_cbkey(key)
        if state == 'Obsoleted':
            action = TransactionDisplay.PKG_OBSOLETE
        elif state == 'Updated':
            action = TransactionDisplay.PKG_CLEANUP
        else:
            action = TransactionDisplay.PKG_ERASE
        for display in self.displays:
            display.progress(
                pkg, action, amount, total, self.complete_actions,
                self.total_actions)

    def _unInstStop(self, key):
        pkg, state, _ = self._extract_cbkey(key)
        if state == 'Obsoleted':
            action = TransactionDisplay.PKG_OBSOLETE
        elif state == 'Updated':
            action = TransactionDisplay.PKG_CLEANUP
        else:
            action = TransactionDisplay.PKG_ERASE
        for display in self.displays:
            display.filelog(pkg, action)

        if self.test:
            return

        if state is not None:
            self._scriptout()

            #  Note that we are currently inside the chroot, which makes
            # sqlite panic when it tries to open it's journal file.
            # So let's have some "fun" and workaround that:
            _do_chroot = False
            if _do_chroot and self.base.conf.installroot != '/':
                os.chroot(".")
            pid   = self.base.history.pkg2pid(pkg)
            self.base.history.trans_data_pid_end(pid, state)
            if _do_chroot and self.base.conf.installroot != '/':
                os.chroot(self.base.conf.installroot)
        else:
            self._scriptout()

    def _cpioError(self, key):
        # In the case of a remove, we only have a name, not a tsi:
        pkg, _, _ = self._extract_cbkey(key)
        msg = "Error in cpio payload of rpm package %s" % pkg
        for display in self.displays:
            display.error(msg)

    def _unpackError(self, key):
        pkg, _, _ = self._extract_cbkey(key)
        msg = "Error unpacking rpm package %s" % pkg
        for display in self.displays:
            display.error(msg)

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

        if total:
            msg = ("Error in %s scriptlet in rpm package %s" %
                   (scriptlet_name, name))
        else:
            msg = ("Non-fatal %s scriptlet failure in rpm package %s" %
                   (scriptlet_name, name))
        for display in self.displays:
            display.error(msg)

    def _script_start(self, key):
        action = TransactionDisplay.PKG_SCRIPTLET
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
