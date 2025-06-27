# substitutions.py
# Config file substitutions.
#
# Copyright (C) 2012-2016 Red Hat, Inc.
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

import logging
import os
import re

from dnf.i18n import _
from dnf.exceptions import ReadOnlyVariableError

ENVIRONMENT_VARS_RE = re.compile(r'^DNF_VAR_[A-Za-z0-9_]+$')
READ_ONLY_VARIABLES = frozenset(("releasever_major", "releasever_minor"))
logger = logging.getLogger('dnf')


class Substitutions(dict):
    # :api

    def __init__(self):
        super(Substitutions, self).__init__()
        self._update_from_env()

    def _update_from_env(self):
        numericvars = ['DNF%d' % num for num in range(0, 10)]
        for key, val in os.environ.items():
            if ENVIRONMENT_VARS_RE.match(key):
                self[key[8:]] = val  # remove "DNF_VAR_" prefix
            elif key in numericvars:
                self[key] = val

    @staticmethod
    def _split_releasever(releasever):
        # type: (str) -> tuple[str, str]
        pos = releasever.find(".")
        if pos == -1:
            releasever_major = releasever
            releasever_minor = ""
        else:
            releasever_major = releasever[:pos]
            releasever_minor = releasever[pos + 1:]
        return releasever_major, releasever_minor

    def __setitem__(self, key, value):
        if Substitutions.is_read_only(key):
            raise ReadOnlyVariableError(f"Variable \"{key}\" is read-only", variable_name=key)

        setitem = super(Substitutions, self).__setitem__
        setitem(key, value)

        if key == "releasever" and value:
            releasever_major, releasever_minor = Substitutions._split_releasever(value)
            setitem("releasever_major", releasever_major)
            setitem("releasever_minor", releasever_minor)

    @staticmethod
    def is_read_only(key):
        # type: (str) -> bool
        return key in READ_ONLY_VARIABLES

    def update_from_etc(self, installroot, varsdir=("/etc/yum/vars/", "/etc/dnf/vars/")):
        # :api

        for vars_path in varsdir:
            fsvars = []
            try:
                dir_fsvars = os.path.join(installroot, vars_path.lstrip('/'))
                fsvars = os.listdir(dir_fsvars)
            except OSError:
                continue
            for fsvar in fsvars:
                filepath = os.path.join(dir_fsvars, fsvar)
                val = None
                if os.path.isfile(filepath):
                    try:
                        with open(filepath) as fp:
                            val = fp.readline()
                        if val and val[-1] == '\n':
                            val = val[:-1]
                    except (OSError, IOError, UnicodeDecodeError) as e:
                        logger.warning(_("Error when parsing a variable from file '{0}': {1}").format(filepath, e))
                        continue
                if val is not None:
                    self[fsvar] = val
