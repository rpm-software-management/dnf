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

import os
import os.path
import sys
import time
from i18n import _
import libxml2

import yum.Errors

class YumOutput:

    def printtime(self):
        return time.strftime('%b %d %H:%M:%S ', time.localtime(time.time()))
        
    
    def failureReport(self, errobj):
        """failure output for failovers from urlgrabber"""
        
        self.errorlog(1, '%s: %s' % (errobj.url, str(errobj.exception)))
        self.errorlog(1, 'Trying other mirror.')
        raise errobj.exception
    
        
    def simpleProgressBar(self, current, total, name=None):
        """simple progress bar 50 # marks"""
        
        mark = '#'
        if not sys.stdout.isatty():
            return
            
        if current == 0:
            percent = 0 
        else:
            if total != 0:
                percent = current*100/total
            else:
                percent = 0
    
        numblocks = int(percent/2)
        hashbar = mark * numblocks
        if name is None:
            output = '\r%-50s %d/%d' % (hashbar, current, total)
        else:
            output = '\r%-10.10s: %-50s %d/%d' % (name, hashbar, current, total)
         
        if current <= total:
            sys.stdout.write(output)
    
        if current == total:
            sys.stdout.write('\n')
    
        sys.stdout.flush()
        
    
    def simpleList(self, pkg):
        ver = pkg.printVer()
        na = '%s.%s' % (pkg.name, pkg.arch)
        repo = pkg.returnSimple('repoid')
        
        print "%-40.40s %-22.22s %-16.16s" % (na, ver, repo)
    
        
    def infoOutput(self, pkg):
        print _("Name   : %s") % pkg.name
        print _("Arch   : %s") % pkg.arch
        print _("Version: %s") % pkg.version
        print _("Release: %s") % pkg.release
        print _("Size   : %s") % self.format_number(float(pkg.size()))
        print _("Repo   : %s") % pkg.returnSimple('repoid')
        print _("Summary: %s") % pkg.returnSimple('summary')
        print _("Description:\n %s") % pkg.returnSimple('description')
        print ""
    
    def updatesObsoletesList(self, uotup, changetype):
        """takes an updates or obsoletes tuple of pkgobjects and
           returns a simple printed string of the output and a string
           explaining the relationship between the tuple members"""
        (changePkg, instPkg) = uotup
        c_compact = changePkg.compactPrint()
        i_compact = '%s.%s' % (instPkg.name, instPkg.arch)
        c_repo = changePkg.repoid
        # FIXME - other ideas for how to print this out?
        print '%-35.35s [%.12s] %.10s %-20.20s' % (c_compact, c_repo, changetype, i_compact)

    def listPkgs(self, lst, description, outputType):
        """outputs based on whatever outputType is. Current options:
           'list' - simple pkg list
           'info' - similar to rpm -qi output
           'rss' - rss feed-type output"""
        
        if outputType in ['list', 'info']:
            thingslisted = 0
            if len(lst) > 0:
                thingslisted = 1
                print '%s' % description
                lst.sort(self.sortPkgObj)
                for pkg in lst:
                    if outputType == 'list':
                        self.simpleList(pkg)
                    elif outputType == 'info':
                        self.infoOutput(pkg)
                    else:
                        pass
    
            if thingslisted == 0:
                return 1, ['No Packages to list']
        
        elif outputType == 'rss':
            # take recent updates only and dump to an rss compat output
            if len(lst) > 0:
                if self.conf.getConfigOption('rss-filename') is None:
                    raise yum.Errors.YumBaseError, \
                       "No File specified for rss create"
                else:
                    fn = self.conf.getConfigOption('rss-filename')
    
                if fn[0] != '/':
                    cwd = os.getcwd()
                    fn = os.path.join(cwd, fn)
                try:
                    fo = open(fn, 'w')
                except IOError, e:
                    raise yum.Errors.YumBaseError, \
                       "Could not open file %s for rss create" % (e)

                doc = libxml2.newDoc('1.0')
                self.xmlescape = doc.encodeEntitiesReentrant
                rss = doc.newChild(None, 'rss', None)
                rss.setProp('version', '2.0')
                node = rss.newChild(None, 'channel', None)
                rssheader = self.startRSS(description)
                fo.write(rssheader)
                for pkg in lst:
                    item = self.rssnode(node, pkg)
                    fo.write(item.serialize("utf-8", 1))
                    item.unlinkNode()
                    item.freeNode()
                    del item
                
                end = self.endRSS()
                fo.write(end)
                fo.close()
                del fo
                doc.freeDoc()
                del doc
                
    def startRSS(self, description='Yum Package List'):
        """return string representation of rss preamble"""
    
        rfc822_format = "%a, %d %b %Y %X GMT"
        now = time.strftime(rfc822_format, time.gmtime())
        rssheader = """<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <title>%s</title>
        <link>http://linux.duke.edu/projects/yum/</link>
        <description>%s</description>
        <pubDate>%s</pubDate>
        <generator>Yum</generator>
        """ % (description, description, now)
        
        return rssheader
    
    def rssnode(self, node, pkg):
        """return an rss20 compliant item node
           takes a node, and a pkg object"""
        
        repo = self.repos.getRepo(pkg.repoid)
        url = repo.urls[0]
        rfc822_format = "%a, %d %b %Y %X GMT"
        clog_format = "%a, %d %b %Y GMT"
        xhtml_ns = "http://www.w3.org/1999/xhtml"
        escape = self.xmlescape
        
        item = node.newChild(None, 'item', None)
        title = escape(str(pkg))
        item.newChild(None, 'title', title)
        date = time.gmtime(float(pkg.returnSimple('buildtime')))
        item.newChild(None, 'pubDate', time.strftime(rfc822_format, date))
        item.newChild(None, 'guid', pkg.returnSimple('id'))
        link = url + '/' + pkg.returnSimple('relativepath')
        item.newChild(None, 'link', escape(link))

        # build up changelog
        changelog = ''
        cnt = 0
        for e in pkg.changelog:
            cnt += 1
            if cnt > 3: 
                changelog += '...'
                break
            (date, author, desc) = e
            date = time.strftime(clog_format, time.gmtime(float(date)))
            changelog += '%s - %s\n%s\n\n' % (date, author, desc)
        body = item.newChild(None, "body", None)
        body.newNs(xhtml_ns, None)
        body.newChild(None, "p", escape(pkg.returnSimple('summary')))
        body.newChild(None, "pre", escape(pkg.returnSimple('description')))
        body.newChild(None, "p", 'Change Log:')
        body.newChild(None, "pre", escape(changelog))
        description = '<pre>%s - %s\n\n' % (escape(pkg.name), 
                                            escape(pkg.returnSimple('summary')))
        description += '%s\n\nChange Log:\n\n</pre>' % escape(pkg.returnSimple('description'))
        description += escape('<pre>%s</pre>' % escape(changelog))
        item.newChild(None, 'description', description)
        
        return item
        
    
    def endRSS(self):
        """end the rss output"""
        end="\n  </channel>\n</rss>\n"
        return end
    
        
    def userconfirm(self):
        """gets a yes or no from the user, defaults to No"""
        choice = raw_input('Is this ok [y/N]: ')
        if len(choice) == 0:
            return 0
        else:
            if choice[0] != 'y' and choice[0] != 'Y':
                return 0
            else:
                return 1
                
    
    def displayPkgsInGroups(self, group):
        print '\nGroup: %s' % group
        if len(self.groupInfo.sub_groups[group]) > 0:
            print ' Required Groups:'
            for item in self.groupInfo.sub_groups[group]:
                print '   %s' % item
        if len(self.groupInfo.default_metapkgs[group]) > 0:
            print ' Default Metapkgs:'
            for item in self.groupInfo.default_metapkgs[group]:
                print '   %s' % item
        if len(self.groupInfo.optional_metapkgs[group]) > 0:
            print ' Optional Metapkgs:'
            for item in self.groupInfo.optional_metapkgs[group]:
                print '   %s' % item
        if len(self.groupInfo.mandatory_pkgs[group]) > 0:
            print ' Mandatory Packages:'
            for item in self.groupInfo.mandatory_pkgs[group]:
                print '   %s' % item
        if len(self.groupInfo.default_pkgs[group]) > 0:
            print ' Default Packages:'
            for item in self.groupInfo.default_pkgs[group]:
                print '   %s' % item
        if len(self.groupInfo.optional_pkgs[group]) > 0:
            print ' Optional Packages'
            for item in self.groupInfo.optional_pkgs[group]:
                print '   %s' % item

           
    def format_number(self, number, SI=0, space=' '):
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

    def matchcallback(self, po, values):
        self.log(2, '\n\n')
        self.simpleList(po)
        self.log(2, 'Matched from:')
        for item in values:
            self.log(2, '%s' % item)

    def listTransaction(self):
        """displays the transaction in an easy-to-read way."""
        
        out = ''
        userout = ''
        depout = ''
        otherout = ''
        
        updated, installed, removed, obsoleted, depup, depinst, deprem = self.tsInfo.makelists()

        for (action, pkglist) in [('Remove', removed), ('Install', installed), 
                                  ('Update', updated)]:

            for txmbr in pkglist:
                (n,a,e,v,r) = txmbr.pkgtup
                msg = "  %s: %s.%s %s:%s-%s\n" % (action, n,a,e,v,r)
                userout = userout + msg
                   
        for (action, pkglist) in [('Remove', deprem), ('Install', depinst), 
                                  ('Update', depup)]:

            for txmbr in pkglist:
                (n,a,e,v,r) = txmbr.pkgtup
                msg = "  %s: %s.%s %s:%s-%s\n" % (action, n,a,e,v,r)
                depout = depout + msg
                   

        for txmbr in obsoleted:
            (n,a,e,v,r) = txmbr.pkgtup
            obspkg = None
            for (pkg, relationship) in txmbr.relatedto:
                if relationship == 'osboletedby':
                    obspkg = '%s.%s %s:%s-%s' % pkg
            if obspkg is not None:
                otherout = otherout + "  Obsoleting: %s.%s %s:%s-%s with %s\n" % (n, a, e, v, r, obspkg)

        out = "Transaction Listing:\n%s" % userout 
        if depout != '':
            out = out + "\nPerforming the following to resolve dependencies:\n%s" % depout
        if otherout != '':
            out = out + "\nOther Transactions:\n%s\n" % otherout
              
        return out

    def postTransactionOutput(self):
        out = ''
        
        updated, installed, removed, obsoleted, depup, depinst, deprem = self.tsInfo.makelists()

        for (action, pkglist) in [('Removed', removed), ('Dependency Removed', deprem),
                                  ('Installed', installed), ('Dependency Installed', depinst),
                                  ('Updated', updated), ('Dependency Updated', depup),
                                  ('Obsoleted', obsoleted)]:
            
            if len(pkglist) > 0:
                out += '\n%s:' % action
                for txmbr in pkglist:
                    (n,a,e,v,r) = txmbr.pkgtup
                    msg = " %s.%s %s:%s-%s" % (n,a,e,v,r)
                    out += msg
        
        return out


    
    def pickleRecipe(self):
        """ don't ask """
        
        recipe = """
        
                        7 Day Sweet Pickle Recipe

Recipe By     : Simply Good Cooking Pennsylvanis Dutch Style
Serving Size  : 1    Preparation Time :0:00
Categories    : Canned                           Pickles

  Amount  Measure       Ingredient -- Preparation Method
--------  ------------  --------------------------------
   7      pounds        cucumber
                        water to cover
   1      quart         vinegar
   8      cups          sugar
   2      tablespoons   salt
   2      tablespoons   mixed pickle spices

Wash cucumbers & cover with boiling water.  Let stand 24 hours and repeat
process daily using fresh hot water until the 5th day.  On the 5th morning,
cut cucumbers into 1/4 inch rings.  Prepare vinegar brine: bring vinegar,
sugar, salt & spices to a boil.  Pour over cucmbers.  let stand 24 hours.
The next morning, drain off brine; reheat, add cucmbers & bring to a boil.
Pack in jars & seal while hot.

                   - - - - - - - - - - - - - - - - - -

NOTES : This should be processed in a boiling water bath to avoid risk of
contamination.        


"""
        return recipe
    

class DepSolveProgressCallBack:
    """provides text output callback functions for Dependency Solver callback"""
    
    def __init__(self, log, errorlog):
        """requires yum-cli log and errorlog functions as arguments"""
        self.log = log
        self.errorlog = errorlog
        self.loops = 0
    
    def pkgAdded(self, pkgtup, mode):
        modedict = { 'i': 'installed',
                     'u': 'updated',
                     'o': 'obsoleted',
                     'e': 'erased'}
        (n, a, e, v, r) = pkgtup
        modeterm = modedict[mode]
        self.log(2, '---> Package %s.%s %s:%s-%s set to be %s' % (n, a, e, v, r, modeterm))
        
    def start(self):
        self.loops += 1
        
    def tscheck(self):
        self.log(2, '--> Running transaction check')
        
    def restartLoop(self):
        self.loops += 1
        self.log(2, '--> Restarting Dependency Resolution with new changes.')
        self.log(3, '---> Loop Number: %d' % self.loops)
    
    def end(self):
        self.log(2, '--> Finished Dependency Resolution')

    
    def procReq(self, name, formatted_req):
        self.log(2, '--> Processing Dependency: %s for package: %s' % (formatted_req, name))
        
    
    def unresolved(self, msg):
        self.log(2, '--> Unresolved Dependency: %s' % msg)

    
    def procConflict(self, name, confname):
        self.log(2, '--> Processing Conflict: %s conflicts %s' % (name, confname))

    def transactionPopulation(self):
        self.log(2, '--> Populating transaction set with selected packages. Please wait.')
    
    def downloadHeader(self, name):
        self.log(2, '---> Downloading header for %s to pack into transaction set.' % name)
        
