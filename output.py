#!/usr/bin/python -t

"""This handles actual output from the cli"""

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
# Copyright 2004 Duke University 

import sys
import time

def printtime():
    return time.strftime('%b %d %H:%M:%S', time.localtime(time.time()))
    

def simpleProgressBar(current, total, name=None):
    """simple progress bar 50 # marks"""
    
    mark = '#'

    if current == 0:
        percent = 0 
    else:
        percent = current*100/total

    numblocks = int(percent/2)
    hashbar = mark * numblocks
    if name is None:
        output = '\r%-50s %d/%d' % (hashbar, current, total)
    else:
        output = '\r%s:%-50s %d/%d' % (name, hashbar, current, total)
     
    sys.stdout.write(output)
    if current == total:
        sys.stdout.write('\n')
        


def listPkgs(pkgLists, outputType):
    """outputs based on whatever outputType is. Current options:
       'list' - simple pkg list
       'info' - similar to rpm -qi output
       'genrate-rss' - rss feed-type output"""
    
    FIXMEFIXMEFIXME
    if len(lst) > 0:
            if len(self.extcmds) > 0:
                exactmatch, matched, unmatched = yum.packages.parsePackages(lst, self.extcmds)
                lst = yum.misc.unique(matched + exactmatch)

    # check our reduced list
        if len(lst) > 0:
            thingslisted = 1
            self.log(2, '%s packages' % name)
            lst.sort(sortPkgTup)
            if name in ['Installed', 'Extra']:
                for pkg in lst:
                    (n, a, e, v, r) = pkg
                    if e != '0':
                        ver = '%s:%s-%s' % (e, v, r)
                    else:
                        ver = '%s-%s' % (v, r)
                        
                    self.log(2, "%-36s%-7s%-25s%-12s" % (n, a, ver, 'installed'))
            else:
                for pkg in lst:
                    po = self.getPackageObject(pkg)
                    if po.epoch != '0':
                        ver = '%s:%s-%s' % (po.epoch, po.version, po.release)
                    else:
                        ver = '%s-%s' % (po.version, po.release)
                    self.log(2, "%-36s%-7s%-25s%-12s" % (po.name, po.arch, 
                                           ver, po.returnSimple('repoid')))

    if thingslisted == 0:
        self.errorlog(1, 'No Packages to list')

    return 0, ['Success']
    
    def userconfirm(self):
        """gets a yes or no from the user, defaults to No"""
        choice = raw_input('Is this ok [y/N]: ')
        if len(choice) == 0:
            return 1
        else:
            if choice[0] != 'y' and choice[0] != 'Y':
                return 1
            else:
                return 0        
                


#FIXME - we should be taking a simple list of packages and displaying them or 
#giving their info - consider copying the rpm -qi interface for the info output
#need to get repo information per-pkg - so the search interface for the packageSack
#should be better

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

       
def format_number(number, SI=0, space=' '):
    """Turn numbers into human-readable metric-like numbers"""
    symbols = ['',  # (none)
                'k', # kilo
                'M', # mega
                'G', # giga
                'T', # tera
                'P', # peta
                'E', # exa
                'Z', # zetta
                'Y'] # yotta

    if SI: step = 1000.0
    else: step = 1024.0

    thresh = 999
    depth = 0

    # we want numbers between 
    while number > thresh:
        depth  = depth + 1
        number = number / step

    # just in case someone needs more than 1000 yottabytes!
    diff = depth - len(symbols) + 1
    if diff > 0:
        depth = depth - diff
        number = number * thresh**depth

    if type(number) == type(1) or type(number) == type(1L):
        format = '%i%s%s'
    elif number < 9.95:
        # must use 9.95 for proper sizing.  For example, 9.99 will be
        # rounded to 10.0 with the .1f format string (which is too long)
        format = '%.1f%s%s'
    else:
        format = '%.0f%s%s'

    return(format % (number, space, symbols[depth]))
