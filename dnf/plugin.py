# plugin.py
# The interface for building DNF plugins.
#
# Copyright (C) 2012-2013  Red Hat, Inc.
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
import logging
import operator
import os
import sys

logger = logging.getLogger('dnf')

DYNAMIC_PACKAGE = 'dnf.plugin.dynamic'

class Plugin(object):
    """The base class custom plugins must derive from. #:api"""

    name = '<invalid>'

    @staticmethod
    def read_config(conf, name):
        # :api
        parser = iniparse.compat.ConfigParser()
        files = ['%s/%s.conf' % (path, name) for path in conf.pluginconfpath]
        parser.read(files)
        return parser

    def __init__(self, base, cli):
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

    def load(self, paths, skips):
        """Dynamically load relevant plugin modules."""

        if DYNAMIC_PACKAGE in sys.modules:
            raise RuntimeError("load_plugins() called twice")
        sys.modules[DYNAMIC_PACKAGE] = package = dnf.pycomp.ModuleType(DYNAMIC_PACKAGE)
        package.__path__ = []

        files = iter_py_files(paths, skips)
        import_modules(package, files)
        self.plugin_cls = plugin_classes()[:]
        if len(self.plugin_cls) > 0:
            names = [plugin.name for plugin in self.plugin_cls]
            logger.debug('Loaded plugins: %s', ', '.join(names))

    run_config = _caller('config')

    def run_init(self, base, cli=None):
        for p_cls in self.plugin_cls:
            plugin = p_cls(base, cli)
            self.plugins.append(plugin)

    run_sack = _caller('sack')
    run_resolved = _caller('resolved')
    run_transaction = _caller('transaction')

    def unload(self):
        del sys.modules[DYNAMIC_PACKAGE]

def plugin_classes():
    return Plugin.__subclasses__()

def import_modules(package, py_files):
    for fn in py_files:
        path, module = os.path.split(fn)
        package.__path__.append(path)
        (module, ext) = os.path.splitext(module)
        name = '%s.%s' % (package.__name__, module)
        try:
            module = importlib.import_module(name)
        except Exception as e:
            logger.error(_('Failed loading plugin: %s'), module)
            logger.log(dnf.logging.SUBDEBUG, '', exc_info=True)

def iter_py_files(paths, skips):
    for p in paths:
        for fn in glob.glob('%s/*.py' % p):
            (name, _) = os.path.splitext(os.path.basename(fn))
            if any(fnmatch.fnmatch(name, pattern) for pattern in skips):
                continue
            yield fn
