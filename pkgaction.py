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
try:
    import rpm404
    rpm = rpm404
except ImportError, e:
    import rpm

import clientStuff
import fnmatch
import archwork
import types


def installpkgs(tsnevral,nulist,userlist,hinevral,rpmnevral):
    #get the list of pkgs you want to install from userlist
    #check to see if they are already installed - if they are try to upgrade them
    #if they are the latest version then error and exit
    #if they are not, check to see if there is more than one arch, if so pass it to bestarch then use the bestone for this platform
    #add that one as 'iu' to the tsinfo
    #if they are not a pkg and you can't find it at all error and exit
    if len(nulist) > 0:
        for n in userlist:
            foundit=0
            for (name,arch) in nulist:
                if n == name or fnmatch.fnmatch(name, n):
                    #found it
                    foundit=1
                    archlist = archwork.availablearchs(hinevral,name)
                    bestarch = archwork.bestarch(archlist)
                    if rpmnevral.exists(name,bestarch):
                        (e1,v1,r1)=rpmnevral.evr(name,bestarch)
                        (e2,v2,r2)=hinevral.evr(name,bestarch)
                        rc = clientStuff.compareEVR((e1,v1,r1),(e2,v2,r2))
                        if rc < 0:
                            #we should be upgrading this
                            log(4,"Switching to upgrading %s" % (name))
                            ((e, v, r, a, l, i), s)=hinevral._get_data(name,bestarch)
                            tsnevral.add((name,e,v,r,a,l,i),'u')            
                        else:
                            #this is the best there is :(
                            errorlog(1,"%s is installed and is the latest version." % (name))
                            sys.exit(1)
                    else:
                        #we should install this
                        ((e, v, r, a, l, i), s)=hinevral._get_data(name,bestarch)
                        log(4,"state - iu: %s, %s" % (name,bestarch))
                        tsnevral.add((name,e,v,r,a,l,i),'iu')
            if foundit==0:
                if rpmnevral.exists(n):
                    errorlog(1,"%s is installed and is the latest version." % (n))
                else:
                    errorlog(0,"Cannot find a package matching %s" % (n))
                sys.exit(1)
            
    else:
        errorlog(1,"No Packages Available for Update or Install")    
    

def listpkgs(pkglist, userlist, nevral):
    if len(pkglist) > 0:
        pkglist.sort(clientStuff.nasort)
        print "%-40s %-10s %s" %('Name','Arch','Version')
        print "-" * 80
        if type(userlist) is types.StringType:
            if userlist=='all' or userlist =='updates':
                for (name, arch) in pkglist:
                    (e,v,r)=nevral.evr(name,arch)
                    print "%-40s %-10s %s-%s" %(name, arch, v, r)
                print ' '
        else:    
            for (name,arch) in pkglist:
                for n in userlist:
                    if n == name or fnmatch.fnmatch(name, n):
                        (e,v,r)=nevral.evr(name,arch)
                        print "%-40s %-10s %s-%s" %(name, arch, v, r)
            print ' '
    else:
        print "No Packages Available"
            
def listpkginfo(pkglist, userlist, nevral):
    if len(pkglist) > 0:
        pkglist.sort(clientStuff.nasort)
        if type(userlist) is types.StringType:
            if userlist=='all' or userlist=='updates':
                for (name, arch) in pkglist:
                    hdr=nevral.getHeader(name,arch)
                    displayinfo(hdr)
                    del hdr
        else:    
            for (name,arch) in pkglist:
                for n in userlist:
                    if n == name or fnmatch.fnmatch(name, n):
                        hdr=nevral.getHeader(name,arch)
                        displayinfo(hdr)
                        del hdr
    else:
        print "No Packages Available"

def displayinfo(hdr):
    print "Name   : %s" % hdr[rpm.RPMTAG_NAME]
    print "Arch   : %s" % hdr[rpm.RPMTAG_ARCH]
    print "Version: %s" % hdr[rpm.RPMTAG_VERSION]
    print "Release: %s" % hdr[rpm.RPMTAG_RELEASE]
    print "Size   : %s" % clientStuff.descfsize(hdr[rpm.RPMTAG_SIZE])
    print "Group  : %s" % hdr[rpm.RPMTAG_GROUP]
    print "Summary: %s" % hdr[rpm.RPMTAG_SUMMARY]
    print "Description:\n %s" % hdr[rpm.RPMTAG_DESCRIPTION]
    print ""
    

def updatepkgs(tsnevral,hinevral,rpmnevral,nulist,uplist,obslist,userlist):
    #get the list of what people want updated, match like in install.
    #add as 'u' to the tsnevral if its already there, if its not then add as 'i' and warn
    #if its all then take obslist and uplist and iterate through the tsinfo'u'
    #
    if len(nulist) > 0 :
        if type(userlist) is types.StringType and userlist=='all':
            for (name,arch) in uplist:
                log(4,"Updating: %s" % name)
                ((e, v, r, a, l, i), s)=hinevral._get_data(name,arch)
                tsnevral.add((name,e,v,r,a,l,i),'u')
        else:        
            for n in userlist:
                foundit=0
                for (name,arch) in uplist:
                    if n == name or fnmatch.fnmatch(name, n):
                        #found it
                        foundit=1
                        archlist = archwork.availablearchs(hinevral,name)
                        bestarch = archwork.bestarch(archlist)
                        log(4,"bestarch %s" % bestarch)
                        for currarch in archlist:
                            log(4, "arch = %s" % currarch)
                            if uplist.count((name,currarch))>0:
                                #its one of the archs we do and its in the uplist - update it
                                log(4, "Updating %s" % (name))
                                ((e, v, r, a, l, i), s)=hinevral._get_data(name,currarch)
                                tsnevral.add((name,e,v,r,a,l,i),'u')            
                            elif uplist.count((name,currarch)) < 1 and nulist.count((name,currarch))>0:
                                #its one of the archs we do and its not installed, install it but only the bestarch
                                if currarch == bestarch:
                                    log(4,"Installing %s" % (name))
                                    ((e, v, r, a, l, i), s)=hinevral._get_data(name,currarch)
                                    tsnevral.add((name,e,v,r,a,l,i),'iu')
                            elif uplist.count((name,currarch)) < 1 and nulist.count((name,currarch))<1:
                                #its an arch we do, its not updated and its installed
                                #but we keep going b/c we may not be done
                                log(5, "nope not %s" % currarch)
                if foundit==0:
                    if rpmnevral.exists(n):
                        errorlog(1,"%s is installed and the latest version." % (n))
                    else:
                        errorlog(0,"Cannot find any package matching %s available to be updated." % (n))
                    sys.exit(1)
    else:
        errorlog(1,"No Packages Available for Update or Install")
            
def upgradepkgs(tsnevral,hinevral,rpmnevral,nulist,uplist,obslist,obsdict,userlist):
    #global upgrade - including obsoletes - this must do the following:
    #if there is an update AND an obsolete - take the update first.
    completeuplist=[]
    uplistnames=[]
    for (name, arch) in uplist:
        uplistnames.append(name)
        completeuplist.append((name,arch))
        log(4,"Updating: %s" % name)
        
    for (name, arch) in obsdict.keys():
        if obsdict[(name,arch)] not in uplistnames:
            completeuplist.append((name,arch))
            log(4,"Obsolete: %s by %s" % (obsdict[(name,arch)], name))
            
    if len(completeuplist) > 0 :
        for (name,arch) in completeuplist:
            ((e, v, r, a, l, i), s)=hinevral._get_data(name,arch)
            tsnevral.add((name,e,v,r,a,l,i),'u')
    else:
        errorlog(1,"No Packages Available for Update or Install")

def erasepkgs(tsnevral,rpmnevral,userlist):
    #mark for erase iff the userlist item exists in the rpmnevral
    for n in userlist:
        foundit = 0
        for (name,arch) in rpmnevral.NAkeys():
            if n == name or fnmatch.fnmatch(name, n):
                foundit=1
                log(4,"Erasing %s" % (name))
                ((e, v, r, a, l, i), s)=rpmnevral._get_data(name,arch)
                tsnevral.add((name,e,v,r,a,l,i),'e')                
        if foundit==0:
            errorlog(0,"Erase: No matches for %s" % n)
            sys.exit(1)

def whatprovides(usereq, nulist, nevral, localrpmdb):
    # figure out what the user wants, traverse all the provides and file lists 
    # in every file in the header, return the fnmatch()es for the usereq
    # return the thing they match too.
    # do this:
    # get the header from the rpmnevral or the hinevral
    # get list of filenames and dirnames, get list of provides
    # traverse all searching for a match - hand back (name, arch) and what matched
    #for (name, arch) in hinevral.NAkeys():
    #    
    #else:
    #    print "No Packages Available"
    
    # short term - must check if its installed - if it is then make it check the rpmdb
    # do each matching quickly - at select time
    # long term
    # push all of provides+files+dirs into a dict dict[pkg]=list
    # deal with "where the hell is the pkg - hi or rpm
    # figure out how to make nevral.getHeader more robust
    results = 0
    if localrpmdb == 0:
        for (name, arch) in nulist:
            hdr = nevral.getHeader(name, arch)
            fullprovideslist = hdr[rpm.RPMTAG_PROVIDES] + hdr[rpm.RPMTAG_FILENAMES]
            if hdr[rpm.RPMTAG_DIRNAMES] != None:
                fullprovideslist = fullprovideslist + hdr[rpm.RPMTAG_DIRNAMES]
            for req in usereq:
                for item in fullprovideslist:
                    log(6, '%s vs %s' % (item, req))
                    if req == item or fnmatch.fnmatch(item, req):
                        results = results + 1
                        log(2,'Available package: %s provides %s' % (name, item))
            del fullprovideslist
    elif localrpmdb == 1:
        for (name, arch) in nevral.NAkeys():
            hdr=nevral.getHeader(name,arch)
            fullprovideslist = hdr[rpm.RPMTAG_PROVIDES] + hdr[rpm.RPMTAG_FILENAMES]
            if hdr[rpm.RPMTAG_DIRNAMES] != None:
                fullprovideslist = fullprovideslist + hdr[rpm.RPMTAG_DIRNAMES]
            for req in usereq:
                for item in fullprovideslist:
                    log(6, '%s vs %s' % (item, req))
                    if req == item or fnmatch.fnmatch(item, req):
                        results = results + 1
                        log(2,'Installed package: %s provides %s' % (name, item))
            del fullprovideslist
    else:
        errorlog(1,'localrpmdb not defined')
        
        
    if results > 0:
        log(2,'%s results returned' % results)
    else:
        log(2,'No packages found')
    
    

def kernelupdate(tsnevral):
    #figure out if we have updated a kernel
    #do what up2date does to update lilo and/or grub
    kernel_list = []
    # reopen the database read/write
    for (name,arch) in tsnevral.NAkeys():
        s = tsnevral.state(name,arch)
        if s in ['i','u','ud','iu']:
            if name in ['kernel','kernel-smp','kernel-enterprise','kernel-bigmem','kernel-BOOT']:
                hdr=tsnevral.getHeader(name,arch)
                if "kernel-smp" in hdr[rpm.RPMTAG_PROVIDES]:
                    extraInfo = "kernel-smp"
                elif "kernel-enterprise" in hdr[rpm.RPMTAG_PROVIDES]:
                    extraInfo = "kernel-enterprise"
                elif "kernel-bigmem" in hdr[rpm.RPMTAG_PROVIDES]:
                    extraInfo = "kernel-bigmem"
                elif "kernel-BOOT" in hdr[rpm.RPMTAG_PROVIDES]:
                    extraInfo = "kernel-BOOT"    
                else:
                    extraInfo = "kernel"

                # this logics a bit weird
                if extraInfo == None:
                    infoString = ""
                elif extraInfo == "kernel":
                    infoString = ""
                elif extraInfo == "kernel-BOOT":
                    infoString = "BOOT"
                elif extraInfo == "kernel-enterprise":
                    infoString = "enterprise"  
                elif extraInfo == "kernel-bigmem":
                    infoString = "bigmem"  
                elif extraInfo == "kernel-smp":
                    infoString = "smp"
                else:
                    infoString = ""
                verRel = "%s-%s%s" % (hdr[rpm.RPMTAG_VERSION], hdr[rpm.RPMTAG_RELEASE],infoString)
                kernel_list.append((verRel, extraInfo))
        
    if len(kernel_list) > 0:
        log(2,"Kernel Updated/Installed, fixing the bootloader")
        # code from up2date/up2date.py
        #figure out which bootloader, run the script for that bootloader
        import checkbootloader
        bootloader = checkbootloader.whichBootLoader()
        import up2datetheft
        if bootloader == "LILO":
            log(2,"Lilo found - adding kernel to lilo and making it the default")
            up2datetheft.install_lilo(kernel_list)
        elif bootloader == "GRUB":
            # at the moment, kernel rpms are supposed to grok grub
            # and do the Right Thing. Just a placeholder for doc purposes and
            #to put the kernels in the right order
            log(2,"Grub found - making this kernel the default")
            up2datetheft.install_grub(kernel_list)

def checkRpmMD5(package):
    check=rpm.CHECKSIG_MD5
    # RPM spews to stdout/stderr.  Redirect.
    # code for this from up2date.py
    saveStdout = os.dup(1)
    saveStderr = os.dup(2)
    redirStdout = os.open("/dev/null", os.O_WRONLY | os.O_APPEND)
    redirStderr = os.open("/dev/null", os.O_WRONLY | os.O_APPEND)
    os.dup2(redirStdout, 1)
    os.dup2(redirStderr, 2)
    # now do the rpm thing
    sigcheck = rpm.checksig(package, check)
    # restore normal stdout and stderr
    os.dup2(saveStdout, 1)
    os.dup2(saveStderr, 2)
    # close the redirect files.
    os.close(redirStdout)
    os.close(redirStderr)
    os.close(saveStdout)
    os.close(saveStderr)
    if sigcheck:
        errorlog(0, 'Error: MD5 Signature check failed for %s' %(package))
        errorlog(0, 'You may want to run yum clean or remove the file:\n %s' % (package))
        errorlog(0, 'Exiting.')
        sys.exit(1)


def checkRpmSig(package, serverid):
    # check for gpg
    # get the right sig information from config
    # if we have a keyring then use it
    # if not then just set gpg_home
    # check the package
    
    # sig info should work like this:
    # if we have a keyring defined for the server section - use that
    # if not use the default
    # if the default is not defined but gpgcheck is - use gpg_home
    
    hdr = clientStuff.readHeader(package)
    
    if clientStuff.checkGPGInstallation() != 0:
        errorlog(0, 'Error: /usr/bin/gpg could not be found')
        sys.exit(1)
        return 1
    if hdr['SIGGPG'] == None:
        errorlog(0, 'Warning: package %s is unsigned' % package)
        errorlog(0, 'You may want to disable GPG checking to install this package')
        errorlog(0, 'Exiting')
        sys.exit(1)
        return 1
    if clientStuff.checkGPGInstallation() == 0:
        if conf.gpgkeyring:
            gpg_flags = "--homedir %s --no-default-keyring --keyring %s" % (conf.gpghome, conf.gpgkeyring)
        else:
            gpg_flags = "--homedir %s" % conf.gpghome
            
        rpm.addMacro("__gpg_verify_cmd",
                    """%%{__gpg} gpg %s --batch --no-verbose --verify %%{__signature_filename} %%{__plaintext_filename}""" % gpg_flags)
        rpm.addMacro("_gpg_path", conf.gpghome)
        check=rpm.CHECKSIG_GPG
        # RPM spews to stdout/stderr.  Redirect.
        # code for this from up2date.py
        saveStdout = os.dup(1)
        saveStderr = os.dup(2)
        redirStdout = os.open("/dev/null", os.O_WRONLY | os.O_APPEND)
        redirStderr = os.open("/dev/null", os.O_WRONLY | os.O_APPEND)
        os.dup2(redirStdout, 1)
        os.dup2(redirStderr, 2)
        # now do the rpm thing
        result = rpm.checksig(package, check)
        # restore normal stdout and stderr
        os.dup2(saveStdout, 1)
        os.dup2(saveStderr, 2)
        # close the redirect files.
        os.close(redirStdout)
        os.close(redirStderr)
        os.close(saveStdout)
        os.close(saveStderr)
        rpm.delMacro("__gpg_verify_cmd")
        rpm.delMacro("_gpg_path")
        if result:
            errorlog(0, 'Error: GPG Signature check failed for %s' %(package))
            errorlog(0, 'You may want to run yum clean or remove the file:\n %s' % (package))
            errorlog(0, 'You may also want to check to make sure you have the right gpg keys')
            errorlog(0, 'Exiting.')
            sys.exit(1)
        return 0
        
    
