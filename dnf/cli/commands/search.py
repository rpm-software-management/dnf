# search.py
# Search CLI command.
#
# Copyright (C) 2012-2016 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.
#

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import collections

from dnf.cli import commands
from dnf.cli.option_parser import OptionParser
from dnf.i18n import ucd, _, C_

import dnf.i18n
import dnf.match_counter
import dnf.util
import hawkey
import logging

logger = logging.getLogger('dnf')


class SearchCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    search command.
    """

    aliases = ('search', 'se')
    summary = _('search package details for the given string')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('--all', action='store_true',
                            help=_("search also package description and URL"))
        parser.add_argument('query_string', nargs='+', metavar=_('KEYWORD'),
                            choices=['all'], default=None,
                            action=OptionParser.PkgNarrowCallback,
                            help=_("Keyword to search for"))

    def _search(self, args):
        """Search for simple text tags in a package object."""

        TRANS_TBL = collections.OrderedDict((
            ('name', C_('long', 'Name')),
            ('summary', C_('long', 'Summary')),
            ('description', C_('long', 'Description')),
            ('url', _('URL')),
        ))

        def _translate_attr(attr):
            try:
                return TRANS_TBL[attr]
            except:
                return attr

        def _print_section_header(exact_match, attrs, keys):
            trans_attrs = map(_translate_attr, attrs)
            # TRANSLATORS: separator used between package attributes (eg. Name & Summary & URL)
            trans_attrs_str = _(' & ').join(trans_attrs)
            if exact_match:
                # TRANSLATORS: %s  - translated package attributes,
                #              %%s - found keys (in listed attributes)
                section_text = _('%s Exactly Matched: %%s') % trans_attrs_str
            else:
                # TRANSLATORS: %s  - translated package attributes,
                #              %%s - found keys (in listed attributes)
                section_text = _('%s Matched: %%s') % trans_attrs_str
            formatted = self.base.output.fmtSection(section_text % ", ".join(keys))
            print(ucd(formatted))

        counter = dnf.match_counter.MatchCounter()
        for arg in args:
            self._search_counted(counter, 'name', arg)
            self._search_counted(counter, 'summary', arg)

        if self.opts.all:
            for arg in args:
                self._search_counted(counter, 'description', arg)
                self._search_counted(counter, 'url', arg)
        else:
            needles = len(args)
            pkgs = list(counter.keys())
            for pkg in pkgs:
                if len(counter.matched_needles(pkg)) != needles:
                    del counter[pkg]

        used_attrs = None
        matched_needles = None
        exact_match = False
        print_section_header = False
        limit = None
        if not self.base.conf.showdupesfromrepos:
            limit = self.base.sack.query().filterm(pkg=counter.keys()).latest()

        seen = set()
        for pkg in counter.sorted(reverse=True, limit_to=limit):
            if not self.base.conf.showdupesfromrepos:
                if pkg.name + pkg.arch in seen:
                    continue
                seen.add(pkg.name + pkg.arch)

            if used_attrs != counter.matched_keys(pkg):
                used_attrs = counter.matched_keys(pkg)
                print_section_header = True
            if matched_needles != counter.matched_needles(pkg):
                matched_needles = counter.matched_needles(pkg)
                print_section_header = True
            if exact_match != (counter.matched_haystacks(pkg) == matched_needles):
                exact_match = counter.matched_haystacks(pkg) == matched_needles
                print_section_header = True
            if print_section_header:
                _print_section_header(exact_match, used_attrs, matched_needles)
                print_section_header = False
            self.base.output.matchcallback(pkg, counter.matched_haystacks(pkg), args)

        if len(counter) == 0:
            logger.info(_('No matches found.'))

    def _search_counted(self, counter, attr, needle):
        fdict = {'%s__substr' % attr : needle}
        if dnf.util.is_glob_pattern(needle):
            fdict = {'%s__glob' % attr : needle}
        q = self.base.sack.query().filterm(hawkey.ICASE, **fdict)
        for pkg in q.run():
            counter.add(pkg, attr, needle)
        return counter

    def pre_configure(self):
        if not self.opts.quiet:
            self.cli.redirect_logger(stdout=logging.WARNING, stderr=logging.INFO)

    def configure(self):
        if not self.opts.quiet:
            self.cli.redirect_repo_progress()
        demands = self.cli.demands
        demands.available_repos = True
        demands.fresh_metadata = False
        demands.sack_activation = True
        self.opts.all = self.opts.all or self.opts.query_string_action

    def run(self):
        logger.debug(_('Searching Packages: '))
        return self._search(self.opts.query_string)
