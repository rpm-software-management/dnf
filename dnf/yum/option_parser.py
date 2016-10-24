# Copyright (C) 2016  Red Hat, Inc.
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

from __future__ import unicode_literals

import logging

from dnf.cli.option_parser import OptionParser
from dnf.i18n import _

logger = logging.getLogger("dnf")


class YumOptionParser(OptionParser):
    def __init__(self):
        super(YumOptionParser, self).__init__()
        self._yum_parser()

    def _yum_parser(self):
        self.main_parser.add_argument(
            "--skip-broken", dest="skip_broken",
            action="store_true", default=None,
            help=_("resolve depsolve problems by skipping packages"))

    @staticmethod
    def transform_yum_arg(args):
        transformed = []
        for arg in args:
            provides = arg
            if arg.startswith("*") is False:
                provides = "*" + provides

            if arg.endswith("*") is False:
                provides += "*"

            transformed.append(provides)

        return transformed

    def parse_main_args(self, args):
        opts = super(YumOptionParser, self).parse_main_args(args)
        opts.best = None
        if opts.skip_broken is None:
            opts.best = True

        return opts

    def parse_command_args(self, command, args):
        opts = super(YumOptionParser, self).parse_command_args(command, args)
        if opts.command == ['provides']:
            opts.dependency = self.transform_yum_arg(opts.dependency)

        return opts
