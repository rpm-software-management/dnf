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


import rpm
import os
import sys

from i18n import _

class RPMInstallCallback:
    def __init__(self, output=1):
        self.output = output
        self.callbackfilehandles = {}
        self.total_actions = 0
        self.total_installed = 0
        self.installed_pkg_names = []
        self.total_removed = 0
        self.mark = "#"
        self.marks = 27
        self.filelog = None

        self.myprocess = { 'updating': 'Updating', 'erasing': 'Erasing',
                           'installing': 'Installing', 'obsoleted': 'Obsoleted',
                           'obsoleting': 'Installing'}
        self.mypostprocess = { 'updating': 'Updated', 'erasing': 'Erased',
                               'installing': 'Installed', 'obsoleted': 'Obsoleted',
                               'obsoleting': 'Installed'}

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
        if what == rpm.RPMCALLBACK_TRANS_START:
            if bytes == 6:
                self.total_actions = total

        elif what == rpm.RPMCALLBACK_TRANS_PROGRESS:
            pass

        elif what == rpm.RPMCALLBACK_TRANS_STOP:
            pass

        elif what == rpm.RPMCALLBACK_INST_OPEN_FILE:
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
                txmbr = self.tsInfo.getMembers(pkgtup=pkgtup)[0] # if we have more than one I'll eat my hat
                try:
                    process = self.myprocess[txmbr.output_state]
                    processed = self.mypostprocess[txmbr.output_state]
                except KeyError, e:
                    pass

                if self.filelog:
                    pkgrep = self._logPkgString(hdr)
                    msg = '%s: %s' % (processed, pkgrep)
                    self.filelog(0, msg)


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
                        msg = fmt % ('Repackage', h)
                        if bytes == total:
                            msg = msg + "\n"
                            
                        sys.stdout.write(msg)
                        sys.stdout.flush()
                else:
                    hdr, rpmloc = h
                    if total == 0:
                        percent = 0
                    else:
                        percent = (bytes*100L)/total
                    pkgtup = self._dopkgtup(hdr)
                    txmbr = self.tsInfo.getMembers(pkgtup=pkgtup)[0]
                    try:
                        process = self.myprocess[txmbr.output_state]
                    except KeyError, e:
                        print "Error: invalid output state: %s for %s" % \
                           (txmbr.output_state, hdr['name'])
                    else:
                        if self.output and sys.stdout.isatty():
                            fmt = self._makefmt(percent)
                            msg = fmt % (process, hdr['name'])
                            sys.stdout.write(msg)
                            sys.stdout.flush()
                            if bytes == total:
                                print " "


        elif what == rpm.RPMCALLBACK_UNINST_START:
            pass

        elif what == rpm.RPMCALLBACK_UNINST_PROGRESS:
            pass

        elif what == rpm.RPMCALLBACK_UNINST_STOP:
            self.total_removed += 1
            if h not in self.installed_pkg_names:
                logmsg = _('Erased: %s' % (h))
                if self.filelog: self.filelog(0, logmsg)
            
            if self.output and sys.stdout.isatty():
                if h not in self.installed_pkg_names:
                    process = "Removing"
                else:
                    process = "Cleanup"
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

