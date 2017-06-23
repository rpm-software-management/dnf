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

from dnf.conf.config import BoolOption
from dnf.conf.config import ListOption
from dnf.conf.config import MainConf
from dnf.conf.config import PathOption
from dnf.conf.config import PositiveIntOption
from dnf.conf.config import SecondsOption
from dnf.conf.config import inherit


class YumConf(MainConf):
    def __init__(self):
        super(YumConf, self).__init__()

        self._add_option('keepcache', BoolOption(True))
        self._add_option('metadata_expire', SecondsOption(60 * 60 * 6))  # 6 hours
        self._add_option('best', BoolOption(True))
        self._add_option('clean_requirements_on_remove', BoolOption(False))

    def _adjust_conf_options(self):
        """Adjust conf options interactions"""

        MainConf._adjust_conf_options(self)
        skip_broken = self._get_option('skip_broken')
        skip_broken_val = skip_broken._get()
        if skip_broken_val:
            best = self._get_option('best')
            best._set(not skip_broken_val, skip_broken._get_priority())
