# plugin.py
# The interface for building DNF plugins.
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

from __future__ import absolute_import
from __future__ import print_function
from __future__ import unicode_literals

import fnmatch
import glob
import importlib
import inspect
import logging
import operator
import os
import sys
import traceback

import libdnf
import dnf.logging
import dnf.pycomp
import dnf.util
from dnf.i18n import _

logger = logging.getLogger('dnf')

DYNAMIC_PACKAGE = 'dnf.plugin.dynamic'


class Plugin(object):
    """The base class custom plugins must derive from. #:api"""

    name = '<invalid>'
    config_name = None

    @classmethod
    def read_config(cls, conf):
        # :api
        parser = libdnf.conf.ConfigParser()
        name = cls.config_name if cls.config_name else cls.name
        files = ['%s/%s.conf' % (path, name) for path in conf.pluginconfpath]
        for file in files:
            if os.path.isfile(file):
                try:
                    parser.read(file)
                except Exception as e:
                    raise dnf.exceptions.ConfigError(_("Parsing file failed: %s") % str(e))
        return parser

    def __init__(self, base, cli):
        # :api
        self.base = base
        self.cli = cli

    def pre_config(self):
        # :api
        pass

    def config(self):
        # :api
        pass

    def resolved(self):
        # :api
        pass

    def sack(self):
        # :api
        pass

    def pre_transaction(self):
        # :api
        pass

    def transaction(self):
        # :api
        pass


class Plugins(object):
    def __init__(self):
        self.plugin_cls = []
        self.plugins = []

    def _caller(self, method):
        for plugin in self.plugins:
            try:
                getattr(plugin, method)()
            except dnf.exceptions.Error:
                raise
            except Exception:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                except_list = traceback.format_exception(exc_type, exc_value, exc_traceback)
                logger.critical(''.join(except_list))

    def _check_enabled(self, conf, enable_plugins):
        """Checks whether plugins are enabled or disabled in configuration files
           and removes disabled plugins from list"""
        for plug_cls in self.plugin_cls[:]:
            name = plug_cls.name
            if any(fnmatch.fnmatch(name, pattern) for pattern in enable_plugins):
                continue
            parser = plug_cls.read_config(conf)
            # has it enabled = False?
            disabled = (parser.has_section('main')
                        and parser.has_option('main', 'enabled')
                        and not parser.getboolean('main', 'enabled'))
            if disabled:
                self.plugin_cls.remove(plug_cls)

    def _load(self, conf, skips, enable_plugins):
        """Dynamically load relevant plugin modules."""

        if DYNAMIC_PACKAGE in sys.modules:
            raise RuntimeError("load_plugins() called twice")
        sys.modules[DYNAMIC_PACKAGE] = package = dnf.pycomp.ModuleType(DYNAMIC_PACKAGE)
        package.__path__ = []

        files = _get_plugins_files(conf.pluginpath, skips, enable_plugins)
        _import_modules(package, files)
        self.plugin_cls = _plugin_classes()[:]
        self._check_enabled(conf, enable_plugins)
        if len(self.plugin_cls) > 0:
            names = sorted(plugin.name for plugin in self.plugin_cls)
            logger.debug(_('Loaded plugins: %s'), ', '.join(names))

    def _run_pre_config(self):
        self._caller('pre_config')

    def _run_config(self):
        self._caller('config')

    def _run_init(self, base, cli=None):
        for p_cls in self.plugin_cls:
            plugin = p_cls(base, cli)
            self.plugins.append(plugin)

    def run_sack(self):
        self._caller('sack')

    def run_resolved(self):
        self._caller('resolved')

    def run_pre_transaction(self):
        self._caller('pre_transaction')

    def run_transaction(self):
        self._caller('transaction')

    def _unload(self):
        logger.debug(_('Plugins were unloaded'))
        del sys.modules[DYNAMIC_PACKAGE]

    def unload_removed_plugins(self, transaction):
        """
        Unload plugins that were removed in the `transaction`.
        """
        if not transaction.remove_set:
            return

        # gather all installed plugins and their files
        plugins = dict()
        for plugin in self.plugins:
            plugins[inspect.getfile(plugin.__class__)] = plugin

        # gather all removed files that are plugin files
        plugin_files = set(plugins.keys())
        erased_plugin_files = set()
        for pkg in transaction.remove_set:
            erased_plugin_files.update(plugin_files.intersection(pkg.files))
        if not erased_plugin_files:
            return

        # check whether removed plugin file is added at the same time (upgrade of a plugin)
        for pkg in transaction.install_set:
            erased_plugin_files.difference_update(pkg.files)

        # unload plugins that were removed in transaction
        for plugin_file in erased_plugin_files:
            self.plugins.remove(plugins[plugin_file])


def _plugin_classes():
    return Plugin.__subclasses__()


def _import_modules(package, py_files):
    for fn in py_files:
        path, module = os.path.split(fn)
        package.__path__.append(path)
        (module, ext) = os.path.splitext(module)
        name = '%s.%s' % (package.__name__, module)
        try:
            module = importlib.import_module(name)
        except Exception as e:
            logger.error(_('Failed loading plugin "%s": %s'), module, e)
            logger.log(dnf.logging.SUBDEBUG, '', exc_info=True)


def _get_plugins_files(paths, disable_plugins, enable_plugins):
    plugins = []
    disable_plugins = set(disable_plugins)
    enable_plugins = set(enable_plugins)
    pattern_enable_found = set()
    pattern_disable_found = set()
    for p in paths:
        for fn in glob.glob('%s/*.py' % p):
            (plugin_name, dummy) = os.path.splitext(os.path.basename(fn))
            matched = True
            enable_pattern_tested = False
            for pattern_skip in disable_plugins:
                if _plugin_name_matches_pattern(plugin_name, pattern_skip):
                    pattern_disable_found.add(pattern_skip)
                    matched = False
                    for pattern_enable in enable_plugins:
                        if _plugin_name_matches_pattern(plugin_name, pattern_enable):
                            matched = True
                            pattern_enable_found.add(pattern_enable)
                    enable_pattern_tested = True
            if not enable_pattern_tested:
                for pattern_enable in enable_plugins:
                    if _plugin_name_matches_pattern(plugin_name, pattern_enable):
                        pattern_enable_found.add(pattern_enable)
            if matched:
                plugins.append(fn)
    enable_not_found = enable_plugins.difference(pattern_enable_found)
    if enable_not_found:
        logger.warning(_("No matches found for the following enable plugin patterns: {}").format(
            ", ".join(sorted(enable_not_found))))
    disable_not_found = disable_plugins.difference(pattern_disable_found)
    if disable_not_found:
        logger.warning(_("No matches found for the following disable plugin patterns: {}").format(
            ", ".join(sorted(disable_not_found))))
    return plugins


def _plugin_name_matches_pattern(plugin_name, pattern):
    """
    Checks plugin name matches the pattern.

    The alternative plugin name using dashes instead of underscores is tried
    in case of original name is not matched.

    (see https://bugzilla.redhat.com/show_bug.cgi?id=1980712)
    """

    try_names = set((plugin_name, plugin_name.replace('_', '-')))
    return any(fnmatch.fnmatch(name, pattern) for name in try_names)


def register_command(command_class):
    # :api
    """A class decorator for automatic command registration."""
    def __init__(self, base, cli):
        if cli:
            cli.register_command(command_class)
    plugin_class = type(str(command_class.__name__ + 'Plugin'),
                        (dnf.Plugin,),
                        {"__init__": __init__,
                         "name": command_class.aliases[0]})
    command_class._plugin = plugin_class
    return command_class
