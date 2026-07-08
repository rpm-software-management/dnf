# demand.py
# Demand sheet and related classes.
#
# Copyright (C) 2014-2015  Red Hat, Inc.
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

from enum import Enum


class CleanCommandLock(Enum):
    """Clean command lock modes. :api"""
    NONE = 0
    READ = 1
    WRITE = 2


class _Default(object):
    def __init__(self, default, choices=None):
        self.default = default
        self.choices = choices
        self._storing_name = '__%s%x' % (self.__class__.__name__, id(self))

    def __get__(self, obj, objtype=None):
        objdict = obj.__dict__
        if self._storing_name in objdict:
            return objdict[self._storing_name]
        return self.default

    def __set__(self, obj, val):
        if self.choices is not None and val not in self.choices:
            raise ValueError('Invalid demand value: %s' % val)
        objdict = obj.__dict__
        if self._storing_name in objdict:
            current_val = objdict[self._storing_name]
            if current_val != val:
                raise AttributeError('Demand already set.')
        objdict[self._storing_name] = val


_BoolDefault = _Default


class DemandSheet(object):
    """Collection of demands that different CLI parts have on other parts. :api"""

    # :api...
    allow_erasing = _BoolDefault(False)
    available_repos = _BoolDefault(False)
    resolving = _BoolDefault(False)
    root_user = _BoolDefault(False)
    sack_activation = _BoolDefault(False)
    load_system_repo = _BoolDefault(True)
    success_exit_status = 0

    cacheonly = _BoolDefault(False)
    fresh_metadata = _BoolDefault(True)
    freshest_metadata = _BoolDefault(False)
    changelogs = _BoolDefault(False)

    transaction_display = None

    # This demand controlls applicability of the plugins that could filter
    # repositories packages (e.g. versionlock).
    # If it stays None, the demands.resolving is used as a fallback.
    plugin_filtering_enabled = _BoolDefault(None)

    # Determines if/how to lock the clean command lock.
    # This lock is used to ensure clean command (which uses WRITE mode) running concurrently
    # with another dnf process doesn't delete required data (packages).
    clean_command_lock = _Default(CleanCommandLock.NONE, tuple(CleanCommandLock))
