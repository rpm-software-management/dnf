# search.py
# Search CLI command.
#
# Copyright (C) 2012-2014  Red Hat, Inc.
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
from .. import commands
from dnf.i18n import ucd, _

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

    aliases = ('search',)
    summary = _('Search package details for the given string')
    usage = _('QUERY_STRING')

    def _search(self, args):
        """Search for simple text tags in a package object."""

        def _print_match_section(text, keys):
            # Print them in the order they were passed
            used_keys = [arg for arg in args if arg in keys]
            formatted = self.base.output.fmtSection(text % ", ".join(used_keys))
            print(ucd(formatted))

        # prepare the input
        search_all = False
        if len(args) > 1 and args[0] == 'all':
            args.pop(0)
            search_all = True

        counter = dnf.match_counter.MatchCounter()
        for arg in args:
            self._search_counted(counter, 'name', arg)
            self._search_counted(counter, 'summary', arg)

        section_text = _('N/S Matched: %s')
        if search_all or counter.total() == 0:
            section_text = _('Matched: %s')
            for arg in args:
                self._search_counted(counter, 'description', arg)
                self._search_counted(counter, 'url', arg)

        matched_needles = None
        limit = None
        if not self.base.conf.showdupesfromrepos:
            limit = self.base.sack.query().filter(pkg=counter.keys()).latest()
        for pkg in counter.sorted(reverse=True, limit_to=limit):
            if matched_needles != counter.matched_needles(pkg):
                matched_needles = counter.matched_needles(pkg)
                _print_match_section(section_text, matched_needles)
            self.base.output.matchcallback(pkg, counter.matched_haystacks(pkg),
                                           args)

        if len(counter) == 0:
            raise dnf.exceptions.Error(_('No matches found.'))

    def _search_counted(self, counter, attr, needle):
        fdict = {'%s__substr' % attr : needle}
        if dnf.util.is_glob_pattern(needle):
            fdict = {'%s__glob' % attr : needle}
        q = self.base.sack.query().filter(hawkey.ICASE, **fdict)
        for pkg in q.run():
            counter.add(pkg, attr, needle)
        return counter

    def configure(self, _):
        demands = self.cli.demands
        demands.available_repos = True
        demands.fresh_metadata = False
        demands.sack_activation = True

    def doCheck(self, basecmd, extcmds):
        commands.checkItemArg(self.cli, basecmd, extcmds)

    def run(self, extcmds):
        logger.debug(_('Searching Packages: '))
        return self._search(extcmds)
