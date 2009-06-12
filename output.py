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

from weakref import proxy as weakref

from urlgrabber.progress import TextMeter
import urlgrabber.progress
from urlgrabber.grabber import URLGrabError
from yum.misc import prco_tuple_to_string
from yum.i18n import to_str, to_utf8, to_unicode
import yum.misc
from rpmUtils.miscutils import checkSignals
from yum.constants import *

from yum import logginglevels, _
from yum.rpmtrans import RPMBaseCallback
from yum.packageSack import packagesNewestByNameArch

from yum.i18n import utf8_width, utf8_width_fill, utf8_text_fill

def _term_width():
    """ Simple terminal width, limit to 20 chars. and make 0 == 80. """
    if not hasattr(urlgrabber.progress, 'terminal_width_cached'):
        return 80
    ret = urlgrabber.progress.terminal_width_cached()
    if ret == 0:
        return 80
    if ret < 20:
        return 20
    return ret


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

    if hasattr(urlgrabber.progress, 'terminal_width_cached'):
        columns = property(lambda self: _term_width())

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
    __ansi_forced_MODE = {
        'bold' : '\x1b[1m',
        'blink' : '\x1b[5m',
        'dim' : '',
        'reverse' : '\x1b[7m',
        'underline' : '\x1b[4m',
        'normal' : '\x1b(B\x1b[m'
        }
    __ansi_forced_FG_COLOR = {
        'black' : '\x1b[30m',
        'red' : '\x1b[31m',
        'green' : '\x1b[32m',
        'yellow' : '\x1b[33m',
        'blue' : '\x1b[34m',
        'magenta' : '\x1b[35m',
        'cyan' : '\x1b[36m',
        'white' : '\x1b[37m'
        }
    __ansi_forced_BG_COLOR = {
        'black' : '\x1b[40m',
        'red' : '\x1b[41m',
        'green' : '\x1b[42m',
        'yellow' : '\x1b[43m',
        'blue' : '\x1b[44m',
        'magenta' : '\x1b[45m',
        'cyan' : '\x1b[46m',
        'white' : '\x1b[47m'
        }

    def __forced_init(self):
        self.MODE = self.__ansi_forced_MODE
        self.FG_COLOR = self.__ansi_forced_FG_COLOR
        self.BG_COLOR = self.__ansi_forced_BG_COLOR

    def reinit(self, term_stream=None, color='auto'):
        if color == 'never':
            self.__enabled = False
            return

        self.__enabled = True
        if not hasattr(urlgrabber.progress, 'terminal_width_cached'):
            self.columns = 80
        self.lines = 24

        if color == 'always':
            self.__forced_init()
            return
        assert color == 'auto'

        # Output modes:
        self.MODE = {
            'bold' : '',
            'blink' : '',
            'dim' : '',
            'reverse' : '',
            'underline' : '',
            'normal' : ''
            }

        # Colours
        self.FG_COLOR = {
            'black' : '',
            'blue' : '',
            'green' : '',
            'cyan' : '',
            'red' : '',
            'magenta' : '',
            'yellow' : '',
            'white' : ''
            }

        self.BG_COLOR = {
            'black' : '',
            'blue' : '',
            'green' : '',
            'cyan' : '',
            'red' : '',
            'magenta' : '',
            'yellow' : '',
            'white' : ''
            }

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

        if not hasattr(urlgrabber.progress, 'terminal_width_cached'):
            self.columns = curses.tigetnum('cols')
        self.lines = curses.tigetnum('lines')
        
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

    def __init__(self, term_stream=None, color='auto'):
        self.reinit(term_stream, color)

    def _tigetstr(self, cap_name):
        # String capabilities can include "delays" of the form "$<2>".
        # For any modern terminal, we should be able to just ignore
        # these, so strip them out.
        cap = self._ctigetstr(cap_name) or ''
        return re.sub(r'\$<\d+>[/*]?', '', cap)

    def sub(self, haystack, beg, end, needles, escape=None, ignore_case=False):
        if not self.__enabled:
            return haystack

        if not escape:
            escape = re.escape

        render = lambda match: beg + match.group() + end
        for needle in needles:
            pat = escape(needle)
            if ignore_case:
                pat = re.template(pat, re.I)
            haystack = re.sub(pat, render, haystack)
        return haystack
    def sub_norm(self, haystack, beg, needles, **kwds):
        return self.sub(haystack, beg, self.MODE['normal'], needles, **kwds)

    def sub_mode(self, haystack, mode, needles, **kwds):
        return self.sub_norm(haystack, self.MODE[mode], needles, **kwds)

    def sub_bold(self, haystack, needles, **kwds):
        return self.sub_mode(haystack, 'bold', needles, **kwds)
    
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
        self._last_interrupt = None

    
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
        hibeg = ''
        hiend = ''
        if not highlight:
            pass
        elif not isinstance(highlight, basestring) or highlight == 'bold':
            hibeg = self.term.MODE['bold']
        elif highlight == 'normal':
            pass # Minor opt.
        else:
            # Turn a string into a specific output: colour, bold, etc.
            for high in highlight.replace(',', ' ').split():
                if False: pass
                elif high == 'normal':
                    hibeg = ''
                elif high in self.term.MODE:
                    hibeg += self.term.MODE[high]
                elif high in self.term.FG_COLOR:
                    hibeg += self.term.FG_COLOR[high]
                elif (high.startswith('fg:') and
                      high[3:] in self.term.FG_COLOR):
                    hibeg += self.term.FG_COLOR[high[3:]]
                elif (high.startswith('bg:') and
                      high[3:] in self.term.BG_COLOR):
                    hibeg += self.term.BG_COLOR[high[3:]]

        if hibeg:
            hiend = self.term.MODE['normal']
        return (hibeg, hiend)

    def _sub_highlight(self, haystack, highlight, needles, **kwds):
        hibeg, hiend = self._highlight(highlight)
        return self.term.sub(haystack, hibeg, hiend, needles, **kwds)

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

        total_width -= (sum(columns) + (cols - 1) + utf8_width(indent))
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

    def _col_data(self, col_data):
        assert len(col_data) == 2 or len(col_data) == 3
        if len(col_data) == 2:
            (val, width) = col_data
            hibeg = hiend = ''
        if len(col_data) == 3:
            (val, width, highlight) = col_data
            (hibeg, hiend) = self._highlight(highlight)
        return (val, width, hibeg, hiend)

    def fmtColumns(self, columns, msg=u'', end=u''):
        """ Return a string for columns of data, which can overflow."""

        total_width = len(msg)
        data = []
        for col_data in columns[:-1]:
            (val, width, hibeg, hiend) = self._col_data(col_data)

            if not width: # Don't count this column, invisible text
                msg += u"%s"
                data.append(val)
                continue

            (align, width) = self._fmt_column_align_width(width)
            if utf8_width(val) <= width:
                msg += u"%s "
                val = utf8_width_fill(val, width, left=(align == u'-'),
                                      prefix=hibeg, suffix=hiend)
                data.append(val)
            else:
                msg += u"%s%s%s\n" + " " * (total_width + width + 1)
                data.extend([hibeg, val, hiend])
            total_width += width
            total_width += 1
        (val, width, hibeg, hiend) = self._col_data(columns[-1])
        (align, width) = self._fmt_column_align_width(width)
        val = utf8_width_fill(val, width, left=(align == u'-'),
                              prefix=hibeg, suffix=hiend)
        msg += u"%%s%s" % end
        data.append(val)
        return msg % tuple(data)

    def simpleList(self, pkg, ui_overflow=False, indent='', highlight=False,
                   columns=None):
        """ Simple to use function to print a pkg as a line. """

        if columns is None:
            columns = (-40, -22, -16) # Old default
        ver = pkg.printVer()
        na = '%s%s.%s' % (indent, pkg.name, pkg.arch)
        hi_cols = [highlight, 'normal', 'normal']
        rid = pkg.repoid
        if pkg.repoid == 'installed' and 'from_repo' in pkg.yumdb_info:
            rid = '@' + pkg.yumdb_info.from_repo
        columns = zip((na, ver, rid), columns, hi_cols)
        print self.fmtColumns(columns)

    def simpleEnvraList(self, pkg, ui_overflow=False,
                        indent='', highlight=False, columns=None):
        """ Simple to use function to print a pkg as a line, with the pkg
            itself in envra format so it can be pased to list/install/etc. """

        if columns is None:
            columns = (-63, -16) # Old default
        envra = '%s%s' % (indent, str(pkg))
        hi_cols = [highlight, 'normal', 'normal']
        rid = pkg.repoid
        if pkg.repoid == 'installed' and 'from_repo' in pkg.yumdb_info:
            rid = '@' + pkg.yumdb_info.from_repo
        columns = zip((envra, rid), columns, hi_cols)
        print self.fmtColumns(columns)

    def fmtKeyValFill(self, key, val):
        """ Return a key value pair in the common two column output format. """
        val = to_str(val)
        keylen = utf8_width(key)
        cols = self.term.columns
        nxt = ' ' * (keylen - 2) + ': '
        ret = utf8_text_fill(val, width=cols,
                             initial_indent=key, subsequent_indent=nxt)
        if ret.count("\n") > 1 and keylen > (cols / 3):
            # If it's big, redo it again with a smaller subsequent off
            ret = utf8_text_fill(val, width=cols,
                                 initial_indent=key,
                                 subsequent_indent='     ...: ')
        return ret
    
    def fmtSection(self, name, fill='='):
        name = to_str(name)
        cols = self.term.columns - 2
        name_len = utf8_width(name)
        if name_len >= (cols - 4):
            beg = end = fill * 2
        else:
            beg = fill * ((cols - name_len) / 2)
            end = fill * (cols - name_len - len(beg))

        return "%s %s %s" % (beg, name, end)

    def _enc(self, s):
        """Get the translated version from specspo and ensure that
        it's actually encoded in UTF-8."""
        s = to_utf8(s)
        if len(s) > 0:
            for d in self.i18ndomains:
                t = gettext.dgettext(d, s)
                if t != s:
                    s = t
                    break
        return to_unicode(s)

    def infoOutput(self, pkg, highlight=False):
        (hibeg, hiend) = self._highlight(highlight)
        print _("Name       : %s%s%s") % (hibeg, to_unicode(pkg.name), hiend)
        print _("Arch       : %s") % to_unicode(pkg.arch)
        if pkg.epoch != "0":
            print _("Epoch      : %s") % to_unicode(pkg.epoch)
        print _("Version    : %s") % to_unicode(pkg.version)
        print _("Release    : %s") % to_unicode(pkg.release)
        print _("Size       : %s") % self.format_number(float(pkg.size))
        print _("Repo       : %s") % to_unicode(pkg.repoid)
        if pkg.repoid == 'installed' and 'from_repo' in pkg.yumdb_info:
            print _("From repo  : %s") % to_unicode(pkg.yumdb_info.from_repo)
        if self.verbose_logger.isEnabledFor(logginglevels.DEBUG_3):
            print _("Committer  : %s") % to_unicode(pkg.committer)
            print _("Committime : %s") % time.ctime(pkg.committime)
            print _("Buildtime  : %s") % time.ctime(pkg.buildtime)
            if hasattr(pkg, 'installtime'):
                print _("Installtime: %s") % time.ctime(pkg.installtime)
        print self.fmtKeyValFill(_("Summary    : "), self._enc(pkg.summary))
        if pkg.url:
            print _("URL        : %s") % to_unicode(pkg.url)
        print _("License    : %s") % to_unicode(pkg.license)
        print self.fmtKeyValFill(_("Description: "), self._enc(pkg.description))
        print ""
    
    def updatesObsoletesList(self, uotup, changetype, columns=None):
        """takes an updates or obsoletes tuple of pkgobjects and
           returns a simple printed string of the output and a string
           explaining the relationship between the tuple members"""
        (changePkg, instPkg) = uotup

        if columns is not None:
            # New style, output all info. for both old/new with old indented
            chi = self.conf.color_update_remote
            if changePkg.repo.id != 'installed' and changePkg.verifyLocalPkg():
                chi = self.conf.color_update_local
            self.simpleList(changePkg, columns=columns, highlight=chi)
            self.simpleList(instPkg,   columns=columns, indent=' ' * 4,
                            highlight=self.conf.color_update_installed)
            return

        # Old style
        c_compact = changePkg.compactPrint()
        i_compact = '%s.%s' % (instPkg.name, instPkg.arch)
        c_repo = changePkg.repoid
        print '%-35.35s [%.12s] %.10s %-20.20s' % (c_compact, c_repo, changetype, i_compact)

    def listPkgs(self, lst, description, outputType, highlight_na={},
                 columns=None, highlight_modes={}):
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
                    if False: pass
                    elif key not in highlight_na:
                        highlight = highlight_modes.get('not in', 'normal')
                    elif pkg.verEQ(highlight_na[key]):
                        highlight = highlight_modes.get('=', 'normal')
                    elif pkg.verLT(highlight_na[key]):
                        highlight = highlight_modes.get('>', 'bold')
                    else:
                        highlight = highlight_modes.get('<', 'normal')

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
                envra = utf8_width(str(pkg)) + utf8_width(indent)
                if pkg.repoid == 'installed' and 'from_repo' in pkg.yumdb_info:
                    rid = len(pkg.yumdb_info.from_repo) + 1
                else:
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
                    if ipkg and apkg:
                        highlight = self.conf.color_list_installed_older
                    elif apkg:
                        highlight = self.conf.color_list_available_install
                    else:
                        highlight = False
                    self.simpleEnvraList(ipkg or apkg, ui_overflow=True,
                                         indent=indent, highlight=highlight,
                                         columns=columns)
    
    def displayPkgsInGroups(self, group):
        print _('\nGroup: %s') % group.ui_name

        verb = self.verbose_logger.isEnabledFor(logginglevels.DEBUG_3)
        if verb:
            print _(' Group-Id: %s') % to_unicode(group.groupid)
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
        max_depth = len(symbols) - 1
    
        # we want numbers between 0 and thresh, but don't exceed the length
        # of our list.  In that event, the formatting will be screwed up,
        # but it'll still show the right number.
        while number > thresh and depth < max_depth:
            depth  = depth + 1
            number = number / step
    
        if type(number) == type(1) or type(number) == type(1L):
            format = '%i%s%s'
        elif number < 9.95:
            # must use 9.95 for proper sizing.  For example, 9.99 will be
            # rounded to 10.0 with the .1f format string (which is too long)
            format = '%.1f%s%s'
        else:
            format = '%.0f%s%s'
    
        return(format % (float(number or 0), space, symbols[depth]))

    @staticmethod
    def format_time(seconds, use_hours=0):
        return urlgrabber.progress.format_time(seconds, use_hours)

    def matchcallback(self, po, values, matchfor=None, verbose=None,
                      highlight=None):
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
            if highlight is None:
                highlight = self.conf.color_search_match
            msg = self._sub_highlight(msg, highlight, matchfor,ignore_case=True)
        
        print msg

        if verbose is None:
            verbose = self.verbose_logger.isEnabledFor(logginglevels.DEBUG_3)
        if not verbose:
            return

        print _("Repo        : %s") % po.repoid
        print _('Matched from:')
        for item in yum.misc.unique(values):
            item = to_utf8(item)
            if to_utf8(po.name) == item or to_utf8(po.summary) == item:
                continue # Skip double name/summary printing

            can_overflow = True
            if False: pass
            elif to_utf8(po.description) == item:
                key = _("Description : ")
                item = self._enc(item)
            elif to_utf8(po.url) == item:
                key = _("URL         : %s")
                can_overflow = False
            elif to_utf8(po.license) == item:
                key = _("License     : %s")
                can_overflow = False
            elif item.startswith("/"):
                key = _("Filename    : %s")
                item = self._enc(item)
                can_overflow = False
            else:
                key = _("Other       : ")

            if matchfor:
                item = self._sub_highlight(item, highlight, matchfor,
                                           ignore_case=True)
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
        
        self.tsInfo.makelists(True, True)
        out = u""
        pkglist_lines = []
        data  = {'n' : {}, 'v' : {}, 'r' : {}}
        a_wid = 0 # Arch can't get "that big" ... so always use the max.

        def _add_line(lines, data, a_wid, po, obsoletes=[]):
            (n,a,e,v,r) = po.pkgtup
            evr = po.printVer()
            repoid = po.repoid
            pkgsize = float(po.size)
            size = self.format_number(pkgsize)

            if a is None: # gpgkeys are weird
                a = 'noarch'

            # none, partial, full?
            if po.repo.id == 'installed':
                hi = self.conf.color_update_installed
            elif po.verifyLocalPkg():
                hi = self.conf.color_update_local
            else:
                hi = self.conf.color_update_remote
            lines.append((n, a, evr, repoid, size, obsoletes, hi))
            #  Create a dict of field_length => number of packages, for
            # each field.
            for (d, v) in (("n",len(n)), ("v",len(evr)), ("r",len(repoid))):
                data[d].setdefault(v, 0)
                data[d][v] += 1
            if a_wid < len(a): # max() is only in 2.5.z
                a_wid = len(a)
            return a_wid

        for (action, pkglist) in [(_('Installing'), self.tsInfo.installed),
                            (_('Updating'), self.tsInfo.updated),
                            (_('Removing'), self.tsInfo.removed),
                            (_('Reinstalling'), self.tsInfo.reinstalled),
                            (_('Downgrading'), self.tsInfo.downgraded),
                            (_('Installing for dependencies'), self.tsInfo.depinstalled),
                            (_('Updating for dependencies'), self.tsInfo.depupdated),
                            (_('Removing for dependencies'), self.tsInfo.depremoved)]:
            lines = []
            for txmbr in pkglist:
                a_wid = _add_line(lines, data, a_wid, txmbr.po, txmbr.obsoletes)

            pkglist_lines.append((action, lines))

        for (action, pkglist) in [(_('Skipped (dependency problems)'),
                                   self.skipped_packages),]:
            lines = []
            for po in pkglist:
                a_wid = _add_line(lines, data, a_wid, po)

            pkglist_lines.append((action, lines))

        if data['n']:
            data    = [data['n'],    {}, data['v'], data['r'], {}]
            columns = [1,         a_wid,         1,         1,  5]
            columns = self.calcColumns(data, indent="  ", columns=columns,
                                       remainder_column=2)
            (n_wid, a_wid, v_wid, r_wid, s_wid) = columns
            assert s_wid == 5

            out = [u"""
%s
%s
%s
""" % ('=' * self.term.columns,
       self.fmtColumns(((_('Package'), -n_wid), (_('Arch'), -a_wid),
                        (_('Version'), -v_wid), (_('Repository'), -r_wid),
                        (_('Size'), s_wid)), u" "),
       '=' * self.term.columns)]

        for (action, lines) in pkglist_lines:
            if lines:
                totalmsg = u"%s:\n" % action
            for (n, a, evr, repoid, size, obsoletes, hi) in lines:
                columns = ((n,   -n_wid, hi), (a,      -a_wid),
                           (evr, -v_wid), (repoid, -r_wid), (size, s_wid))
                msg = self.fmtColumns(columns, u" ", u"\n")
                hibeg, hiend = self._highlight(self.conf.color_update_installed)
                for obspo in obsoletes:
                    appended = _('     replacing  %s%s%s.%s %s\n\n')
                    appended %= (hibeg, obspo.name, hiend,
                                 obspo.arch, obspo.printVer())
                    msg = msg+appended
                totalmsg = totalmsg + msg
        
            if lines:
                out.append(totalmsg)

        summary = _("""
Transaction Summary
%s
""") % ('=' * self.term.columns,)
        out.append(summary)
        num_in = len(self.tsInfo.installed + self.tsInfo.depinstalled)
        num_up = len(self.tsInfo.updated + self.tsInfo.depupdated)
        summary = _("""\
Install   %5.5s Package(s)
Upgrade   %5.5s Package(s)
""") % (num_in, num_up,)
        if num_in or num_up: # Always do this?
            out.append(summary)
        num_rm = len(self.tsInfo.removed + self.tsInfo.depremoved)
        num_re = len(self.tsInfo.reinstalled)
        num_dg = len(self.tsInfo.downgraded)
        summary = _("""\
Remove    %5.5s Package(s)
Reinstall %5.5s Package(s)
Downgrade %5.5s Package(s)
""") % (num_rm, num_re, num_dg)
        if num_rm or num_re or num_dg:
            out.append(summary)
        
        return ''.join(out)
        
    def postTransactionOutput(self):
        out = ''
        
        self.tsInfo.makelists()

        #  Works a bit like calcColumns, but we never overflow a column we just
        # have a dynamic number of columns.
        def _fits_in_cols(msgs, num):
            """ Work out how many columns we can use to display stuff, in
                the post trans output. """
            if len(msgs) < num:
                return []

            left = self.term.columns - ((num - 1) + 2)
            if left <= 0:
                return []

            col_lens = [0] * num
            col = 0
            for msg in msgs:
                if len(msg) > col_lens[col]:
                    diff = (len(msg) - col_lens[col])
                    if left <= diff:
                        return []
                    left -= diff
                    col_lens[col] = len(msg)
                col += 1
                col %= len(col_lens)

            for col in range(len(col_lens)):
                col_lens[col] += left / num
                col_lens[col] *= -1
            return col_lens

        for (action, pkglist) in [(_('Removed'), self.tsInfo.removed), 
                                  (_('Dependency Removed'), self.tsInfo.depremoved),
                                  (_('Installed'), self.tsInfo.installed), 
                                  (_('Dependency Installed'), self.tsInfo.depinstalled),
                                  (_('Updated'), self.tsInfo.updated),
                                  (_('Dependency Updated'), self.tsInfo.depupdated),
                                  (_('Skipped (dependency problems)'), self.skipped_packages),
                                  (_('Replaced'), self.tsInfo.obsoleted),
                                  (_('Failed'), self.tsInfo.failed)]:
            msgs = []
            if len(pkglist) > 0:
                out += '\n%s:\n' % action
                for txmbr in pkglist:
                    (n,a,e,v,r) = txmbr.pkgtup
                    msg = "%s.%s %s:%s-%s" % (n,a,e,v,r)
                    msgs.append(msg)
                for num in (8, 7, 6, 5, 4, 3, 2):
                    cols = _fits_in_cols(msgs, num)
                    if cols:
                        break
                if not cols:
                    cols = [-(self.term.columns - 2)]
                while msgs:
                    current_msgs = msgs[:len(cols)]
                    out += '  '
                    out += self.fmtColumns(zip(current_msgs, cols), end=u'\n')
                    msgs = msgs[len(cols):]

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
        dscb = DepSolveProgressCallBack(weakref(self))
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
        delta_exit_chk = 2.0      # Delta between C-c's so we treat as exit
        delta_exit_str = _("two") # Human readable version of above

        now = time.time()

        if not self._last_interrupt:
            hibeg = self.term.MODE['bold']
            hiend = self.term.MODE['normal']
            # For translators: This is output like:
#  Current download cancelled, interrupt (ctrl-c) again within two seconds
# to exit.
            # Where "interupt (ctrl-c) again" and "two" are highlighted.
            msg = _("""
 Current download cancelled, %sinterrupt (ctrl-c) again%s within %s%s%s seconds
to exit.
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
        msg = "%s%s%s%s%s" % (utf8_width_fill(_("Total"), tl.rest(), tl.rest()),
                              ui_bs, ui_size, ui_time, ui_end)
        self.verbose_logger.log(logginglevels.INFO_2, msg)


class DepSolveProgressCallBack:
    """provides text output callback functions for Dependency Solver callback"""
    
    def __init__(self, ayum=None):
        """requires yum-cli log and errorlog functions as arguments"""
        self.verbose_logger = logging.getLogger("yum.verbose.cli")
        self.loops = 0
        self.ayum = ayum

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

    def procReqPo(self, po, formatted_req):
        self.verbose_logger.log(logginglevels.INFO_2,
            _('--> Processing Dependency: %s for package: %s'), formatted_req,
            po)
    
    def unresolved(self, msg):
        self.verbose_logger.log(logginglevels.INFO_2, _('--> Unresolved Dependency: %s'),
            msg)

    
    def procConflict(self, name, confname):
        self.verbose_logger.log(logginglevels.INFO_2,
            _('--> Processing Conflict: %s conflicts %s'),
                                name, confname)

    def procConflictPo(self, po, confname):
        self.verbose_logger.log(logginglevels.INFO_2,
            _('--> Processing Conflict: %s conflicts %s'),
                                po, confname)

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

def _pkgname_ui(ayum, pkgname, ts_states=None):
    """ Get more information on a simple pkgname, if we can. We need to search
        packages that we are dealing with atm. and installed packages (if the
        transaction isn't complete). """
    if ayum is None:
        return pkgname

    if ts_states is None:
        #  Note 'd' is a placeholder for downgrade, and
        # 'r' is a placeholder for reinstall. Neither exist atm.
        ts_states = ('d', 'e', 'i', 'r', 'u')

    matches = []
    def _cond_add(po):
        if matches and matches[0].arch == po.arch and matches[0].verEQ(po):
            return
        matches.append(po)

    for txmbr in ayum.tsInfo.matchNaevr(name=pkgname):
        if txmbr.ts_state not in ts_states:
            continue
        _cond_add(txmbr.po)

    if not matches:
        return pkgname
    fmatch = matches.pop(0)
    if not matches:
        return str(fmatch)

    show_ver  = True
    show_arch = True
    for match in matches:
        if not fmatch.verEQ(match):
            show_ver  = False
        if fmatch.arch != match.arch:
            show_arch = False

    if show_ver: # Multilib. *sigh*
        if fmatch.epoch == '0':
            return '%s-%s-%s' % (fmatch.name, fmatch.version, fmatch.release)
        else:
            return '%s:%s-%s-%s' % (fmatch.epoch, fmatch.name,
                                    fmatch.version, fmatch.release)

    if show_arch:
        return '%s.%s' % (fmatch.name, fmatch.arch)

    return pkgname

class YumCliRPMCallBack(RPMBaseCallback):

    """
    Yum specific callback class for RPM operations.
    """

    width = property(lambda x: _term_width())

    def __init__(self, ayum=None):
        RPMBaseCallback.__init__(self)
        self.lastmsg = to_unicode("")
        self.lastpackage = None # name of last package we looked at
        self.output = logging.getLogger("yum.verbose.cli").isEnabledFor(logginglevels.INFO_2)
        
        # for a progress bar
        self.mark = "#"
        self.marks = 22
        self.ayum = ayum

    #  Installing things have pkg objects passed to the events, so only need to
    # lookup for erased/obsoleted.
    def pkgname_ui(self, pkgname, ts_states=('e', None)):
        """ Get more information on a simple pkgname, if we can. """
        return _pkgname_ui(self.ayum, pkgname, ts_states)

    def event(self, package, action, te_current, te_total, ts_current, ts_total):
        # this is where a progress bar would be called
        process = self.action[action]
        
        if type(package) not in types.StringTypes:
            pkgname = str(package)
        else:
            pkgname = self.pkgname_ui(package)
            
        self.lastpackage = package
        if te_total == 0:
            percent = 0
        else:
            percent = (te_current*100L)/te_total
        
        if self.output and (sys.stdout.isatty() or te_current == te_total):
            (fmt, wid1, wid2) = self._makefmt(percent, ts_current, ts_total,
                                              pkgname=pkgname)
            msg = fmt % (utf8_width_fill(process, wid1, wid1),
                         utf8_width_fill(pkgname, wid2, wid2))
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

    def _makefmt(self, percent, ts_current, ts_total, progress = True,
                 pkgname=None):
        l = len(str(ts_total))
        size = "%s.%s" % (l, l)
        fmt_done = "%" + size + "s/%" + size + "s"
        done = fmt_done % (ts_current, ts_total)

        #  This should probably use TerminLine, but we don't want to dep. on
        # that. So we kind do an ok job by hand ... at least it's dynamic now.
        if pkgname is None:
            pnl = 22
        else:
            pnl = utf8_width(pkgname)

        overhead  = (2 * l) + 2 # Length of done, above
        overhead += 19          # Length of begining
        overhead +=  1          # Space between pn and done
        overhead +=  2          # Ends for progress
        overhead +=  1          # Space for end
        width = self.width
        if width < overhead:
            width = overhead    # Give up
        width -= overhead
        if pnl > width / 2:
            pnl = width / 2

        marks = self.width - (overhead + pnl)
        width = "%s.%s" % (marks, marks)
        fmt_bar = "[%-" + width + "s]"
        # pnl = str(28 + marks + 1)
        full_pnl = pnl + marks + 1

        if progress and percent == 100: # Don't chop pkg name on 100%
            fmt = "\r  %s: %s   " + done
            wid2 = full_pnl
        elif progress:
            bar = fmt_bar % (self.mark * int(marks * (percent / 100.0)), )
            fmt = "\r  %s: %s " + bar + " " + done
            wid2 = pnl
        elif percent == 100:
            fmt = "  %s: %s   " + done
            wid2 = full_pnl
        else:
            bar = fmt_bar % (self.mark * marks, )
            fmt = "  %s: %s " + bar + " " + done
            wid2 = pnl
        return fmt, 15, wid2


def progressbar(current, total, name=None):
    """simple progress bar 50 # marks"""
    
    mark = '#'
    if not sys.stdout.isatty():
        return
        
    if current == 0:
        percent = 0 
    else:
        if total != 0:
            percent = float(current) / total
        else:
            percent = 0

    width = _term_width()

    if name is None and current == total:
        name = '-'

    end = ' %d/%d' % (current, total)
    width -= len(end) + 1
    if width < 0:
        width = 0
    if name is None:
        width -= 2
        if width < 0:
            width = 0
        hashbar = mark * int(width * percent)
        output = '\r[%-*s]%s' % (width, hashbar, end)
    elif current == total: # Don't chop name on 100%
        output = '\r%s%s' % (utf8_width_fill(name, width, width), end)
    else:
        width -= 4
        if width < 0:
            width = 0
        nwid = width / 2
        if nwid > utf8_width(name):
            nwid = utf8_width(name)
        width -= nwid
        hashbar = mark * int(width * percent)
        output = '\r%s: [%-*s]%s' % (utf8_width_fill(name, nwid, nwid), width,
                                     hashbar, end)
     
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

    if len(sys.argv) > 1 and sys.argv[1] in ("progress", "rpm-progress"):
        cb = YumCliRPMCallBack()
        cb.output = True
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

    if len(sys.argv) > 1 and sys.argv[1] in ("progress", "i18n-progress",
                                             "rpm-progress",
                                             'i18n-rpm-progress'):
        yum.misc.setup_locale()
    if len(sys.argv) > 1 and sys.argv[1] in ("progress", "i18n-progress"):
        print ""
        print " Doing progress, i18n: small name"
        print ""
        for i in xrange(0, 101):
            progressbar(i, 100, to_unicode('\xe6\xad\xa3\xe5\x9c\xa8\xe5\xae\x89\xe8\xa3\x85'))
            time.sleep(0.1)
        print ""

        print ""
        print " Doing progress, i18n: big name"
        print ""
        for i in xrange(0, 101):
            progressbar(i, 100, to_unicode('\xe6\xad\xa3\xe5\x9c\xa8\xe5\xae\x89\xe8\xa3\x85' * 5 + ".end"))
            time.sleep(0.1)
        print ""


    if len(sys.argv) > 1 and sys.argv[1] in ("progress", "i18n-progress",
                                             "rpm-progress",
                                             'i18n-rpm-progress'):
        cb = YumCliRPMCallBack()
        cb.output = True
        cb.action["foo"] = to_unicode('\xe6\xad\xa3\xe5\x9c\xa8\xe5\xae\x89\xe8\xa3\x85')
        cb.action["bar"] = cb.action["foo"] * 5 + ".end"
        print ""
        print " Doing CB, i18n: small proc / small pkg"
        print ""
        for i in xrange(0, 101):
            cb.event("spkg", "foo", i, 100, i, 100)
            time.sleep(0.1)        
        print ""
        print " Doing CB, i18n: big proc / big pkg"
        print ""
        for i in xrange(0, 101):
            cb.event("lpkg" + "-=" * 15 + ".end", "bar", i, 100, i, 100)
            time.sleep(0.1)
        print ""
        
