# aliases.py
# Resolving aliases in CLI arguments.
#
# Copyright (C) 2018 Red Hat, Inc.
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

import collections
import dnf.cli
from dnf.conf.config import PRIO_DEFAULT
import dnf.exceptions
import libdnf.conf
import logging
import os
import os.path

logger = logging.getLogger('dnf')

ALIASES_DROPIN_DIR = '/etc/dnf/aliases.d/'
ALIASES_CONF_PATH = os.path.join(ALIASES_DROPIN_DIR, 'ALIASES.conf')
ALIASES_USER_PATH = os.path.join(ALIASES_DROPIN_DIR, 'USER.conf')


class AliasesConfig(object):
    def __init__(self, path):
        self._path = path
        self._parser = libdnf.conf.ConfigParser()
        self._parser.read(self._path)

    @property
    def enabled(self):
        option = libdnf.conf.OptionBool(True)
        try:
            option.set(PRIO_DEFAULT, self._parser.getData()["main"]["enabled"])
        except IndexError:
            pass
        return option.getValue()

    @property
    def aliases(self):
        result = collections.OrderedDict()
        section = "aliases"
        if not self._parser.hasSection(section):
            return result
        for key in self._parser.options(section):
            value = self._parser.getValue(section, key)
            if not value:
                continue
            result[key] = value.split()
        return result


class Aliases(object):
    def __init__(self):
        self.aliases = collections.OrderedDict()
        self.conf = None
        self.enabled = True

        if self._disabled_by_environ():
            self.enabled = False
            return

        self._load_main()

        if not self.enabled:
            return

        self._load_aliases()

    def _disabled_by_environ(self):
        option = libdnf.conf.OptionBool(True)
        try:
            option.set(PRIO_DEFAULT, os.environ['DNF_DISABLE_ALIASES'])
            return option.getValue()
        except KeyError:
            return False
        except RuntimeError:
            logger.warning(
                _('Unexpected value of environment variable: '
                  'DNF_DISABLE_ALIASES=%s'), os.environ['DNF_DISABLE_ALIASES'])
            return True

    def _load_conf(self, path):
        try:
            return AliasesConfig(path)
        except RuntimeError as e:
            raise dnf.exceptions.ConfigError(
                _('Parsing file "%s" failed: %s') % (path, e))
        except IOError as e:
            raise dnf.exceptions.ConfigError(
                _('Cannot read file "%s": %s') % (path, e))

    def _load_main(self):
        try:
            self.conf = self._load_conf(ALIASES_CONF_PATH)
            self.enabled = self.conf.enabled
        except dnf.exceptions.ConfigError as e:
            logger.debug(_('Config error: %s'), e)

    def _load_aliases(self, filenames=None):
        if filenames is None:
            try:
                filenames = self._dropin_dir_filenames()
            except dnf.exceptions.ConfigError:
                return
        for filename in filenames:
            try:
                conf = self._load_conf(filename)
                self.aliases.update(conf.aliases)
            except dnf.exceptions.ConfigError as e:
                logger.warning(_('Config error: %s'), e)

    def _dropin_dir_filenames(self):
        # Get default aliases config filenames:
        #   all files from ALIASES_DROPIN_DIR,
        #   and ALIASES_USER_PATH as the last one (-> override all others)
        ignored_filenames = [os.path.basename(ALIASES_CONF_PATH),
                             os.path.basename(ALIASES_USER_PATH)]

        def _ignore_filename(filename):
            return filename in ignored_filenames or\
                filename.startswith('.') or\
                not filename.endswith(('.conf', '.CONF'))

        filenames = []
        try:
            if not os.path.exists(ALIASES_DROPIN_DIR):
                os.mkdir(ALIASES_DROPIN_DIR)
            for fn in os.listdir(ALIASES_DROPIN_DIR):
                if _ignore_filename(fn):
                    continue
                filenames.append(os.path.join(ALIASES_DROPIN_DIR, fn))
        except (IOError, OSError) as e:
            raise dnf.exceptions.ConfigError(e)
        if os.path.exists(ALIASES_USER_PATH):
            filenames.append(ALIASES_USER_PATH)
        return filenames

    def _resolve(self, args):
        stack = []
        self.prefix_options = []

        def store_prefix(args):
            num = 0
            for arg in args:
                if arg and arg[0] != '-':
                    break
                num += 1

            self.prefix_options += args[:num]

            return args[num:]

        def subresolve(args):
            suffix = store_prefix(args)

            if (not suffix or  # Current alias on stack is resolved
                    suffix[0] not in self.aliases or  # End resolving
                    suffix[0].startswith('\\')):  # End resolving
                try:
                    stack.pop()
                except IndexError:
                    pass
                return suffix

            if suffix[0] in stack:  # Infinite recursion detected
                raise dnf.exceptions.Error(
                    _('Aliases contain infinite recursion'))

            # Next word must be an alias
            stack.append(suffix[0])
            current_alias_result = subresolve(self.aliases[suffix[0]])
            if current_alias_result:  # We reached non-alias or '\'
                return current_alias_result + suffix[1:]
            else:  # Need to resolve aliases in the rest
                return subresolve(suffix[1:])

        suffix = subresolve(args)
        return self.prefix_options + suffix

    def resolve(self, args):
        if self.enabled:
            try:
                args = self._resolve(args)
            except dnf.exceptions.Error as e:
                logger.error(_('%s, using original arguments.'), e)
        return args
