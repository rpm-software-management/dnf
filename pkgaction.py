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
import re
import clientStuff
import fnmatch
import archwork
import types
import rpmUtils
from i18n import _


def installpkgs(tsnevral, nulist, userlist, hinevral, rpmnevral, exitoninstalled):
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
                        rc = rpmUtils.compareEVR((e1,v1,r1),(e2,v2,r2))
                        if rc < 0:
                            #we should be upgrading this
                            log(4,"Switching to updating %s" % (name))
                            ((e, v, r, a, l, i), s)=hinevral._get_data(name,bestarch)
                            tsnevral.add((name,e,v,r,a,l,i),'u')            
                        else:
                            #this is the best there is :(
                            errorlog(1, _("%s is installed and is the latest version.") % (name))
                            if exitoninstalled:
                                sys.exit(1)
                                
                    else:
                        #we should install this
                        ((e, v, r, a, l, i), s)=hinevral._get_data(name,bestarch)
                        log(4,"state - iu: %s, %s" % (name,bestarch))
                        tsnevral.add((name,e,v,r,a,l,i),'iu')
            if foundit==0:
                if rpmnevral.exists(n):
                    errorlog(1, _("%s is installed and is the latest version.") % (n))
                    if exitoninstalled:
                        sys.exit(1)
                else:
                    errorlog(0, _("Cannot find a package matching %s") % (n))
                    if exitoninstalled:
                        sys.exit(1)
            
    else:
        errorlog(1, _("No Packages Available for Update or Install"))
    
def updatepkgs(tsnevral, hinevral, rpmnevral, nulist, uplist, userlist, exitoninstalled):
    """Update pkgs - will only update - will not install uninstalled pkgs.
       however it will, on occasion install a new, betterarch of a pkg"""
       
    # get rid of the odd state of no updates or uninstalled pkgs
    if len(uplist) <= 0 :
        errorlog(1, _("No Packages Available for Update"))
        return
    # just update them all
    if type(userlist) is types.StringType and userlist == 'all':
        for (name, arch) in uplist:
            log(4, "Updating %s" % (name))
            ((e, v, r, a, l, i), s) = hinevral._get_data(name, arch)
            tsnevral.add((name,e,v,r,a,l,i),'u')            
        return

    # user specified list - need to match
    for n in userlist:
        # this is a little trick = we have to match the userlist
        # but we want to return useful errors
        # so we check if we can find the things in the list
        # if we can't find one of them then something is wrong
        # check if we can't find it b/c it's not there
        # or if it's the most updated version available
        pkgfound = 0
        for (name, arch) in uplist:
            if n == name or fnmatch.fnmatch(name, n):
                pkgfound = 1
                if rpmnevral.exists(name, arch):
                    log(4, "Updating %s" % name)
                else:
                    log(4, "Updating %s to arch %s" % (name, arch))
                ((e, v, r, a, l, i), s) = hinevral._get_data(name, arch)
                tsnevral.add((name,e,v,r,a,l,i),'u')
                
        if not pkgfound:
            if rpmnevral.exists(n):
                errorlog(1,"%s is installed and the latest version." % (n))
                if exitoninstalled:
                    sys.exit(1)
            else:
                errorlog(0,"Cannot find any package matching %s available to be updated." % (n))
                if exitoninstalled:
                    sys.exit(1)
            
def upgradepkgs(tsnevral, hinevral, rpmnevral, nulist, uplist, obsoleted, obsoleting, userlist, exitoninstalled):
    # must take user arguments
    # this is just like update except it must check for obsoleting pkgs first
    # so if foobar = 1.0 and you have foobar-1.1 in the repo and bazquux1.2 
    # obsoletes foobar then bazquux would get installed.
    
    #tricksy - 
    # go through list of pkgs - obsoleted and uplist
    # if match then obsolete those that can be obsoleted
    #     update those that can only be updated
    # if not match bitch and moan
    # check for duping problems - if something is updateable AND obsoleted
    # we want to obsoleted to take precedence over updateable
    

    # we have to look at pkgs that are available to update
    # AND pkgs that are obsoleted - b/c something could be obsoletable
    # but not updateable
    
    # best to build one list with updated and obsoleteable
    oulist = []
    globalupgrade = 0
    for oname in obsoleted.keys():
        if rpmnevral.exists(oname):
            ((e, v, r, oarch, l, i), s) = rpmnevral._get_data(oname)
            oulist.append((oname, oarch))

    for (name,  arch) in uplist:
        oulist.append((name, arch))

    if type(userlist) is types.StringType and userlist == 'all':
        userlist = ['*']
        globalupgrade = 1

    for n in userlist:
        log(5, 'userlist entry %s' % n)
        pkgfound = 0
        for (name, arch) in oulist:
            if n == name or fnmatch.fnmatch(name, n):
                pkgfound = 1
                log(4, '%s matched in oulist' % name)
                if obsoleted.has_key(name):
                    for (obsname, obsarch) in obsoleted[name]:
                        log(4, '%s obsoleted by %s' % (name, obsname))
                        ((e, v, r, a, l, i), s) = hinevral._get_data(obsname, obsarch)
                        tsnevral.add((obsname,e,v,r,a,l,i),'u')
                else:
                    log(4,"Updating: %s" % name)
                    ((e, v, r, a, l, i), s)=hinevral._get_data(name, arch)
                    tsnevral.add((name,e,v,r,a,l,i),'u')
        if not pkgfound:
            if rpmnevral.exists(n):
                errorlog(1,"No Upgrades available for %s." % (n))
            else:
                if globalupgrade:
                    errorlog(0,"No Upgrades available.")
                else:
                    errorlog(0,"Cannot find any package matching %s available to be upgraded." % (n))
            if exitoninstalled:
                sys.exit(1)
            

def erasepkgs(tsnevral,rpmnevral,userlist, exitoninstalled):
    #mark for erase iff the userlist item exists in the rpmnevral
    # one thing this should do - it should look at the name of each item and see
    # if it is specifying a certain version of a pkg
    # if so it should parse the version and make sure we have it installed
    # if so then mark that SPECIFIC version for removal.
    
    for n in userlist:
        foundit = 0
        for (name,arch) in rpmnevral.NAkeys():
            if n == name or fnmatch.fnmatch(name, n):
                foundit = 1
                log(4,"Erasing %s" % (name))
                ((e, v, r, a, l, i), s)=rpmnevral._get_data(name,arch)
                tsnevral.add((name,e,v,r,a,l,i),'e')
        if foundit == 0:
            errorlog(0, _("Erase: No matches for %s") % n)
            if exitoninstalled:
                sys.exit(1)

def installgroups(rpmnevral, nulist, uplist, grouplist):
    """for each group requested attempt to install all pkgs/metapkgs of default
       or mandatory. Also recurse lists of groups to provide for them too."""
    returnlist = []
    nupkglist = []
    for (name, arch) in nulist:
        nupkglist.append(name)
        
    for group in grouplist:
        if group not in GroupInfo.grouplist:
            errorlog(0, _('Group %s does not exist') % group)
            return returnlist
        pkglist = GroupInfo.pkgTree(group)
        for pkg in pkglist:
            if pkg in nupkglist:
                log(4, 'Adding %s to groupinstall for %s' % (pkg, group))
                returnlist.append(pkg)
        
    return returnlist
        
        
        
        
def updategroups(rpmnevral, nulist, uplist, userlist):
    """get list of any pkg in group that is installed, check to update it
       get list of any mandatory or default pkg attempt to update it if it is installed
       or install it if it is not installed"""
    groups = GroupInfo.grouplist
    groupsmatch = []
    for group in groups:
        for item in userlist:
            if group == item or fnmatch.fnmatch(group, item):
                groupsmatch.append(group)
    uplist_names = []
    groupsmatch.sort()
    updatepkgs = []
    installpkgs = []
    for (name, arch) in uplist:
        uplist_names.append(name)

        
    for group in groupsmatch:
        required = GroupInfo.requiredPkgs(group)
        all = GroupInfo.pkgTree(group)
        for pkg in all:
            if rpmnevral.exists(pkg):
                if pkg in uplist_names:
                    updatepkgs.append((group, pkg))
            else:
                if pkg in required:
                    installpkgs.append((group, pkg))
    for (group, pkg) in updatepkgs:
        log(2, _('From %s updating %s') % (group, pkg))
    for (group, pkg) in installpkgs:
        log(2, _('From %s installing %s') % (group, pkg))
    if len(installpkgs) + len(updatepkgs) == 0:
        log(2, _('Nothing in any group to update or install'))
    return installpkgs, updatepkgs
             
def listpkginfo(pkglist, userlist, nevral, short):
    if len(pkglist) > 0:
        if short:
            log(2, "%-36s%-7s%-25s%-12s" %(_('Name'),_('Arch'),_('Version'), _('Repo')))
            log(2, "-" * 80)
        pkglist.sort(clientStuff.nasort)
        if type(userlist) is types.StringType:
            if userlist=='all' or userlist =='updates':
                for (name, arch) in pkglist:
                    if short:
                        (e,v,r) = nevral.evr(name,arch)
                        id = nevral.serverid(name, arch)
                        if e == '0':
                            ver = '%s-%s' % (v, r)
                        else:
                            ver = '%s:%s-%s' % (e, v, r)
                        print "%-36s%-7s%-25s%-12s" %(name, arch, ver, id)
                    else:
                        displayinfo(name, arch, nevral)
                print ' '
        else:    
            for (name,arch) in pkglist:
                for n in userlist:
                    pattern = fnmatch.translate(n)
                    regex = re.compile(pattern, re.IGNORECASE)
                    if n == name or regex.match(name):
                        if short:
                            (e,v,r)=nevral.evr(name,arch)
                            id = nevral.serverid(name, arch)
                            if e == '0':
                                ver = '%s-%s' % (v, r)
                            else:
                                ver = '%s:%s-%s' % (e, v, r)
                            print "%-36s%-7s%-25s%-12s" %(name, arch, ver, id)
                        else:
                            displayinfo(name, arch, nevral)
            print ' '
    else:
        print _("No Packages Available to List")

def displayinfo(name, arch, nevral):
    hdr = nevral.getHeader(name, arch)
    id = nevral.serverid(name, arch)
    if id == 'db':
        repo = 'Locally Installed'
    else:
        repo = conf.servername[id]
        
    print _("Name   : %s") % hdr[rpm.RPMTAG_NAME]
    print _("Arch   : %s") % hdr[rpm.RPMTAG_ARCH]
    print _("Version: %s") % hdr[rpm.RPMTAG_VERSION]
    print _("Release: %s") % hdr[rpm.RPMTAG_RELEASE]
    print _("Size   : %s") % clientStuff.descfsize(hdr[rpm.RPMTAG_SIZE])
    print _("Group  : %s") % hdr[rpm.RPMTAG_GROUP]
    print _("Repo   : %s") % repo
    print _("Summary: %s") % hdr[rpm.RPMTAG_SUMMARY]
    print _("Description:\n %s") % hdr[rpm.RPMTAG_DESCRIPTION]
    print ""
    

def listgroups(userlist):
    """lists groups - should handle 'installed', 'all', glob, empty,
       maybe visible and invisible too"""
    # this needs tidying and needs to handle empty statements and globs
    # it also needs to handle a userlist - duh
    # take list - if it's zero then it's '_all_' - push that into list
    # otherwise iterate over list producing output
    if len(userlist) > 0:
        if userlist[0] == "hidden":
            groups = GroupInfo.grouplist
            userlist.pop(0)
        else:
            groups = GroupInfo.visible_groups
    else:
        groups = GroupInfo.visible_groups
    
    if len(userlist) == 0:
        userlist = ['_all_']

    groups.sort()
    for item in userlist:
        if item == 'installed':
            print 'Installed Groups'
            for group in groups:
                if GroupInfo.isGroupInstalled(group):
                    grpid = GroupInfo.group_by_name[group]
                    log(4, '%s - %s' % (grpid, group))
                    print '   %s' % group
        elif item == 'available':
            print 'Available Groups'
            for group in groups:
                if not GroupInfo.isGroupInstalled(group):
                    grpid = GroupInfo.group_by_name[group]
                    log(4, '%s - %s' % (grpid, group))
                    print '   %s' % group
        elif item == '_all_':
            print 'Installed Groups'
            for group in groups:
                if GroupInfo.isGroupInstalled(group):
                    grpid = GroupInfo.group_by_name[group]
                    log(4, '%s - %s' % (grpid, group))
                    print '   %s' % group
                    
            print 'Available Groups'
            for group in groups:
                if not GroupInfo.isGroupInstalled(group):
                    grpid = GroupInfo.group_by_name[group]
                    log(4, '%s - %s' % (grpid, group))
                    print '   %s' % group
        else:
            for group in groups:
                if group == item or fnmatch.fnmatch(group, item):
                    grpid = GroupInfo.group_by_name[group]
                    log(4, '%s - %s' % (grpid, group))
                    displayPkgsInGroups(group)

def displayPkgsInGroups(group):
    print 'Group: %s' % group
    if len(GroupInfo.sub_groups[group]) > 0:
        print ' Required Groups:'
        for item in GroupInfo.sub_groups[group]:
            print '   %s' % item
    if len(GroupInfo.default_metapkgs[group]) > 0:
        print ' Default Metapkgs:'
        for item in GroupInfo.default_metapkgs[group]:
            print '   %s' % item
    if len(GroupInfo.optional_metapkgs[group]) > 0:
        print ' Optional Metapkgs:'
        for item in GroupInfo.optional_metapkgs[group]:
            print '   %s' % item
    if len(GroupInfo.mandatory_pkgs[group]) > 0:
        print ' Mandatory Packages:'
        for item in GroupInfo.mandatory_pkgs[group]:
            print '   %s' % item
    if len(GroupInfo.default_pkgs[group]) > 0:
        print ' Default Packages:'
        for item in GroupInfo.default_pkgs[group]:
            print '   %s' % item
    if len(GroupInfo.optional_pkgs[group]) > 0:
        print ' Optional Packages'
        for item in GroupInfo.optional_pkgs[group]:
            print '   %s' % item


def search(usereq, nulist, nevral, localrpmdb, tagslist):
    """search the requested tags for the userreq"""

    results = 0
    if localrpmdb == 0:
        for (name, arch) in nulist:
            hdr = nevral.getHeader(name, arch)
            (epoch, ver, rel) = nevral.evr(name, arch)
            id = nevral.serverid(name, arch)
            searchlist = []
            for tag in tagslist:
                tagdata = hdr[tag]
                if tagdata is None:
                    continue
                if type(tagdata) is types.ListType:
                    searchlist.extend(tagdata)
                else:
                    searchlist.append(tagdata)

            for req in usereq:
                req = '*' + req + '*'
                pattern = fnmatch.translate(req)
                regex = re.compile(pattern, re.IGNORECASE)
                for item in searchlist:
                    log(4, '%s vs %s' % (item, req))
                    if req == item or regex.match(item):
                        results = results + 1
                        log(2, _('Available package: %s.%s %s:%s-%s from %s matches with\n %s') % 
                                (name, arch, epoch, ver, rel, id, item))
            del searchlist
            
    elif localrpmdb == 1:
        matchlist = ts.match()
        for hdrobj in matchlist:
            (name, epoch, ver, rel, arch) = hdrobj.nevra()
            if epoch is None:
                epoch = 0
            searchlist = []
            for tag in tagslist:
                tagdata = hdrobj._getTag(tag)
                if tagdata is None:
                    continue
                if type(tagdata) is types.ListType:
                    searchlist.extend(tagdata)
                else:
                    searchlist.append(tagdata)

            for req in usereq:
                req = '*' + req + '*'
                for item in searchlist:
                    log(4, '%s vs %s' % (item, req))
                    if req == item or fnmatch.fnmatch(item, req):
                        results = results + 1
                        log(2, _('Installed package: %s.%s %s:%s-%s matches with\n %s') % 
                                (name, arch, epoch, ver, rel, item))
            del searchlist
    else:
        errorlog(1, _('localrpmdb not defined'))
        
    if results > 0:
        log(2, _('%s results returned') % results)
    else:
        log(2, _('No packages found'))
    
    

def kernelupdate(tsnevral):
    #figure out if we have updated a kernel
    #do what up2date does to update lilo and/or grub
    kernel_list = []
    # reopen the database read/write
    for (name,arch) in tsnevral.NAkeys():
        s = tsnevral.state(name,arch)
        if s in ['i','u','ud','iu']:
            if name in conf.kernelpkgnames:
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
        log(2, _('Kernel Updated/Installed, checking for bootloader'))
        # code from up2date/up2date.py
        #figure out which bootloader, run the script for that bootloader
        import checkbootloader
        bootloader = checkbootloader.whichBootLoader()
        import up2datetheft
        if bootloader == "LILO":
            from lilocfg import LiloConfError, LiloConfRestoreError, LiloInstallError, LiloConfReadError, LiloConfParseError
            log(2, _('Lilo found - adding kernel to lilo and making it the default'))
            try:
                up2datetheft.install_lilo(kernel_list)
            except LiloConfError, e:
                errorlog(0, '%s' % e)
            except LiloConfRestoreError, e:
                errorlog(0, '%s' % e)
            except LiloConfReadError, e:
                errorlog(0, '%s' % e)
            except LiloInstallError, e:
                errorlog(0, '%s' % e)
            except LiloConfParserError, e:
                errorlog(0, '%s' % e)
        elif bootloader == "GRUB":
            # at the moment, kernel rpms are supposed to grok grub
            # and do the Right Thing. Just a placeholder for doc purposes and
            #to put the kernels in the right order
            log(2, _('Grub found - making this kernel the default'))
            up2datetheft.install_grub(kernel_list)
        else:
            errorlog(1, _('No bootloader found, Cannot configure kernel, continuing.'))
            filelog(1, _('No bootloader found, Cannot configure kernel.'))
