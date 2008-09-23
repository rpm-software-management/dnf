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

import re # For YumTerm

from urlgrabber.progress import TextMeter
import urlgrabber.progress
from urlgrabber.grabber import URLGrabError
from yum.misc import sortPkgObj, prco_tuple_to_string, to_str, to_unicode, get_my_lang_code
import yum.misc
from rpmUtils.miscutils import checkSignals
from yum.constants import *

from yum import logginglevels, _
from yum.rpmtrans import RPMBaseCallback
from yum.packageSack import packagesNewestByNameArch

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
        
        self.logger.error('%s: %s', errobj.url, errobj.exception)
        self.logger.error(_('Trying other mirror.'))
        raise errobj.exception
    
        
    def simpleProgressBar(self, current, total, name=None):
        progressbar(current, total, name)

    def _highlight(self, highlight):
        if highlight:
            hibeg = self.term.MODE['bold']
            hiend = self.term.MODE['normal']
        else:
            hibeg = ''
            hiend = ''
        return (hibeg, hiend)

    @staticmethod
    def _calc_columns_spaces_helps(current, data_tups, left):
        """ Spaces left on the current field will help how many pkgs? """
        ret = 0
        for tup in data_tups:
            if left < (tup[0] - current):
                break
            ret += tup[1]
        return ret

    def calcColumns(self, data, columns=None, remainder_column=0,
                    total_width=None, indent=''):
        """ Dynamically calculate the width of the fields in the data, data is
            of the format [column-number][field_length] = rows. """

        if total_width is None:
            total_width = self.term.columns

        cols = len(data)
        # Convert the data to ascending list of tuples, (field_length, pkgs)
        pdata = data
        data  = [None] * cols # Don't modify the passed in data
        for d in range(0, cols):
            data[d] = sorted(pdata[d].items())

        if columns is None:
            columns = [1] * cols

        total_width -= (sum(columns) + (cols - 1) + len(indent))
        while total_width > 0:
            # Find which field all the spaces left will help best
            helps = 0
            val   = 0
            for d in xrange(0, cols):
                thelps = self._calc_columns_spaces_helps(columns[d], data[d],
                                                         total_width)
                if not thelps:
                    continue
                if thelps < helps:
                    continue
                helps = thelps
                val   = d

            #  If we found a column to expand, move up to the next level with
            # that column and start again with any remaining space.
            if helps:
                diff = data[val].pop(0)[0] - columns[val]
                columns[val] += diff
                total_width  -= diff
                continue

            #  Split the remaining spaces among each column equally, except the
            # last one. And put the rest into the remainder column
            cols -= 1
            norm = total_width / cols
            for d in xrange(0, cols):
                columns[d] += norm
            columns[remainder_column] += total_width - (cols * norm)
            total_width = 0

        return columns

    @staticmethod
    def _fmt_column_align_width(width):
        if width < 0:
            return (u"-", -width)
        return (u"", width)

    def fmtColumns(self, columns, msg=u'', end=u''):
        """ Return a string for columns of data, which can overflow."""

        total_width = len(msg)
        data = []
        for (val, width) in columns[:-1]:
            if not width: # Don't count this column, invisible text
                msg += u"%s"
                data.append(val)
                continue

            (align, width) = self._fmt_column_align_width(width)
            if len(val) <= width:
                msg += u"%%%s%ds " % (align, width)
            else:
                msg += u"%s\n" + " " * (total_width + width + 1)
            total_width += width
            total_width += 1
            data.append(val)
        (val, width) = columns[-1]
        (align, width) = self._fmt_column_align_width(width)
        msg += u"%%%s%ds%s" % (align, width, end)
        data.append(val)
        return msg % tuple(data)

    def simpleList(self, pkg, ui_overflow=False, indent='', highlight=False,
                   columns=None):
        """ Simple to use function to print a pkg as a line. """

        if columns is None:
            columns = (-40, -22, -16) # Old default
        (hibeg, hiend) = self._highlight(highlight)
        ver = pkg.printVer()
        na = '%s%s.%s' % (indent, pkg.name, pkg.arch)
        columns = zip((na, ver, pkg.repoid), columns)
        columns.insert(1, (hiend, 0))
        columns.insert(0, (hibeg, 0))
        print self.fmtColumns(columns)

    def simpleEnvraList(self, pkg, ui_overflow=False,
                        indent='', highlight=False, columns=None):
        """ Simple to use function to print a pkg as a line, with the pkg
            itself in envra format so it can be pased to list/install/etc. """

        if columns is None:
            columns = (-63, -16) # Old default
        (hibeg, hiend) = self._highlight(highlight)
        envra = '%s%s' % (indent, str(pkg))
        columns = zip((envra, pkg.repoid), columns)
        columns.insert(1, (hiend, 0))
        columns.insert(0, (hibeg, 0))
        print self.fmtColumns(columns)

    def fmtKeyValFill(self, key, val):
        """ Return a key value pair in the common two column output format. """
        val = to_str(val)
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
        name = to_str(name)
        cols = self.term.columns - 2
        name_len = len(name)
        if name_len >= (cols - 4):
            beg = end = fill * 2
        else:
            beg = fill * ((cols - name_len) / 2)
            end = fill * (cols - name_len - len(beg))

        return "%s %s %s" % (beg, name, end)

    def _enc(self, s):
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
        return to_unicode(s)

    def infoOutput(self, pkg, highlight=False):
        (hibeg, hiend) = self._highlight(highlight)
        print _("Name       : %s%s%s") % (hibeg, pkg.name, hiend)
        print _("Arch       : %s") % pkg.arch
        if pkg.epoch != "0":
            print _("Epoch      : %s") % pkg.epoch
        print _("Version    : %s") % pkg.version
        print _("Release    : %s") % pkg.release
        print _("Size       : %s") % self.format_number(float(pkg.size))
        print _("Repo       : %s") % pkg.repoid
        if self.verbose_logger.isEnabledFor(logginglevels.DEBUG_3):
            print _("Committer  : %s") % pkg.committer
            print _("Committime : %s") % time.ctime(pkg.committime)
            print _("Buildtime  : %s") % time.ctime(pkg.buildtime)
            if hasattr(pkg, 'installtime'):
                print _("Installtime: %s") % time.ctime(pkg.installtime)
        print self.fmtKeyValFill(_("Summary    : "), self._enc(pkg.summary))
        if pkg.url:
            print _("URL        : %s") % pkg.url
        print _("License    : %s") % pkg.license
        print self.fmtKeyValFill(_("Description: "), self._enc(pkg.description))
        print ""
    
    def updatesObsoletesList(self, uotup, changetype, columns=None):
        """takes an updates or obsoletes tuple of pkgobjects and
           returns a simple printed string of the output and a string
           explaining the relationship between the tuple members"""
        (changePkg, instPkg) = uotup

        if columns is not None:
            # New style, output all info. for both old/new with old indented
            self.simpleList(changePkg, columns=columns)
            self.simpleList(instPkg,   columns=columns, indent=' ' * 4)
            return

        # Old style
        c_compact = changePkg.compactPrint()
        i_compact = '%s.%s' % (instPkg.name, instPkg.arch)
        c_repo = changePkg.repoid
        print '%-35.35s [%.12s] %.10s %-20.20s' % (c_compact, c_repo, changetype, i_compact)

    def listPkgs(self, lst, description, outputType, highlight_na={},
                 columns=None):
        """outputs based on whatever outputType is. Current options:
           'list' - simple pkg list
           'info' - similar to rpm -qi output
           ...also highlight_na can be passed, and we'll highlight
           pkgs with (names, arch) in that set."""

        if outputType in ['list', 'info']:
            thingslisted = 0
            if len(lst) > 0:
                thingslisted = 1
                print '%s' % description
                for pkg in sorted(lst):
                    key = (pkg.name, pkg.arch)
                    highlight = False
                    if key in highlight_na and pkg.verLT(highlight_na[key]):
                        highlight = True

                    if outputType == 'list':
                        self.simpleList(pkg, ui_overflow=True,
                                        highlight=highlight, columns=columns)
                    elif outputType == 'info':
                        self.infoOutput(pkg, highlight=highlight)
                    else:
                        pass
    
            if thingslisted == 0:
                return 1, ['No Packages to list']
            return 0, []
        
    
        
    def userconfirm(self):
        """gets a yes or no from the user, defaults to No"""

        yui = (to_unicode(_('y')), to_unicode(_('yes')))
        nui = (to_unicode(_('n')), to_unicode(_('no')))
        aui = (yui[0], yui[1], nui[0], nui[1])
        while True:
            try:
                choice = raw_input(_('Is this ok [y/N]: '))
            except UnicodeEncodeError:
                raise
            except UnicodeDecodeError:
                raise
            except:
                choice = ''
            choice = to_unicode(choice)
            choice = choice.lower()
            if len(choice) == 0 or choice in aui:
                break
            # If the enlish one letter names don't mix, allow them too
            if u'y' not in aui and u'y' == choice:
                choice = yui[0]
                break
            if u'n' not in aui and u'n' == choice:
                break

        if len(choice) == 0 or choice not in yui:
            return False
        else:            
            return True
    
    def _cli_confirm_gpg_key_import(self, keydict):
        # FIXME what should we be printing here?
        return self.userconfirm()

    def _group_names2aipkgs(self, pkg_names):
        """ Convert pkg_names to installed pkgs or available pkgs, return
            value is a dict on pkg.name returning (apkg, ipkg). """
        ipkgs = self.rpmdb.searchNames(pkg_names)
        apkgs = self.pkgSack.searchNames(pkg_names)
        apkgs = packagesNewestByNameArch(apkgs)

        # This is somewhat similar to doPackageLists()
        pkgs = {}
        for pkg in ipkgs:
            pkgs[(pkg.name, pkg.arch)] = (None, pkg)
        for pkg in apkgs:
            key = (pkg.name, pkg.arch)
            if key not in pkgs:
                pkgs[(pkg.name, pkg.arch)] = (pkg, None)
            elif pkg.verGT(pkgs[key][1]):
                pkgs[(pkg.name, pkg.arch)] = (pkg, pkgs[key][1])

        # Convert (pkg.name, pkg.arch) to pkg.name dict
        ret = {}
        for (apkg, ipkg) in pkgs.itervalues():
            pkg = apkg or ipkg
            ret.setdefault(pkg.name, []).append((apkg, ipkg))
        return ret

    def _calcDataPkgColumns(self, data, pkg_names, pkg_names2pkgs,
                            indent='   '):
        for item in pkg_names:
            if item not in pkg_names2pkgs:
                continue
            for (apkg, ipkg) in pkg_names2pkgs[item]:
                pkg = ipkg or apkg
                envra = len(str(pkg)) + len(indent)
                rid   = len(pkg.repoid)
                for (d, v) in (('envra', envra), ('rid', rid)):
                    data[d].setdefault(v, 0)
                    data[d][v] += 1

    def _displayPkgsFromNames(self, pkg_names, verbose, pkg_names2pkgs,
                              indent='   ', columns=None):
        if not verbose:
            for item in sorted(pkg_names):
                print '%s%s' % (indent, item)
        else:
            for item in sorted(pkg_names):
                if item not in pkg_names2pkgs:
                    print '%s%s' % (indent, item)
                    continue
                for (apkg, ipkg) in sorted(pkg_names2pkgs[item],
                                           key=lambda x: x[1] or x[0]):
                    self.simpleEnvraList(ipkg or apkg, ui_overflow=True,
                                         indent=indent, highlight=ipkg and apkg,
                                         columns=columns)
    
    def displayPkgsInGroups(self, group):
        print _('\nGroup: %s') % group.ui_name

        verb = self.verbose_logger.isEnabledFor(logginglevels.DEBUG_3)
        pkg_names2pkgs = None
        if verb:
            pkg_names2pkgs = self._group_names2aipkgs(group.packages)
        if group.ui_description:
            print _(' Description: %s') % to_unicode(group.ui_description)

        sections = ((_(' Mandatory Packages:'),   group.mandatory_packages),
                    (_(' Default Packages:'),     group.default_packages),
                    (_(' Optional Packages:'),    group.optional_packages),
                    (_(' Conditional Packages:'), group.conditional_packages))
        columns = None
        if verb:
            data = {'envra' : {}, 'rid' : {}}
            for (section_name, pkg_names) in sections:
                self._calcDataPkgColumns(data, pkg_names, pkg_names2pkgs)
            data = [data['envra'], data['rid']]
            columns = self.calcColumns(data)
            columns = (-columns[0], -columns[1])

        for (section_name, pkg_names) in sections:
            if len(pkg_names) > 0:
                print section_name
                self._displayPkgsFromNames(pkg_names, verb, pkg_names2pkgs,
                                           columns=columns)

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

    @staticmethod
    def format_time(seconds, use_hours=0):
        return urlgrabber.progress.format_time(seconds, use_hours)

    def matchcallback(self, po, values, matchfor=None, verbose=None):
        """ Output search/provides type callback matches. po is the pkg object,
            values are the things in the po that we've matched.
            If matchfor is passed, all the strings in that list will be
            highlighted within the output.
            verbose overrides logginglevel, if passed. """

        if self.conf.showdupesfromrepos:
            msg = '%s : ' % po
        else:
            msg = '%s.%s : ' % (po.name, po.arch)
        msg = self.fmtKeyValFill(msg, self._enc(po.summary))
        if matchfor:
            msg = self.term.sub_bold(msg, matchfor)
        
        print msg

        if verbose is None:
            verbose = self.verbose_logger.isEnabledFor(logginglevels.DEBUG_3)
        if not verbose:
            return

        print _('Matched from:')
        for item in yum.misc.unique(values):
            if po.name == item or po.summary == item:
                continue # Skip double name/summary printing

            can_overflow = True
            if False: pass
            elif po.description == item:
                key = _("Description : ")
                item = self._enc(item)
            elif po.url == item:
                key = _("URL         : %s")
                can_overflow = False
            elif po.license == item:
                key = _("License     : %s")
                can_overflow = False
            elif item.startswith("/"):
                key = _("Filename    : %s")
                item = self._enc(item)
                can_overflow = False
            else:
                key = _("Other       : ")

            if matchfor:
                item = self.term.sub_bold(item, matchfor)
            if can_overflow:
                print self.fmtKeyValFill(key, item)
            else:
                print key % item
        print '\n\n'

    def matchcallback_verbose(self, po, values, matchfor=None):
        return self.matchcallback(po, values, matchfor, verbose=True)
        
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
        out = u""
        pkglist_lines = []
        #  Tried to do this statically using:
        #   http://fedorapeople.org/~james/yum/commands/length_distributions.py
        # but it sucked for corner cases, so this is dynamic...

        data  = {'n' : {}, 'v' : {}, 'r' : {}}
        a_wid = 0 # Arch can't get "that big" ... so always use the max.
        for (action, pkglist) in [(_('Installing'), self.tsInfo.installed),
                            (_('Updating'), self.tsInfo.updated),
                            (_('Removing'), self.tsInfo.removed),
                            (_('Installing for dependencies'), self.tsInfo.depinstalled),
                            (_('Updating for dependencies'), self.tsInfo.depupdated),
                            (_('Removing for dependencies'), self.tsInfo.depremoved)]:
            lines = []
            for txmbr in pkglist:
                (n,a,e,v,r) = txmbr.pkgtup
                evr = txmbr.po.printVer()
                repoid = txmbr.repoid
                pkgsize = float(txmbr.po.size)
                size = self.format_number(pkgsize)

                if a is None: # gpgkeys are weird
                    a = 'noarch'

                lines.append((n, a, evr, repoid, size, txmbr.obsoletes))
                #  Create a dict of field_length => number of packages, for
                # each field.
                for (d, v) in (("n",len(n)), ("v",len(evr)), ("r",len(repoid))):
                    data[d].setdefault(v, 0)
                    data[d][v] += 1
                if a_wid < len(a): # max() is only in 2.5.z
                    a_wid = len(a)

            pkglist_lines.append((action, lines))

        if data['n']:
            data    = [data['n'],    {}, data['v'], data['r'], {}]
            columns = [1,         a_wid,         1,         1,  5]
            columns = self.calcColumns(data, indent="  ", columns=columns,
                                       remainder_column=2)
            (n_wid, a_wid, v_wid, r_wid, s_wid) = columns
            assert s_wid == 5

            out = u"""
%s
%s
%s
""" % ('=' * self.term.columns,
       self.fmtColumns(((_('Package'), -n_wid), (_('Arch'), -a_wid),
                        (_('Version'), -v_wid), (_('Repository'), -r_wid),
                        (_('Size'), s_wid)), u" "),
       '=' * self.term.columns)

        for (action, lines) in pkglist_lines:
            if lines:
                totalmsg = u"%s:\n" % action
            for (n, a, evr, repoid, size, obsoletes) in lines:
                columns = ((n,   -n_wid), (a,      -a_wid),
                           (evr, -v_wid), (repoid, -r_wid), (size, s_wid))
                msg = self.fmtColumns(columns, u" ", u"\n")
                for obspo in obsoletes:
                    appended = _('     replacing  %s.%s %s\n\n') % (obspo.name,
                        obspo.arch, obspo.printVer())
                    msg = msg+appended
                totalmsg = totalmsg + msg
        
            if lines:
                out = out + totalmsg

        summary = _("""
Transaction Summary
%s
Install  %5.5s Package(s)         
Update   %5.5s Package(s)         
Remove   %5.5s Package(s)         
""") % ('=' * self.term.columns,
        len(self.tsInfo.installed + self.tsInfo.depinstalled),
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
    
    def setupKeyImportCallbacks(self):
        self.repos.confirm_func = self._cli_confirm_gpg_key_import
        self.repos.gpg_import_func = self.getKeyForRepo

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

    def download_callback_total_cb(self, remote_pkgs, remote_size,
                                   download_start_timestamp):
        if len(remote_pkgs) <= 1:
            return
        if not hasattr(urlgrabber.progress, 'TerminalLine'):
            return

        tl = urlgrabber.progress.TerminalLine(8)
        self.verbose_logger.log(logginglevels.INFO_2, "-" * tl.rest())
        dl_time = time.time() - download_start_timestamp
        ui_size = tl.add(' | %5sB' % self.format_number(remote_size))
        ui_time = tl.add(' %9s' % self.format_time(dl_time))
        ui_end  = tl.add(' ' * 5)
        ui_bs   = tl.add(' %5sB/s' % self.format_number(remote_size / dl_time))
        msg = "%-*.*s%s%s%s%s" % (tl.rest(), tl.rest(), _("Total"),
                                  ui_bs, ui_size, ui_time, ui_end)
        self.verbose_logger.log(logginglevels.INFO_2, msg)


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
        self.marks = 22
        
        
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
                sys.stdout.write(to_unicode(msg))
                sys.stdout.flush()
                self.lastmsg = msg
            if te_current == te_total:
                print " "

    def scriptout(self, package, msgs):
        if msgs:
            sys.stdout.write(to_unicode(msgs))
            sys.stdout.flush()

    def _makefmt(self, percent, ts_current, ts_total, progress = True):
        l = len(str(ts_total))
        size = "%s.%s" % (l, l)
        fmt_done = "[%" + size + "s/%" + size + "s]"
        done = fmt_done % (ts_current, ts_total)
        marks = self.marks - (2 * l)
        width = "%s.%s" % (marks, marks)
        fmt_bar = "%-" + width + "s"
        pnl = str(28 + marks + 1)

        if progress and percent == 100: # Don't chop pkg name on 100%
            fmt = "\r  %-15.15s: %-" + pnl + '.' + pnl + "s " + done
        elif progress:
            bar = fmt_bar % (self.mark * int(marks * (percent / 100.0)), )
            fmt = "\r  %-15.15s: %-28.28s " + bar + " " + done
        elif percent == 100:
            fmt = "  %-15.15s: %-" + pnl + '.' + pnl + "s " + done
        else:
            bar = fmt_bar % (self.mark * marks, )
            fmt = "  %-15.15s: %-28.28s "  + bar + " " + done
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
    elif current == total: # Don't chop name on 100%
        output = '\r%-62.62s %d/%d' % (name, current, total)
    else:
        output = '\r%-10.10s: %-50s %d/%d' % (name, hashbar, current, total)
     
    if current <= total:
        sys.stdout.write(output)

    if current == total:
        sys.stdout.write('\n')

    sys.stdout.flush()
        

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "progress":
        print ""
        print " Doing progress, small name"
        print ""
        for i in xrange(0, 101):
            progressbar(i, 100, "abcd")
            time.sleep(0.1)
        print ""
        print " Doing progress, big name"
        print ""
        for i in xrange(0, 101):
            progressbar(i, 100, "_%s_" % ("123456789 " * 5))
            time.sleep(0.1)
        print ""
        print " Doing progress, no name"
        print ""
        for i in xrange(0, 101):
            progressbar(i, 100)
            time.sleep(0.1)

        cb = YumCliRPMCallBack()
        cb.action["foo"] = "abcd"
        cb.action["bar"] = "_12345678_.end"
        print ""
        print " Doing CB, small proc / small pkg"
        print ""
        for i in xrange(0, 101):
            cb.event("spkg", "foo", i, 100, i, 100)
            time.sleep(0.1)        
        print ""
        print " Doing CB, big proc / big pkg"
        print ""
        for i in xrange(0, 101):
            cb.event("lpkg" + "-=" * 15 + ".end", "bar", i, 100, i, 100)
            time.sleep(0.1)
        print ""
        
