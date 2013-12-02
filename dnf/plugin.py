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

import dnf.util
import glob
import importlib
import itertools
import logging
import operator
import os
import sys
import types

logger = logging.getLogger('dnf')

DYNAMIC_PACKAGE = 'dnf.plugin.dynamic'

class Plugin(object):
    """The base class custom plugins must derive from."""

    name = '<invalid>'

    def config(self):
        pass

class Plugins(object):
    def __init__(self):
        self.plugin_cls = None
        self.plugins = []

    def _caller(method):
        def fn(self):
            dnf.util.mapall(operator.methodcaller('config'), self.plugins)
        return fn

    def load(self, paths):
        """Dynamically load relevant plugin modules."""

        if DYNAMIC_PACKAGE in sys.modules:
            raise RuntimeError("load_plugins() called twice")
        sys.modules[DYNAMIC_PACKAGE] = package = types.ModuleType(DYNAMIC_PACKAGE)
        package.__path__ = []

        files = iter_py_files(paths)
        import_modules(package, files)
        self.plugin_cls = plugin_classes()[:]

    run_config = _caller('config')

    def run_init(self, base, cli=None):
        for p_cls in self.plugin_cls:
            plugin = p_cls(base, cli)
            self.plugins.append(plugin)

    def unload(self):
        del sys.modules[DYNAMIC_PACKAGE]

def plugin_classes():
    return Plugin.__subclasses__()

def import_modules(package, py_files):
    for fn in py_files:
        path, module = os.path.split(fn)
        package.__path__.append(path)
        (module, _) = os.path.splitext(module)
        name = '%s.%s' % (package.__name__, module)
        module = importlib.import_module(name)

def iter_py_files(paths):
    return (fn for p in paths for fn in glob.glob('%s/*.py' % p))

