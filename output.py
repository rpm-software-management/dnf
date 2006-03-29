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
# Copyright 2005 Duke University 

import os
import os.path
import sys
import time
from i18n import _

from urlgrabber.progress import TextMeter
from yum.misc import sortPkgObj

try:
    import readline
except:
    pass

import yum.Errors

class YumOutput:

    def printtime(self):
        months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                  'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        now = time.localtime(time.time())
        ret = months[int(time.strftime('%m', now)) - 1] + \
              time.strftime(' %d %T ', now)
        return ret
         
    def failureReport(self, errobj):
        """failure output for failovers from urlgrabber"""
        
        self.errorlog(1, '%s: %s' % (errobj.url, str(errobj.exception)))
        self.errorlog(1, 'Trying other mirror.')
        raise errobj.exception
    
        
    def simpleProgressBar(self, current, total, name=None):
        progressbar(current, total, name)
    
    def simpleList(self, pkg):
        ver = pkg.printVer()
        na = '%s.%s' % (pkg.name, pkg.arch)
        repo = pkg.returnSimple('repoid')
        
        print "%-40.40s %-22.22s %-16.16s" % (na, ver, repo)
    
        
    def infoOutput(self, pkg):
        print _("Name   : %s") % pkg.name
        print _("Arch   : %s") % pkg.arch
        if pkg.epoch != "0":
            print _("Epoch  : %s") % pkg.epoch
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
           'info' - similar to rpm -qi output"""
        
        if outputType in ['list', 'info']:
            thingslisted = 0
            if len(lst) > 0:
                thingslisted = 1
                print '%s' % description
                lst.sort(sortPkgObj)
                for pkg in lst:
                    if outputType == 'list':
                        self.simpleList(pkg)
                    elif outputType == 'info':
                        self.infoOutput(pkg)
                    else:
                        pass
    
            if thingslisted == 0:
                return 1, ['No Packages to list']
        
    
        
    def userconfirm(self):
        """gets a yes or no from the user, defaults to No"""

        while True:            
            choice = raw_input('Is this ok [y/N]: ')
            choice = choice.lower()
            if len(choice) == 0 or choice[0] in ['y', 'n']:
                break

        if len(choice) == 0 or choice[0] != 'y':
            return False
        else:            
            return True
                
    
    def displayPkgsInGroups(self, group):
        print '\nGroup: %s' % group.name
        if group.description != "":
            print ' Description: %s' % group.description
        if len(group.mandatory_packages.keys()) > 0:
            print ' Mandatory Packages:'
            for item in group.mandatory_packages.keys():
                print '   %s' % item

        if len(group.default_packages.keys()) > 0:
            print ' Default Packages:'
            for item in group.default_packages.keys():
                print '   %s' % item
        
        if len(group.optional_packages.keys()) > 0:
            print ' Optional Packages:'
            for item in group.optional_packages.keys():
                print '   %s' % item

        if len(group.conditional_packages.keys()) > 0:
            print ' Conditional Packages:'
            for item, cond in group.conditional_packages.iteritems():
                print '   %s' % (item,)

    def depListOutput(self, results):
        """take a list of findDeps results and 'pretty print' the output"""
        
        for pkg in results.keys():
            print "package: %s" % pkg.compactPrint()
            if len(results[pkg].keys()) == 0:
                print "  No dependencies for this package"
                continue

            for req in results[pkg].keys():
                reqlist = results[pkg][req] 
                print "  dependency: %s" % pkg.prcoPrintable(req)
                if not reqlist:
                    print "   Unsatisfied dependency"
                    continue
                
                for po in reqlist:
                    print "   provider: %s" % po.compactPrint()


        
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

    def reportDownloadSize(self, packages):
        """Report the total download size for a set of packages"""
        totsize = 0
        error = False
        for pkg in packages:
            # Just to be on the safe side, if for some reason getting
            # the package size fails, log the error and don't report download
            # size
            try:
                size = int(pkg.size())
                totsize += size
            except:
                 error = True
                 self.errorlog(1, 'There was an error calculating total download size')
                 break

        if (not error):
            self.log(1, "Total download size: %s" % (self.format_number(totsize)))
            
    def listTransaction(self):
        """returns a string rep of the  transaction in an easy-to-read way."""
        
        self.tsInfo.makelists()
        if len(self.tsInfo) > 0:
            out = """
=============================================================================
 %-22s  %-9s  %-15s  %-16s  %-5s
=============================================================================
""" % ('Package', 'Arch', 'Version', 'Repository', 'Size')
        else:
            out = ""

        for (action, pkglist) in [('Installing', self.tsInfo.installed),
                            ('Updating', self.tsInfo.updated),
                            ('Removing', self.tsInfo.removed),
                            ('Installing for dependencies', self.tsInfo.depinstalled),
                            ('Updating for dependencies', self.tsInfo.depupdated),
                            ('Removing for dependencies', self.tsInfo.depremoved)]:
            if pkglist:
                totalmsg = "%s:\n" % action
            for txmbr in pkglist:
                (n,a,e,v,r) = txmbr.pkgtup
                evr = txmbr.po.printVer()
                repoid = txmbr.repoid
                pkgsize = float(txmbr.po.size())
                size = self.format_number(pkgsize)
                msg = " %-22s  %-9s  %-15s  %-16s  %5s\n" % (n, a,
                              evr, repoid, size)
                for obspo in txmbr.obsoletes:
                    appended = '     replacing  %s.%s %s\n\n' % (obspo.name,
                        obspo.arch, obspo.printVer())
                    msg = msg+appended
                totalmsg = totalmsg + msg
        
            if pkglist:
                out = out + totalmsg

        summary = """
Transaction Summary
=============================================================================
Install  %5.5s Package(s)         
Update   %5.5s Package(s)         
Remove   %5.5s Package(s)         
""" % (len(self.tsInfo.installed + self.tsInfo.depinstalled),
       len(self.tsInfo.updated + self.tsInfo.depupdated),
       len(self.tsInfo.removed + self.tsInfo.depremoved))
        out = out + summary
        
        return out
        
    def postTransactionOutput(self):
        out = ''
        
        self.tsInfo.makelists()

        for (action, pkglist) in [('Removed', self.tsInfo.removed), 
                                  ('Dependency Removed', self.tsInfo.depremoved),
                                  ('Installed', self.tsInfo.installed), 
                                  ('Dependency Installed', self.tsInfo.depinstalled),
                                  ('Updated', self.tsInfo.updated),
                                  ('Dependency Updated', self.tsInfo.depupdated),
                                  ('Replaced', self.tsInfo.obsoleted)]:
            
            if len(pkglist) > 0:
                out += '\n%s:' % action
                for txmbr in pkglist:
                    (n,a,e,v,r) = txmbr.pkgtup
                    msg = " %s.%s %s:%s-%s" % (n,a,e,v,r)
                    out += msg
        
        return out

    def setupProgessCallbacks(self):
        """sets up the progress callbacks and various 
           output bars based on debug level"""

        # if we're below 2 on the debug level we don't need to be outputting
        # progress bars - this is hacky - I'm open to other options
        # One of these is a download
        if self.conf.debuglevel < 2 or not sys.stdout.isatty():
            self.repos.setProgressBar(None)
            self.repos.callback = None
        else:
            self.repos.setProgressBar(TextMeter(fo=sys.stdout))
            self.repos.callback = CacheProgressCallback(self.log, self.errorlog,
                                                        self.filelog)
        # setup our failure report for failover
        freport = (self.failureReport,(),{})
        self.repos.setFailureCallback(freport)
        
        # setup our depsolve progress callback
        dscb = DepSolveProgressCallBack(self.log, self.errorlog)
        self.dsCallback = dscb
            
    
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
       

class CacheProgressCallback:

    '''
    The class handles text output callbacks during metadata cache updates.
    '''
    
    def __init__(self, log, errorlog, filelog=None):
        self.log = log
        self.errorlog = errorlog
        self.filelog = filelog

    def log(self, level, message):
        self.log(level, message)

    def errorlog(self, level, message):
        if self.errorlog:
            self.errorlog(level, message)

    def filelog(self, level, message):
        if self.filelog:
            self.filelog(level, message)

    def progressbar(self, current, total, name=None):
        progressbar(current, total, name)


def progressbar(current, total, name=None):
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
        
