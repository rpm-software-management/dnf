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
        parser.add_argument('--timer', action='store_true')
        # compatibility with dnf < 2.0
        parser.add_argument('timer', nargs='?', choices=['timer'],
                            metavar='timer', help=argparse.SUPPRESS)

    def configure(self):
        """Verify that conditions are met so that this command can
        run; namely that there is an enabled repository.
        """
        commands._checkEnabledRepo(self.base)

    def run(self):
        msg = _("Making cache files for all metadata files.")
        logger.debug(msg)
        period = self.base.conf.metadata_timer_sync
        timer = self.opts.timer is not None
        persistor = self.base._repo_persistor
        if timer:
            if dnf.util.on_ac_power() is False:
                msg = _('Metadata timer caching disabled '
                        'when running on a battery.')
                logger.info(msg)
                return False
            if period <= 0:
                msg = _('Metadata timer caching disabled.')
                logger.info(msg)
                return False
            since_last_makecache = persistor.since_last_makecache()
            if since_last_makecache is not None and since_last_makecache < period:
                logger.info(_('Metadata cache refreshed recently.'))
                return False
            self.base.repos.all()._max_mirror_tries = 1

        for r in self.base.repos.iter_enabled():
            (is_cache, expires_in) = r._metadata_expire_in()
            if expires_in is None:
                logger.info('%s: will never be expired'
                            ' and will not be refreshed.', r.id)
            elif not is_cache or expires_in <= 0:
                logger.debug('%s: has expired and will be refreshed.', r.id)
                r._md_expire_cache()
            elif timer and expires_in < period:
                # expires within the checking period:
                msg = "%s: metadata will expire after %d seconds " \
                    "and will be refreshed now"
                logger.debug(msg, r.id, expires_in)
                r._md_expire_cache()
            else:
                logger.debug('%s: will expire after %d seconds.', r.id,
                             expires_in)

        if timer:
            persistor.reset_last_makecache = True
        self.base.fill_sack() # performs the md sync
        logger.info(_('Metadata cache created.'))
        return True
