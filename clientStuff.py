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
