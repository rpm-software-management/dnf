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
# Copyright 2002 Duke University 


import rpm
import os
import sys

from i18n import _

class RPMInstallCallback:
    def __init__(self):
        self.callbackfilehandles = {}
        self.total_actions = 0
        self.total_installed = 0
        self.installed_pkg_names = []
        self.total_removed = 0
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
            if h != None:
                hdr, rpmloc = h
                handle = '%s:%s.%s-%s-%s' % (hdr[rpm.RPMTAG_EPOCH],
                    hdr[rpm.RPMTAG_NAME], hdr[rpm.RPMTAG_VERSION],
                    hdr[rpm.RPMTAG_RELEASE], hdr[rpm.RPMTAG_ARCH])
                fd = os.open(rpmloc, os.O_RDONLY)
                self.callbackfilehandles[handle]=fd
                self.total_installed += 1
                self.installed_pkg_names.append(hdr[rpm.RPMTAG_NAME])
                return fd
            else:
                print _("No header - huh?")
  
        elif what == rpm.RPMCALLBACK_INST_CLOSE_FILE:
            hdr = None
            if h != None:
                hdr, rpmloc = h
                handle = '%s:%s.%s-%s-%s' % (hdr[rpm.RPMTAG_EPOCH],
                  hdr[rpm.RPMTAG_NAME], hdr[rpm.RPMTAG_VERSION],
                  hdr[rpm.RPMTAG_RELEASE], hdr[rpm.RPMTAG_ARCH])
            os.close(self.callbackfilehandles[handle])
            fd = 0

        elif what == rpm.RPMCALLBACK_INST_PROGRESS:
            if h != None:
                pkg, rpmloc = h
                if total == 0:
                    percent = 0
                else:
                    percent = (bytes*100L)/total
                if conf.debuglevel >= 2:
                    sys.stdout.write("\r%s %d %% done %d/%d" % (pkg[rpm.RPMTAG_NAME], 
                      percent, self.total_installed + self.total_removed, self.total_actions))
                    if bytes == total:
                        print " "
        elif what == rpm.RPMCALLBACK_UNINST_START:
            pass
        elif what == rpm.RPMCALLBACK_UNINST_STOP:
            self.total_removed += 1
            if conf.debuglevel >= 2:
                if h not in self.installed_pkg_names:
                    print 'Erasing: %s %d/%d' % (h, self.total_removed + 
                      self.total_installed, self.total_actions)
                else:
                    print 'Completing update for %s  - %d/%d' % (h, self.total_removed +
                      self.total_installed, self.total_actions)
