# conf.py
# dnf configuration classes.
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


"""
The configuration classes and routines in yum are splattered over too many
places, hard to change and debug. The new structure here will replace that. Its
goal is to:

* accept configuration options from all three sources (the main config file,
  repo config files, command line switches)
* handle all the logic of storing those and producing related values.
* returning configuration values.
* optionally: asserting no value is overridden once it has been applied
  somewhere (e.g. do not let a new repo be initialized with different global
  cache path than an already existing one).

"""

from __future__ import absolute_import
from __future__ import unicode_literals
from dnf import util
from dnf.i18n import ucd, _
from dnf.yum import misc
import dnf.const
import dnf.yum.config
import logging


Conf = dnf.yum.config.YumConf # :api
logger = logging.getLogger('dnf')


class CliCache(object):
    def __init__(self, prefix):
        # set from the client, at most once:
        self.prefix = prefix
        # internal:
        self._ready = False
        self._cachedir = None
        self._system_cachedir = None

    def _make_ready(self):
        if self._ready:
            return

        self._ready = True
        self._system_cachedir = self.prefix
        if util.am_i_root():
            self._cachedir = self._system_cachedir
        else:
            try:
                user_prefix = misc.getCacheDir()
                self._cachedir = user_prefix
            except (IOError, OSError) as e:
                logger.critical(_('Could not set cachedir: %s'), ucd(e))

    @property
    def cachedir(self):
        self._make_ready()
        return self._cachedir

    @property
    def system_cachedir(self):
        self._make_ready()
        return self._system_cachedir
