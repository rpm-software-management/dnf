#!/usr/bin/python
# depchecktree.py [dirs you want checked]
# Seth Vidal <skvidal@phy.duke.edu>
#
# returns a list of conflicts/dependency problems in a set of dirs - just makes sure
# a installation or other tree can satisfy all its own depedencies. Segements of this code liberally
# lifted from anaconda :)
#
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


import os
import sys
import re
import string
import rpm

from i18n import _

debug = 0


def Usage():
    # yah, duh.
    print _("%s dirs you want to check") % (sys.argv[0])
    sys.exit(1)

def log(mess):
    if debug: 
        print mess

def readHeader(rpmfn):
    # read the header from the rpm if its an rpm, from a file its a file
    # return 'source' if its a src.rpm - something useful here would be good probably.
    if string.lower(rpmfn[-4:]) == '.rpm':
        fd = os.open(rpmfn, os.O_RDONLY)
        (h,src) = rpm.headerFromPackage(fd)
        os.close(fd)
        if src:
            return 'source'
        else:
            return h
    else:
        fd = open(rpmfn, "r")
        h = rpm.headerLoad(fd.read())
        fd.close()
        return h

def getfilelist(path, ext, list):
    # get all the files matching the 3 letter extension that is ext in path, recursively
    # store them in append them to list
    # return list
    # ignore symlinks
    dir_list = os.listdir(path)

    for d in dir_list:
        if os.path.isdir(path + '/' + d):
            list = getfilelist(path + '/' + d, ext, list)
        else:
            if string.lower(d[-4:]) == '%s' % (ext):
                if not os.path.islink( path + '/' + d): 
                    newpath = os.path.normpath(path + '/' + d)
                    list.append(newpath)
    return(list)

def formatRequire (name, version, flags):
    string = name
        
    if flags:
        if flags & (rpm.RPMSENSE_LESS | rpm.RPMSENSE_GREATER | rpm.RPMSENSE_EQUAL):
            string = string + " "
        if flags & rpm.RPMSENSE_LESS:
            string = string + "<"
        if flags & rpm.RPMSENSE_GREATER:
            string = string + ">"
        if flags & rpm.RPMSENSE_EQUAL:
            string = string + "="
            string = string + " %s" % version
    return string


def depchecktree(rpmlist):
    ts = rpm.TransactionSet('/')
    error=0
    msgs=[]
    for rpmfn in rpmlist:
        h = readHeader(rpmfn)
        if h != 'source':
            ts.add(h, h[rpm.RPMTAG_NAME], 'i')
            log("adding %s" % h[rpm.RPMTAG_NAME])       
    errors = ts.depcheck()
    if errors:
        for ((name, version, release), (reqname, reqversion), \
            flags, suggest, sense) in errors:
            if sense==rpm.RPMDEP_SENSE_REQUIRES:
                error=1
                msgs.append("depcheck: package %s needs %s" % ( name, formatRequire(reqname, reqversion, flags)))
            elif sense==rpm.RPMDEP_SENSE_CONFLICTS:
                error=1
                msgs.append("depcheck: package %s conflicts with %s" % (name, reqname))
        
    return (error,msgs)


def main():
    if len(sys.argv) < 2:
        Usage()
    
    treerpmlist = []
    for arg in sys.argv[1:]:
        log(arg)
        treerpmlist=getfilelist(arg,'.rpm',treerpmlist)
    
    (error,msgs) = depchecktree(treerpmlist)
    if error==1:
        print _("Errors within the dir(s):\n %s") % sys.argv[1:]
        for msg in msgs:
            print "   " + msg
    else:
        print _("All dependencies resolved and no conflicts detected")
    
if __name__ == "__main__":
    main()
