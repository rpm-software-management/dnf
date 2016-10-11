#
# Copyright (C) 2016 Red Hat, Inc.
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
from __future__ import unicode_literals
from dnf.i18n import _
from dnf.cli import commands

import argparse
import dnf.exceptions


class CheckCommand(commands.Command):
    """A class containing methods needed by the cli to execute the check
    command.
    """

    aliases = ('check',)
    summary = _('check for problems in the packagedb')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('--all', dest='check_types',
                            action='append_const', const='all',
                            help=_('show all problems; default'))
        parser.add_argument('--dependencies', dest='check_types',
                            action='append_const', const='dependencies',
                            help=_('show dependency problems'))
        parser.add_argument('--duplicates', dest='check_types',
                            action='append_const', const='duplicates',
                            help=_('show duplicate problems'))
        parser.add_argument('--obsoleted', dest='check_types',
                            action='append_const', const='obsoleted',
                            help=_('show obsoleted packages'))
        parser.add_argument('--provides', dest='check_types',
                            action='append_const', const='provides',
                            help=_('show problems with provides'))
        # Add compatibility with yum but invisible in help
        parser.add_argument('check_yum_types', nargs='*',
                            help=argparse.SUPPRESS)

    def configure(self):
        self.cli.demands.sack_activation = True
        if self.opts.check_yum_types:
            if self.opts.check_types:
                self.opts.check_types = self.opts.check_types + \
                                        self.opts.check_yum_types
            else:
                self.opts.check_types = self.opts.check_yum_types
        if not self.opts.check_types:
            self.opts.check_types = {'all'}
        else:
            self.opts.check_types = set(self.opts.check_types)

    def run(self):
        output_set = set()
        q = self.base.sack.query().installed()

        if self.opts.check_types.intersection({'all', 'dependencies'}):
            for pkg in q:
                for require in pkg.requires:
                    if str(require).startswith('rpmlib'):
                        continue
                    if not len(q.filter(provides=[require])):
                        msg = _("{} has missing requires of {}")
                        output_set.add(msg.format(
                            self.base.output.term.bold(pkg),
                            self.base.output.term.bold(require)))
                for conflict in pkg.conflicts:
                    conflicted = q.filter(provides=[conflict],
                                          name=str(conflict).split()[0])
                    for conflict_pkg in conflicted:
                        msg = '{} has installed conflict "{}": {}'
                        output_set.add(msg.format(
                            self.base.output.term.bold(pkg),
                            self.base.output.term.bold(conflict),
                            self.base.output.term.bold(conflict_pkg)))

        if self.opts.check_types.intersection({'all', 'duplicates'}):
            installonly = self.base._get_installonly_query(q)
            dups = q.duplicated().difference(installonly)._name_dict()
            for name, pkgs in dups.items():
                pkgs.sort()
                for dup in pkgs[1:]:
                    msg = _("{} is a duplicate with {}").format(
                        self.base.output.term.bold(pkgs[0]),
                        self.base.output.term.bold(dup))
                    output_set.add(msg)

        if self.opts.check_types.intersection({'all', 'obsoleted'}):
            for pkg in q:
                for obsolete in pkg.obsoletes:
                    obsoleted = q.filter(provides=[obsolete],
                                         name=str(obsolete).split()[0])
                    if len(obsoleted):
                        msg = _("{} is obsoleted by {}").format(
                            self.base.output.term.bold(obsoleted[0]),
                            self.base.output.term.bold(pkg))
                        output_set.add(msg)

        if self.opts.check_types.intersection({'all', 'provides'}):
            for pkg in q:
                for provide in pkg.provides:
                    if pkg not in q.filter(provides=[provide]):
                        msg = _("{} provides {} but it cannot be found")
                        output_set.add(msg.format(
                            self.base.output.term.bold(pkg),
                            self.base.output.term.bold(provide)))

        for msg in sorted(output_set):
            print(msg)

        if output_set:
            raise dnf.exceptions.Error(
                'Check discovered {} problem(s)'.format(len(output_set)))
