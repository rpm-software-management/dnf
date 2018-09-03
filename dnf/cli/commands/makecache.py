# makecache.py
# Makecache CLI command.
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
from dnf.i18n import _

import argparse
import dnf.cli
import dnf.exceptions
import dnf.util
import logging

logger = logging.getLogger("dnf")


class MakeCacheCommand(commands.Command):
    aliases = ('makecache',)
    summary = _('generate the metadata cache')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('--timer', action='store_true', dest="timer_opt")
        # compatibility with dnf < 2.0
        parser.add_argument('timer', nargs='?', choices=['timer'],
                            metavar='timer', help=argparse.SUPPRESS)

    def run(self):
        timer = self.opts.timer is not None or self.opts.timer_opt
        msg = _("Making cache files for all metadata files.")
        logger.debug(msg)
        return self.base.update_cache(timer)
