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
import sys
import gzip

def stripENVRA(foo):
  archIndex = string.rfind(foo, ".")
  arch = foo[archIndex+1:]
  relIndex = string.rfind(foo[:archIndex], "-")
  rel = foo[relIndex+1:archIndex]
  verIndex = string.rfind(foo[:relIndex], "-")
  ver = foo[verIndex+1:relIndex]
  epochIndex = string.find(foo, ":")
  epoch = foo[:epochIndex]
  name = foo[epochIndex + 1:verIndex]
  return (epoch, name, ver, rel, arch)

def stripEVR(str):
   epochIndex = string.find(str, ':')
   epoch = str[:epochIndex]
   relIndex = string.rfind(str, "-")
   rel = str[relIndex+1:]
   verIndex = string.rfind(str[:relIndex], "-")
   ver = str[epochIndex+1:relIndex]  
   return (epoch, ver, rel)

def stripNA(str):
    archIndex = string.rfind(str, ".")
    arch = str[archIndex+1:]
    name = str[:archIndex]
    return (name, arch)

def compareEVR((e1,v1,r1), (e2,v2,r2)):
    # return 1: a is newer than b 
    # 0: a and b are the same version 
    # -1: b is newer than a 
    rc = rpm.labelCompare((e1,v1,r1), (e2,v2,r2))
    log(6, "%s, %s, %s vs %s, %s, %s = %s" % (e1, v1, r1, e2, v2, r2, rc))
    return rc

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
    import string
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

def HeaderInfoNevralLoad(filename,nevral,serverid):
    info = []
    in_file = open(filename,"r")
    while 1:
        in_line = in_file.readline()
        if in_line == "":
            break
        info.append(in_line)
    in_file.close()

    for line in info:
        (envraStr, rpmpath) = string.split(line,'=')
        (epoch, name, ver, rel, arch) = stripENVRA(envraStr)
        rpmpath = string.replace(rpmpath, "\n","")
        if name not in conf.excludes:
            if conf.pkgpolicy=="last":
                nevral.add((name,epoch,ver,rel,arch,rpmpath,serverid),'a')    
            else:
                if nevral.exists(name, arch):
                    (e1, v1, r1) = nevral.evr(name, arch)
                    (e2, v2, r2) = (epoch, ver, rel)    
                    rc = compareEVR((e1,v1,r1), (e2,v2,r2))
                    if (rc < 0):
                        #ooo  the second one is newer - push it in.
                        nevral.add((name,epoch,ver,rel,arch,rpmpath,serverid),'a')
                else:
                    nevral.add((name,epoch,ver,rel,arch,rpmpath,serverid),'a')


def openrpmdb(option=0, dbpath=None):
    dbpath = "/var/lib/rpm/"
    rpm.addMacro("_dbpath", dbpath)

    try:
        db = rpm.opendb(option)
    except rpm.error, e:
        raise RpmError(_("Could not open RPM database for reading. Perhaps it is already in use?"))
    
    return db


def rpmdbNevralLoad(nevral):
    rpmdbdict = {}
    db = openrpmdb()
    serverid = "db"
    rpmloc = "in_rpm_db"
    index = db.firstkey()
    while index:
        rpmdbh = db[index]
        (epoch, name, ver, rel, arch) = getENVRA(rpmdbh)
        #deal with multiple versioned dupes and dupe entries in localdb
        if not rpmdbdict.has_key((name, arch)):
            rpmdbdict[(name,arch)] = (epoch, ver, rel)
        else:
            (e1, v1, r1) = (rpmdbdict[(name, arch)])
            (e2, v2, r2) = (epoch, ver, rel)    
            rc = compareEVR((e1,v1,r1), (e2,v2,r2))
            if (rc <= -1):
                rpmdbdict[(name,arch)] = (epoch, ver, rel)
            elif (rc == 0):
                log(4,"dupe entry in rpmdb %s\n" % key)
        index = db.nextkey(index)
    for value in rpmdbdict.keys():
        (name, arch) = value
        (epoch,ver, rel) = rpmdbdict[value]
        nevral.add((name,epoch,ver,rel,arch,rpmloc,serverid),'n')

def readHeader(rpmfn):
    if string.lower(rpmfn[-4:]) == '.rpm':
        fd = open(rpmfn, "r")
        h = rpm.headerFromPackage(fd)[0]
        fd.close()
        return h
    else:
        try:
            fd = gzip.open(rpmfn,"r")
            h = rpm.headerLoad(fd.read())
        except IOError,e:
            fd = open(rpmfn, "r")
            h = rpm.headerLoad(fd.read())
    fd.close()
    return h


def returnObsoletes(headerNevral,rpmNevral,uninstNAlist):
    packages = []
    obsdict = {} #obsdict[obseletinglist]=packageitobsoletes
    for (name,arch) in uninstNAlist:
        #print '%s, %s' % (name, arch)
        header = headerNevral.getHeader(name, arch)
        obs = header[rpm.RPMTAG_OBSOLETES]
        if obs:
        #print "%s, %s obs something" % (name, arch)
        # if there is one its a nonversioned obsolete
        # if there are 3 its a versioned obsolete
        # nonversioned are obvious - check the rpmdb if it exists
        # then the pkg obsoletes something in the rpmdb
        # versioned obsolete - obvalue[0] is the name of the pkg
        #                      obvalue[1] is >,>=,<,<=,=
        #                      obvalue[2] is an e:v-r string
        # get the two version strings - labelcompare them
        # get the return value - then run through
        # an if/elif statement regarding obvalue[1] and determine
        # if the pkg obsoletes something in the rpmdb
            for ob in obs:
                obvalue = string.split(ob)
                if rpmNevral.exists(obvalue[0]):
                    if len(obvalue) == 1:
                        packages.append((name, arch))
                        obsdict[(name,arch)]=obvalue[0]
                        log(4,"%s obsoleting %s" % (name,ob))
                    elif len(obvalue) == 3:
                        (e1,v1,r1) = rpmNevral.evr(name, arch)
                        (e2,v2,r2) = str_to_version(obvalue[3])
                        rc = compareEVR((e1,v1,r1), (e2,v2,r2))
                        if obvalue[2] == '>':
                            if rc >= 1:
                                packages.append((name, arch))
                                obsdict[(name,arch)]=obvalue[0]
                            elif rc == 0:
                                pass
                            elif rc <= -1:
                                pass
                        elif obvalue[2] == '>=':
                            if rc >= 1:
                                packages.append((name, arch))
                                obsdict[(name,arch)]=obvalue[0]
                            elif rc == 0:
                                packages.append((name, arch))
                                obsdict[(name,arch)]=obvalue[0]
                            elif rc <= -1:
                                pass
                        elif obvalue[2] == '=':
                            if rc >= 1:
                                pass
                            elif rc == 0:
                                packages.append((name, arch))
                                obsdict[(name,arch)]=obvalue[0]
                            elif rc <= -1:
                                pass
                        elif obvalue[2] == '<=':
                            if rc >= 1:
                                pass
                            elif rc == 0:
                                packages.append((name, arch))
                                obsdict[(name,arch)]=obvalue[0]
                            elif rc <= -1:
                                packages.append((name, arch))
                                obsdict[(name,arch)]=obvalue[0]
                        elif obvalue[2] == '<':
                            if rc >= 1:
                                pass
                            elif rc == 0:
                                pass
                            elif rc <= -1:
                                packages.append((name, arch))
                                obsdict[(name,arch)]=obvalue[0]
    return obsdict

def progresshook(blocks, blocksize, total):
    totalblocks=total/blocksize
    curbytes=blocks*blocksize
    sys.stdout.write("\r" + " " * 80)
    sys.stdout.write("\rblock: %d/%d" % (blocks,totalblocks))
    sys.stdout.flush()
    if curbytes==total:
        print " "
        

def urlgrab(url, filename=None,nohook=None):
    import urllib, rfc822, urlparse, os
    (scheme,host, path, parm, query, frag) = urlparse.urlparse(url)
    path = os.path.normpath(path)
    url = urlparse.urlunparse((scheme,host,path,parm,query,frag))
    if filename == None:
        filename = os.path.basename(path)
    try:
        (fh, hdr) = urllib.urlretrieve(url, filename)
    except IOError, e:
        errorlog(0,"IOError: %s"  % (e))
        errorlog(0,"URL: %s" % (url))
        sys.exit(1)
    #this is a cute little hack - if there isn't a "Content-Length" header then its either a 404 or a directory list
    #either way its not what we want so I put this check in here as a little bit of sanity checking
    if hdr != None:
        if not hdr.has_key('Content-Length'):
            errorlog(0,"ERROR: Url Return no Content-Length  - something is wrong")
            errorlog(0,"URL: %s" % (url))
            sys.exit(1)
    return fh


def getupdatedhdrlist(headernevral, rpmnevral):
    "returns (name,arch) tuples of updated and uninstalled pkgs"
    uplist = []
    newlist = []
    for (name, arch) in headernevral.NAkeys():
        hdrfile = headernevral.hdrfn(name, arch)
        serverid = headernevral.serverid(name, arch)
        if rpmnevral.exists(name, arch):
            #here we check if we are better than the installed version - including arch
            rc = compareEVR(headernevral.evr(name, arch), rpmnevral.evr(name, arch))
            if (rc > 0):
                #here we check if we are the best ignoring arch (this is to deal with multiple kernel archs
                #it catches the problem of kernel-2.4.18-4 (athlon) being installed but also kernel-2.4.31-9 (i686)
                #installed. Before this catch it would always answer that the kernel needed to be upgraded b/c the old i686
                #kernel was there and there was an available i686 kernel in the headernevral
                rc = compareEVR(headernevral.evr(name, arch), rpmnevral.evr(name))
                if rc > 0:
                    uplist.append((name,arch))
        else:
            newlist.append((name,arch))
    nulist=uplist+newlist
    return (uplist,newlist,nulist)

    
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


def actionslists(nevral):
    install_list = []
    update_list = []
    erase_list = []
    updatedeps_list = []
    erasedeps_list = []
    for (name, arch) in nevral.NAkeys():
        if nevral.state(name,arch) in ('i','iu'):
            install_list.append((name,arch))
        if nevral.state(name,arch) == 'u':
            update_list.append((name,arch))
        if nevral.state(name,arch) == 'e':
            erase_list.append((name,arch))
        if nevral.state(name,arch) == 'ud':
            updatedeps_list.append((name,arch))
        if nevral.state(name,arch) == 'ed':
            erasedeps_list.append((name,arch))
    
    return install_list, update_list, erase_list, updatedeps_list, erasedeps_list
    
def printactions(i_list, u_list, e_list, ud_list, ed_list):
    log(2,"I will do the following:")
    for pkg in i_list:
        (name,arch) = pkg
        log(2,"[install: %s.%s]" % (name,arch))
    for pkg in u_list:
        (name,arch) = pkg
        log(2,"[update: %s.%s]" % (name,arch))
    for pkg in e_list:
        (name,arch) = pkg
        log(2,"[erase: %s.%s]" % (name,arch))
    if len(ud_list) > 0:
        log(2,"I will install/upgrade these to satisfy the depedencies:")
        for pkg in ud_list:
            (name,arch) = pkg
            log(2, "[deps: %s.%s]" %(name,arch))
    if len(ed_list) > 0:
        log(2,"I will erase these to satisfy the depedencies:")
        for pkg in ed_list:
            (name,arch) = pkg
            log(2, "[deps: %s.%s]" %(name,arch))

def filelogactions(i_list, u_list,e_list,ud_list,ed_list):
    i_log="Installed: "
    u_log="Updated: "
    e_log="Erased: "
        
    for (name, arch) in i_list:
        filelog(1,i_log + name + '-' + arch)
    for (name, arch) in u_list+ud_list:
        filelog(1,u_log + name + '-' + arch)
    for (name, arch) in e_list+ed_list:
        filelog(1,e_log + name + '-' + arch)
        

def shortlogactions(i_list, u_list,e_list,ud_list,ed_list):
    i_log="Installed: "
    u_log="Updated: "
    e_log="Erased: "
    
    for (name, arch) in i_list:
        i_log=i_log + ' ' + name + '-' + arch
    for (name, arch) in u_list+ud_list:
        u_log=u_log + ' ' + name + '-' + arch
    for (name, arch) in e_list+ed_list:
        e_log=e_log + ' ' + name + '-' + arch
    if len(i_list) > 0:
        log(1, i_log)
    if len(u_list+ud_list) > 0:
        log(1, u_log)
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
        


def nasort((n1,a1), (n2, a2)):
    if n1 > n2:
        return 1
    elif n1 == n2:
        return 0
    else:
        return -1
        
def getfilelist(path, ext, list):
    # get all the files matching the 3 letter extension that is ext in path, recursively
    # store them in append them to list
    # return list
    # ignore symlinks
    import os
    import string

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
    serverlist=conf.servers
    for serverid in serverlist:
        servername = conf.servername[serverid]
        hdrdir = conf.serverhdrdir[serverid]
        hdrlist = getfilelist(hdrdir, '.hdr', [])
        for hdr in hdrlist:
            log(4,"Deleting Header %s" % hdr)
            os.unlink(hdr)
            


def clean_up_packages():
    serverlist=conf.servers
    for serverid in serverlist:
        servername = conf.servername[serverid]
        rpmdir = conf.serverpkgdir[serverid]
        rpmlist = getfilelist(rpmdir, '.rpm', [])
        for rpm in rpmlist:
            log(4,"Deleting Package %s" % rpm)
            os.unlink(rpm)
    

def clean_up_old_headers(rpmDBInfo, HeaderInfo):
    serverlist=conf.servers
    hdrlist =[]
    for serverid in serverlist:
        servername = conf.servername[serverid]
        hdrdir = conf.serverhdrdir[serverid]
        hdrlist = getfilelist(hdrdir, '.hdr', hdrlist)
    for hdrfn in hdrlist:
        hdr = readHeader(hdrfn)
        (e, n, v, r, a) = getENVRA(hdr)
        if rpmDBInfo.exists(n, a):
            (e1, v1, r1) = rpmDBInfo.evr(n, a)
            rc = compareEVR((e1,v1,r1), (e,v,r))
            #if the rpmdb has an equal or better rpm then delete
            #the header
            if (rc >= 0):
                log(4,"Deleting Header %s" % hdrfn)
                os.unlink(hdrfn)
        if not HeaderInfo.exists(n,a):
            #if its not in the HeaderInfo nevral anymore just kill it
            log(4,"Deleting Header %s" % hdrfn)
            os.unlink(hdrfn)
            

def printtime():
    import time
    return time.strftime('%m/%d/%y %H:%M:%S ',time.localtime(time.time()))



