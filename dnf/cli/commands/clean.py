# clean.py
# Clean CLI command.
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
from dnf.i18n import _, P_
from dnf.yum import misc

import dnf.cli
import dnf.exceptions
import dnf.lock
import dnf.logging
import dnf.repo
import logging
import os
import re
import time

logger = logging.getLogger("dnf")

# Dict mapping cmdline arguments to actual data types to be cleaned up
_CACHE_TYPES = {
    'metadata': ['metadata', 'dbcache', 'expire-cache'],
    'packages': ['packages'],
    'dbcache': ['dbcache'],
    'expire-cache': ['expire-cache'],
    'all': ['metadata', 'packages', 'dbcache'],
}


def _tree(dirpath):
    """Traverse dirpath recursively and yield relative filenames."""
    for root, dirs, files in os.walk(dirpath):
        base = os.path.relpath(root, dirpath)
        for f in files:
            path = os.path.join(base, f)
            yield os.path.normpath(path)


def _filter(files, patterns):
    """Yield those filenames that match any of the patterns."""
    return (f for f in files for p in patterns if re.match(p, f))


def _clean(dirpath, files):
    """Remove the given filenames from dirpath."""
    count = 0
    for f in files:
        path = os.path.join(dirpath, f)
        logger.log(dnf.logging.DDEBUG, _('Removing file %s'), path)
        misc.unlink_f(path)
        count += 1
    return count


def _cached_repos(files):
    """Return the repo IDs that have some cached metadata around."""
    metapat = dnf.repo.CACHE_FILES['metadata']
    matches = (re.match(metapat, f) for f in files)
    return set(m.group('repoid') for m in matches if m)


class CleanCommand(commands.Command):
    """A class containing methods needed by the cli to execute the
    clean command.
    """

    aliases = ('clean',)
    summary = _('remove cached data')

    @staticmethod
    def set_argparser(parser):
        parser.add_argument('type', nargs='+',
                           choices=_CACHE_TYPES.keys(),
                           help=_('Metadata type to clean'))

    def run(self):
        cachedir = self.base.conf.cachedir
        md_lock = dnf.lock.build_metadata_lock(cachedir, True)
        download_lock = dnf.lock.build_download_lock(cachedir, True)
        rpmdb_lock = dnf.lock.build_rpmdb_lock(self.base.conf.persistdir, True)
        while True:
            try:
                with md_lock, download_lock, rpmdb_lock:
                    types = set(t for c in self.opts.type for t in _CACHE_TYPES[c])
                    files = list(_tree(cachedir))
                    logger.debug(_('Cleaning data: ' + ' '.join(types)))

                    if 'expire-cache' in types:
                        expired = _cached_repos(files)
                        self.base._repo_persistor.expired_to_add.update(expired)
                        types.remove('expire-cache')
                        logger.info(_('Cache was expired'))

                    patterns = [dnf.repo.CACHE_FILES[t] for t in types]
                    count = _clean(cachedir, _filter(files, patterns))
                    logger.info(P_('%d file removed', '%d files removed', count) % count)
                    return
            except dnf.exceptions.LockError as e:
                if not self.base.conf.exit_on_lock:
                    msg = _('Waiting for process with pid %d to finish.') % (e.pid)
                    logger.info(msg)
                    time.sleep(3)
                else:
                    raise e
