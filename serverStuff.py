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

import os
import sys
import rpm
import string
import types
import rpmUtils
from i18n import _



def getfilelist(path, ext, list, usesymlinks):
    # get all the files matching the 3 letter extension that is ext in path, recursively
    # store them in append them to list
    # return list
    # ignore symlinks unless told otherwise

    dir_list = os.listdir(path)

    for d in dir_list:
        if os.path.isdir(path + '/' + d):
            list = getfilelist(path + '/' + d, ext, list, usesymlinks)
        else:
            if string.lower(d[-4:]) == '%s' % (ext):
                if usesymlinks:
                    newpath = os.path.normpath(path + '/' + d)
                    list.append(newpath)
                else:
                    if not os.path.islink( path + '/' + d): 
                        newpath = os.path.normpath(path + '/' + d)
                        list.append(newpath)
                    
    return(list)


def Usage():
    print _("""Usage:
yum-arch [-v] [-z] [-l] [-c] [-n] [-d] [-q] [-vv] (path of dir where headers/ should/does live)
   -d  = check dependencies and conflicts in tree
   -v  = more verbose output
   -vv = even more verbose output
   -n  = don't generate headers
   -c  = check pkgs with gpg and md5 checksums - cannot be used with -n
   -z  = gzip compress the headers (default, deprecated as an option)
   -s  = generate headers for source packages too
   -l  = use symlinks as valid rpms when building headers
   -q  = make the display more quiet""")
    sys.exit(1)



def depchecktree(rpmlist):
    _ts = rpm.TransactionSet()
    _ts.closeDB()
    error=0
    msgs=[]
    currpm=0
    numrpms=len(rpmlist)
    log(1, "Checking dependencies")
    for rpmfn in rpmlist:
        currpm=currpm + 1
        log(2, "Checking deps %d/%d complete" %(currpm, numrpms))
        hobj = rpmUtils.RPM_Work(rpmfn)
        if hobj.hdr == None:
            log(1, "ignoring bad rpm: %s" % rpmfn)
        elif hobj.isSource():
            log(2, "ignoring srpm: %s" % rpmfn)
        else:
            _ts.addInstall(hobj.hdr, hobj.name(), 'i')
            log(3, "adding %s" % hobj.name())
    errors = _ts.check()
    if errors:
        print 'errors found'
        for ((name, version, release), (reqname, reqversion), \
            flags, suggest, sense) in errors:
            if sense==rpm.RPMDEP_SENSE_REQUIRES:
                error=1
                msgs.append("depcheck: package %s needs %s" % ( name, rpmUtils.formatRequire(reqname, reqversion, flags)))
            elif sense==rpm.RPMDEP_SENSE_CONFLICTS:
                error=1
                msgs.append("depcheck: package %s conflicts with %s" % (name, reqname))
    print ""    
    return (error,msgs)
