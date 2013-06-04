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

from __future__ import print_function
import dnf.transaction
import rpm
import os
import fcntl
import time
import logging
import types
import sys
from constants import *
from i18n import _
import misc
import tempfile

class NoOutputCallBack:
    def __init__(self):
        pass

    def event(self, package, action, te_current, te_total, ts_current, ts_total):
        """
        @param package: A yum package object or simple string of a package name
        @param action: A constant transaction set state
        @param te_current: current number of bytes processed in the transaction
                           element being processed
        @param te_total: total number of bytes in the transaction element being
                         processed
        @param ts_current: number of processes completed in whole transaction
        @param ts_total: total number of processes in the transaction.
        """
        # this is where a progress bar would be called

        pass

    def scriptout(self, package, msgs):
        """package is the package.  msgs is the messages that were
        output (if any)."""
        pass

    def errorlog(self, msg):
        """takes a simple error msg string"""

        pass

    def filelog(self, package, action):
        # check package object type - if it is a string - just output it
        """package is the same as in event() - a package object or simple string
           action is also the same as in event()"""
        pass

    def verify_tsi_package(self, pkg, count, total):
        pass

class RPMBaseCallback:
    '''
    Base class for a RPMTransaction display callback class
    '''
    def __init__(self):
        self.action = {dnf.transaction.DOWNGRADE : _('Downgrading'),
                       dnf.transaction.ERASE : _('Erasing'),
                       dnf.transaction.INSTALL : _('Installing'),
                       dnf.transaction.REINSTALL : _('Reinstalling'),
                       dnf.transaction.UPGRADE :  _('Upgrading'),
                       'obsoleting' : _('Obsoleting'),
                       'cleanup' : _('Cleanup')}
        self.fileaction = {dnf.transaction.DOWNGRADE : 'Downgraded',
                           dnf.transaction.ERASE : 'Erased',
                           dnf.transaction.INSTALL : 'Installed',
                           dnf.transaction.REINSTALL : _('Reinstalled'),
                           dnf.transaction.UPGRADE :  'Upgraded',
                           'obsoleting' : 'Obsoleted',
                           'cleanup' : 'Cleanup'}
        self.logger = logging.getLogger("dnf.rpm")

    def event(self, package, action, te_current, te_total, ts_current, ts_total):
        """
        :param package: A yum package object or simple string of a package name
        :param action: A yum.constant transaction set state
        :param te_current: Current number of bytes processed in the transaction
          element being processed
        :param te_total: Total number of bytes in the transaction element being
          processed
        :param ts_current: number of processes completed in whole transaction
        :param ts_total: total number of processes in the transaction.
        """
        raise NotImplementedError()

    def scriptout(self, package, msgs):
        """package is the package.  msgs is the messages that were
        output (if any)."""
        pass

    def errorlog(self, msg):
        # FIXME this should probably dump to the filelog, too
        print(msg, file=sys.stderr)

    def filelog(self, package, action):
        # If the action is not in the fileaction list then dump it as a string
        # hurky but, sadly, not much else
        if action in self.fileaction:
            msg = '%s: %s' % (self.fileaction[action], package)
        else:
            msg = '%s: %s' % (package, action)
        self.logger.info(msg)

    def verify_tsi_package(self, pkg, count, total):
        pass

#  This is ugly, but atm. rpm can go insane and run the "cleanup" phase
# without the "install" phase if it gets an exception in it's callback. The
# following means that we don't really need to know/care about that in the
# display callback functions.
#  Note try/except's in RPMTransaction are for the same reason.
class _WrapNoExceptions:
    def __init__(self, parent):
        self.__parent = parent

    def __getattr__(self, name):
        """ Wraps all access to the parent functions. This is so it'll eat all
            exceptions because rpm doesn't like exceptions in the callback. """
        func = getattr(self.__parent, name)

        def newFunc(*args, **kwargs):
            try:
                func(*args, **kwargs)
            except Exception, e:
                # It's impossible to debug stuff without this:
                try:
                    print("Error:", "display callback failed:", e)
                except:
                    pass

        newFunc.__name__ = func.__name__
        newFunc.__doc__ = func.__doc__
        newFunc.__dict__.update(func.__dict__)
        return newFunc

class RPMTransaction:
    def __init__(self, base, test=False, display=NoOutputCallBack):
        if not callable(display):
            self.display = display
        else:
            self.display = display() # display callback
        self.display = _WrapNoExceptions(self.display)
        self.base = base # base yum object b/c we need so much
        self.test = test # are we a test?
        self.trans_running = False
        self.fd = None
        self.total_actions = 0
        self.total_installed = 0
        self.complete_actions = 0
        self.installed_pkg_names = set()
        self.total_removed = 0
        self.logger = logging.getLogger("dnf.rpm")
        self.filelog = False

        self._setupOutputLogging(base.conf.rpmverbosity)

    # Error checking? -- these should probably be where else
    def _fdSetNonblock(self, fd):
        """ Set the Non-blocking flag for a filedescriptor. """
        flag = os.O_NONBLOCK
        current_flags = fcntl.fcntl(fd, fcntl.F_GETFL)
        if current_flags & flag:
            return
        fcntl.fcntl(fd, fcntl.F_SETFL, current_flags | flag)

    def _fdSetCloseOnExec(self, fd):
        """ Set the close on exec. flag for a filedescriptor. """
        flag = fcntl.FD_CLOEXEC
        current_flags = fcntl.fcntl(fd, fcntl.F_GETFD)
        if current_flags & flag:
            return
        fcntl.fcntl(fd, fcntl.F_SETFD, current_flags | flag)

    def _setupOutputLogging(self, rpmverbosity="info"):
        # UGLY... set up the transaction to record output from scriptlets
        io_r = tempfile.NamedTemporaryFile()
        self._readpipe = io_r
        self._writepipe = open(io_r.name, 'w+b')
        self.base.ts.setScriptFd(self._writepipe)
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

    def _scriptout(self, data):
        msgs = self._scriptOutput()
        self.display.scriptout(data, msgs)
        self.base.history.log_scriptlet_output(data, msgs)

    def __del__(self):
        self._shutdownOutputLogging()

    def _extract_cbkey(self, cbkey):
        if isinstance(cbkey, dnf.transaction.TransactionItem):
            return self._extract_tsi_cbkey(cbkey)
        else:
            return self._extract_str_cbkey(cbkey)

    @staticmethod
    def _extract_tsi_cbkey(tsi):
        assert(isinstance(tsi, dnf.transaction.TransactionItem))
        return (tsi.active, tsi)

    def _extract_str_cbkey(self, name):
        assert(isinstance(name, basestring))
        obsoleted = obsoleted_tsi = None
        for tsi in self.base.transaction:
            # only walk the tsis once. prefer finding an erase over an obsoleted
            # package:
            if tsi.erased is not None and tsi.erased.name == name:
                return (tsi.erased, tsi)
            for o in tsi.obsoleted:
                if o.name == name:
                    obsoleted = o
                    obsoleted_tsi = tsi
        return (obsoleted, obsoleted_tsi)

    def _fn_rm_installroot(self, filename):
        """ Remove the installroot from the filename. """
        # to handle us being inside a chroot at this point
        # we hand back the right path to those 'outside' of the chroot() calls
        # but we're using the right path inside.
        if self.base.conf.installroot == '/':
            return filename

        return filename.replace(os.path.normpath(self.base.conf.installroot),'')

    def ts_done_open(self):
        """ Open the transaction done file, must be started outside the
            chroot. """

        if self.test: return False

        if hasattr(self, '_ts_done'):
            return True

        self.ts_done_fn = '%s/transaction-done.%s' % (self.base.conf.persistdir,
                                                      self._ts_time)
        ts_done_fn = self._fn_rm_installroot(self.ts_done_fn)

        try:
            self._ts_done = open(ts_done_fn, 'w')
        except (IOError, OSError), e:
            self.display.errorlog('could not open ts_done file: %s' % e)
            self._ts_done = None
            return False
        self._fdSetCloseOnExec(self._ts_done.fileno())
        return True

    def ts_done_write(self, msg):
        """ Write some data to the transaction done file. """
        if self._ts_done is None:
            return

        try:
            self._ts_done.write(msg)
            self._ts_done.flush()
        except (IOError, OSError), e:
            #  Having incomplete transactions is probably worse than having
            # nothing.
            self.display.errorlog('could not write to ts_done file: %s' % e)
            self._ts_done = None
            misc.unlink_f(self.ts_done_fn)

    def ts_done(self, package, action):
        """writes out the portions of the transaction which have completed"""

        if not self.ts_done_open(): return

        # walk back through self._te_tuples
        # make sure the package and the action make some kind of sense
        # write it out and pop(0) from the list

        # make sure we have a list to work from
        if len(self._te_tuples) == 0:
            # if we don't then this is pretrans or postrans or a trigger
            # either way we have to respond correctly so just return and don't
            # emit anything
            return

        (t,e,n,v,r,a) = self._te_tuples[0] # what we should be on

        # make sure we're in the right action state
        msg = 'ts_done state is %s %s should be %s %s' % (package, action, t, n)
        if action in TS_REMOVE_STATES:
            if t != 'erase':
                self.display.filelog(package, msg)
        if action in TS_INSTALL_STATES:
            if t != 'install':
                self.display.filelog(package, msg)

        # check the pkg name out to make sure it matches
        if type(package) in types.StringTypes:
            name = package
        else:
            name = package.name

        if n != name:
            msg = 'ts_done name in te is %s should be %s' % (n, package)
            self.display.filelog(package, msg)

        # hope springs eternal that this isn't wrong
        msg = '%s %s:%s-%s-%s.%s\n' % (t,e,n,v,r,a)

        self.ts_done_write(msg)
        self._te_tuples.pop(0)

    def ts_all(self):
        """write out what our transaction will do"""

        # save the transaction elements into a list so we can run across them
        if not hasattr(self, '_te_tuples'):
            self._te_tuples = []

        for te in self.base.ts:
            n = te.N()
            a = te.A()
            v = te.V()
            r = te.R()
            e = te.E()
            if e is None:
                e = '0'
            if te.Type() == 1:
                t = 'install'
            elif te.Type() == 2:
                t = 'erase'
            else:
                t = te.Type()

            # save this in a list
            self._te_tuples.append((t,e,n,v,r,a))

        # write to a file
        self._ts_time = time.strftime('%Y-%m-%d.%H:%M.%S')
        tsfn = '%s/transaction-all.%s' % (self.base.conf.persistdir, self._ts_time)
        self.ts_all_fn = tsfn
        tsfn = self._fn_rm_installroot(tsfn)

        try:
            if not os.path.exists(os.path.dirname(tsfn)):
                os.makedirs(os.path.dirname(tsfn)) # make the dir,
            fo = open(tsfn, 'w')
        except (IOError, OSError), e:
            self.display.errorlog('could not open ts_all file: %s' % e)
            self._ts_done = None
            return

        try:
            for (t,e,n,v,r,a) in self._te_tuples:
                msg = "%s %s:%s-%s-%s.%s\n" % (t,e,n,v,r,a)
                fo.write(msg)
            fo.flush()
            fo.close()
        except (IOError, OSError), e:
            #  Having incomplete transactions is probably worse than having
            # nothing.
            self.display.errorlog('could not write to ts_all file: %s' % e)
            misc.unlink_f(tsfn)
            self._ts_done = None

    def callback( self, what, bytes, total, h, user ):
        if what == rpm.RPMCALLBACK_TRANS_START:
            self._transStart( bytes, total, h )
        elif what == rpm.RPMCALLBACK_TRANS_PROGRESS:
            self._transProgress( bytes, total, h )
        elif what == rpm.RPMCALLBACK_TRANS_STOP:
            self._transStop( bytes, total, h )
        elif what == rpm.RPMCALLBACK_INST_OPEN_FILE:
            return self._instOpenFile( bytes, total, h )
        elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            self._instCloseFile(  bytes, total, h )
        elif what == rpm.RPMCALLBACK_INST_PROGRESS:
            self._instProgress( bytes, total, h )
        elif what == rpm.RPMCALLBACK_UNINST_START:
            self._unInstStart( bytes, total, h )
        elif what == rpm.RPMCALLBACK_UNINST_PROGRESS:
            self._unInstProgress( bytes, total, h )
        elif what == rpm.RPMCALLBACK_UNINST_STOP:
            self._unInstStop( bytes, total, h )
        elif what == rpm.RPMCALLBACK_CPIO_ERROR:
            self._cpioError(bytes, total, h)
        elif what == rpm.RPMCALLBACK_UNPACK_ERROR:
            self._unpackError(bytes, total, h)
        # SCRIPT_ERROR is only in rpm >= 4.6.0
        elif hasattr(rpm, "RPMCALLBACK_SCRIPT_ERROR") and what == rpm.RPMCALLBACK_SCRIPT_ERROR:
            self._scriptError(bytes, total, h)


    def _transStart(self, bytes, total, h):
        self.total_actions = total
        if self.test: return
        self.trans_running = True
        self.ts_all() # write out what transaction will do
        self.ts_done_open()

    def _transProgress(self, bytes, total, h):
        pass

    def _transStop(self, bytes, total, h):
        pass

    def _instOpenFile(self, bytes, total, h):
        self.lastmsg = None
        (pkg, tsi) = self._extract_tsi_cbkey(h)
        rpmloc = pkg.localPkg()
        try:
            self.fd = file(rpmloc)
        except IOError, e:
            self.display.errorlog("Error: Cannot open file %s: %s" % (rpmloc, e))
        else:
            if self.trans_running:
                self.total_installed += 1
                self.complete_actions += 1
                self.installed_pkg_names.add(pkg.name)
            return self.fd.fileno()

    def _instCloseFile(self, bytes, total, h):
        (pkg, tsi) = self._extract_tsi_cbkey(h)
        self.fd.close()
        self.fd = None
        if self.test:
            return
        if self.trans_running:
            self.display.filelog(pkg, tsi.op_type)
            self._scriptout(pkg)
            pid   = self.base.history.pkg2pid(pkg)
            state = tsi.history_state(pkg)
            self.base.history.trans_data_pid_end(pid, state)
            # :dead
            # self.ts_done(txmbr.po, txmbr.output_state)

    def _instProgress(self, bytes, total, h):
        (pkg, tsi) = self._extract_tsi_cbkey(h)
        self.display.event(pkg, tsi.op_type, bytes, total, self.complete_actions,
                           self.total_actions)

    def _unInstStart(self, bytes, total, h):
        pass

    def _unInstProgress(self, bytes, total, h):
        pass

    def _unInstStop(self, bytes, total, h):
        (pkg, tsi) = self._extract_str_cbkey(h)
        self.total_removed += 1
        self.complete_actions += 1
        if pkg in tsi.obsoleted:
            action = 'obsoleting'
        elif tsi.op_type == dnf.transaction.UPGRADE:
            action = 'cleanup'
        else:
            action = dnf.transaction.ERASE
        self.display.filelog(pkg, action)
        self.display.event(pkg, action, 100, 100, self.complete_actions,
                           self.total_actions)

        if self.test:
            return

        if tsi is not None:
            self._scriptout(pkg)

            #  Note that we are currently inside the chroot, which makes
            # sqlite panic when it tries to open it's journal file.
            # So let's have some "fun" and workaround that:
            _do_chroot = False
            if _do_chroot and self.base.conf.installroot != '/':
                os.chroot(".")
            pid   = self.base.history.pkg2pid(pkg)
            state = tsi.history_state(pkg)
            self.base.history.trans_data_pid_end(pid, state)
            if _do_chroot and self.base.conf.installroot != '/':
                os.chroot(self.base.conf.installroot)
            # :dead
            # self.ts_done(txmbr.po, txmbr.output_state)
        else:
            self._scriptout(name)
            # :dead
            # self.ts_done(name, action)

    def _cpioError(self, bytes, total, h):
        # In the case of a remove, we only have a name, not a tsi:
        pkg, _ = self._extract_cbkey(h)
        msg = "Error in cpio payload of rpm package %s" % pkg
        self.display.errorlog(msg)

    def _unpackError(self, bytes, total, h):
        pkg, _ = self._extract_cbkey(h)
        msg = "Error unpacking rpm package %s" % pkg
        self.display.errorlog(msg)

    def _scriptError(self, bytes, total, h):
        # "bytes" carries the failed scriptlet tag,
        # "total" carries fatal/non-fatal status
        scriptlet_name = rpm.tagnames.get(bytes, "<unknown>")

        pkg, _ = self._extract_cbkey(h)
        name = pkg.name

        if total:
            msg = ("Error in %s scriptlet in rpm package %s" %
                   (scriptlet_name, name))
        else:
            msg = ("Non-fatal %s scriptlet failure in rpm package %s" %
                   (scriptlet_name, name))
        self.display.errorlog(msg)

    def verify_tsi_package(self, pkg, count, total):
        self.display.verify_tsi_package(pkg, count, total)
