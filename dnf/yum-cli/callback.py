#!/usr/bin/python -t
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
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
# Copyright 2005 Duke University

"""
Progress display callback classes for the yum command line.
"""

import rpm
import os
import sys
import logging
from yum import _
from yum.constants import *


class RPMInstallCallback:
    """Yum command line callback class for callbacks from the RPM library."""

    def __init__(self, output=1):
        self.output = output
        self.callbackfilehandles = {}
        self.total_actions = 0
        self.total_installed = 0
        self.installed_pkg_names = []
        self.total_removed = 0
        self.mark = "#"
        self.marks = 27
        self.lastmsg = None
        self.logger = logging.getLogger('yum.filelogging.RPMInstallCallback')
        self.filelog = False

        self.myprocess = { TS_UPDATE : _('Updating'), 
                           TS_ERASE: _('Erasing'),
                           TS_INSTALL: _('Installing'), 
                           TS_TRUEINSTALL : _('Installing'),
                           TS_OBSOLETED: _('Obsoleted'),
                           TS_OBSOLETING: _('Installing')}
        self.mypostprocess = { TS_UPDATE: _('Updated'), 
                               TS_ERASE: _('Erased'),
                               TS_INSTALL: _('Installed'), 
                               TS_TRUEINSTALL: _('Installed'), 
                               TS_OBSOLETED: _('Obsoleted'),
                               TS_OBSOLETING: _('Installed')}

        self.tsInfo = None # this needs to be set for anything else to work

    def _dopkgtup(self, hdr):
        tmpepoch = hdr['epoch']
        if tmpepoch is None: epoch = '0'
        else: epoch = str(tmpepoch)

        return (hdr['name'], hdr['arch'], epoch, hdr['version'], hdr['release'])

    def _makeHandle(self, hdr):
        handle = '%s:%s.%s-%s-%s' % (hdr['epoch'], hdr['name'], hdr['version'],
          hdr['release'], hdr['arch'])

        return handle

    def _localprint(self, msg):
        if self.output:
            print msg

    def _makefmt(self, percent, progress = True):
        l = len(str(self.total_actions))
        size = "%s.%s" % (l, l)
        fmt_done = "[%" + size + "s/%" + size + "s]"
        done = fmt_done % (self.total_installed + self.total_removed,
                           self.total_actions)
        marks = self.marks - (2 * l)
        width = "%s.%s" % (marks, marks)
        fmt_bar = "%-" + width + "s"
        if progress:
            bar = fmt_bar % (self.mark * int(marks * (percent / 100.0)), )
            fmt = "\r  %-10.10s: %-28.28s " + bar + " " + done
        else:
            bar = fmt_bar % (self.mark * marks, )
            fmt = "  %-10.10s: %-28.28s "  + bar + " " + done
        return fmt

    def _logPkgString(self, hdr):
        """return nice representation of the package for the log"""
        (n,a,e,v,r) = self._dopkgtup(hdr)
        if e == '0':
            pkg = '%s.%s %s-%s' % (n, a, v, r)
        else:
            pkg = '%s.%s %s:%s-%s' % (n, a, e, v, r)

        return pkg

    def callback(self, what, bytes, total, h, user):
        """Handle callbacks from the RPM library.

        :param what: number identifying the type of callback
        :param bytes: the number of bytes associated with the
           callback; the exact meaning depends on the type of 
           the callback.  For example, for a RPMCALLBACK_INST_PROGRESS
           callback, bytes will represent the current amount of work done
        :param total: the total amount of work associated with the
           callback; the exact meaning depends on the type of the
           callback. For example, *total* may represent the total
           number of transactions in a transaction set
        :param h: a package object or string identifying the package
           involved in the callback
        :param user: unused
        """
        if what == rpm.RPMCALLBACK_TRANS_START:
            if bytes == 6:
                self.total_actions = total

        elif what == rpm.RPMCALLBACK_TRANS_PROGRESS:
            pass

        elif what == rpm.RPMCALLBACK_TRANS_STOP:
            pass

        elif what == rpm.RPMCALLBACK_INST_OPEN_FILE:
            self.lastmsg = None
            hdr = None
            if h is not None:
                hdr, rpmloc = h
                handle = self._makeHandle(hdr)
                fd = os.open(rpmloc, os.O_RDONLY)
                self.callbackfilehandles[handle]=fd
                self.total_installed += 1
                self.installed_pkg_names.append(hdr['name'])
                return fd
            else:
                self._localprint(_("No header - huh?"))

        elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            hdr = None
            if h is not None:
                hdr, rpmloc = h
                handle = self._makeHandle(hdr)
                os.close(self.callbackfilehandles[handle])
                fd = 0

                # log stuff
                pkgtup = self._dopkgtup(hdr)
                
                txmbrs = self.tsInfo.getMembers(pkgtup=pkgtup)
                for txmbr in txmbrs:
                    try:
                        process = self.myprocess[txmbr.output_state]
                        processed = self.mypostprocess[txmbr.output_state]
                    except KeyError:
                        pass

                    if self.filelog:
                        pkgrep = self._logPkgString(hdr)
                        msg = '%s: %s' % (processed, pkgrep)
                        self.logger.info(msg)


        elif what == rpm.RPMCALLBACK_INST_PROGRESS:
            if h is not None:
                # If h is a string, we're repackaging.
                # Why the RPMCALLBACK_REPACKAGE_PROGRESS flag isn't set, I have no idea
                if type(h) == type(""):
                    if total == 0:
                        percent = 0
                    else:
                        percent = (bytes*100L)/total
                    if self.output and sys.stdout.isatty():
                        fmt = self._makefmt(percent)
                        msg = fmt % (_('Repackage'), h)
                        if bytes == total:
                            msg = msg + "\n"

                        if msg != self.lastmsg:
                            sys.stdout.write(msg)
                            sys.stdout.flush()
                            self.lastmsg = msg
                else:
                    hdr, rpmloc = h
                    if total == 0:
                        percent = 0
                    else:
                        percent = (bytes*100L)/total
                    pkgtup = self._dopkgtup(hdr)
                    
                    txmbrs = self.tsInfo.getMembers(pkgtup=pkgtup)
                    for txmbr in txmbrs:
                        try:
                            process = self.myprocess[txmbr.output_state]
                        except KeyError, e:
                            print _("Error: invalid output state: %s for %s") % \
                               (txmbr.output_state, hdr['name'])
                        else:
                            if self.output and (sys.stdout.isatty() or bytes == total):
                                fmt = self._makefmt(percent)
                                msg = fmt % (process, hdr['name'])
                                if msg != self.lastmsg:
                                    sys.stdout.write(msg)
                                    sys.stdout.flush()
                                    self.lastmsg = msg
                                if bytes == total:
                                    print " "


        elif what == rpm.RPMCALLBACK_UNINST_START:
            pass

        elif what == rpm.RPMCALLBACK_UNINST_PROGRESS:
            pass

        elif what == rpm.RPMCALLBACK_UNINST_STOP:
            self.total_removed += 1
            if self.filelog and h not in self.installed_pkg_names:
                logmsg = _('Erased: %s' % (h))
                self.logger.info(logmsg)
            
            if self.output and sys.stdout.isatty():
                if h not in self.installed_pkg_names:
                    process = _("Removing")
                else:
                    process = _("Cleanup")
                percent = 100
                fmt = self._makefmt(percent, False)
                msg = fmt % (process, h)
                sys.stdout.write(msg + "\n")
                sys.stdout.flush()

        elif what == rpm.RPMCALLBACK_REPACKAGE_START:
            pass
        elif what == rpm.RPMCALLBACK_REPACKAGE_STOP:
            pass
        elif what == rpm.RPMCALLBACK_REPACKAGE_PROGRESS:
            pass

