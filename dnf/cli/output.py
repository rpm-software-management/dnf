# Copyright 2005 Duke University
# Copyright (C) 2012-2016 Red Hat, Inc.
#
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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

"""Handle actual output from the cli."""

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import libdnf.transaction

from copy import deepcopy
from dnf.cli.format import format_number, format_time
from dnf.i18n import _, C_, P_, ucd, fill_exact_width, textwrap_fill, exact_width, select_short_long
from dnf.pycomp import xrange, basestring, long, unicode
from dnf.yum.rpmtrans import LoggingTransactionDisplay
from dnf.db.history import MergedTransactionWrapper
import dnf.base
import dnf.callback
import dnf.cli.progress
import dnf.cli.term
import dnf.conf
import dnf.crypto
import dnf.i18n
import dnf.transaction
import dnf.util
import dnf.yum.misc
import fnmatch
import hawkey
import itertools
import logging
import operator
import pwd
import sys
import time

logger = logging.getLogger('dnf')

def _make_lists(transaction, goal):
    b = dnf.util.Bunch({
        'downgraded': [],
        'erased': [],
        'erased_clean': [],
        'erased_dep': [],
        'installed': [],
        'installed_group': [],
        'installed_dep': [],
        'installed_weak': [],
        'reinstalled': [],
        'upgraded': [],
        'failed': [],
    })

    for tsi in transaction:
        if tsi.state == libdnf.transaction.TransactionItemState_ERROR:
            b.failed.append(tsi)
        elif tsi.action == libdnf.transaction.TransactionItemAction_DOWNGRADE:
            b.downgraded.append(tsi)
        elif tsi.action == libdnf.transaction.TransactionItemAction_INSTALL:
            if tsi.reason == libdnf.transaction.TransactionItemReason_GROUP:
                b.installed_group.append(tsi)
            elif tsi.reason == libdnf.transaction.TransactionItemReason_DEPENDENCY:
                b.installed_dep.append(tsi)
            elif tsi.reason == libdnf.transaction.TransactionItemReason_WEAK_DEPENDENCY:
                b.installed_weak.append(tsi)
            else:
                # TransactionItemReason_USER
                b.installed.append(tsi)
        elif tsi.action == libdnf.transaction.TransactionItemAction_REINSTALL:
            b.reinstalled.append(tsi)
        elif tsi.action == libdnf.transaction.TransactionItemAction_REMOVE:
            if tsi.reason == libdnf.transaction.TransactionItemReason_CLEAN:
                b.erased_clean.append(tsi)
            elif tsi.reason == libdnf.transaction.TransactionItemReason_DEPENDENCY:
                b.erased_dep.append(tsi)
            else:
                b.erased.append(tsi)
        elif tsi.action == libdnf.transaction.TransactionItemAction_UPGRADE:
            b.upgraded.append(tsi)

    return b


def _spread_in_columns(cols_count, label, lst):
    left = itertools.chain((label,), itertools.repeat(''))
    lst_length = len(lst)
    right_count = cols_count - 1
    missing_items = -lst_length % right_count
    if not lst_length:
        lst = itertools.repeat('', right_count)
    elif missing_items:
        lst.extend(('',) * missing_items)
    lst_iter = iter(lst)
    return list(zip(left, *[lst_iter] * right_count))


class Output(object):
    """Main output class for the yum command line."""

    GRP_PACKAGE_INDENT = ' ' * 3

    def __init__(self, base, conf):
        self.conf = conf
        self.base = base
        self.term = dnf.cli.term.Term()
        self.progress = None

    def _banner(self, col_data, row):
        term_width = self.term.columns
        rule = '%s' % '=' * term_width
        header = self.fmtColumns(zip(row, col_data), ' ')
        return rule, header, rule

    def _col_widths(self, rows):
        col_data = [dict() for _ in rows[0]]
        for row in rows:
            for (i, val) in enumerate(row):
                col_dct = col_data[i]
                length = len(val)
                col_dct[length] = col_dct.get(length, 0) + 1
        cols = self.calcColumns(col_data, None, indent='  ')
        # align to the left
        return list(map(operator.neg, cols))

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
                if high == 'normal':
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

    @property
    def history(self):
        return self.base.history

    @property
    def sack(self):
        return self.base.sack

    def calcColumns(self, data, columns=None, remainder_column=0,
                    total_width=None, indent=''):
        """Dynamically calculate the widths of the columns that the
        fields in data should be placed into for output.

        :param data: a list of dictionaries that represent the data to
           be output.  Each dictionary in the list corresponds to a
           column of output. The keys of the dictionary are the
           lengths of the items to be output, and the value associated
           with a key is the number of items of that length.
        :param columns: a list containing the minimum amount of space
           that must be allocated for each row. This can be used to
           ensure that there is space available in a column if, for
           example, the actual lengths of the items being output
           cannot be given in *data*
        :param remainder_column: number of the column to receive a few
           extra spaces that may remain after other allocation has
           taken place
        :param total_width: the total width of the output.
           self.term.real_columns is used by default
        :param indent: string that will be prefixed to a line of
           output to create e.g. an indent
        :return: a list of the widths of the columns that the fields
           in data should be placed into for output
        """
        cols = len(data)
        # Convert the data to ascending list of tuples, (field_length, pkgs)
        pdata = data
        data = [None] * cols # Don't modify the passed in data
        for d in range(0, cols):
            data[d] = sorted(pdata[d].items())

        if total_width is None:
            total_width = self.term.real_columns

        # i'm not able to get real terminal width so i'm probably
        # running in non interactive terminal (pipe to grep, redirect to file...)
        # avoid splitting lines to enable filtering output
        if not total_width:
            full_columns = []
            for col in data:
                if col:
                    full_columns.append(col[-1][0])
                else:
                    full_columns.append(0)
            full_columns[0] += len(indent)
            # if possible, try to keep default width (usually 80 columns)
            default_width = self.term.columns
            if sum(full_columns) > default_width:
                return full_columns
            total_width = default_width

        #  We start allocating 1 char to everything but the last column, and a
        # space between each (again, except for the last column). Because
        # at worst we are better with:
        # |one two three|
        # | four        |
        # ...than:
        # |one two three|
        # |            f|
        # |our          |
        # ...the later being what we get if we pre-allocate the last column, and
        # thus. the space, due to "three" overflowing it's column by 2 chars.
        if columns is None:
            columns = [1] * (cols - 1)
            columns.append(0)

        total_width -= (sum(columns) + (cols - 1) + exact_width(indent))
        if not columns[-1]:
            total_width += 1
        while total_width > 0:
            # Find which field all the spaces left will help best
            helps = 0
            val = 0
            for d in xrange(0, cols):
                thelps = self._calc_columns_spaces_helps(columns[d], data[d],
                                                         total_width)
                if not thelps:
                    continue
                #  We prefer to overflow: the last column, and then earlier
                # columns. This is so that in the best case (just overflow the
                # last) ... grep still "works", and then we make it prettier.
                if helps and (d == (cols - 1)) and (thelps / 2) < helps:
                    continue
                if thelps < helps:
                    continue
                helps = thelps
                val = d

            #  If we found a column to expand, move up to the next level with
            # that column and start again with any remaining space.
            if helps:
                diff = data[val].pop(0)[0] - columns[val]
                if not columns[val] and (val == (cols - 1)):
                    #  If we are going from 0 => N on the last column, take 1
                    # for the space before the column.
                    total_width -= 1
                columns[val] += diff
                total_width -= diff
                continue

            overflowed_columns = 0
            for d in xrange(0, cols):
                if not data[d]:
                    continue
                overflowed_columns += 1
            if overflowed_columns:
                #  Split the remaining spaces among each overflowed column
                # equally
                norm = total_width // overflowed_columns
                for d in xrange(0, cols):
                    if not data[d]:
                        continue
                    columns[d] += norm
                    total_width -= norm

            #  Split the remaining spaces among each column equally, except the
            # last one. And put the rest into the remainder column
            cols -= 1
            norm = total_width // cols
            for d in xrange(0, cols):
                columns[d] += norm
            columns[remainder_column] += total_width - (cols * norm)
            total_width = 0

        return columns

    @staticmethod
    def _fmt_column_align_width(width):
        """Returns tuple of (align_left, width)"""
        if width < 0:
            return (True, -width)
        return (False, width)

    def _col_data(self, col_data):
        assert len(col_data) == 2 or len(col_data) == 3
        if len(col_data) == 2:
            (val, width) = col_data
            hibeg = hiend = ''
        if len(col_data) == 3:
            (val, width, highlight) = col_data
            (hibeg, hiend) = self._highlight(highlight)
        return (ucd(val), width, hibeg, hiend)

    def fmtColumns(self, columns, msg=u'', end=u''):
        """Return a row of data formatted into a string for output.
        Items can overflow their columns.

        :param columns: a list of tuples containing the data to
           output.  Each tuple contains first the item to be output,
           then the amount of space allocated for the column, and then
           optionally a type of highlighting for the item
        :param msg: a string to begin the line of output with
        :param end: a string to end the line of output with
        :return: a row of data formatted into a string for output
        """
        columns = list(columns)
        total_width = len(msg)
        data = []
        for col_data in columns[:-1]:
            (val, width, hibeg, hiend) = self._col_data(col_data)

            if not width: # Don't count this column, invisible text
                msg += u"%s"
                data.append(val)
                continue

            (align_left, width) = self._fmt_column_align_width(width)
            val_width = exact_width(val)
            if val_width <= width:
                #  Don't use fill_exact_width() because it sucks performance
                # wise for 1,000s of rows. Also allows us to use len(), when
                # we can.
                msg += u"%s%s%s%s "
                if align_left:
                    data.extend([hibeg, val, " " * (width - val_width), hiend])
                else:
                    data.extend([hibeg, " " * (width - val_width), val, hiend])
            else:
                msg += u"%s%s%s\n" + " " * (total_width + width + 1)
                data.extend([hibeg, val, hiend])
            total_width += width
            total_width += 1
        (val, width, hibeg, hiend) = self._col_data(columns[-1])
        (align_left, width) = self._fmt_column_align_width(width)
        val = fill_exact_width(val, width, left=align_left,
                              prefix=hibeg, suffix=hiend)
        msg += u"%%s%s" % end
        data.append(val)
        return msg % tuple(data)

    def simpleList(self, pkg, ui_overflow=False, indent='', highlight=False,
                   columns=None):
        """Print a package as a line.

        :param pkg: the package to be printed
        :param ui_overflow: unused
        :param indent: string to be prefixed onto the line to provide
           e.g. an indent
        :param highlight: highlighting options for the name of the
           package
        :param colums: tuple containing the space allocated for each
           column of output.  The columns are the package name, version,
           and repository
        """
        if columns is None:
            columns = (-40, -22, -16) # Old default
        na = '%s%s.%s' % (indent, pkg.name, pkg.arch)
        hi_cols = [highlight, 'normal', 'normal']

        columns = zip((na, pkg.evr, pkg._from_repo), columns, hi_cols)
        print(self.fmtColumns(columns))

    def simpleEnvraList(self, pkg, ui_overflow=False,
                        indent='', highlight=False, columns=None):
        """Print a package as a line, with the package itself in envra
        format so it can be passed to list/install/etc.

        :param pkg: the package to be printed
        :param ui_overflow: unused
        :param indent: string to be prefixed onto the line to provide
           e.g. an indent
        :param highlight: highlighting options for the name of the
           package
        :param colums: tuple containing the space allocated for each
           column of output.  The columns the are the package envra and
           repository
        """
        if columns is None:
            columns = (-63, -16) # Old default
        envra = '%s%s' % (indent, ucd(pkg))
        hi_cols = [highlight, 'normal', 'normal']
        rid = pkg.ui_from_repo
        columns = zip((envra, rid), columns, hi_cols)
        print(self.fmtColumns(columns))

    def simple_name_list(self, pkg):
        """Print a package as a line containing its name."""
        print(ucd(pkg.name))

    def simple_nevra_list(self, pkg):
        """Print a package as a line containing its NEVRA."""
        print(ucd(pkg))

    def fmtKeyValFill(self, key, val):
        """Return a key value pair in the common two column output
        format.

        :param key: the key to be formatted
        :param val: the value associated with *key*
        :return: the key value pair formatted in two columns for output
        """
        keylen = exact_width(key)
        cols = self.term.columns
        nxt = ' ' * (keylen - 2) + ': '
        if not val:
            # textwrap.fill in case of empty val returns empty string
            return key
        val = ucd(val)
        ret = textwrap_fill(val, width=cols, initial_indent=key,
                            subsequent_indent=nxt)
        if ret.count("\n") > 1 and keylen > (cols // 3):
            # If it's big, redo it again with a smaller subsequent off
            ret = textwrap_fill(val, width=cols, initial_indent=key,
                                subsequent_indent='     ...: ')
        return ret

    def fmtSection(self, name, fill='='):
        """Format and return a section header.  The format of the
        header is a line with *name* centred, and *fill* repeated on
        either side to fill an entire line on the terminal.

        :param name: the name of the section
        :param fill: the character to repeat on either side of *name*
          to fill an entire line.  *fill* must be a single character.
        :return: a string formatted to be a section header
        """
        name = ucd(name)
        cols = self.term.columns - 2
        name_len = exact_width(name)
        if name_len >= (cols - 4):
            beg = end = fill * 2
        else:
            beg = fill * ((cols - name_len) // 2)
            end = fill * (cols - name_len - len(beg))

        return "%s %s %s" % (beg, name, end)

    def infoOutput(self, pkg, highlight=False):
        """Print information about the given package.

        :param pkg: the package to print information about
        :param hightlight: highlighting options for the name of the
           package
        """
        def format_key_val(key, val):
            return " ".join([fill_exact_width(key, 12, 12), ":", str(val)])

        def format_key_val_fill(key, val):
            return self.fmtKeyValFill(fill_exact_width(key, 12, 12) + " : ", val or "")

        output_list = []
        (hibeg, hiend) = self._highlight(highlight)
        # Translators: This is abbreviated 'Name'. Should be no longer
        # than 12 characters. You can use the full version if it is short
        # enough in your language.
        key = select_short_long(12, C_("short", "Name"),
                                    C_("long", "Name"))
        output_list.append(format_key_val(key,
                                          "%s%s%s" % (hibeg, pkg.name, hiend)))
        if pkg.epoch:
            # Translators: This message should be no longer than 12 characters.
            output_list.append(format_key_val(_("Epoch"), pkg.epoch))
        key = select_short_long(12, C_("short", "Version"),
                                    C_("long", "Version"))
        output_list.append(format_key_val(key, pkg.version))
        # Translators: This message should be no longer than 12 characters.
        output_list.append(format_key_val(_("Release"), pkg.release))
        key = select_short_long(12, C_("short", "Arch"),
                                    C_("long", "Architecture"))
        output_list.append(format_key_val(key, pkg.arch))
        key = select_short_long(12, C_("short", "Size"), C_("long", "Size"))
        output_list.append(format_key_val(key,
                                          format_number(float(pkg._size))))
        # Translators: This message should be no longer than 12 characters.
        output_list.append(format_key_val(_("Source"), pkg.sourcerpm))
        key = select_short_long(12, C_("short", "Repo"),
                                    C_("long", "Repository"))
        output_list.append(format_key_val(key, pkg.repoid))

        if pkg._from_system:
            history_repo = self.history.repo(pkg)
            if history_repo:
                # Translators: This message should be no longer than 12 chars.
                output_list.append(format_key_val(_("From repo"), history_repo))
        if self.conf.verbose:
            # :hawkey does not support changelog information
            # print(_("Committer   : %s") % ucd(pkg.committer))
            # print(_("Committime  : %s") % time.ctime(pkg.committime))
            # Translators: This message should be no longer than 12 characters.
            output_list.append(format_key_val(_("Packager"), pkg.packager))
            # Translators: This message should be no longer than 12 characters.
            output_list.append(format_key_val(_("Buildtime"),
                                              dnf.util.normalize_time(pkg.buildtime)))
            if pkg.installtime:
            # Translators: This message should be no longer than 12 characters.
                output_list.append(format_key_val(_("Install time"),
                                                  dnf.util.normalize_time(pkg.installtime)))
            history_pkg = self.history.package_data(pkg)
            if history_pkg:
                try:
                    uid = int(history_pkg._item.getInstalledBy())
                except ValueError: # In case int() fails
                    uid = None
                # Translators: This message should be no longer than 12 chars.
                output_list.append(format_key_val(_("Installed by"), self._pwd_ui_username(uid)))
        # Translators: This is abbreviated 'Summary'. Should be no longer
        # than 12 characters. You can use the full version if it is short
        # enough in your language.
        key = select_short_long(12, C_("short", "Summary"),
                                    C_("long", "Summary"))
        output_list.append(format_key_val_fill(key, pkg.summary))
        if pkg.url:
            output_list.append(format_key_val(_("URL"), ucd(pkg.url)))
        # Translators: This message should be no longer than 12 characters.
        output_list.append(format_key_val_fill(_("License"), pkg.license))
        # Translators: This is abbreviated 'Description'. Should be no longer
        # than 12 characters. You can use the full version if it is short
        # enough in your language.
        key = select_short_long(12, C_("short", "Description"),
                                    C_("long", "Description"))
        output_list.append(format_key_val_fill(key, pkg.description))
        return "\n".join(output_list)

    def updatesObsoletesList(self, uotup, changetype, columns=None):
        """Print a simple string that explains the relationship
        between the members of an update or obsoletes tuple.

        :param uotup: an update or obsoletes tuple.  The first member
           is the new package, and the second member is the old
           package
        :param changetype: a string indicating what the change between
           the packages is, e.g. 'updates' or 'obsoletes'
        :param columns: a tuple containing information about how to
           format the columns of output.  The absolute value of each
           number in the tuple indicates how much space has been
           allocated for the corresponding column.  If the number is
           negative, the text in the column will be left justified,
           and if it is positive, the text will be right justified.
           The columns of output are the package name, version, and repository
        """
        (changePkg, instPkg) = uotup

        if columns is not None:
            # New style, output all info. for both old/new with old indented
            chi = self.conf.color_update_remote
            if changePkg.reponame != hawkey.SYSTEM_REPO_NAME:
                chi = self.conf.color_update_local
            self.simpleList(changePkg, columns=columns, highlight=chi)
            self.simpleList(instPkg, columns=columns, indent=' ' * 4,
                            highlight=self.conf.color_update_installed)
            return

        # Old style
        c_compact = changePkg.compactPrint()
        i_compact = '%s.%s' % (instPkg.name, instPkg.arch)
        c_repo = changePkg.repoid
        print('%-35.35s [%.12s] %.10s %-20.20s' %
              (c_compact, c_repo, changetype, i_compact))

    def listPkgs(self, lst, description, outputType, highlight_na={},
                 columns=None, highlight_modes={}):
        """Prints information about the given list of packages.

        :param lst: a list of packages to print information about
        :param description: string describing what the list of
           packages contains, e.g. 'Available Packages'
        :param outputType: The type of information to be printed.
           Current options::

              'list' - simple pkg list
              'info' - similar to rpm -qi output
              'name' - simple name list
              'nevra' - simple nevra list
        :param highlight_na: a dictionary containing information about
              packages that should be highlighted in the output.  The
              dictionary keys are (name, arch) tuples for the package,
              and the associated values are the package objects
              themselves.
        :param columns: a tuple containing information about how to
           format the columns of output.  The absolute value of each
           number in the tuple indicates how much space has been
           allocated for the corresponding column.  If the number is
           negative, the text in the column will be left justified,
           and if it is positive, the text will be right justified.
           The columns of output are the package name, version, and
           repository
        :param highlight_modes: dictionary containing information
              about to highlight the packages in *highlight_na*.
              *highlight_modes* should contain the following keys::

                 'not_in' - highlighting used for packages not in *highlight_na*
                 '=' - highlighting used when the package versions are equal
                 '<' - highlighting used when the package has a lower version
                       number
                 '>' - highlighting used when the package has a higher version
                       number
        :return: (exit_code, [errors])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string

        """
        if outputType in ['list', 'info', 'name', 'nevra']:
            thingslisted = 0
            if len(lst) > 0:
                thingslisted = 1
                print('%s' % description)
                for pkg in sorted(lst):
                    key = (pkg.name, pkg.arch)
                    highlight = False
                    if key not in highlight_na:
                        highlight = highlight_modes.get('not in', 'normal')
                    elif pkg.evr_eq(highlight_na[key]):
                        highlight = highlight_modes.get('=', 'normal')
                    elif pkg.evr_lt(highlight_na[key]):
                        highlight = highlight_modes.get('>', 'bold')
                    else:
                        highlight = highlight_modes.get('<', 'normal')

                    if outputType == 'list':
                        self.simpleList(pkg, ui_overflow=True,
                                        highlight=highlight, columns=columns)
                    elif outputType == 'info':
                        print(self.infoOutput(pkg, highlight=highlight) + "\n")
                    elif outputType == 'name':
                        self.simple_name_list(pkg)
                    elif outputType == 'nevra':
                        self.simple_nevra_list(pkg)
                    else:
                        pass

            if thingslisted == 0:
                return 1, [_('No packages to list')]
            return 0, []

    def userconfirm(self, msg=None, defaultyes_msg=None):
        """Get a yes or no from the user, and default to No

        :msg: String for case with [y/N]
        :defaultyes_msg: String for case with [Y/n]
        :return: True if the user selects yes, and False if the user
           selects no
        """
        yui = (ucd(_('y')), ucd(_('yes')))
        nui = (ucd(_('n')), ucd(_('no')))
        aui = yui + nui
        while True:
            if msg is None:
                msg = _('Is this ok [y/N]: ')
            choice = ''
            if self.conf.defaultyes:
                if defaultyes_msg is None:
                    msg = _('Is this ok [Y/n]: ')
                else:
                    msg = defaultyes_msg
            try:
                choice = dnf.i18n.ucd_input(msg)
            except EOFError:
                pass
            except KeyboardInterrupt:
                choice = nui[0]
            choice = ucd(choice).lower()
            if len(choice) == 0:
                choice = yui[0] if self.conf.defaultyes else nui[0]
            if choice in aui:
                break

            # If the English one letter names don't mix with the translated
            # letters, allow them too:
            if u'y' == choice and u'y' not in aui:
                choice = yui[0]
                break
            if u'n' == choice and u'n' not in aui:
                choice = nui[0]
                break

        if choice in yui:
            return True
        return False

    def _pkgs2name_dict(self, sections):
        installed = self.sack.query().installed()._name_dict()
        available = self.sack.query().available()._name_dict()

        d = {}
        for pkg_name in itertools.chain(*list(zip(*sections))[1]):
            if pkg_name in installed:
                d[pkg_name] = installed[pkg_name][0]
            elif pkg_name in available:
                d[pkg_name] = available[pkg_name][0]
        return d

    def _pkgs2col_lengths(self, sections, name_dict):
        nevra_lengths = {}
        repo_lengths = {}
        for pkg_name in itertools.chain(*list(zip(*sections))[1]):
            pkg = name_dict.get(pkg_name)
            if pkg is None:
                continue
            nevra_l = exact_width(ucd(pkg)) + exact_width(self.GRP_PACKAGE_INDENT)
            repo_l = exact_width(ucd(pkg.reponame))
            nevra_lengths[nevra_l] = nevra_lengths.get(nevra_l, 0) + 1
            repo_lengths[repo_l] = repo_lengths.get(repo_l, 0) + 1
        return (nevra_lengths, repo_lengths)

    def _display_packages(self, pkg_names):
        for name in pkg_names:
            print('%s%s' % (self.GRP_PACKAGE_INDENT, name))

    def _display_packages_verbose(self, pkg_names, name_dict, columns):
        for name in pkg_names:
            try:
                pkg = name_dict[name]
            except KeyError:
                # package not in any repo -> print only package name
                print('%s%s' % (self.GRP_PACKAGE_INDENT, name))
                continue
            highlight = False
            if not pkg._from_system:
                highlight = self.conf.color_list_available_install
            self.simpleEnvraList(pkg, ui_overflow=True,
                                 indent=self.GRP_PACKAGE_INDENT,
                                 highlight=highlight,
                                 columns=columns)

    def display_pkgs_in_groups(self, group):
        """Output information about the packages in a given group

        :param group: a Group object to output information about
        """
        def names(packages):
            return sorted(pkg.name for pkg in packages)
        print('\n' + _('Group: %s') % group.ui_name)

        verbose = self.conf.verbose
        if verbose:
            print(_(' Group-Id: %s') % ucd(group.id))
        if group.ui_description:
            print(_(' Description: %s') % ucd(group.ui_description) or "")
        if group.lang_only:
            print(_(' Language: %s') % group.lang_only)

        sections = (
            (_(' Mandatory Packages:'), names(group.mandatory_packages)),
            (_(' Default Packages:'), names(group.default_packages)),
            (_(' Optional Packages:'), names(group.optional_packages)),
            (_(' Conditional Packages:'), names(group.conditional_packages)))
        if verbose:
            name_dict = self._pkgs2name_dict(sections)
            col_lengths = self._pkgs2col_lengths(sections, name_dict)
            columns = self.calcColumns(col_lengths)
            columns = (-columns[0], -columns[1])
            for (section_name, packages) in sections:
                if len(packages) < 1:
                    continue
                print(section_name)
                self._display_packages_verbose(packages, name_dict, columns)
        else:
            for (section_name, packages) in sections:
                if len(packages) < 1:
                    continue
                print(section_name)
                self._display_packages(packages)

    def display_groups_in_environment(self, environment):
        """Output information about the packages in a given environment

        :param environment: an Environment object to output information about
        """
        def names(groups):
            return sorted(group.name for group in groups)
        print(_('Environment Group: %s') % environment.ui_name)

        if self.conf.verbose:
            print(_(' Environment-Id: %s') % ucd(environment.id))
        if environment.ui_description:
            description = ucd(environment.ui_description) or ""
            print(_(' Description: %s') % description)

        sections = (
            (_(' Mandatory Groups:'), names(environment.mandatory_groups)),
            (_(' Optional Groups:'), names(environment.optional_groups)))
        for (section_name, packages) in sections:
            if len(packages) < 1:
                continue
            print(section_name)
            self._display_packages(packages)

    def matchcallback(self, po, values, matchfor=None, verbose=None,
                      highlight=None):
        """Output search/provides type callback matches.

        :param po: the package object that matched the search
        :param values: the information associated with *po* that
           matched the search
        :param matchfor: a list of strings to be highlighted in the
           output
        :param verbose: whether to output extra verbose information
        :param highlight: highlighting options for the highlighted matches
        """
        def print_highlighted_key_item(key, item, printed_headline, can_overflow=False):
            if not printed_headline:
                print(_('Matched from:'))
            item = ucd(item) or ""
            if item == "":
                return
            if matchfor:
                item = self._sub_highlight(item, highlight, matchfor, ignore_case=True)
            if can_overflow:
                print(self.fmtKeyValFill(key, item))
            else:
                print(key % item)

        def print_file_provides(item, printed_match):
            if not any([item.startswith("/"), item.startswith('*/')]):
                return False
            key = _("Filename    : %s")
            file_match = False
            for filename in po.files:
                if fnmatch.fnmatch(filename, item):
                    file_match = True
                    print_highlighted_key_item(key, filename, printed_match, can_overflow=False)
            return file_match

        if self.conf.showdupesfromrepos:
            msg = '%s : ' % po
        else:
            msg = '%s.%s : ' % (po.name, po.arch)
        msg = self.fmtKeyValFill(msg, po.summary or "")
        if matchfor:
            if highlight is None:
                highlight = self.conf.color_search_match
            msg = self._sub_highlight(msg, highlight, matchfor, ignore_case=True)
        print(msg)

        if verbose is None:
            verbose = self.conf.verbose
        if not verbose:
            return

        print(_("Repo        : %s") % po.ui_from_repo)
        printed_match = False
        name_match = False
        for item in set(values):
            if po.summary == item:
                name_match = True
                continue # Skip double name/summary printing

            if po.description == item:
                key = _("Description : ")
                print_highlighted_key_item(key, item, printed_match, can_overflow=True)
                printed_match = True
            elif po.url == item:
                key = _("URL         : %s")
                print_highlighted_key_item(key, item, printed_match, can_overflow=False)
                printed_match = True
            elif po.license == item:
                key = _("License     : %s")
                print_highlighted_key_item(key, item, printed_match, can_overflow=False)
                printed_match = True
            elif print_file_provides(item, printed_match):
                printed_match = True
            else:
                key = _("Provide    : %s")
                for provide in po.provides:
                    provide = str(provide)
                    if fnmatch.fnmatch(provide, item):
                        print_highlighted_key_item(key, provide, printed_match, can_overflow=False)
                        printed_match = True
                    else:
                        first_provide = provide.split()[0]
                        possible = set('=<>')
                        if any((char in possible) for char in item):
                            item_new = item.split()[0]
                        else:
                            item_new = item
                        if fnmatch.fnmatch(first_provide, item_new):
                            print_highlighted_key_item(
                                key, provide, printed_match, can_overflow=False)
                            printed_match = True

        if not any([printed_match, name_match]):
            for item in set(values):
                key = _("Other       : %s")
                print_highlighted_key_item(key, item, printed_match, can_overflow=False)
        print()

    def matchcallback_verbose(self, po, values, matchfor=None):
        """Output search/provides type callback matches.  This will
        output more information than :func:`matchcallback`.

        :param po: the package object that matched the search
        :param values: the information associated with *po* that
           matched the search
        :param matchfor: a list of strings to be highlighted in the
           output
        """
        return self.matchcallback(po, values, matchfor, verbose=True)

    def reportDownloadSize(self, packages, installonly=False):
        """Report the total download size for a set of packages

        :param packages: a list of package objects
        :param installonly: whether the transaction consists only of installations
        """
        totsize = 0
        locsize = 0
        insize = 0
        error = False
        for pkg in packages:
            # Just to be on the safe side, if for some reason getting
            # the package size fails, log the error and don't report download
            # size
            try:
                size = int(pkg._size)
                totsize += size
                try:
                    if pkg.verifyLocalPkg():
                        locsize += size
                except Exception:
                    pass

                if not installonly:
                    continue

                try:
                    size = int(pkg.installsize)
                except Exception:
                    pass
                insize += size
            except Exception:
                error = True
                msg = _('There was an error calculating total download size')
                logger.error(msg)
                break

        if not error:
            if locsize:
                logger.info(_("Total size: %s"),
                                        format_number(totsize))
            if locsize != totsize:
                logger.info(_("Total download size: %s"),
                                        format_number(totsize - locsize))
            if installonly:
                logger.info(_("Installed size: %s"), format_number(insize))

    def reportRemoveSize(self, packages):
        """Report the total size of packages being removed.

        :param packages: a list of package objects
        """
        totsize = 0
        error = False
        for pkg in packages:
            # Just to be on the safe side, if for some reason getting
            # the package size fails, log the error and don't report download
            # size
            try:
                size = pkg._size
                totsize += size
            except Exception:
                error = True
                msg = _('There was an error calculating installed size')
                logger.error(msg)
                break
        if not error:
            logger.info(_("Freed space: %s"), format_number(totsize))

    def list_group_transaction(self, comps, history, diff):
        if not diff:
            return None

        out = []
        rows = []
        if diff.new_groups:
            out.append(_('Marking packages as installed by the group:'))
        for grp_id in diff.new_groups:
            pkgs = list(diff.added_packages(grp_id))
            group_object = comps._group_by_id(grp_id)
            grp_name = group_object.ui_name if group_object else grp_id
            rows.extend(_spread_in_columns(4, "@" + grp_name, pkgs))
        if diff.removed_groups:
            out.append(_('Marking packages as removed by the group:'))
        for grp_id in diff.removed_groups:
            pkgs = list(diff.removed_packages(grp_id))
            grp_name = history.group.get(grp_id).ui_name
            rows.extend(_spread_in_columns(4, "@" + grp_name, pkgs))

        if rows:
            col_data = self._col_widths(rows)
            for row in rows:
                out.append(self.fmtColumns(zip(row, col_data), ' '))
            out[0:0] = self._banner(col_data, (_('Group'), _('Packages'), '', ''))
        return '\n'.join(out)

    def _skipped_packages(self, report_problems):
        """returns set of conflicting packages and set of packages with broken dependency that would
        be additionally installed when --best and --allowerasing"""
        if self.base._goal.actions & (hawkey.INSTALL | hawkey.UPGRADE | hawkey.UPGRADE_ALL):
            best = True
        else:
            best = False
        ng = deepcopy(self.base._goal)
        params = {"allow_uninstall": self.base._allow_erasing,
                  "force_best": best,
                  "ignore_weak": True}
        ret = ng.run(**params)
        if not ret and report_problems:
            msg = dnf.util._format_resolve_problems(ng.problem_rules())
            logger.warning(msg)
        problem_conflicts = set(ng.problem_conflicts(available=True))
        problem_dependency = set(ng.problem_broken_dependency(available=True)) - problem_conflicts
        return problem_conflicts, problem_dependency

    def list_transaction(self, transaction):
        """Return a string representation of the transaction in an
        easy-to-read format.
        """
        forward_actions = hawkey.UPGRADE | hawkey.UPGRADE_ALL | hawkey.DISTUPGRADE | \
            hawkey.DISTUPGRADE_ALL | hawkey.DOWNGRADE | hawkey.INSTALL
        skipped_conflicts = set()
        skipped_broken = set()

        if transaction is None:
            # set empty transaction list instead of returning None
            # in order to display module changes when RPM transaction is empty
            transaction = []

        list_bunch = _make_lists(transaction, self.base._goal)
        pkglist_lines = []
        data = {'n' : {}, 'v' : {}, 'r' : {}}
        a_wid = 0 # Arch can't get "that big" ... so always use the max.

        def _add_line(lines, data, a_wid, po, obsoletes=[]):
            (n, a, e, v, r) = po.pkgtup
            evr = po.evr
            repoid = po._from_repo
            size = format_number(po._size)

            if a is None: # gpgkeys are weird
                a = 'noarch'

            # none, partial, full?
            if po._from_system:
                hi = self.conf.color_update_installed
            elif po._from_cmdline:
                hi = self.conf.color_update_local
            else:
                hi = self.conf.color_update_remote
            lines.append((n, a, evr, repoid, size, obsoletes, hi))
            #  Create a dict of field_length => number of packages, for
            # each field.
            for (d, v) in (("n", len(n)), ("v", len(evr)), ("r", len(repoid))):
                data[d].setdefault(v, 0)
                data[d][v] += 1
            a_wid = max(a_wid, len(a))
            return a_wid
        ins_group_msg = _('Installing group/module packages') if dnf.base.WITH_MODULES \
            else _('Installing group packages')

        for (action, pkglist) in [
                # TRANSLATORS: This is for a list of packages to be installed.
                (C_('summary', 'Installing'), list_bunch.installed),
                # TRANSLATORS: This is for a list of packages to be upgraded.
                (C_('summary', 'Upgrading'), list_bunch.upgraded),
                # TRANSLATORS: This is for a list of packages to be reinstalled.
                (C_('summary', 'Reinstalling'), list_bunch.reinstalled),
                (ins_group_msg, list_bunch.installed_group),
                (_('Installing dependencies'), list_bunch.installed_dep),
                (_('Installing weak dependencies'), list_bunch.installed_weak),
                # TRANSLATORS: This is for a list of packages to be removed.
                (_('Removing'), list_bunch.erased),
                (_('Removing dependent packages'), list_bunch.erased_dep),
                (_('Removing unused dependencies'), list_bunch.erased_clean),
                # TRANSLATORS: This is for a list of packages to be downgraded.
                (C_('summary', 'Downgrading'), list_bunch.downgraded)]:
            lines = []

            # build a reverse mapping to 'replaced_by'
            # this is required to achieve reasonable speed
            replaces = {}
            for tsi in transaction:
                if tsi.action != libdnf.transaction.TransactionItemAction_OBSOLETED:
                    continue
                for i in tsi._item.getReplacedBy():
                    replaces.setdefault(i, set()).add(tsi)

            for tsi in pkglist:
                if tsi.action not in dnf.transaction.FORWARD_ACTIONS + [libdnf.transaction.TransactionItemAction_REMOVE]:
                    continue

                # get TransactionItems obsoleted by tsi
                obsoleted = sorted(replaces.get(tsi._item, []))

                a_wid = _add_line(lines, data, a_wid, tsi.pkg, obsoleted)

            pkglist_lines.append((action, lines))

        installedProfiles = sorted(dict(self.base._moduleContainer.getInstalledProfiles()).items())
        if installedProfiles:
            action = _("Installing module profiles")
            lines = []
            for name, profiles in installedProfiles:
                for profile in list(profiles):
                    lines.append(("%s/%s" % (name, profile), "", "", "", "", "", ""))
            pkglist_lines.append((action, lines))

        removedProfiles = sorted(dict(self.base._moduleContainer.getRemovedProfiles()).items())
        if removedProfiles:
            action = _("Disabling module profiles")
            lines = []
            for name, profiles in removedProfiles:
                for profile in list(profiles):
                    lines.append(("%s/%s" % (name, profile), "", "", "", "", "", ""))
            pkglist_lines.append((action, lines))

        enabledStreams = sorted(dict(self.base._moduleContainer.getEnabledStreams()).items())
        if enabledStreams:
            action = _("Enabling module streams")
            lines = []
            for name, stream in enabledStreams:
                lines.append((name, "", stream, "", "", "", ""))
            pkglist_lines.append((action, lines))

        switchedStreams = sorted(dict(self.base._moduleContainer.getSwitchedStreams()).items())
        if switchedStreams:
            action = _("Switching module streams")
            lines = []
            for name, stream in switchedStreams:
                lines.append((name, "", "%s -> %s" % (stream[0], stream[1]), "", "", "", ""))
            pkglist_lines.append((action, lines))

        disabledModules = sorted(list(self.base._moduleContainer.getDisabledModules()))
        if disabledModules:
            action = _("Disabling modules")
            lines = []
            for name in disabledModules:
                lines.append((name, "", "", "", "", "", ""))
            pkglist_lines.append((action, lines))

        resetModules = sorted(list(self.base._moduleContainer.getResetModules()))
        if resetModules:
            action = _("Resetting modules")
            lines = []
            for name in resetModules:
                lines.append((name, "", "", "", "", "", ""))
            pkglist_lines.append((action, lines))
        if self.base._history:
            install_env_group = self.base._history.env._installed
            if install_env_group:
                action = _("Installing Environment Groups")
                lines = []
                for group in install_env_group.values():
                    lines.append((group.getName(), "", "", "", "", "", ""))
                pkglist_lines.append((action, lines))
            upgrade_env_group = self.base._history.env._upgraded
            if upgrade_env_group:
                action = _("Upgrading Environment Groups")
                lines = []
                for group in upgrade_env_group.values():
                    lines.append((group.getName(), "", "", "", "", "", ""))
                pkglist_lines.append((action, lines))
            remove_env_group = self.base._history.env._removed
            if remove_env_group:
                action = _("Removing Environment Groups")
                lines = []
                for group in remove_env_group.values():
                    lines.append((group.getName(), "", "", "", "", "", ""))
                pkglist_lines.append((action, lines))
            install_group = self.base._history.group._installed
            if install_group:
                action = _("Installing Groups")
                lines = []
                for group in install_group.values():
                    lines.append((group.getName(), "", "", "", "", "", ""))
                pkglist_lines.append((action, lines))
            upgrade_group = self.base._history.group._upgraded
            if upgrade_group:
                action = _("Upgrading Groups")
                lines = []
                for group in upgrade_group.values():
                    lines.append((group.getName(), "", "", "", "", "", ""))
                pkglist_lines.append((action, lines))
            remove_group = self.base._history.group._removed
            if remove_group:
                action = _("Removing Groups")
                lines = []
                for group in remove_group.values():
                    lines.append((group.getName(), "", "", "", "", "", ""))
                pkglist_lines.append((action, lines))
        # show skipped conflicting packages
        if not self.conf.best and self.base._goal.actions & forward_actions:
            lines = []
            skipped_conflicts, skipped_broken = self._skipped_packages(report_problems=True)
            for pkg in sorted(skipped_conflicts):
                a_wid = _add_line(lines, data, a_wid, pkg, [])
            recommendations = ["--best"]
            if not self.base._allow_erasing:
                recommendations.append("--allowerasing")
            skip_str = _("Skipping packages with conflicts:\n"
                         "(add '%s' to command line "
                         "to force their upgrade)") % " ".join(recommendations)
            pkglist_lines.append((skip_str, lines))

            lines = []
            for pkg in sorted(skipped_broken):
                a_wid = _add_line(lines, data, a_wid, pkg, [])
            skip_str = _("Skipping packages with broken dependencies%s")
            if self.base.conf.upgrade_group_objects_upgrade:
                skip_str = skip_str % ""
            else:
                skip_str = skip_str % _(" or part of a group")

            pkglist_lines.append((skip_str, lines))

        if not data['n'] and not self.base._moduleContainer.isChanged() and not \
                (self.base._history and (self.base._history.group or self.base._history.env)):
            return u''
        else:
            data = [data['n'], {}, data['v'], data['r'], {}]
            columns = [1, a_wid, 1, 1, 5]
            columns = self.calcColumns(data, indent="  ", columns=columns,
                                       remainder_column=2)
            (n_wid, a_wid, v_wid, r_wid, s_wid) = columns

            # Do not use 'Package' without context. Using context resolves
            # RhBug 1302935 as a side effect.
            msg_package = select_short_long(n_wid,
            # Translators: This is the short version of 'Package'. You can
            # use the full (unabbreviated) term 'Package' if you think that
            # the translation to your language is not too long and will
            # always fit to limited space.
                                            C_('short', 'Package'),
            # Translators: This is the full (unabbreviated) term 'Package'.
                                            C_('long', 'Package'))
            msg_arch = select_short_long(a_wid,
            # Translators: This is abbreviated 'Architecture', used when
            # we have not enough space to display the full word.
                                         C_('short', 'Arch'),
            # Translators: This is the full word 'Architecture', used when
            # we have enough space.
                                         C_('long', 'Architecture'))
            msg_version = select_short_long(v_wid,
            # Translators: This is the short version of 'Version'. You can
            # use the full (unabbreviated) term 'Version' if you think that
            # the translation to your language is not too long and will
            # always fit to limited space.
                                            C_('short', 'Version'),
            # Translators: This is the full (unabbreviated) term 'Version'.
                                            C_('long', 'Version'))
            msg_repository = select_short_long(r_wid,
            # Translators: This is abbreviated 'Repository', used when
            # we have not enough space to display the full word.
                                               C_('short', 'Repo'),
            # Translators: This is the full word 'Repository', used when
            # we have enough space.
                                               C_('long', 'Repository'))
            msg_size = select_short_long(s_wid,
            # Translators: This is the short version of 'Size'. It should
            # not be longer than 5 characters. If the term 'Size' in your
            # language is not longer than 5 characters then you can use it
            # unabbreviated.
                                         C_('short', 'Size'),
            # Translators: This is the full (unabbreviated) term 'Size'.
                                         C_('long', 'Size'))

            out = [u"%s\n%s\n%s\n" % ('=' * self.term.columns,
                                      self.fmtColumns(((msg_package, -n_wid),
                                                       (msg_arch, -a_wid),
                                                       (msg_version, -v_wid),
                                                       (msg_repository, -r_wid),
                                                       (msg_size, s_wid)), u" "),
                                      '=' * self.term.columns)]

        for (action, lines) in pkglist_lines:
            if lines:
                totalmsg = u"%s:\n" % action
            for (n, a, evr, repoid, size, obsoletes, hi) in lines:
                columns = ((n, -n_wid, hi), (a, -a_wid),
                           (evr, -v_wid), (repoid, -r_wid), (size, s_wid))
                msg = self.fmtColumns(columns, u" ", u"\n")
                hibeg, hiend = self._highlight(self.conf.color_update_installed)
                for obspo in sorted(obsoletes):
                    appended = '     ' + _('replacing') + '  %s%s%s.%s %s\n'
                    appended %= (hibeg, obspo.name, hiend, obspo.arch, obspo.evr)
                    msg += appended
                totalmsg = totalmsg + msg

            if lines:
                out.append(totalmsg)

        out.append(_("""
Transaction Summary
%s
""") % ('=' * self.term.columns))
        summary_data = (
            (_('Install'), len(list_bunch.installed) +
             len(list_bunch.installed_group) +
             len(list_bunch.installed_weak) +
             len(list_bunch.installed_dep), 0),
            (_('Upgrade'), len(list_bunch.upgraded), 0),
            (_('Remove'), len(list_bunch.erased) + len(list_bunch.erased_dep) +
             len(list_bunch.erased_clean), 0),
            (_('Downgrade'), len(list_bunch.downgraded), 0),
            (_('Skip'), len(skipped_conflicts) + len(skipped_broken), 0))
        max_msg_action = 0
        max_msg_count = 0
        max_msg_pkgs = 0
        max_msg_depcount = 0
        for action, count, depcount in summary_data:
            if not count and not depcount:
                continue

            msg_pkgs = P_('Package', 'Packages', count)
            len_msg_action = exact_width(action)
            len_msg_count = exact_width(unicode(count))
            len_msg_pkgs = exact_width(msg_pkgs)

            if depcount:
                len_msg_depcount = exact_width(unicode(depcount))
            else:
                len_msg_depcount = 0

            max_msg_action = max(len_msg_action, max_msg_action)
            max_msg_count = max(len_msg_count, max_msg_count)
            max_msg_pkgs = max(len_msg_pkgs, max_msg_pkgs)
            max_msg_depcount = max(len_msg_depcount, max_msg_depcount)

        for action, count, depcount in summary_data:
            msg_pkgs = P_('Package', 'Packages', count)
            if depcount:
                msg_deppkgs = P_('Dependent package', 'Dependent packages',
                                 depcount)
                action_msg = fill_exact_width(action, max_msg_action)
                if count:
                    msg = '%s  %*d %s (+%*d %s)\n'
                    out.append(msg % (action_msg,
                                      max_msg_count, count,
                                      "%-*s" % (max_msg_pkgs, msg_pkgs),
                                      max_msg_depcount, depcount, msg_deppkgs))
                else:
                    msg = '%s  %s  ( %*d %s)\n'
                    out.append(msg % (action_msg,
                                      (max_msg_count + max_msg_pkgs) * ' ',
                                      max_msg_depcount, depcount, msg_deppkgs))
            elif count:
                msg = '%s  %*d %s\n'
                out.append(msg % (fill_exact_width(action, max_msg_action),
                                  max_msg_count, count, msg_pkgs))
        return ''.join(out)

    def post_transaction_output(self, transaction):
        """Returns a human-readable summary of the results of the
        transaction.

        :return: a string containing a human-readable summary of the
           results of the transaction
        """
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
                col_lens[col] += left // num
                col_lens[col] *= -1
            return col_lens

        out = ''
        list_bunch = _make_lists(transaction, self.base._goal)
        skipped_conflicts, skipped_broken = self._skipped_packages(report_problems=False)
        skipped = skipped_conflicts.union(skipped_broken)
        skipped = sorted(set([str(pkg) for pkg in skipped]))

        for (action, tsis) in [(_('Upgraded'), list_bunch.upgraded),
                               (_('Downgraded'), list_bunch.downgraded),
                               (_('Installed'), list_bunch.installed +
                                list_bunch.installed_group +
                                list_bunch.installed_weak +
                                list_bunch.installed_dep),
                               (_('Reinstalled'), list_bunch.reinstalled),
                               (_('Skipped'), skipped),
                               (_('Removed'), list_bunch.erased +
                                   list_bunch.erased_dep +
                                   list_bunch.erased_clean),
                               (_('Failed'), list_bunch.failed)]:
            if not tsis:
                continue
            msgs = []
            out += '\n%s:\n' % action
            for tsi in tsis:
                msgs.append(str(tsi))
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

    def setup_progress_callbacks(self):
        """Set up the progress callbacks and various
           output bars based on debug level.
        """
        progressbar = None
        if self.conf.debuglevel >= 2:
            progressbar = dnf.cli.progress.MultiFileProgressMeter(fo=sys.stdout)
            self.progress = dnf.cli.progress.MultiFileProgressMeter(fo=sys.stdout)

        # setup our depsolve progress callback
        return (progressbar, DepSolveProgressCallBack())

    def download_callback_total_cb(self, remote_size, download_start_timestamp):
        """Outputs summary information about the download process.

        :param remote_size: the total amount of information that was
           downloaded, in bytes
        :param download_start_timestamp: the time when the download
           process started, in seconds since the epoch
        """
        if remote_size <= 0:
            return

        width = self.term.columns
        logger.info("-" * width)
        dl_time = max(0.01, time.time() - download_start_timestamp)
        msg = ' %5sB/s | %5sB %9s     ' % (
            format_number(remote_size // dl_time),
            format_number(remote_size),
            format_time(dl_time))
        msg = fill_exact_width(_("Total"), width - len(msg)) + msg
        logger.info(msg)

    def _history_uiactions(self, hpkgs):
        actions = set()
        actions_short = set()
        count = 0
        for pkg in hpkgs:
            if pkg.action in (libdnf.transaction.TransactionItemAction_UPGRADED, libdnf.transaction.TransactionItemAction_DOWNGRADED):
                # skip states we don't want to display in user input
                continue
            actions.add(pkg.action_name)
            actions_short.add(pkg.action_short)
            count += 1

        if len(actions) > 1:
            return count, ", ".join(sorted(actions_short))

        # So empty transactions work, although that "shouldn't" really happen
        return count, "".join(list(actions))

    def _pwd_ui_username(self, uid, limit=None):
        if isinstance(uid, list):
            return [self._pwd_ui_username(u, limit) for u in uid]

        # loginuid is set to      -1 (0xFFFF_FFFF) on init, in newer kernels.
        # loginuid is set to INT_MAX (0x7FFF_FFFF) on init, in older kernels.
        if uid is None or uid in (0xFFFFFFFF, 0x7FFFFFFF):
            loginid = _("<unset>")
            name = _("System") + " " + loginid
            if limit is not None and len(name) > limit:
                name = loginid
            return ucd(name)

        def _safe_split_0(text, *args):
            """ Split gives us a [0] for everything _but_ '', this function
                returns '' in that case. """
            ret = text.split(*args)
            if not ret:
                return ''
            return ret[0]

        try:
            user = pwd.getpwuid(int(uid))
            fullname = _safe_split_0(ucd(user.pw_gecos), ';', 2)
            user_name = ucd(user.pw_name)
            name = "%s <%s>" % (fullname, user_name)
            if limit is not None and len(name) > limit:
                name = "%s ... <%s>" % (_safe_split_0(fullname), user_name)
                if len(name) > limit:
                    name = "<%s>" % user_name
            return name
        except KeyError:
            return ucd(uid)

    @staticmethod
    def _historyRangeRTIDs(old, tid):
        ''' Convert a user "TID" string of 2..4 into: (2, 4). '''
        def str2int(x):
            try:
                if x == '--last' or x.startswith('--last-'):
                    tid = old.tid
                    if x.startswith('--last-'):
                        off = int(x[len('--last-'):])
                        if off <= 0:
                            int("z")
                        tid -= off
                    return tid
                return int(x)
            except ValueError:
                return None

        if '..' not in tid:
            return None
        btid, etid = tid.split('..', 2)
        btid = str2int(btid)
        if btid > old.tid:
            return None
        elif btid <= 0:
            return None
        etid = str2int(etid)
        if etid > old.tid:
            return None

        if btid is None or etid is None:
            return None

        # Have a range ... do a "merged" transaction.
        if btid > etid:
            btid, etid = etid, btid
        return (btid, etid)

    def _historyRangeTIDs(self, rtids):
        ''' Convert a list of ranged tid typles into all the tids needed, Eg.
            [(2,4), (6,8)] == [2, 3, 4, 6, 7, 8]. '''
        tids = set()
        last_end = -1 # This just makes displaying it easier...
        for mtid in sorted(rtids):
            if mtid[0] < last_end:
                msg = _('Skipping merged transaction %d to %d, as it overlaps')
                logger.warning(msg, mtid[0], mtid[1])
                continue # Don't do overlapping
            last_end = mtid[1]
            for num in range(mtid[0], mtid[1] + 1):
                tids.add(num)
        return tids

    def _history_list_transactions(self, extcmds):
        old = self.history.last()
        if old is None:
            logger.critical(_('No transactions'))
            return None

        tids = set()
        pats = []
        usertids = extcmds
        for tid in usertids:
            try:
                int(tid)
                tids.add(tid)
            except ValueError:
                rtid = self._historyRangeRTIDs(old, tid)
                if rtid:
                    tids.update(self._historyRangeTIDs([rtid]))
                    continue
                pats.append(tid)
        if pats:
            tids.update(self.history.search(pats))

        if not tids and usertids:
            logger.critical(_('Bad transaction IDs, or package(s), given'))
            return None
        return tids

    def historyListCmd(self, extcmds):
        """Output a list of information about the history of yum
        transactions.

        :param extcmds: list of extra command line arguments
        :return: (exit_code, [errors])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
        """
        tids = self._history_list_transactions(extcmds)
        if tids is not None:
            old_tids = self.history.old(tids)
            if self.conf.history_list_view == 'users':
                uids = [1, 2]
            elif self.conf.history_list_view == 'commands':
                uids = [1]
            else:
                assert self.conf.history_list_view == 'single-user-commands'
                uids = set()
                done = 0
                blanks = 0
                for old in old_tids:
                    done += 1
                    if old.cmdline is None:
                        blanks += 1
                    uids.add(old.loginuid)

            fmt = "%s | %s | %s | %s | %s"
            if len(uids) == 1:
                name = _("Command line")
            else:
                # TRANSLATORS: user names who executed transaction in history command output
                name = _("User name")
            print(fmt % (fill_exact_width(_("ID"), 6, 6),
                        fill_exact_width(name, 24, 24),
                        fill_exact_width(_("Date and time"), 16, 16),
                        fill_exact_width(_("Action(s)"), 14, 14),
                        fill_exact_width(_("Altered"), 7, 7)))
            print("-" * 79)
            fmt = "%6u | %s | %-16.16s | %s | %4u"

            for old in old_tids:
                if len(uids) == 1:
                    name = old.cmdline or ''
                else:
                    name = self._pwd_ui_username(old.loginuid, 24)
                name = ucd(name)
                tm = time.strftime("%Y-%m-%d %H:%M",
                                   time.localtime(old.beg_timestamp))
                num, uiacts = self._history_uiactions(old.data())
                name = fill_exact_width(name, 24, 24)
                uiacts = fill_exact_width(uiacts, 14, 14)
                rmark = lmark = ' '
                if old.return_code is None:
                    rmark = lmark = '*'
                elif old.return_code:
                    rmark = lmark = '#'
                    # We don't check .errors, because return_code will be non-0
                elif old.is_output:
                    rmark = lmark = 'E'
                if old.altered_lt_rpmdb:
                    rmark = '<'
                if old.altered_gt_rpmdb:
                    lmark = '>'
                print(fmt % (old.tid, name, tm, uiacts, num), "%s%s" % (lmark, rmark))

    def historyInfoCmd(self, extcmds, pats=[], mtids=set()):
        """Output information about a transaction in history

        :param extcmds: list of extra command line arguments
        :return: (exit_code, [errors])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
        """
        tids = set(extcmds)
        old = self.history.last()
        if old is None:
            logger.critical(_('No transactions'))
            return 1, [_('Failed history info')]

        lasttid = old.tid
        lastdbv = old.end_rpmdb_version

        transactions = []
        if not tids and len(extcmds) < 2:
            old = self.history.last(complete_transactions_only=False)
            if old is not None:
                tids.add(old.tid)
                transactions.append(old)
        else:
            transactions = self.history.old(tids)

        if not tids:
            logger.critical(_('No transaction ID, or package, given'))
            return 1, [_('Failed history info')]

        bmtid, emtid = -1, -1
        mobj = None
        done = False

        if mtids:
            mtids = sorted(mtids)
            bmtid, emtid = mtids.pop()

        for trans in transactions:
            if lastdbv is not None and trans.tid == lasttid:
                #  If this is the last transaction, is good and it doesn't
                # match the current rpmdb ... then mark it as bad.
                rpmdbv = self.sack._rpmdb_version()
                trans.compare_rpmdbv(str(rpmdbv))
            lastdbv = None

            merged = False

            if trans.tid >= bmtid and trans.tid <= emtid:
                if mobj is None:
                    mobj = MergedTransactionWrapper(trans)
                else:
                    mobj.merge(trans)
                merged = True
            elif mobj is not None:
                if done:
                    print("-" * 79)
                done = True

                self._historyInfoCmd(mobj)
                mobj = None

                if mtids:
                    bmtid, emtid = mtids.pop()
                    if trans.tid >= bmtid and trans.tid <= emtid:
                        mobj = trans
                        merged = True

            if not merged:
                if done:
                    print("-" * 79)
                done = True
                self._historyInfoCmd(trans, pats)

        if mobj is not None:
            if done:
                print("-" * 79)
            self._historyInfoCmd(mobj)

    def _historyInfoCmd(self, old, pats=[]):
        loginuid = old.loginuid
        if isinstance(loginuid, int):
            loginuid = [loginuid]
        name = [self._pwd_ui_username(uid) for uid in loginuid]

        _pkg_states_installed = {'i' : _('Installed'), 'e' : _('Erased'),
                                 'o' : _('Upgraded'), 'n' : _('Downgraded')}
        _pkg_states_available = {'i' : _('Installed'), 'e' : _('Not installed'),
                                 'o' : _('Older'), 'n' : _('Newer')}
        maxlen = max([len(x) for x in (list(_pkg_states_installed.values()) +
                                       list(_pkg_states_available.values()))])
        _pkg_states_installed['maxlen'] = maxlen
        _pkg_states_available['maxlen'] = maxlen
        def _simple_pkg(pkg, prefix_len, was_installed=False, highlight=False,
                        pkg_max_len=0, show_repo=True):
            prefix = " " * prefix_len
            if was_installed:
                _pkg_states = _pkg_states_installed
            else:
                _pkg_states = _pkg_states_available
            state = _pkg_states['i']

            # get installed packages with name = pkg.name
            ipkgs = self.sack.query().installed().filterm(name=pkg.name).run()

            if not ipkgs:
                state = _pkg_states['e']
            else:
                # get latest installed package from software database
                inst_pkg = self.history.package(ipkgs[0])
                if inst_pkg:
                    res = pkg.compare(inst_pkg)
                    # res is:
                    # 0 if inst_pkg == pkg
                    # > 0 when inst_pkg > pkg
                    # < 0 when inst_pkg < pkg
                    if res == 0:
                        pass  # installed
                    elif res > 0:
                        state = _pkg_states['o']  # updated
                    else:
                        state = _pkg_states['n']  # downgraded

            if highlight:
                (hibeg, hiend) = self._highlight('bold')
            else:
                (hibeg, hiend) = self._highlight('normal')
            state = fill_exact_width(state, _pkg_states['maxlen'])
            ui_repo = ''
            if show_repo:
                ui_repo = pkg.ui_from_repo()
            print("%s%s%s%s %-*s %s" % (prefix, hibeg, state, hiend,
                                        pkg_max_len, str(pkg), ui_repo))

        tids = old.tids()
        if len(tids) > 1:
            print(_("Transaction ID :"), "%u..%u" % (tids[0], tids[-1]))
        else:
            print(_("Transaction ID :"), tids[0])
        begt = float(old.beg_timestamp)
        begtm = time.strftime("%c", time.localtime(begt))
        print(_("Begin time     :"), begtm)
        if old.beg_rpmdb_version is not None:
            if old.altered_lt_rpmdb:
                print(_("Begin rpmdb    :"), old.beg_rpmdb_version, "**")
            else:
                print(_("Begin rpmdb    :"), old.beg_rpmdb_version)
        if old.end_timestamp is not None:
            endt = old.end_timestamp
            endtm = time.strftime("%c", time.localtime(endt))
            diff = endt - begt
            if diff < 5 * 60:
                diff = _("(%u seconds)") % diff
            elif diff < 5 * 60 * 60:
                diff = _("(%u minutes)") % (diff // 60)
            elif diff < 5 * 60 * 60 * 24:
                diff = _("(%u hours)") % (diff // (60 * 60))
            else:
                diff = _("(%u days)") % (diff // (60 * 60 * 24))
            print(_("End time       :"), endtm, diff)
        if old.end_rpmdb_version is not None:
            if old.altered_gt_rpmdb:
                print(_("End rpmdb      :"), old.end_rpmdb_version, "**")
            else:
                print(_("End rpmdb      :"), old.end_rpmdb_version)
        if isinstance(name, (list, tuple)):
            seen = set()
            for i in name:
                if i in seen:
                    continue
                seen.add(i)
                print(_("User           :"), i)
        else:
            print(_("User           :"), name)
        if isinstance(old.return_code, (list, tuple)):
            codes = old.return_code
            if codes[0] is None:
                print(_("Return-Code    :"), "**", _("Aborted"), "**")
                codes = codes[1:]
            elif not all(codes):
                print(_("Return-Code    :"), _("Success"))
            elif codes:
                print(_("Return-Code    :"), _("Failures:"), ", ".join([str(i) for i in codes]))
        elif old.return_code is None:
            print(_("Return-Code    :"), "**", _("Aborted"), "**")
        elif old.return_code:
            print(_("Return-Code    :"), _("Failure:"), old.return_code)
        else:
            print(_("Return-Code    :"), _("Success"))

        if isinstance(old.releasever, (list, tuple)):
            seen = set()
            for i in old.releasever:
                if i in seen:
                    continue
                seen.add(i)
            print(_("Releasever     :"), i)
        else:
            print(_("Releasever     :"), old.releasever)

        if old.cmdline is not None:
            if isinstance(old.cmdline, (list, tuple)):
                for cmdline in old.cmdline:
                    print(_("Command Line   :"), cmdline)
            else:
                print(_("Command Line   :"), old.cmdline)

        # TODO:
        # comment = self.history.addon_data.read(old.tid, item='transaction-comment')
        comment = ""
        if comment:
            print(_("Comment        :"), comment)

        perf_with = old.performed_with()
        if perf_with:
            print(_("Transaction performed with:"))
        max_len = 0
        for with_pkg in perf_with:
            str_len = len(str(with_pkg))
            if str_len > max_len:
                max_len = str_len
        for with_pkg in perf_with:
            _simple_pkg(with_pkg, 4, was_installed=True, pkg_max_len=max_len)

        print(_("Packages Altered:"))

        self.historyInfoCmdPkgsAltered(old, pats)

        t_out = old.output()
        if t_out:
            print(_("Scriptlet output:"))
            num = 0
            for line in t_out:
                num += 1
                print("%4d" % num, line)
        t_err = old.error()
        if t_err:
            print(_("Errors:"))
            num = 0
            for line in t_err:
                num += 1
                print("%4d" % num, line)

    # TODO: remove
    _history_state2uistate = {'True-Install' : _('Install'),
                              'Install'      : _('Install'),
                              'Dep-Install'  : _('Dep-Install'),
                              'Obsoleted'    : _('Obsoleted'),
                              'Obsoleting'   : _('Obsoleting'),
                              'Erase'        : _('Erase'),
                              'Reinstall'    : _('Reinstall'),
                              'Downgrade'    : _('Downgrade'),
                              'Downgraded'   : _('Downgraded'),
                              'Update'       : _('Upgrade'),
                              'Updated'      : _('Upgraded'),
                              }
    def historyInfoCmdPkgsAltered(self, old, pats=[]):
        """Print information about how packages are altered in a transaction.

        :param old: the :class:`DnfSwdbTrans` to
           print information about
        :param pats: a list of patterns.  Packages that match a patten
           in *pats* will be highlighted in the output
        """
        last = None
        #  Note that these don't use _simple_pkg() because we are showing what
        # happened to them in the transaction ... not the difference between the
        # version in the transaction and now.
        all_uistates = self._history_state2uistate
        maxlen = 0
        pkg_max_len = 0

        packages = old.packages()

        for pkg in packages:
            uistate = all_uistates.get(pkg.action_name, pkg.action_name)
            if maxlen < len(uistate):
                maxlen = len(uistate)
            pkg_len = len(str(pkg))
            if pkg_max_len < pkg_len:
                pkg_max_len = pkg_len

        for pkg in packages:
            prefix = " " * 4
            if pkg.state != libdnf.transaction.TransactionItemState_DONE:
                prefix = " ** "

            highlight = 'normal'
            if pats:
                if any([pkg.match(pat) for pat in pats]):
                    highlight = 'bold'
            (hibeg, hiend) = self._highlight(highlight)

            cn = str(pkg)

            uistate = all_uistates.get(pkg.action_name, pkg.action_name)
            uistate = fill_exact_width(ucd(uistate), maxlen)

            if (last is not None and last.action == libdnf.transaction.TransactionItemAction_UPGRADED and
                    last.name == pkg.name and pkg.action == libdnf.transaction.TransactionItemAction_UPGRADE):

                ln = len(pkg.name) + 1
                cn = (" " * ln) + cn[ln:]
            elif (last is not None and last.action == libdnf.transaction.TransactionItemAction_DOWNGRADE and
                  last.name == pkg.name and pkg.action == libdnf.transaction.TransactionItemAction_DOWNGRADED):

                ln = len(pkg.name) + 1
                cn = (" " * ln) + cn[ln:]
            else:
                last = None
                if pkg.action in (libdnf.transaction.TransactionItemAction_UPGRADED, libdnf.transaction.TransactionItemAction_DOWNGRADE):
                    last = pkg
            print("%s%s%s%s %-*s %s" % (prefix, hibeg, uistate, hiend,
                                        pkg_max_len, str(pkg),
                                        pkg.ui_from_repo()))

    def historyPackageListCmd(self, extcmds):
        """Print a list of information about transactions from history
        that involve the given package or packages.

        :param extcmds: list of extra command line arguments
        """
        tids = self.history.search(extcmds)
        limit = None
        if extcmds and not tids:
            logger.critical(_('Bad transaction IDs, or package(s), given'))
            return 1, ['Failed history packages-list']
        if not tids:
            limit = 20

        all_uistates = self._history_state2uistate

        fmt = "%s | %s | %s"
        # REALLY Needs to use columns!
        print(fmt % (fill_exact_width(_("ID"), 6, 6),
                     fill_exact_width(_("Action(s)"), 14, 14),
        # This is also a hack to resolve RhBug 1302935 correctly.
                     fill_exact_width(C_("long", "Package"), 53, 53)))
        print("-" * 79)
        fmt = "%6u | %s | %-50s"
        num = 0
        for old in self.history.old(tids, limit=limit):
            packages = old.packages()
            if limit and num and (num + len(packages)) > limit:
                break
            last = None

            # Copy and paste from list ... uh.
            rmark = lmark = ' '
            if old.return_code is None:
                rmark = lmark = '*'
            elif old.return_code:
                rmark = lmark = '#'
                # We don't check .errors, because return_code will be non-0
            elif old.output:
                rmark = lmark = 'E'
            elif old.rpmdb_problems:
                rmark = lmark = 'P'
            elif old.trans_skip:
                rmark = lmark = 's'
            if old.altered_lt_rpmdb:
                rmark = '<'
            if old.altered_gt_rpmdb:
                lmark = '>'

            # Find a pkg to go with each cmd...
            for pkg in packages:
                if limit is None:
                    if not any([pkg.match(pat) for pat in extcmds]):
                        continue

                uistate = all_uistates.get(pkg.action_name, pkg.action_name)
                uistate = fill_exact_width(uistate, 14)

                #  To chop the name off we need nevra strings, str(pkg) gives
                # envra so we have to do it by hand ... *sigh*.
                cn = pkg.ui_nevra

                if (last is not None and last.action == libdnf.transaction.TransactionItemAction_UPGRADED and
                        last.name == pkg.name and pkg.action == libdnf.transaction.TransactionItemAction_UPGRADE):
                    ln = len(pkg.name) + 1
                    cn = (" " * ln) + cn[ln:]
                elif (last is not None and
                      last.action == libdnf.transaction.TransactionItemAction_DOWNGRADE and last.name == pkg.name and
                      pkg.action == libdnf.transaction.TransactionItemAction_DOWNGRADED):
                    ln = len(pkg.name) + 1
                    cn = (" " * ln) + cn[ln:]
                else:
                    last = None
                    if pkg.action in (libdnf.transaction.TransactionItemAction_UPGRADED, libdnf.transaction.TransactionItemAction_DOWNGRADE):
                        last = pkg

                num += 1
                print(fmt % (old.tid, uistate, cn), "%s%s" % (lmark, rmark))

class DepSolveProgressCallBack(dnf.callback.Depsolve):
    """Provides text output callback functions for Dependency Solver callback."""

    def __init__(self):
        """requires yum-cli log and errorlog functions as arguments"""
        self.loops = 0

    def pkg_added(self, pkg, mode):
        """Print information about a package being added to the
        transaction set.

        :param pkgtup: tuple containing the package name, arch,
           version, and repository
        :param mode: a short string indicating why the package is
           being added to the transaction set.

        Valid current values for *mode* are::

           i = the package will be installed
           u = the package will be an update
           e = the package will be erased
           r = the package will be reinstalled
           d = the package will be a downgrade
           o = the package will be obsoleting another package
           ud = the package will be updated
           od = the package will be obsoleted
        """
        output = None
        if mode == 'i':
            output = _('---> Package %s.%s %s will be installed')
        elif mode == 'u':
            output = _('---> Package %s.%s %s will be an upgrade')
        elif mode == 'e':
            output = _('---> Package %s.%s %s will be erased')
        elif mode == 'r':
            output = _('---> Package %s.%s %s will be reinstalled')
        elif mode == 'd':
            output = _('---> Package %s.%s %s will be a downgrade')
        elif mode == 'o':
            output = _('---> Package %s.%s %s will be obsoleting')
        elif mode == 'ud':
            output = _('---> Package %s.%s %s will be upgraded')
        elif mode == 'od':
            output = _('---> Package %s.%s %s will be obsoleted')

        if output:
            logger.debug(output, pkg.name, pkg.arch, pkg.evr)

    def start(self):
        """Perform setup at the beginning of the dependency solving
        process.
        """
        logger.debug(_('--> Starting dependency resolution'))
        self.loops += 1

    def end(self):
        """Output a message stating that dependency resolution has finished."""
        logger.debug(_('--> Finished dependency resolution'))


class CliKeyImport(dnf.callback.KeyImport):
    def __init__(self, base, output):
        self.base = base
        self.output = output

    def _confirm(self, id, userid, fingerprint, url, timestamp):

        def short_id(id):
            rj = '0' if dnf.pycomp.PY3 else b'0'
            return id[-8:].rjust(8, rj)

        msg = (_('Importing GPG key 0x%s:\n'
                 ' Userid     : "%s"\n'
                 ' Fingerprint: %s\n'
                 ' From       : %s') %
               (short_id(id), userid,
                dnf.crypto._printable_fingerprint(fingerprint),
                url.replace("file://", "")))
        logger.critical("%s", msg)

        if self.base.conf.assumeyes:
            return True
        if self.base.conf.assumeno:
            return False
        return self.output.userconfirm()


class CliTransactionDisplay(LoggingTransactionDisplay):
    """A YUM specific callback class for RPM operations."""

    width = property(lambda self: dnf.cli.term._term_width())

    def __init__(self):
        super(CliTransactionDisplay, self).__init__()
        self.lastmsg = ""
        self.lastpackage = None # name of last package we looked at
        self.output = True

        # for a progress bar
        self.mark = "="
        self.marks = 22

    def progress(self, package, action, ti_done, ti_total, ts_done, ts_total):
        """Output information about an rpm operation.  This may
        include a text progress bar.

        :param package: the package involved in the event
        :param action: the type of action that is taking place.  Valid
           values are given by
           :func:`rpmtrans.LoggingTransactionDisplay.action.keys()`
        :param ti_done: a number representing the amount of work
           already done in the current transaction
        :param ti_total: a number representing the total amount of work
           to be done in the current transaction
        :param ts_done: the number of the current transaction in
           transaction set
        :param ts_total: the total number of transactions in the
           transaction set
        """
        action_str = dnf.transaction.ACTIONS.get(action)
        if action_str is None:
            return

        wid1 = self._max_action_width()

        pkgname = ucd(package)
        self.lastpackage = package
        if ti_total == 0:
            percent = 0
        else:
            percent = (ti_done*long(100))//ti_total
        self._out_progress(ti_done, ti_total, ts_done, ts_total,
                           percent, action_str, pkgname, wid1)

    def _max_action_width(self):
        if not hasattr(self, '_max_action_wid_cache'):
            wid1 = 0
            for val in dnf.transaction.ACTIONS.values():
                wid_val = exact_width(val)
                if wid1 < wid_val:
                    wid1 = wid_val
            self._max_action_wid_cache = wid1
        wid1 = self._max_action_wid_cache
        return wid1

    def _out_progress(self, ti_done, ti_total, ts_done, ts_total,
                      percent, process, pkgname, wid1):
        if self.output and (sys.stdout.isatty() or ti_done == ti_total):
            (fmt, wid1, wid2) = self._makefmt(percent, ts_done, ts_total,
                                              progress=sys.stdout.isatty(),
                                              pkgname=pkgname, wid1=wid1)
            pkgname = ucd(pkgname)
            msg = fmt % (fill_exact_width(process, wid1, wid1),
                         fill_exact_width(pkgname, wid2, wid2))
            if msg != self.lastmsg:
                dnf.util._terminal_messenger('write_flush', msg, sys.stdout)
                self.lastmsg = msg
                if ti_done == ti_total:
                    print(" ")

    def filelog(self, package, action):
        pass

    def error(self, message):
        pass

    def scriptout(self, msgs):
        """Print messages originating from a package script.

        :param msgs: the messages coming from the script
        """
        if msgs:
            self.rpm_logger.info(ucd(msgs))

    def _makefmt(self, percent, ts_done, ts_total, progress=True,
                 pkgname=None, wid1=15):
        l = len(str(ts_total))
        size = "%s.%s" % (l, l)
        fmt_done = "%" + size + "s/%" + size + "s"
        done = fmt_done % (ts_done, ts_total)

        #  This should probably use TerminLine, but we don't want to dep. on
        # that. So we kind do an ok job by hand ... at least it's dynamic now.
        if pkgname is None:
            pnl = 22
        else:
            pnl = exact_width(pkgname)

        overhead = (2 * l) + 2 # Length of done, above
        overhead += 2 + wid1 +2 # Length of beginning ("  " action " :")
        overhead += 1          # Space between pn and done
        overhead += 2          # Ends for progress
        overhead += 1          # Space for end
        width = self.width
        if width < overhead:
            width = overhead    # Give up
        width -= overhead
        if pnl > width // 2:
            pnl = width // 2

        marks = self.width - (overhead + pnl)
        width = "%s.%s" % (marks, marks)
        fmt_bar = "[%-" + width + "s]"
        # pnl = str(28 + marks + 1)
        full_pnl = pnl + marks + 1

        if progress and percent == 100: # Don't chop pkg name on 100%
            fmt = "\r  %s: %s   " + done
            wid2 = full_pnl
        elif progress:
            if marks > 5:
                bar = fmt_bar % (self.mark * int(marks * (percent / 100.0)), )
            else:
                bar = ""
            fmt = "\r  %s: %s " + bar + " " + done
            wid2 = pnl
        elif percent == 100:
            fmt = "  %s: %s   " + done
            wid2 = full_pnl
        else:
            if marks > 5:
                bar = fmt_bar % (self.mark * marks, )
            else:
                bar = ""
            fmt = "  %s: %s " + bar + " " + done
            wid2 = pnl
        return fmt, wid1, wid2

def progressbar(current, total, name=None):
    """Output the current status to the terminal using a simple
    text progress bar consisting of 50 # marks.

    :param current: a number representing the amount of work
       already done
    :param total: a number representing the total amount of work
       to be done
    :param name: a name to label the progress bar with
    """

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

    width = dnf.cli.term._term_width()

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
        output = '\r%s%s' % (fill_exact_width(name, width, width), end)
    else:
        width -= 4
        if width < 0:
            width = 0
        nwid = width // 2
        if nwid > exact_width(name):
            nwid = exact_width(name)
        width -= nwid
        hashbar = mark * int(width * percent)
        output = '\r%s: [%-*s]%s' % (fill_exact_width(name, nwid, nwid), width,
                                     hashbar, end)

    if current <= total:
        dnf.util._terminal_messenger('write', output, sys.stdout)

    if current == total:
        dnf.util._terminal_messenger('write', '\n', sys.stdout)

    dnf.util._terminal_messenger('flush', out=sys.stdout)
