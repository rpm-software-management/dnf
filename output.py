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
from i18n import _

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
        
def sortPkgObj(pkg1 ,pkg2):
    """sorts a list of package tuples by name"""
    if pkg1.name > pkg2.name:
        return 1
    elif pkg1.name == pkg2.name:
        return 0
    else:
        return -1
    


def simpleList(pkg):
    n = pkg.name
    a = pkg.arch
    e = pkg.epoch
    v = pkg.version
    r = pkg.release
    repo = pkg.returnSimple('repoid')
    if e != '0':
        ver = '%s:%s-%s' % (e, v, r)
    else:
        ver = '%s-%s' % (v, r)
    
    print "%-36s%-7s%-25s%-12s" % (n, a, ver, repo)


def infoOutput(pkg):
    print _("Name   : %s") % pkg.name
    print _("Arch   : %s") % pkg.arch
    print _("Version: %s") % pkg.version
    print _("Release: %s") % pkg.release
#    print _("Size   : %s") % clientStuff.descfsize(hdr[rpm.RPMTAG_SIZE])
#    print _("Group  : %s") % hdr[rpm.RPMTAG_GROUP]
    print _("Repo   : %s") % pkg.returnSimple('repoid')
    print _("Summary: %s") % pkg.returnSimple('summary')
    print _("Description:\n %s") % pkg.returnSimple('description')
    print ""

    
def listPkgs(pkgLists, outputType):
    """outputs based on whatever outputType is. Current options:
       'list' - simple pkg list
       'info' - similar to rpm -qi output
       'rss' - rss feed-type output"""
    
    if outputType in ['list', 'info']:
        thingslisted = 0
        for (lst, description) in pkgLists:
            if len(lst) > 0:
                thingslisted = 1
                print '%s packages' % description
                lst.sort(sortPkgObj)
                for pkg in lst:
                    if outputType == 'list':
                        simpleList(pkg)
                    elif outputType == 'info':
                        infoOutput(pkg)
                    else:
                        print 'foo'
                        pass

        if thingslisted == 0:
            return 1, ['No Packages to list']
    
    elif outputType == 'rss':
        # take recent updates only and dump to an rss compat output
        pass
    

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
