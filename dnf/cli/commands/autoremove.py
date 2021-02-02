# autoremove.py
# Autoremove CLI command.
#
# Copyright (C) 2014-2016 Red Hat, Inc.
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
from dnf.cli import commands
from dnf.cli.option_parser import OptionParser
from dnf.i18n import _

import dnf.exceptions
import hawkey
import logging

logger = logging.getLogger("dnf")


class AutoremoveCommand(commands.Command):

    nevra_forms = {'autoremove-n': hawkey.FORM_NAME,
                   'autoremove-na': hawkey.FORM_NA,
                   'autoremove-nevra': hawkey.FORM_NEVRA}

    aliases = ('autoremove',) + tuple(nevra_forms.keys())
    summary = _('remove all unneeded packages that were originally installed '
                'as dependencies')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('packages', nargs='*', help=_('Package to remove'),
                            action=OptionParser.ParseSpecGroupFileCallback,
                            metavar=_('PACKAGE'))

    def configure(self):
        demands = self.cli.demands
        demands.resolving = True
        demands.root_user = True
        demands.sack_activation = True

        if any([self.opts.grp_specs, self.opts.pkg_specs, self.opts.filenames]):
            self.base.conf.clean_requirements_on_remove = True
            demands.allow_erasing = True
            # disable all available repos to delete whole dependency tree
            # instead of replacing removable package with available packages
            demands.available_repos = False
        else:
            demands.available_repos = True
            demands.fresh_metadata = False

    def run(self):
        if any([self.opts.grp_specs, self.opts.pkg_specs, self.opts.filenames]):
            forms = []
            if self.opts.command in self.nevra_forms:
                forms = [self.nevra_forms[self.opts.command]]

            self.base.autoremove(forms,
                                 self.opts.pkg_specs,
                                 self.opts.grp_specs,
                                 self.opts.filenames)
        else:
            self.base.autoremove()
