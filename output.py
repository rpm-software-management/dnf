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

import sys
import time
import logging
import types
import gettext
import rpm
from yum.i18n import _

import re # For YumTerm

from urlgrabber.progress import TextMeter
from urlgrabber.grabber import URLGrabError
from yum.misc import sortPkgObj, prco_tuple_to_string
from rpmUtils.miscutils import checkSignals
from yum.constants import *

from yum import logginglevels
from yum.rpmtrans import RPMBaseCallback

from textwrap import fill

class YumTextMeter(TextMeter):

    """
    Text progress bar output.
    """

    def update(self, amount_read, now=None):
        checkSignals()
        TextMeter.update(self, amount_read, now)

class YumTerm:
    """some terminal "UI" helpers based on curses"""

    # From initial search for "terminfo and python" got:
    # http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/475116
    # ...it's probably not copyrightable, but if so ASPN says:
    #
    #  Except where otherwise noted, recipes in the Python Cookbook are
    # published under the Python license.

    __enabled = True

    columns = 80
    lines   = 24
    # Output modes:
    MODE = {
        'bold' : '',
        'blink' : '',
        'dim' : '',
        'reverse' : '',
        'underline' : '',
        'normal' : ''
        }

    # Colours
    FG_COLOR = {
        'black' : '',
        'blue' : '',
        'green' : '',
        'cyan' : '',
        'red' : '',
        'magenta' : '',
        'yellow' : '',
        'white' : ''
        }

    BG_COLOR = {
        'black' : '',
        'blue' : '',
        'green' : '',
        'cyan' : '',
        'red' : '',
        'magenta' : '',
        'yellow' : '',
        'white' : ''
        }

    __cap_names = {
        'underline' : 'smul',
        'reverse' : 'rev',
        'normal' : 'sgr0',
        }
    
    __colors = {
        'black' : 0,
        'blue' : 1,
        'green' : 2,
        'cyan' : 3,
        'red' : 4,
        'magenta' : 5,
        'yellow' : 6,
        'white' : 7
        }
    __ansi_colors = {
        'black' : 0,
        'red' : 1,
        'green' : 2,
        'yellow' : 3,
        'blue' : 4,
        'magenta' : 5,
        'cyan' : 6,
        'white' : 7
        }

    def __init__(self, term_stream=None):
        # Curses isn't available on all platforms
        try:
            import curses
        except:
            self.__enabled = False
            return

        # If the stream isn't a tty, then assume it has no capabilities.
        if not term_stream:
            term_stream = sys.stdout
        if not term_stream.isatty():
            self.__enabled = False
            return
        
        # Check the terminal type.  If we fail, then assume that the
        # terminal has no capabilities.
        try:
            curses.setupterm(fd=term_stream.fileno())
        except:
            self.__enabled = False
            return
        self._ctigetstr = curses.tigetstr

        self.columns = curses.tigetnum('cols')
        self.lines   = curses.tigetnum('lines')
        
        # Look up string capabilities.
        for cap_name in self.MODE:
            mode = cap_name
            if cap_name in self.__cap_names:
                cap_name = self.__cap_names[cap_name]
            self.MODE[mode] = self._tigetstr(cap_name) or ''

        # Colors
        set_fg = self._tigetstr('setf')
        if set_fg:
            for (color, val) in self.__colors.items():
                self.FG_COLOR[color] = curses.tparm(set_fg, val) or ''
        set_fg_ansi = self._tigetstr('setaf')
        if set_fg_ansi:
            for (color, val) in self.__ansi_colors.items():
                self.FG_COLOR[color] = curses.tparm(set_fg_ansi, val) or ''
        set_bg = self._tigetstr('setb')
        if set_bg:
            for (color, val) in self.__colors.items():
                self.BG_COLOR[color] = curses.tparm(set_bg, val) or ''
        set_bg_ansi = self._tigetstr('setab')
        if set_bg_ansi:
            for (color, val) in self.__ansi_colors.items():
                self.BG_COLOR[color] = curses.tparm(set_bg_ansi, val) or ''

    def _tigetstr(self, cap_name):
        # String capabilities can include "delays" of the form "$<2>".
        # For any modern terminal, we should be able to just ignore
        # these, so strip them out.
        cap = self._ctigetstr(cap_name) or ''
        return re.sub(r'\$<\d+>[/*]?', '', cap)

    def sub(self, haystack, beg, end, needles, escape=None):
        if not self.__enabled:
            return haystack

        if not escape:
            escape = re.escape

        render = lambda match: beg + match.group() + end
        for needle in needles:
            haystack = re.sub(escape(needle), render, haystack)
        return haystack
    def sub_norm(self, haystack, beg, needles, **kwds):
        return self.sub(haystack, beg, self.MODE['normal'], needles, **kwds)

    def sub_mode(self, haystack, mode, needles, **kwds):
        return self.sub_norm(haystack, self.MODE[mode], needles, **kwds)

    def sub_bold(self, haystack, needles, **kwds):
        return self.sub_mode(haystack, 'bold', needles)
    
    def sub_fg(self, haystack, color, needles, **kwds):
        return self.sub_norm(haystack, self.FG_COLOR[color], needles, **kwds)

    def sub_bg(self, haystack, color, needles, **kwds):
        return self.sub_norm(haystack, self.BG_COLOR[color], needles, **kwds)



class YumOutput:

    """
    Main output class for the yum command line.
    """

    def __init__(self):
        self.logger = logging.getLogger("yum.cli")
        self.verbose_logger = logging.getLogger("yum.verbose.cli")
        if hasattr(rpm, "expandMacro"):
            self.i18ndomains = rpm.expandMacro("%_i18ndomains").split(":")
        else:
            self.i18ndomains = ["redhat-dist"]

        self.term = YumTerm()
    
    def printtime(self):
        months = [_('Jan'), _('Feb'), _('Mar'), _('Apr'), _('May'), _('Jun'),
                  _('Jul'), _('Aug'), _('Sep'), _('Oct'), _('Nov'), _('Dec')]
        now = time.localtime(time.time())
        ret = months[int(time.strftime('%m', now)) - 1] + \
              time.strftime(' %d %T ', now)
        return ret
         
    def failureReport(self, errobj):
        """failure output for failovers from urlgrabber"""
        
        self.logger.error('%s: %s', errobj.url, str(errobj.exception))
        self.logger.error(_('Trying other mirror.'))
        raise errobj.exception
    
        
    def simpleProgressBar(self, current, total, name=None):
        progressbar(current, total, name)
    
    def simpleList(self, pkg):
        ver = pkg.printVer()
        na = '%s.%s' % (pkg.name, pkg.arch)
        
        print "%-40.40s %-22.22s %-16.16s" % (na, ver, pkg.repoid)


    def fmtKeyValFill(self, key, val):
        """ Return a key value pair in the common two column output format. """
        keylen = len(key)
        cols = self.term.columns
        nxt = ' ' * (keylen - 2) + ': '
        ret = fill(val, width=cols,
                   initial_indent=key, subsequent_indent=nxt)
        if ret.count("\n") > 1 and keylen > (cols / 3):
            # If it's big, redo it again with a smaller subsequent off
            ret = fill(val, width=cols,
                       initial_indent=key, subsequent_indent='     ...: ')
        return ret
    
    def fmtSection(self, name, fill='='):
        name = str(name)
        cols = self.term.columns - 2
        name_len = len(name)
        if name_len >= (cols - 4):
            beg = end = fill * 2
        else:
            beg = fill * ((cols - name_len) / 2)
            end = fill * (cols - name_len - len(beg))

        return "%s %s %s" % (beg, name, end)

    def infoOutput(self, pkg):
        def enc(s):
            """Get the translated version from specspo and ensure that
            it's actually encoded in UTF-8."""
            if type(s) == unicode:
                s = s.encode("UTF-8")
            if len(s) > 0:
                for d in self.i18ndomains:
                    t = gettext.dgettext(d, s)
                    if t != s:
                        s = t
                        break
            s = unicode(s, "UTF-8")
            return s
        print _("Name       : %s") % pkg.name
        print _("Arch       : %s") % pkg.arch
        if pkg.epoch != "0":
            print _("Epoch      : %s") % pkg.epoch
        print _("Version    : %s") % pkg.version
        print _("Release    : %s") % pkg.release
        print _("Size       : %s") % self.format_number(float(pkg.size))
        print _("Repo       : %s") % pkg.repoid
        if self.verbose_logger.isEnabledFor(logginglevels.DEBUG_3):
            print _("Committer  : %s") % pkg.committer
        print self.fmtKeyValFill(_("Summary    : "), enc(pkg.summary))
        if pkg.url:
            print _("URL        : %s") % pkg.url
        print _("License    : %s") % pkg.license
        print self.fmtKeyValFill(_("Description: "), enc(pkg.description))
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
            return 0, []
        
    
        
    def userconfirm(self):
        """gets a yes or no from the user, defaults to No"""

        while True:
            try:
                choice = raw_input(_('Is this ok [y/N]: ').encode("utf-8"))
            except UnicodeEncodeError:
                raise
            except:
                choice = ''
            choice = choice.lower()
            if len(choice) == 0 or choice in [_('y'), _('n'), _('yes'), _('no')]:
                break

        if len(choice) == 0 or choice not in [_('y'), _('yes')]:
            return False
        else:            
            return True
                
    
    def displayPkgsInGroups(self, group):
        print _('\nGroup: %s') % group.name
        if group.description != "":
            print _(' Description: %s') % group.description.encode("UTF-8")
        if len(group.mandatory_packages) > 0:
            print _(' Mandatory Packages:')
            for item in group.mandatory_packages:
                print '   %s' % item

        if len(group.default_packages) > 0:
            print _(' Default Packages:')
            for item in group.default_packages:
                print '   %s' % item
        
        if len(group.optional_packages) > 0:
            print _(' Optional Packages:')
            for item in group.optional_packages:
                print '   %s' % item

        if len(group.conditional_packages) > 0:
            print _(' Conditional Packages:')
            for item, cond in group.conditional_packages.iteritems():
                print '   %s' % (item,)

    def depListOutput(self, results):
        """take a list of findDeps results and 'pretty print' the output"""
        
        for pkg in results:
            print _("package: %s") % pkg.compactPrint()
            if len(results[pkg]) == 0:
                print _("  No dependencies for this package")
                continue

            for req in results[pkg]:
                reqlist = results[pkg][req] 
                print _("  dependency: %s") % prco_tuple_to_string(req)
                if not reqlist:
                    print _("   Unsatisfied dependency")
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

    def matchcallback(self, po, values, matchfor=None):
        if self.conf.showdupesfromrepos:
            msg = '%s : ' % po
        else:
            msg = '%s.%s : ' % (po.name, po.arch)
        msg = self.fmtKeyValFill(msg, po.summary)
        if matchfor:
            msg = self.term.sub_bold(msg, matchfor)
        
        print msg
        self.verbose_logger.debug(_('Matched from:'))
        for item in values:
            if matchfor:
                item = self.term.sub_bold(item, matchfor)
            self.verbose_logger.debug('%s', item)
        self.verbose_logger.debug('\n\n')
        
    def reportDownloadSize(self, packages):
        """Report the total download size for a set of packages"""
        totsize = 0
        locsize = 0
        error = False
        for pkg in packages:
            # Just to be on the safe side, if for some reason getting
            # the package size fails, log the error and don't report download
            # size
            try:
                size = int(pkg.size)
                totsize += size
                try:
                   if pkg.verifyLocalPkg():
                       locsize += size
                except:
                   pass
            except:
                 error = True
                 self.logger.error(_('There was an error calculating total download size'))
                 break

        if (not error):
            if locsize:
                self.verbose_logger.log(logginglevels.INFO_1, _("Total size: %s"), 
                                        self.format_number(totsize))
            if locsize != totsize:
                self.verbose_logger.log(logginglevels.INFO_1, _("Total download size: %s"), 
                                        self.format_number(totsize - locsize))
            
    def listTransaction(self):
        """returns a string rep of the  transaction in an easy-to-read way."""
        
        self.tsInfo.makelists()
        if len(self.tsInfo) > 0:
            out = u"""
=============================================================================
 %-22s  %-9s  %-15s  %-16s  %-5s
=============================================================================
""" % (_('Package'), _('Arch'), _('Version'), _('Repository'), _('Size'))
        else:
            out = u""

        for (action, pkglist) in [(_('Installing'), self.tsInfo.installed),
                            (_('Updating'), self.tsInfo.updated),
                            (_('Removing'), self.tsInfo.removed),
                            (_('Installing for dependencies'), self.tsInfo.depinstalled),
                            (_('Updating for dependencies'), self.tsInfo.depupdated),
                            (_('Removing for dependencies'), self.tsInfo.depremoved)]:
            if pkglist:
                totalmsg = u"%s:\n" % action
            for txmbr in pkglist:
                (n,a,e,v,r) = txmbr.pkgtup
                evr = txmbr.po.printVer()
                repoid = txmbr.repoid
                pkgsize = float(txmbr.po.size)
                size = self.format_number(pkgsize)
                msg = u" %-22s  %-9s  %-15s  %-16s  %5s\n" % (n, a,
                              evr, repoid, size)
                for obspo in txmbr.obsoletes:
                    appended = _('     replacing  %s.%s %s\n\n') % (obspo.name,
                        obspo.arch, obspo.printVer())
                    msg = msg+appended
                totalmsg = totalmsg + msg
        
            if pkglist:
                out = out + totalmsg

        summary = _("""
Transaction Summary
=============================================================================
Install  %5.5s Package(s)         
Update   %5.5s Package(s)         
Remove   %5.5s Package(s)         
""") % (len(self.tsInfo.installed + self.tsInfo.depinstalled),
       len(self.tsInfo.updated + self.tsInfo.depupdated),
       len(self.tsInfo.removed + self.tsInfo.depremoved))
        out = out + summary
        
        return out
        
    def postTransactionOutput(self):
        out = ''
        
        self.tsInfo.makelists()

        for (action, pkglist) in [(_('Removed'), self.tsInfo.removed), 
                                  (_('Dependency Removed'), self.tsInfo.depremoved),
                                  (_('Installed'), self.tsInfo.installed), 
                                  (_('Dependency Installed'), self.tsInfo.depinstalled),
                                  (_('Updated'), self.tsInfo.updated),
                                  (_('Dependency Updated'), self.tsInfo.depupdated),
                                  (_('Replaced'), self.tsInfo.obsoleted)]:
            
            if len(pkglist) > 0:
                out += '\n%s:' % action
                for txmbr in pkglist:
                    (n,a,e,v,r) = txmbr.pkgtup
                    msg = " %s.%s %s:%s-%s" % (n,a,e,v,r)
                    out += msg
        
        return out

    def setupProgressCallbacks(self):
        """sets up the progress callbacks and various 
           output bars based on debug level"""

        # if we're below 2 on the debug level we don't need to be outputting
        # progress bars - this is hacky - I'm open to other options
        # One of these is a download
        if self.conf.debuglevel < 2 or not sys.stdout.isatty():
            self.repos.setProgressBar(None)
            self.repos.callback = None
        else:
            self.repos.setProgressBar(YumTextMeter(fo=sys.stdout))
            self.repos.callback = CacheProgressCallback()

        # setup our failure report for failover
        freport = (self.failureReport,(),{})
        self.repos.setFailureCallback(freport)

        # setup callback for CTRL-C's
        self.repos.setInterruptCallback(self.interrupt_callback)
        
        # setup our depsolve progress callback
        dscb = DepSolveProgressCallBack()
        self.dsCallback = dscb
    
    def setupProgessCallbacks(self):
        # api purposes only to protect the typo
        self.setupProgressCallbacks()
        
    def interrupt_callback(self, cbobj):
        '''Handle CTRL-C's during downloads

        If a CTRL-C occurs a URLGrabError will be raised to push the download
        onto the next mirror.  
        
        If two CTRL-C's occur in quick succession then yum will exit.

        @param cbobj: urlgrabber callback obj
        '''
        delta_exit_chk = 2.0   # Delta between C-c's so we treat as exit
        delta_exit_str = "two" # Human readable version of above

        now = time.time()

        if not hasattr(self, '_last_interrupt'):
            hibeg = self.term.MODE['bold']
            hiend = self.term.MODE['normal']
            msg = _("""
 Current download cancelled, %sinterrupt (ctrl-c) again%s within %s%s%s seconds to exit.
""") % (hibeg, hiend, hibeg, delta_exit_str, hiend)
            self.verbose_logger.log(logginglevels.INFO_2, msg)
        elif now - self._last_interrupt < delta_exit_chk:
            # Two quick CTRL-C's, quit
            raise KeyboardInterrupt

        # Go to next mirror
        self._last_interrupt = now
        raise URLGrabError(15, _('user interrupt'))

class DepSolveProgressCallBack:
    """provides text output callback functions for Dependency Solver callback"""
    
    def __init__(self):
        """requires yum-cli log and errorlog functions as arguments"""
        self.verbose_logger = logging.getLogger("yum.verbose.cli")
        self.loops = 0
    
    def pkgAdded(self, pkgtup, mode):
        modedict = { 'i': _('installed'),
                     'u': _('updated'),
                     'o': _('obsoleted'),
                     'e': _('erased')}
        (n, a, e, v, r) = pkgtup
        modeterm = modedict[mode]
        self.verbose_logger.log(logginglevels.INFO_2,
            _('---> Package %s.%s %s:%s-%s set to be %s'), n, a, e, v, r,
            modeterm)
        
    def start(self):
        self.loops += 1
        
    def tscheck(self):
        self.verbose_logger.log(logginglevels.INFO_2, _('--> Running transaction check'))
        
    def restartLoop(self):
        self.loops += 1
        self.verbose_logger.log(logginglevels.INFO_2,
            _('--> Restarting Dependency Resolution with new changes.'))
        self.verbose_logger.debug('---> Loop Number: %d', self.loops)
    
    def end(self):
        self.verbose_logger.log(logginglevels.INFO_2,
            _('--> Finished Dependency Resolution'))

    
    def procReq(self, name, formatted_req):
        self.verbose_logger.log(logginglevels.INFO_2,
            _('--> Processing Dependency: %s for package: %s'), formatted_req,
            name)
        
    
    def unresolved(self, msg):
        self.verbose_logger.log(logginglevels.INFO_2, _('--> Unresolved Dependency: %s'),
            msg)

    
    def procConflict(self, name, confname):
        self.verbose_logger.log(logginglevels.INFO_2,
            _('--> Processing Conflict: %s conflicts %s'), name, confname)

    def transactionPopulation(self):
        self.verbose_logger.log(logginglevels.INFO_2, _('--> Populating transaction set '
            'with selected packages. Please wait.'))
    
    def downloadHeader(self, name):
        self.verbose_logger.log(logginglevels.INFO_2, _('---> Downloading header for %s '
            'to pack into transaction set.'), name)
       

class CacheProgressCallback:

    '''
    The class handles text output callbacks during metadata cache updates.
    '''
    
    def __init__(self):
        self.logger = logging.getLogger("yum.cli")
        self.verbose_logger = logging.getLogger("yum.verbose.cli")
        self.file_logger = logging.getLogger("yum.filelogging.cli")

    def log(self, level, message):
        self.verbose_logger.log(level, message)

    def errorlog(self, level, message):
        self.logger.log(level, message)

    def filelog(self, level, message):
        self.file_logger.log(level, message)

    def progressbar(self, current, total, name=None):
        progressbar(current, total, name)

class YumCliRPMCallBack(RPMBaseCallback):

    """
    Yum specific callback class for RPM operations.
    """

    def __init__(self):
        RPMBaseCallback.__init__(self)
        self.lastmsg = None
        self.lastpackage = None # name of last package we looked at
        self.output = True
        
        # for a progress bar
        self.mark = "#"
        self.marks = 27
        
        
    def event(self, package, action, te_current, te_total, ts_current, ts_total):
        # this is where a progress bar would be called
        process = self.action[action]
        
        if type(package) not in types.StringTypes:
            pkgname = package.name
        else:
            pkgname = package
            
        self.lastpackage = package
        if te_total == 0:
            percent = 0
        else:
            percent = (te_current*100L)/te_total
        
        if self.output and (sys.stdout.isatty() or te_current == te_total):
            fmt = self._makefmt(percent, ts_current, ts_total)
            msg = fmt % (process, pkgname)
            if msg != self.lastmsg:
                sys.stdout.write(msg)
                sys.stdout.flush()
                self.lastmsg = msg
            if te_current == te_total:
                print " "

    def scriptout(self, package, msgs):
        if msgs:
            sys.stdout.write(msgs)
            sys.stdout.flush()

    def _makefmt(self, percent, ts_current, ts_total, progress = True):
        l = len(str(ts_total))
        size = "%s.%s" % (l, l)
        fmt_done = "[%" + size + "s/%" + size + "s]"
        done = fmt_done % (ts_current, ts_total)
        marks = self.marks - (2 * l)
        width = "%s.%s" % (marks, marks)
        fmt_bar = "%-" + width + "s"
        if progress:
            bar = fmt_bar % (self.mark * int(marks * (percent / 100.0)), )
            fmt = "\r  %-10.10s: %-28.28s " + bar + " " + done
        else:
            bar = fmt_bar % (self.mark * marks, )
            fmt = "  %-10.10s: %-28.28s "  + bar + " " + done
        return fmt


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
        
