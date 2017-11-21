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

from dnf.i18n import _
import dnf.logging
import dnf.pycomp
import dnf.util
import fnmatch
import glob
import importlib
import iniparse.compat
import inspect
import logging
import operator
import os
import sys

logger = logging.getLogger('dnf')

DYNAMIC_PACKAGE = 'dnf.plugin.dynamic'


class Plugin(object):
    """The base class custom plugins must derive from. #:api"""

    name = '<invalid>'
    config_name = None

    @classmethod
    def read_config(cls, conf):
        # :api
        parser = iniparse.compat.ConfigParser()
        name = cls.config_name if cls.config_name else cls.name
        files = ['%s/%s.conf' % (path, name) for path in conf.pluginconfpath]
        parser.read(files)
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

    def _caller(method):
        def fn(self):
            dnf.util.mapall(operator.methodcaller(method), self.plugins)
        return fn

    def _check_enabled(self, conf):
        """Checks whether plugins are enabled or disabled in configuration files
           and removes disabled plugins from list"""
        for plug_cls in self.plugin_cls[:]:
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

        files = _iter_py_files(conf.pluginpath, skips, enable_plugins)
        _import_modules(package, files, skips, enable_plugins)
        self.plugin_cls = _plugin_classes()[:]
        self._check_enabled(conf)
        if len(self.plugin_cls) > 0:
            names = sorted(plugin.name for plugin in self.plugin_cls)
            logger.debug('Loaded plugins: %s', ', '.join(names))

    _run_pre_config = _caller('pre_config')

    _run_config = _caller('config')

    def _run_init(self, base, cli=None):
        for p_cls in self.plugin_cls:
            plugin = p_cls(base, cli)
            self.plugins.append(plugin)

    run_sack = _caller('sack')
    run_resolved = _caller('resolved')
    run_pre_transaction = _caller('pre_transaction')
    run_transaction = _caller('transaction')

    def _unload(self):
        del sys.modules[DYNAMIC_PACKAGE]

    def unload_removed_plugins(self, transaction):
        erased = set([package.name for package in transaction.remove_set])
        if not erased:
            return
        installed = set([package.name for package in transaction.install_set])
        transaction_diff = erased - installed
        if not transaction_diff:
            return
        files_erased = set()
        for pkg in transaction.remove_set:
            if pkg.name in transaction_diff:
                files_erased.update(pkg.files)
        for plugin in self.plugins[:]:
            if inspect.getfile(plugin.__class__) in files_erased:
                self.plugins.remove(plugin)

def _plugin_classes():
    return Plugin.__subclasses__()


def _import_modules(package, py_files, disabled_plugins=None, enabled_plugins=None):
    plugin_names = []
    for fn in py_files:
        path, module = os.path.split(fn)
        package.__path__.append(path)
        (module, ext) = os.path.splitext(module)
        name = '%s.%s' % (package.__name__, module)
        plugin_names.append(module)
        try:
            module = importlib.import_module(name)
        except Exception as e:
            logger.error(_('Failed loading plugin: %s'), module)
            logger.log(dnf.logging.SUBDEBUG, '', exc_info=True)

    for plugin in disabled_plugins + enabled_plugins:
        if plugin not in plugin_names:
            logger.error(_("Plugin '{}' does not exist").format(plugin))


def _iter_py_files(paths, skips, enable_plugins):
    for p in paths:
        for fn in glob.glob('%s/*.py' % p):
            (name, _) = os.path.splitext(os.path.basename(fn))
            if any(fnmatch.fnmatch(name, pattern) for pattern in skips):
                if not any(fnmatch.fnmatch(name, pattern) for pattern in enable_plugins):
                    continue
            yield fn


def register_command(command_class):
    #:api
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
