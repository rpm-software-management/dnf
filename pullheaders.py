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
import rpmUtils
import serverStuff
import rpm
import types
from logger import Logger
from i18n import _

log=Logger(threshold=2, default=2, prefix='', preprefix='')
serverStuff.log = log
rpmUtils.log = log
rpmUtils.errorlog = log
ts = rpmUtils.Rpm_Ts_Work()
rpmUtils.ts = ts
serverStuff.ts = ts

def main():
    tempheaderdir = '.newheaders'
    tempheaderinfo = tempheaderdir + '/' + 'header.info'
    tempsrcheaderinfo = tempheaderdir + '/' + 'header.src.info'
    oldheaderdir = '.oldheaders'
    oldheaderinfo = oldheaderdir + '/' + 'header.info'
    oldsrcheaderinfo = oldheaderdir + '/' + 'header.src.info'
    headerdir = 'headers'
    headerinfo = headerdir + '/' + 'header.info'
    srcheaderinfo = headerdir + '/' + 'header.src.info'
    if  len(sys.argv) < 2:
        serverStuff.Usage()
    cmds = {}
    cmds['checkdeps'] = 0
    cmds['writehdrs'] = 1
    cmds['rpmcheck'] = 0
    cmds['compress'] = 1
    cmds['usesymlinks'] = 0
    cmds['dosrpms'] = 0
    cmds['quiet'] = 0
    cmds['loud'] = 0
    args = sys.argv[1:]
    basedir = args[-1]
    del args[-1]
    for arg in args:
        if arg == "-v":
            cmds['loud'] = 1
        elif arg == "-d":
            cmds['checkdeps'] = 1
        elif arg == "-n":
            cmds['writehdrs'] = 0
        elif arg == "-c":
            cmds['rpmcheck'] = 1
        elif arg == "-z":
            cmds['compress'] = 1
        elif arg == "-l":
            cmds['usesymlinks'] = 1
        elif arg == "-s":
            cmds['dosrpms'] = 1
        elif arg == "-q":
            cmds['quiet'] = 1
            log.threshold = 1
        elif arg == "-vv":
            cmds['loud'] = 1
            log.threshold = 4
        if arg in ['-h','--help']:
            serverStuff.Usage()
    # save where we are right now
    curdir = os.getcwd()
    # start the sanity/stupidity checks
    if not os.path.exists(basedir):
        print _("Directory of rpms must exist")
        serverStuff.Usage()
    if not os.path.isdir(basedir):
        print _("Directory of rpms must be a directory.")
        sys.exit(1)
        
    # change to the basedir to work from w/i the path - for relative url paths
    os.chdir(basedir)
    
    # get the list of rpms
    rpms=serverStuff.getfilelist('./', '.rpm', [], cmds['usesymlinks'])

    # some quick checks - we know we don't have ANY rpms - so, umm what do we
    # do? - if we have a headers dir then maybe we already had some and its
    # a now-empty repo - well, lets clean it up
    # kill the hdrs, kill the header.info - write an empty one
    if len(rpms) == 0:
        if os.path.exists(headerdir):
            hdrlist = serverStuff.getfilelist(headerdir, '.hdr', [], 0)
            removeCurrentHeaders(hdrlist)
            if cmds['dosrpms']:
                removeHeaderInfo(srcheaderinfo)
                srcheaderfd = open(srcheaderinfo, "w")
                srcheaderfd.close()
            removeHeaderInfo(headerinfo)
            headerfd = open(headerinfo, "w")
            headerfd.close()
            sys.exit(0)
        else:
            print _('No rpms to work with and no header dir. Exiting.')
            sys.exit(1)
            
    # depcheck if requested
    if cmds['checkdeps']:
        (error, msgs) = serverStuff.depchecktree(rpms)
        if error == 1:
            print _("Errors within the dir(s):\n %s") % basedir
            for msg in msgs:
                print _("   ") + msg
            sys.exit(1)
        else:
            print _("All dependencies resolved and no conflicts detected")
    
    if cmds['writehdrs']:
        # this should flow like this:
        # make sure the tempheaderdir is made, etc
        # check on the headerdir too
        # make the newheaders and header.info in tempheaderdir
        # mv the headers dir to .oldheaders
        # mv .newheaders to headers
        # clean out the old .hdrs
        # remove the .oldheaders/header.info
        # remove the .oldheaders dir
        # if the headerdir exists and its a file then we're in deep crap
        if not checkandMakeDir(headerdir):
            sys.exit(1)
        if not checkandMakeDir(tempheaderdir):
            sys.exit(1)

        # generate the new headers
        rpminfo = genhdrs(rpms, tempheaderdir, cmds)
        
        # Write header.info file
        if not cmds['quiet']:
            print _("\nWriting header.info file")
        headerfd = open(tempheaderinfo, "w")
        if cmds['dosrpms']:
            srcheaderfd = open(tempsrcheaderinfo, "w")
        for item in rpminfo.keys():
            (name,epoch, ver, rel, arch, source) = item
            rpmloc = rpminfo[item]
            if source:
                info = "%s:%s-%s-%s.src=%s\n" % (epoch, name, ver, rel, rpmloc)
                srcheaderfd.write(info)
            else:
                info = "%s:%s-%s-%s.%s=%s\n" % (epoch, name, ver, rel, arch, rpmloc)
                headerfd.write(info)
        if cmds['dosrpms']:
            srcheaderfd.close()
        headerfd.close()

        try:
            os.rename(headerdir, oldheaderdir)
        except OSError, e:
            print _("Error moving %s to %s, fatal") % (headerdir, oldheaderdir)
            sys.exit(1)
        
        try:
            os.rename(tempheaderdir, headerdir)
        except OSError, e:
            print _("Error moving %s to %s, fatal") % (headerdir, oldheaderdir)
            # put the old dir back, don't leave everything broken
            print _("Putting back old headers")
            os.rename(oldheaderdir, headerdir)
            sys.exit(1)
        
        # looks for a list of .hdr files and the header.info file
        hdrlist = serverStuff.getfilelist(oldheaderdir, '.hdr', [], 0)
        removeCurrentHeaders(hdrlist)
        removeHeaderInfo(oldheaderinfo)
        removeHeaderInfo(oldsrcheaderinfo)
        os.rmdir(oldheaderdir)

    # take us home mr. data
    os.chdir(curdir)

def checkandMakeDir(dir):
    """check out the dir and make it, if possible, return 1 if done, else return 0"""
    if os.path.exists(dir):
        if not os.path.isdir(dir):
            print _("%s is not a dir") % dir
            result = 0
        else:
            if not os.access(dir, os.W_OK):
                print _("%s is not writable") % dir
                result = 0
            else:
                result = 1
    else:
        try:
            os.mkdir(dir)
        except OSError, e:
            print _('Error creating dir %s: %s') % (dir, e)
            result = 0
        else:
            result = 1
    return result
            
        
def removeCurrentHeaders(hdrlist):
    """remove the headers before building the new ones"""
    for hdr in hdrlist:
        if os.path.exists(hdr):
            try:
                os.unlink(hdr)
            except OSerror, e:
                print _('Cannot delete file %s') % hdr
        else:
            print _('Odd header %s suddenly disappeared') % hdr

def removeHeaderInfo(headerinfo):
    """remove header.info file"""
    if os.path.exists(headerinfo):
        try:
            os.unlink(headerinfo)
        except OSerror, e:
            print _('Cannot delete %s - check perms') % headerinfo
            

def genhdrs(rpms,headerdir,cmds):
    """ Take a list of rpms, a place to put the headers and a config dictionary.
        outputs .hdr files and returns a dict containing all the header entries.
    """
    rpminfo = {}
    numrpms = len(rpms)
    goodrpm = 0
    currpm = 0
    srpms = 0
    for rpmfn in rpms:
        rpmname = os.path.basename(rpmfn)
        currpm=currpm + 1
        percent = (currpm*100)/numrpms
        if not cmds['quiet']:
            if cmds['loud']:
                print _('Digesting rpm - %s - %d/%d') % (rpmname, currpm, numrpms)
            else:
                sys.stdout.write('\r' + ' ' * 80)
                sys.stdout.write("\rDigesting rpms %d %% complete: %s" % (percent, rpmname))
                sys.stdout.flush()
        if cmds['rpmcheck']:
            log(2,_("\nChecking sig on %s") % rpmname)
            if rpmUtils.checkSig(rpmfn) > 0:
                log(0, _("\n\nProblem with gpg sig or md5sum on %s\n\n") % rpmfn)
                sys.exit(1)
        hobj = rpmUtils.RPM_Work(rpmfn)
        if hobj.hdr is None:
            log(1, "\nignoring bad rpm: %s" % rpmfn)
        else:
            (name, epoch, ver, rel, arch) = hobj.nevra()
            if hobj.isSource():
                if not cmds['dosrpms']:
                    if cmds['loud']:
                        print "\nignoring srpm: %s" % rpmfn
                    continue
                    
            if epoch is None:
                epoch = '0'
                
            rpmloc = rpmfn
            rpmstat = os.stat(rpmfn)
            rpmmtime = rpmstat[-2]
            rpmatime = rpmstat[-3]
            rpmtup = (name, epoch, ver, rel, arch, hobj.isSource())
            # do we already have this name.arch tuple in the dict?
            if rpminfo.has_key(rpmtup):
                log(2, _("\nAlready found tuple: %s %s:\n%s ") % (name, arch, rpmfn))
                
            headerloc = hobj.writeHeader(headerdir, cmds['compress'])
            os.utime(headerloc, (rpmatime, rpmmtime))
            
            if hobj.isSource():
                srpms = srpms + 1
                
            rpminfo[rpmtup]=rpmloc
            goodrpm = goodrpm + 1
            
    if not cmds['quiet']:
        print _("\n   Total: %d\n   Used: %d\n   Src: %d") %(numrpms, goodrpm, srpms)
    return rpminfo



if __name__ == "__main__":
    main()
