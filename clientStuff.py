#!/usr/bin/python
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

import string
import rpm
import os
import os.path
import sys
import gzip
import archwork
import fnmatch
import pkgaction
import callback
import rpmUtils
import time
import urlparse
import types

import urlgrabber
from urlgrabber import close_all, urlgrab, URLGrabError, retrygrab
# it would be nice to make this slurp the REAL version from somewhere :)
urlgrabber.set_user_agent("Yum/2.X")

from i18n import _

def stripENVRA(str):
    archIndex = string.rfind(str, '.')
    arch = str[archIndex+1:]
    relIndex = string.rfind(str[:archIndex], '-')
    rel = str[relIndex+1:archIndex]
    verIndex = string.rfind(str[:relIndex], '-')
    ver = str[verIndex+1:relIndex]
    epochIndex = string.find(str, ':')
    epoch = str[:epochIndex]
    name = str[epochIndex + 1:verIndex]
    return (epoch, name, ver, rel, arch)

def stripEVR(str):
    epochIndex = string.find(str, ':')
    epoch = str[:epochIndex]
    relIndex = string.rfind(str, '-')
    rel = str[relIndex+1:]
    verIndex = string.rfind(str[:relIndex], '-')
    ver = str[epochIndex+1:relIndex]  
    return (epoch, ver, rel)

def stripNA(str):
    archIndex = string.rfind(str, '.')
    arch = str[archIndex+1:]
    name = str[:archIndex]
    return (name, arch)

def getENVRA(header):
    if header[rpm.RPMTAG_EPOCH] == None:
        epoch = '0'
    else:
        epoch = '%s' % header[rpm.RPMTAG_EPOCH]
    name = header[rpm.RPMTAG_NAME]
    ver = header[rpm.RPMTAG_VERSION]
    rel = header[rpm.RPMTAG_RELEASE]
    arch = header[rpm.RPMTAG_ARCH]
    return (epoch, name, ver, rel, arch)

def str_to_version(str):
    i = string.find(str, ':')
    if i != -1:
        epoch = string.atol(str[:i])
    else:
        epoch = '0'
    j = string.find(str, '-')
    if j != -1:
        if str[i + 1:j] == '':
            version = None
        else:
            version = str[i + 1:j]
        release = str[j + 1:]
    else:
        if str[i + 1:] == '':
            version = None
        else:
            version = str[i + 1:]
        release = None
    return (epoch, version, release)

def HeaderInfoNevralLoad(filename, nevral, serverid):
    in_file = open(filename, 'r')
    info = in_file.readlines()
    in_file.close()
    archlist = archwork.compatArchList()
    for line in info:
        try:
            (envraStr, rpmpath) = string.split(line, '=')
            (epoch, name, ver, rel, arch) = stripENVRA(envraStr)
        except ValueError, e:
            errorlog(0, _('Damaged or Bad header.info from %s') % conf.servername[serverid])
            errorlog(0, _('This is probably because of a downed server or an invalid header.info on a repository.'))
            sys.exit(1)
        rpmpath = string.replace(rpmpath, '\n', '')
        if arch in archlist:
            if not nameInExcludes(name, serverid):
                if conf.pkgpolicy == 'last':
                    # just add in the last one don't compare
                    if nevral.exists(name, arch):
                        # but if one already exists in the nevral replace it
                        if serverid == nevral.serverid(name, arch):
                            # unless we're in the same serverid then we need to take the newest
                            (e1, v1, r1) = nevral.evr(name, arch)
                            (e2, v2, r2) = (epoch, ver, rel)    
                            rc = rpmUtils.compareEVR((e1, v1, r1), (e2, v2, r2))
                            if (rc < 0):
                                # ooo  the second one is newer - push it in.
                                nevral.add((name, epoch, ver, rel, arch, rpmpath, serverid), 'a')
                        else:
                            nevral.add((name, epoch, ver, rel, arch, rpmpath, serverid), 'a')
                    else:
                        nevral.add((name, epoch, ver, rel, arch, rpmpath, serverid), 'a')
                else:
                    if nevral.exists(name, arch):
                        (e1, v1, r1) = nevral.evr(name, arch)
                        (e2, v2, r2) = (epoch, ver, rel)    
                        rc = rpmUtils.compareEVR((e1, v1, r1), (e2, v2, r2))
                        if (rc < 0):
                            # ooo  the second one is newer - push it in.
                            nevral.add((name, epoch, ver, rel, arch, rpmpath, serverid), 'a')
                    else:
                        nevral.add((name, epoch, ver, rel, arch, rpmpath, serverid), 'a')


def nameInExcludes(name, serverid=None):
    # this function should take a name and check it against the excludes
    # list to see if it shouldn't be in there
    # return true if it is in the Excludes list
    # return false if it is not in the Excludes list
    for exclude in conf.excludes:
        if name == exclude or fnmatch.fnmatch(name, exclude):
            return 1
    if serverid != None: 
        for exclude in conf.serverexclude[serverid]:
            if name == exclude or fnmatch.fnmatch(name, exclude):
                return 1
    return 0

def rpmdbNevralLoad(nevral):
    rpmdbdict = {}
    serverid = 'db'
    rpmloc = 'in_rpm_db'
    hdrs = ts.dbMatch()
    for hdr in hdrs:
        (epoch, name, ver, rel, arch) = getENVRA(hdr)
        # deal with multiple versioned dupes and dupe entries in localdb
        if not rpmdbdict.has_key((name, arch)):
            rpmdbdict[(name, arch)] = (epoch, ver, rel)
        else:
            (e1, v1, r1) = (rpmdbdict[(name, arch)])
            (e2, v2, r2) = (epoch, ver, rel)    
            rc = rpmUtils.compareEVR((e1,v1,r1), (e2,v2,r2))
            if (rc <= -1):
                rpmdbdict[(name, arch)] = (epoch, ver, rel)
            elif (rc == 0):
                log(4, 'dupe entry in rpmdb %s %s' % (name, arch))
    for value in rpmdbdict.keys():
        (name, arch) = value
        (epoch, ver, rel) = rpmdbdict[value]
        nevral.add((name, epoch, ver, rel, arch, rpmloc, serverid), 'n')

def readHeader(rpmfn):
    if string.lower(rpmfn[-4:]) == '.rpm':
        fd = os.open(rpmfn, os.O_RDONLY)
        h = ts.hdrFromFdno(fd)
        os.close(fd)
        if h[rpm.RPMTAG_SOURCEPACKAGE]:
            return 'source'
        else:
            return h
    else:
        try:
            fd = gzip.open(rpmfn, 'r')
            try: 
                h = rpm.headerLoad(fd.read())
            except rpm.error, e:
                errorlog(0,_('Damaged Header %s') % rpmfn)
                return None
        except IOError,e:
            fd = open(rpmfn, 'r')
            try:
                h = rpm.headerLoad(fd.read())
            except rpm.error, e:
                errorlog(0,_('Damaged Header %s') % rpmfn)
                return None
        except ValueError, e:
            return None
    fd.close()
    return h


def correctFlags(flags):
    returnflags=[]
    if flags is None:
        return returnflags
                                                                               
    if type(flags) is not types.ListType:
        newflag = flags & 0xf
        returnflags.append(newflag)
    else:
        for flag in flags:
            newflag = flag
            if flag is not None:
                newflag = flag & 0xf
            returnflags.append(newflag)
    return returnflags


def correctVersion(vers):
     returnvers = []
     vertuple = (None, None, None)
     if vers is None:
         returnvers.append(vertuple)
         return returnvers
         
     if type(vers) is not types.ListType:
         if vers is not None:
             vertuple = str_to_version(vers)
         else:
             vertuple = (None, None, None)
         returnvers.append(vertuple)
     else:
         for ver in vers:
             if ver is not None:
                 vertuple = str_to_version(ver)
             else:
                 vertuple = (None, None, None)
             returnvers.append(vertuple)
     return returnvers

def returnObsoletes(headerNevral, rpmNevral, uninstNAlist):
    obsoleting = {} # obsoleting[pkgobsoleting]=[list of pkgs it obsoletes]
    obsoleted = {} # obsoleted[pkgobsoleted]=[list of pkgs obsoleting it]
    for (name, arch) in uninstNAlist:
        header = headerNevral.getHeader(name, arch)
        obs = []
        names = header[rpm.RPMTAG_OBSOLETENAME]
        tmpflags = header[rpm.RPMTAG_OBSOLETEFLAGS]
        flags = correctFlags(tmpflags)
        ver = correctVersion(header[rpm.RPMTAG_OBSOLETEVERSION])
        if names is not None:
            obs = zip(names, flags, ver)
        del header

        # nonversioned are obvious - check the rpmdb if it exists
        # then the pkg obsoletes something in the rpmdb
        # versioned obsolete - obvalue[0] is the name of the pkg
        #                      obvalue[1] is >,>=,<,<=,=
        #                      obvalue[2] is an (e,v,r) tuple
        # get the two version strings - labelcompare them
        # get the return value - then run through
        # an if/elif statement regarding obvalue[1] and determine
        # if the pkg obsoletes something in the rpmdb
        if obs:
            for (obspkg, obscomp, (obe, obv, obr)) in obs:
                if rpmNevral.exists(obspkg):
                    if obscomp == 0: #unversioned obsolete
                        if not obsoleting.has_key((name, arch)):
                            obsoleting[(name, arch)] = []
                        obsoleting[(name, arch)].append(obspkg)
                        if not obsoleted.has_key(obspkg):
                            obsoleted[obspkg] = []
                        obsoleted[obspkg].append((name, arch))
                        log(4,'%s obsoleting %s' % (name, obspkg))
                    else:
                        log(4,'versioned obsolete')
                        log(5, '%s, %s, %s, %s, %s' % (obspkg, obscomp, obe, obv, obr))
                        (e1, v1, r1) = rpmNevral.evr(name, arch)
                        rc = rpmUtils.compareEVR((e1, v1, r1), (obe, obv, obr))
                        if obscomp == 4:
                            if rc >= 1:
                                if not obsoleting.has_key((name, arch)):
                                    obsoleting[(name, arch)] = []
                                obsoleting[(name, arch)].append(obspkg)
                                if not obsoleted.has_key(obspkg):
                                    obsoleted[obspkg] = []
                                obsoleted[obspkg].append((name, arch))
                                log(4,'%s obsoleting %s' % (name, obspkg))
                        elif obscomp == 12:
                            if rc >= 1:
                                if not obsoleting.has_key((name, arch)):
                                    obsoleting[(name, arch)] = []
                                obsoleting[(name, arch)].append(obspkg)
                                if not obsoleted.has_key(obspkg):
                                    obsoleted[obspkg] = []
                                obsoleted[obspkg].append((name, arch))
                                log(4,'%s obsoleting %s' % (name, obspkg))
                            elif rc == 0:
                                if not obsoleting.has_key((name, arch)):
                                    obsoleting[(name, arch)] = []
                                obsoleting[(name, arch)].append(obspkg)
                                if not obsoleted.has_key(obspkg):
                                    obsoleted[obspkg] = []
                                obsoleted[obspkg].append((name, arch))
                                log(4,'%s obsoleting %s' % (name, obspkg))
                        elif obscomp == 8:
                            if rc == 0:
                                if not obsoleting.has_key((name, arch)):
                                    obsoleting[(name, arch)] = []
                                obsoleting[(name, arch)].append(obspkg)
                                if not obsoleted.has_key(obspkg):
                                    obsoleted[obspkg] = []
                                obsoleted[obspkg].append((name, arch))
                                log(4,'%s obsoleting %s' % (name, obspkg))
                        elif obscomp == 10:
                            if rc == 0:
                                if not obsoleting.has_key((name, arch)):
                                    obsoleting[(name, arch)] = []
                                obsoleting[(name, arch)].append(obspkg)
                                if not obsoleted.has_key(obspkg):
                                    obsoleted[obspkg] = []
                                obsoleted[obspkg].append((name, arch))
                                log(4,'%s obsoleting %s' % (name, obspkg))
                            elif rc <= -1:
                                if not obsoleting.has_key((name, arch)):
                                    obsoleting[(name, arch)] = []
                                obsoleting[(name, arch)].append(obspkg)
                                if not obsoleted.has_key(obspkg):
                                    obsoleted[obspkg] = []
                                obsoleted[obspkg].append((name, arch))
                                log(4,'%s obsoleting %s' % (name, obspkg))
                        elif obscomp == 2:
                            if rc <= -1:
                                if not obsoleting.has_key((name, arch)):
                                    obsoleting[(name, arch)] = []
                                obsoleting[(name, arch)].append(obspkg)
                                if not obsoleted.has_key(obspkg):
                                    obsoleted[obspkg] = []
                                obsoleted[obspkg].append((name, arch))
                                log(4,'%s obsoleting %s' % (name, obspkg))
    return obsoleting, obsoleted

def getupdatedhdrlist(headernevral, rpmnevral):
    "returns (name, arch) tuples of updated and uninstalled pkgs"
    uplist = []
    newlist = []
    simpleupdate = []
    complexupdate = []
        # this is all hard and goofy to deal with pkgs changing arch
        # if we have the package installed
        # if the pkg isn't installed then it's a new pkg
        # else
        #   if there isn't more than on available arch from the hinevral 
        #       then compare it to the installed one 
        #   if there is more than one installed or available:
        #   compare highest version and bestarch (in that order of precdence) 
        #   of installed pkgs to highest version and bestarch of available pkgs
        
        # best bet is to chew through the pkgs and throw out the new ones early
        # then deal with the ones where there are a single pkg installed and a 
        # single pkg available
        # then deal with the multiples
        # write a sub-function that takes (nevral, name) and returns list of
        # archs that have the highest version
        
        # additional tricksiness - include a config option to make it ONLY 
        # update identical matches so glibc.i386 can only be updated by 
        # glibc.i386 not by glibc.i686 - this is for the anal and bizare
        
        # look at the fresh new pain - what about multilib
        # I need to have foo.i386 and foo.x86_64 both installed and visible as
        # available, if one isn't installed. 
        # so a complex update really isn't the difficult part
        # i need to mark foo.arch as newlist if it is
        # pretty much if: it's not precisely what we have installed then it's in
        # newlist unless it is precisely a name.arch match for update.
        # those that aren't a name.arch match but are a name match get dealt with like
        #  if exactarch:
        #   newer different arch then it's available but not an update
        #   newer same arch as installed then it's an update not available
        #   equal and same arch as installed then ignore it
        #   older and different arch as installed then grab it
        #   older and same arch as installed then ignore it        
        
        # we should take the whole list as a 'newlist' and remove those entries
        # which are clearly:
        #   1. updates 
        #   2. identical to rpmnevral
        #   3. not in our archdict at all
        
    newlist.extend(headernevral.NAkeys())
    
    for (name, arch) in headernevral.NAkeys():
        # remove stuff not in our archdict
        if arch not in archwork.compatArchList():
            newlist.remove((name, arch))
            continue
            
        # simple ones - look for exact matches or older stuff
        if rpmnevral.exists(name, arch):
            (rpm_e, rpm_v, rpm_r) = rpmnevral.evr(name, arch)
            rc = rpmUtils.compareEVR(headernevral.evr(name, arch), (rpm_e, rpm_v, rpm_r))
            if rc <= 0:
                newlist.remove((name, arch))
                continue

        if rpmnevral.exists(name):
            hdrarchs = archwork.availablearchs(headernevral, name)
            rpmarchs = archwork.availablearchs(rpmnevral, name)
            if len(hdrarchs) > 1 or len(rpmarchs) > 1:
                if name not in complexupdate:
                    log(4, 'putting %s in complex update list' % name)
                    complexupdate.append(name)
            else:
                log(4, 'putting %s in simple update list' % name)
                simpleupdate.append((name, arch))
    # we have our lists to work with now

    # simple cases
    for (name, arch) in simpleupdate:
        # try to be as precise as possible
        if conf.exactarch:
            if rpmnevral.exists(name, arch):
                (rpm_e, rpm_v, rpm_r) = rpmnevral.evr(name, arch)
                rc = rpmUtils.compareEVR(headernevral.evr(name), (rpm_e, rpm_v, rpm_r))
                if rc > 0:
                    uplist.append((name,arch))
                    newlist.remove((name, arch))

        else:
            (rpm_e, rpm_v, rpm_r) = rpmnevral.evr(name)
            rc = rpmUtils.compareEVR(headernevral.evr(name), (rpm_e, rpm_v, rpm_r))
            if rc > 0:
                uplist.append((name, arch))
                newlist.remove((name, arch))
            
    # complex cases
    for name in complexupdate:
        hdrarchs = bestversion(headernevral, name)
        rpmarchs = bestversion(rpmnevral, name)
        hdr_best_arch = archwork.bestarch(hdrarchs)
        log(5, 'Best ver+arch avail for %s is %s' % (name, hdr_best_arch))
        rpm_best_arch = archwork.bestarch(rpmarchs)
        log(5, 'Best ver+arch installed for %s is %s' % (name, rpm_best_arch))
        
        # dealing with requests to only update exactly what is installed
        # we clearly want to update the stuff that is installed
        # and compare it to best that is available - but only if the arch 
        # matches so we go through the lists of rpmarchs of bestversion, check 
        # for them in hdrarchs - if they are there compare them and mark them
        # accordingly
        # if for some reason someone has two pkgs of the same version but 
        # different arch installed and we happen to have both available then
        # they'll get both - if anyone can point out a situation when this is 
        # "legal" let me know.

        if conf.exactarch:
            for arch in rpmarchs:
                if arch in hdrarchs:
                    log(5, 'Exact match in complex for %s - %s' % (name, arch))
                    rc = rpmUtils.compareEVR(headernevral.evr(name, arch), rpmnevral.evr(name, arch))
                    if rc > 0:
                        uplist.append((name, arch))
                        newlist.remove((name, arch))
                else:
                    log(5, 'Inexact match in complex for %s - %s' % (name, arch))
        else:
            rc = rpmUtils.compareEVR(headernevral.evr(name, hdr_best_arch), rpmnevral.evr(name, rpm_best_arch))
            if rc > 0:
                uplist.append((name, hdr_best_arch))
                newlist.remove((name, hdr_best_arch))
                
    nulist=uplist+newlist
    return (uplist, newlist, nulist)


def bestversion(nevral, name):
    """this takes a nevral and a pkg name - it iterates through them to return
       the list of archs having the highest version number - so if someone has
       package foo.i386 and foo.i686 then we'll get a list of i386 and i686 returned
       minimum of one thing returned"""
    # first we get a list of the archs
    # determine the best e-v-r
    # then we determine the archs that have that version and append them to a list
    returnarchs = []
    
    archs = archwork.availablearchs(nevral, name)
    currentarch = archs[0]
    for arch in archs[1:]:
        rc = rpmUtils.compareEVR(nevral.evr(name, currentarch), nevral.evr(name, arch))
        if rc < 0:
            currentarch = arch
        elif rc == 0:
            pass
        elif rc > 0:
            pass
    (best_e, best_v, best_r) = nevral.evr(name, currentarch)
    log(3, _('Best version for %s is %s:%s-%s') % (name, best_e, best_v, best_r))
    
    for arch in archs:
        rc = rpmUtils.compareEVR(nevral.evr(name, arch), (best_e, best_v, best_r))
        if rc == 0:
            returnarchs.append(arch)
        elif rc > 0:
            log(4, 'What the hell, we just determined it was the bestversion')
    
    log(7, returnarchs)
    return returnarchs
    
def formatRequire (name, version, flags):
    string = name
        
    if flags:
        if flags & (rpm.RPMSENSE_LESS | rpm.RPMSENSE_GREATER | rpm.RPMSENSE_EQUAL):
            string = string + ' '
        if flags & rpm.RPMSENSE_LESS:
            string = string + '<'
        if flags & rpm.RPMSENSE_GREATER:
            string = string + '>'
        if flags & rpm.RPMSENSE_EQUAL:
            string = string + '='
            string = string + ' %s' % version
    return string


def actionslists(nevral):
    install_list = []
    update_list = []
    erase_list = []
    updatedeps_list = []
    erasedeps_list = []
    for (name, arch) in nevral.NAkeys():
        if nevral.state(name, arch) in ('i', 'iu'):
            install_list.append((name, arch))
        if nevral.state(name, arch) == 'u':
            update_list.append((name, arch))
        if nevral.state(name, arch) == 'e':
            erase_list.append((name, arch))
        if nevral.state(name, arch) == 'ud':
            updatedeps_list.append((name, arch))
        if nevral.state(name, arch) == 'ed':
            erasedeps_list.append((name, arch))
    
    return install_list, update_list, erase_list, updatedeps_list, erasedeps_list
    
def printactions(i_list, u_list, e_list, ud_list, ed_list, nevral):
    log(2, _('I will do the following:'))
    
    for pkg in i_list:
        (name,arch) = pkg
        (e, v, r) = nevral.evr(name, arch)
        if e > '0':
            pkgstring = '%s %s:%s-%s.%s' % (name, e, v, r, arch)
        else:
            pkgstring = '%s %s-%s.%s' % (name, v, r, arch)
        log(2, _('[install: %s]') % pkgstring)
        
    for pkg in u_list:
        (name,arch) = pkg
        (e, v, r) = nevral.evr(name, arch)
        if e > '0':
            pkgstring = '%s %s:%s-%s.%s' % (name, e, v, r, arch)
        else:
            pkgstring = '%s %s-%s.%s' % (name, v, r, arch)
        log(2, _('[update: %s]') % pkgstring)
        
    for pkg in e_list:
        (name,arch) = pkg
        (e, v, r) = nevral.evr(name, arch)
        if e > '0':
            pkgstring = '%s %s:%s-%s.%s' % (name, e, v, r, arch)
        else:
            pkgstring = '%s %s-%s.%s' % (name, v, r, arch)
        log(2, _('[erase: %s]') % pkgstring)
        
    if len(ud_list) > 0:
        log(2, _('I will install/upgrade these to satisfy the dependencies:'))
        for pkg in ud_list:
            (name, arch) = pkg
            (e, v, r) = nevral.evr(name, arch)
            if e > '0':
                pkgstring = '%s %s:%s-%s.%s' % (name, e, v, r, arch)
            else:
                pkgstring = '%s %s-%s.%s' % (name, v, r, arch)            
            log(2, _('[deps: %s]') % pkgstring)
            
    if len(ed_list) > 0:
        log(2, _('I will erase these to satisfy the dependencies:'))
        for pkg in ed_list:
            (name, arch) = pkg
            (e, v, r) = nevral.evr(name, arch)
            if e > '0':
                pkgstring = '%s %s:%s-%s.%s' % (name, e, v, r, arch)
            else:
                pkgstring = '%s %s-%s.%s' % (name, v, r, arch)
            log(2, _('[deps: %s]') % pkgstring)

def filelogactions(i_list, u_list, e_list, ud_list, ed_list, nevral):
    i_log = _('Installed: ')
    ud_log = _('Dep Installed: ')
    u_log = _('Updated: ')
    e_log = _('Erased: ')
        
    for (name, arch) in i_list:
        (e, v, r) = nevral.evr(name, arch)
        if e > '0':
            pkgstring = '%s %s:%s-%s.%s' % (name, e, v, r, arch)
        else:
            pkgstring = '%s %s-%s.%s' % (name, v, r, arch)
        filelog(1, i_log + pkgstring)

    for (name, arch) in ud_list:
        (e, v, r) = nevral.evr(name, arch)
        if e > '0':
            pkgstring = '%s %s:%s-%s.%s' % (name, e, v, r, arch)
        else:
            pkgstring = '%s %s-%s.%s' % (name, v, r, arch)
        filelog(1, ud_log + pkgstring)
        
    for (name, arch) in u_list:
        (e, v, r) = nevral.evr(name, arch)
        if e > '0':
            pkgstring = '%s %s:%s-%s.%s' % (name, e, v, r, arch)
        else:
            pkgstring = '%s %s-%s.%s' % (name, v, r, arch)
        filelog(1, u_log + pkgstring)
        
    for (name, arch) in e_list+ed_list:
        (e, v, r) = nevral.evr(name, arch)
        if e > '0':
            pkgstring = '%s %s:%s-%s.%s' % (name, e, v, r, arch)
        else:
            pkgstring = '%s %s-%s.%s' % (name, v, r, arch)
        filelog(1, e_log + pkgstring)
        

def shortlogactions(i_list, u_list, e_list, ud_list, ed_list, nevral):
    i_log = _('Installed: ')
    ud_log = _('Dep Installed: ')
    u_log = _('Updated: ')
    e_log = _('Erased: ')
    
    for (name, arch) in i_list:
        (e, v, r) = nevral.evr(name, arch)
        if e > '0':
            pkgstring = '%s %s:%s-%s.%s' % (name, e, v, r, arch)
        else:
            pkgstring = '%s %s-%s.%s' % (name, v, r, arch)
        i_log = i_log + ' ' + pkgstring
        
    for (name, arch) in ud_list:
        (e, v, r) = nevral.evr(name, arch)
        if e > '0':
            pkgstring = '%s %s:%s-%s.%s' % (name, e, v, r, arch)
        else:
            pkgstring = '%s %s-%s.%s' % (name, v, r, arch)
        ud_log = ud_log + ' ' + pkgstring
        
    for (name, arch) in u_list:
        (e, v, r) = nevral.evr(name, arch)
        if e > '0':
            pkgstring = '%s %s:%s-%s.%s' % (name, e, v, r, arch)
        else:
            pkgstring = '%s %s-%s.%s' % (name, v, r, arch)
        u_log = u_log + ' ' + pkgstring
        
    for (name, arch) in e_list+ed_list:
        (e, v, r) = nevral.evr(name, arch)
        if e > '0':
            pkgstring = '%s %s:%s-%s.%s' % (name, e, v, r, arch)
        else:
            pkgstring = '%s %s-%s.%s' % (name, v, r, arch)
        e_log = e_log + ' ' + pkgstring

    if len(i_list) > 0:
        log(1, i_log)
    if len(u_list) > 0:
        log(1, u_log)
    if len(ud_list) > 0:
        log(1, ud_log)
    if len(e_list+ed_list) > 0:
        log(1, e_log)
        


def userconfirm():
    """gets a yes or no from the user, defaults to No"""
    choice = raw_input('Is this ok [y/N]: ')
    if len(choice) == 0:
        return 1
    else:
        if choice[0] != 'y' and choice[0] != 'Y':
            return 1
        else:
            return 0
        


def nasort((n1, a1), (n2, a2)):
    if n1 > n2:
        return 1
    elif n1 == n2:
        return 0
    else:
        return -1
        
def getfilelist(path, ext, list):
    # get all the files matching the 3 letter extension that is ext in path, 
    # recursively
    # append them to list
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

def clean_up_headers():
    serverlist = conf.servers
    for serverid in serverlist:
        hdrdir = conf.serverhdrdir[serverid]
        hdrlist = getfilelist(hdrdir, '.hdr', [])
        # remove header.info file too
        headerinfofile = os.path.join(conf.cachedir, serverid, 'header.info')
        log(4, 'Deleting header.info for %s' % serverid)
        os.unlink(headerinfofile)
        for hdr in hdrlist:
            log(4, 'Deleting Header %s' % hdr)
            os.unlink(hdr)
            

def clean_up_packages():
    serverlist = conf.servers
    for serverid in serverlist:
        rpmdir = conf.serverpkgdir[serverid]
        rpmlist = getfilelist(rpmdir, '.rpm', [])
        for rpm in rpmlist:
            log(4, 'Deleting Package %s' % rpm)
            os.unlink(rpm)
    

def clean_up_old_headers(rpmDBInfo, HeaderInfo):
    serverlist = conf.servers
    hdrlist = []
    for serverid in serverlist:
        hdrdir = conf.serverhdrdir[serverid]
        hdrlist = getfilelist(hdrdir, '.hdr', hdrlist)
    for hdrfn in hdrlist:
        hdr = readHeader(hdrfn)
        (e, n, v, r, a) = getENVRA(hdr)
        if rpmDBInfo.exists(n, a):
            (e1, v1, r1) = rpmDBInfo.evr(n, a)
            rc = rpmUtils.compareEVR((e1, v1, r1), (e, v, r))
            # if the rpmdb has an equal or better rpm then delete
            # the header
            if (rc >= 0):
                log(5, 'Deleting Header %s' % hdrfn)
                try:
                    os.unlink(hdrfn)
                except OSError, e:
                    errorlog(2, _('Attempt to delete a missing file %s - ignoring.') % hdrfn)
        if not HeaderInfo.exists(n, a):
            # if its not in the HeaderInfo nevral anymore just kill it
            log(5, 'Deleting Header %s' % hdrfn)
            try:
                os.unlink(hdrfn)
            except OSError, e:
                errorlog(2, _('Attempt to delete a missing file %s - ignoring.') % hdrfn)
            

def printtime():
    return time.strftime('%m/%d/%y %H:%M:%S ', time.localtime(time.time()))

def get_groups_from_servers(serveridlist):
    """takes a list of serverids - returns a list of servers that either:
       gave us yumcomps.xml or for whom we had a cached one"""
       
    log(2, 'Getting groups from servers')
    validservers = []
    for serverid in serveridlist:
        remotegroupfile = conf.remoteGroups(serverid)
        localgroupfile = conf.localGroups(serverid)
        if not conf.cache:
            log(3, _('getting groups from server: %s') % serverid)
            try:
                localgroupfile = grab(serverid, remotegroupfile, localgroupfile, nofail=1, copy_local=1)
            except URLGrabError, e:
                log(3, _('Error getting file %s') % remotegroupfile)
                log(3, '%s' % e)
        else:
            if os.path.exists(localgroupfile):
                log(2, _('using cached groups from server: %s') % serverid)
        if os.path.exists(localgroupfile):
            log(3, _('Got a file - yay'))
            validservers.append(serverid)
    return validservers
        
def get_package_info_from_servers(serveridlist, HeaderInfo):
    """gets header.info from each server if it can, checks it, if it can, then
       builds the list of available pkgs from there by handing each headerinfofn
       to HeaderInfoNevralLoad()"""
    log(2, _('Gathering header information file(s) from server(s)'))
    for serverid in serveridlist:
        servername = conf.servername[serverid]
        serverheader = conf.remoteHeader(serverid)
        servercache = conf.servercache[serverid]
        log(2, _('Server: %s') % (servername))
        log(4, _('CacheDir: %s') % (servercache))
        localpkgs = conf.serverpkgdir[serverid]
        localhdrs = conf.serverhdrdir[serverid]
        localheaderinfo = conf.localHeader(serverid)
        if not conf.cache:
            if not os.path.exists(servercache):
                os.mkdir(servercache)
            if not os.path.exists(localpkgs):
                os.mkdir(localpkgs)
            if not os.path.exists(localhdrs):
                os.mkdir(localhdrs)
            log(3, _('Getting header.info from server'))
            try:
                headerinfofn = grab(serverid, serverheader, localheaderinfo, copy_local=1,
                                    progress_obj=None)
            except URLGrabError, e:
                errorlog(0, _('Error getting file %s') % serverheader)
                errorlog(0, '%s' % e)
                sys.exit(1)
        else:
            if os.path.exists(localheaderinfo):
                log(3, _('Using cached header.info file'))
                headerinfofn = localheaderinfo
            else:
                errorlog(0, _('Error - %s cannot be found') % localheaderinfo)
                if conf.uid != 0:
                    errorlog(1, _('Please ask your sysadmin to update the headers on this system.'))
                else:
                    errorlog(1, _('Please run yum in non-caching mode to correct this header.'))
                sys.exit(1)
        log(4,'headerinfofn: ' + headerinfofn)
        HeaderInfoNevralLoad(headerinfofn, HeaderInfo, serverid)

def download_headers(HeaderInfo, nulist):
    total = len(nulist)
    current = 1
    for (name, arch) in nulist:
        LocalHeaderFile = HeaderInfo.localHdrPath(name, arch)
        RemoteHeaderFile = HeaderInfo.remoteHdrUrl(name, arch)
        
        serverid = HeaderInfo.serverid(name, arch)
        # if we have one cached, check it, if it fails, unlink it and continue
        # as if it never existed
        # else move along
        if os.path.exists(LocalHeaderFile):
            log(5, 'checking cached header: %s' % LocalHeaderFile)
            try:
                rpmUtils.checkheader(LocalHeaderFile, name, arch)
            except URLGrabError, e:
                if conf.cache:
                    errorlog(0, _('The file %s is damaged.') % LocalHeaderFile)
                    if conf.uid != 0:
                        errorlog(1, _('Please ask your sysadmin to update the headers on this system.'))
                    else:
                        errorlog(1, _('Please run yum in non-caching mode to correct this header.'))
                    errorlog(1, _('Deleting entry from Available packages'))
                    HeaderInfo.delete(name, arch)
                    #sys.exit(1)
                else:
                    os.unlink(LocalHeaderFile)
            else:
                continue
                
        if not conf.cache:
            log(3, _('getting %s') % (LocalHeaderFile))
            try:
                hdrfn = grab(serverid, RemoteHeaderFile, LocalHeaderFile, copy_local=1,
                                  checkfunc=(rpmUtils.checkheader, (name, arch), {}))
            except URLGrabError, e:
                errorlog(0, _('Error getting file %s') % RemoteHeaderFile)
                errorlog(0, '%s' % e)
                sys.exit(1)
            HeaderInfo.setlocalhdrpath(name, arch, hdrfn)
        else:
            errorlog(1, _('Cannot download %s in caching only mode or when running as non-root user.') % RemoteHeaderFile)
            errorlog(1, _('Deleting entry from Available packages'))
            HeaderInfo.delete(name, arch)
            #sys.exit(1)
        current = current + 1
    close_all()
                
def take_action(cmds, nulist, uplist, newlist, obsoleting, tsInfo, HeaderInfo, rpmDBInfo, obsoleted):
    from yummain import usage
    
    basecmd = cmds.pop(0)
    
    if conf.uid != 0:
        if basecmd in ['install','update','clean','upgrade','erase', 'groupupdate', 'groupupgrade', 'groupinstall']:
            errorlog(0, _('You need to be root to perform these commands'))
            sys.exit(1)
    
    if basecmd == 'install':
        if len(cmds) == 0:
            errorlog(0, _('Need to pass a list of pkgs to install'))
            usage()
        else:
            if conf.tolerant:
                pkgaction.installpkgs(tsInfo, nulist, cmds, HeaderInfo, rpmDBInfo, 0)
            else: 
                pkgaction.installpkgs(tsInfo, nulist, cmds, HeaderInfo, rpmDBInfo, 1)
                
    elif basecmd == 'provides':
        taglist = ['filenames', 'dirnames', 'provides']
        if len(cmds) == 0:
            errorlog(0, _('Need a provides to match'))
            usage()
        else:
            log(2, _('Looking in available packages for a providing package'))
            pkgaction.search(cmds, nulist, HeaderInfo, 0, taglist)
            log(2, _('Looking in installed packages for a providing package'))
            pkgaction.search(cmds, nulist, rpmDBInfo, 1, taglist)
        sys.exit(0)
    
    elif basecmd == 'search':
        taglist = ['description', 'summary', 'packager', 'name']
        if len(cmds) == 0:
            errorlog(0, _('Need an item to search'))
            usage()
        else:
            log(2, _('Looking in available packages for a providing package'))
            pkgaction.search(cmds, nulist, HeaderInfo, 0, taglist)
            log(2, _('Looking in installed packages for a providing package'))
            pkgaction.search(cmds, nulist, rpmDBInfo, 1, taglist)
        sys.exit(0)

    elif basecmd == 'update':
        if len(cmds) == 0:
            pkgaction.updatepkgs(tsInfo, HeaderInfo, rpmDBInfo, nulist, uplist, 'all', 0)
        else:
            if conf.tolerant:
                pkgaction.updatepkgs(tsInfo, HeaderInfo, rpmDBInfo, nulist, uplist, cmds, 0)
            else:
                pkgaction.updatepkgs(tsInfo, HeaderInfo, rpmDBInfo, nulist, uplist, cmds, 1)
            
    elif basecmd == 'upgrade':
        if len(cmds) == 0:
            pkgaction.upgradepkgs(tsInfo, HeaderInfo, rpmDBInfo, nulist, uplist, obsoleted, obsoleting, 'all', 0)
        else:
            if conf.tolerant:
                pkgaction.upgradepkgs(tsInfo, HeaderInfo, rpmDBInfo, nulist, uplist, obsoleted, obsoleting, cmds, 1)
            else:
                pkgaction.upgradepkgs(tsInfo, HeaderInfo, rpmDBInfo, nulist, uplist, obsoleted, obsoleting, cmds, 0)
    
    elif basecmd in ('erase', 'remove'):
        if len(cmds) == 0:
            usage()
            errorlog (0, _('Need to pass a list of pkgs to erase'))
        else:
            if conf.tolerant:
                pkgaction.erasepkgs(tsInfo, rpmDBInfo, cmds, 0)
            else:
                pkgaction.erasepkgs(tsInfo, rpmDBInfo, cmds, 1)
    
    elif basecmd == 'check-update':
        if len(uplist) > 0:
            pkgaction.listpkginfo(uplist, 'all', HeaderInfo, 1)
            sys.exit(100)
        else:
            sys.exit(0)
            
    elif basecmd in ['list', 'info']:
        if basecmd == 'list':
            short = 1
        else:
            short = 0
        if len(cmds) == 0:
            pkgaction.listpkginfo(nulist, 'all', HeaderInfo, short)
            sys.exit(0)
        else:
            if cmds[0] == 'updates':
                pkgaction.listpkginfo(uplist, 'updates', HeaderInfo, short)
            elif cmds[0] == 'available':
                pkgaction.listpkginfo(newlist, 'all', HeaderInfo, short)
            elif cmds[0] == 'installed':
                pkglist = rpmDBInfo.NAkeys()
                pkgaction.listpkginfo(pkglist, 'all', rpmDBInfo, short)
            elif cmds[0] == 'extras':
                pkglist=[]
                for (name, arch) in rpmDBInfo.NAkeys():
                    if not HeaderInfo.exists(name, arch):
                        pkglist.append((name,arch))
                if len(pkglist) > 0:
                    pkgaction.listpkginfo(pkglist, 'all', rpmDBInfo, short)
                else:
                    log(2, _('No Packages installed not included in a repository'))
            else:    
                log(2, _('Looking in Available Packages:'))
                pkgaction.listpkginfo(nulist, cmds, HeaderInfo, short)
                log(2, _('Looking in Installed Packages:'))
                pkglist = rpmDBInfo.NAkeys()
                pkgaction.listpkginfo(pkglist, cmds, rpmDBInfo, short)
        sys.exit(0)
    elif basecmd == 'grouplist':
        pkgaction.listgroups(cmds)
        sys.exit(0)
    
    elif basecmd == 'groupupdate':
        if len(cmds) == 0:
            errorlog(0, _('Need a list of groups to update'))
            sys.exit(1)
        installs, updates = pkgaction.updategroups(rpmDBInfo, nulist, uplist, cmds)
        if len(updates) > 0:
            pkglist = []
            for (group, pkg) in updates:
                pkglist.append(pkg)
            pkgaction.updatepkgs(tsInfo, HeaderInfo, rpmDBInfo, nulist, uplist, pkglist, 0)
        if len(installs) > 0:
            pkglist = []
            for (group, pkg) in installs:
                pkglist.append(pkg)
            pkgaction.installpkgs(tsInfo, nulist, pkglist, HeaderInfo, rpmDBInfo, 0)
            
    elif basecmd == 'groupinstall':
        if len(cmds) == 0:
            errorlog(0, _('Need a list of groups to update'))
            sys.exit(1)
        instpkglist = pkgaction.installgroups(rpmDBInfo, nulist, uplist, cmds)
        if len(instpkglist) > 0:
            pkgaction.installpkgs(tsInfo, nulist, instpkglist, HeaderInfo, rpmDBInfo, 0)
        
            
    elif basecmd == 'clean':
        if len(cmds) == 0 or cmds[0] == 'all':
            log(2, _('Cleaning packages and old headers'))
            clean_up_packages()
            clean_up_old_headers(rpmDBInfo, HeaderInfo)
        elif cmds[0] == 'packages':
            log(2, _('Cleaning packages'))
            clean_up_packages()
        elif cmds[0] == 'headers':
            log(2, _('Cleaning all headers'))
            clean_up_headers()
        elif cmds[0] == 'oldheaders':
            log(2, _('Cleaning old headers'))
            clean_up_old_headers(rpmDBInfo, HeaderInfo)
        else:
            errorlog(0, _('Invalid clean option %s') % cmds[0])
            sys.exit(1)
        sys.exit(0)    
    else:
        usage()

def create_final_ts(tsInfo):
    # download the pkgs to the local paths and add them to final transaction set
    tsfin = rpm.TransactionSet(conf.installroot)
    for (name, arch) in tsInfo.NAkeys():
        pkghdr = tsInfo.getHeader(name, arch)
        rpmloc = tsInfo.localRpmPath(name, arch)
        serverid = tsInfo.serverid(name, arch)
        state = tsInfo.state(name, arch)
        if state in ('u', 'ud', 'iu', 'i'): # inst/update
            # this should be just like the hdr getting
            # check it out- if it is good, move along
            # otherwise, download, check, wash, rinse, repeat
            # just md5/open check - we'll mess with gpg checking after we know
            # that the pkg is valid
            if os.path.exists(rpmloc):
                log(4, 'Checking cached RPM %s' % (os.path.basename(rpmloc)))
                if not rpmUtils.checkRpmMD5(rpmloc):
                    errorlog(0, _('Damaged RPM %s, removing.') % (rpmloc))
                    os.unlink(rpmloc)
                else:
                    rpmobj = rpmUtils.RPM_Work(rpmloc)
                    hdre = pkghdr['epoch']
                    hdrv = pkghdr['version']
                    hdrr = pkghdr['release']
                    (rpme, rpmv, rpmr) = rpmobj.evr()
                    if (rpme, rpmv, rpmr) != (hdre, hdrv, hdrr):
                        errorlog(2, _('NonMatching RPM version, %s, removing.') %(rpmloc))
                        os.unlink(rpmloc)

            # gotten rid of the bad ones
            # now lets download things
            if os.path.exists(rpmloc):
                pass
            else:
                log(2, _('Getting %s') % (os.path.basename(rpmloc)))
                remoterpmurl = tsInfo.remoteRpmUrl(name, arch)
                try:
                    localrpmpath = grab(serverid, remoterpmurl, rpmloc, copy_local=0,
                                             checkfunc=(rpmUtils.checkRpmMD5, (), {'urlgraberror':1})) 
                except URLGrabError, e:
                    errorlog(0, _('Error getting file %s') % remoterpmurl)
                    errorlog(0, '%s' % e)
                    sys.exit(1)
                else:
                    tsInfo.setlocalrpmpath(name, arch, localrpmpath)
                    
            # we now actually have the rpm and we know where it is - so use it
            rpmloc = tsInfo.localRpmPath(name, arch)
            if conf.servergpgcheck[serverid]:
                rc = rpmUtils.checkSig(rpmloc)
                if rc == 1:
                    errorlog(0, _('Error: Could not find the GPG Key necessary to validate pkg %s') % rpmloc)
                    errorlog(0, _('Error: You may want to run yum clean or remove the file: \n %s') % rpmloc)
                    errorlog(0, _('Error: You may also check that you have the correct GPG keys installed'))
                    sys.exit(1)
                elif rc == 2:
                    errorlog(0, _('Error Reading Header on %s') % rpmloc)
                    errorlog(0, _('Error: You may want to run yum clean or remove the file: \n %s') % rpmloc)
                    sys.exit(1)
                elif rc == 3:
                    errorlog(0, _('Error: Untrusted GPG key on %s') % rpmloc)
                    errorlog(0, _('Error: You may want to run yum clean or remove the file: \n %s') % rpmloc)
                    errorlog(0, _('Error: You may also check that you have the correct GPG keys installed'))
                    sys.exit(1)
                elif rc == 4:
                    errorlog(0, _('Error: Unsigned Package %s') % rpmloc)
                    errorlog(0, _('Error: You may want to run yum clean or remove the file: \n %s') % rpmloc)
                    errorlog(0, _('Error: You may need to disable gpg checking to install this package\n'))
                    sys.exit(1)
            if state == 'i':
                tsfin.addInstall(pkghdr, (pkghdr, rpmloc), 'i')
            else:
                tsfin.addInstall(pkghdr, (pkghdr, rpmloc), 'u')
        elif state == 'a':
            pass
        elif state == 'e' or state == 'ed':
            tsfin.addErase(name)
    close_all()
    return tsfin

def tsTest(checkts):
    checkts.setFlags(rpm.RPMTRANS_FLAG_TEST)
    if conf.diskspacecheck == 0:
        checkts.setProbFilter(rpm.RPMPROB_FILTER_DISKSPACE)
    cb = callback.RPMInstallCallback()
    tserrors = checkts.run(cb.callback, '')
    reserrors = []
    if tserrors:
        for (descr, (type, mount, need)) in tserrors:
            reserrors.append(descr)
    if len(reserrors) > 0:
        errorlog(0, _('Errors reported doing trial run'))
        for error in reserrors:
            errorlog(0, '%s' % error)
        sys.exit(1)



def descfsize(size):
    """The purpose of this function is to accept a file size in bytes,
    and describe it in a human readable fashion."""
    if size < 1000:
        return "%d bytes" % size
    elif size < 1000000:
        size = size / 1000.0
        return "%.2f kB" % size
    elif size < 1000000000:
        size = size / 1000000.0
        return "%.2f MB" % size
    else:
        size = size / 1000000000.0
        return "%.2f GB" % size

def grab(serverID, url, filename=None, nofail=0, copy_local=0, 
          close_connection=0,
          progress_obj='normal', throttle=None, bandwidth=None,
          numtries=3, retrycodes=[-1,2,4,5,6,7], checkfunc=None):

    """Wrap retry grab and add in failover stuff.  This needs access to
    the conf class as well as the serverID.

    nofail -- Set to true to go through the failover object without
       incrementing the failures counter.  (Actualy this just resets
       the failures counter.)  Usefull in the yumgroups.xml special case.

    We do look at retrycodes here to see if we should return or failover.
    On fail we will raise the last exception that we got."""
    if not conf.keepalive:
        log(5, 'Disabling Keepalive support by user configuration')
        urlgrabber.disable_keepalive()

    if progress_obj == 'normal':
        progress_obj = conf.progress_obj
        
    fc = conf.get_failClass(serverID)
    base = ''
    findex = fc.get_index()
    
    for root in conf.serverurl[serverID]:
        if string.find(url, root) == 0:
            # We found the current base this url is made of
            base = root
            break
    if base == '':
        # We didn't find the base...something is wrong
        raise Exception, "%s isn't made from a base URL I know about" % url
    filepath = url[len(base):]
    log(3, "failover: baseURL = " + base)
    log(3, "failover: path = " + filepath)

    # don't trust the base that the user supplied
    # this call will return the same thing as fc.get_serverurl(findex)
    base = fc.get_serverurl()
    while base != None:
        # Loop over baseURLs until one works or all are dead
        try:
            (scheme, host, path, parm, query, frag) = urlparse.urlparse(base)
            path = os.path.normpath(path + '/' + filepath)
            finalurl = urlparse.urlunparse((scheme, host, path, parm, query, frag))
            return retrygrab(finalurl, filename, copy_local,
                             close_connection, progress_obj, throttle,
                             bandwidth, conf.retries, retrycodes, checkfunc)
            # What?  We were successful?
        except URLGrabError, e:
            if e.errno in retrycodes:
                if not nofail:
                    errorlog(1, _("retrygrab() failed for:\n  %s%s\n  Executing failover method") % (base, filepath))
                if nofail:
                    findex = findex + 1
                    base = fc.get_serverurl(findex)
                else:
                    fc.server_failed()
                    base = fc.get_serverurl()
                if base == None:
                    if not nofail:
                        errorlog(1, _("failover: out of servers to try"))
                    raise
            else:
                raise
