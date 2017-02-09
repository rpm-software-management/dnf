# Copyright (C) 2013-2016 Red Hat, Inc.
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

import dnf.logging
import dnf.plugin
import dnf.pycomp
import tests.support

PLUGINS = "%s/tests/plugins" % tests.support.dnf_toplevel()

def testconf():
    conf = tests.support.FakeConf()
    conf.pluginpath = [PLUGINS]
    conf.pluginconfpath = [PLUGINS]
    return conf

class PluginTest(tests.support.TestCase):
    def setUp(self):
        self.plugins = dnf.plugin.Plugins()
        self.plugins._load(testconf(), (), ())

    def tearDown(self):
        self.plugins._unload()

    def test_load(self):
        self.assertLength(self.plugins.plugin_cls, 1)
        cls = self.plugins.plugin_cls[0]
        assert(issubclass(cls, dnf.plugin.Plugin))
        self.assertEqual(cls.name, 'lucky')

    def test_runs(self):
        self.assertLength(self.plugins.plugins, 0)
        self.plugins._run_init(None, None)
        self.assertLength(self.plugins.plugins, 1)
        self.plugins._run_config()
        lucky = self.plugins.plugins[0]
        self.assertTrue(lucky._config)

    def test_config(self):
        base = tests.support.MockBase()
        base.conf.pluginconfpath = ['/wrong', PLUGINS]
        self.plugins._run_init(base, None)
        lucky = self.plugins.plugins[0]
        conf = lucky.read_config(base.conf)
        self.assertTrue(conf.getboolean('main', 'enabled'))
        self.assertEqual(conf.get('main', 'wanted'), '/to/be/haunted')

    def test_disabled(self):
        base = tests.support.MockBase()
        base.conf.pluginconfpath = [PLUGINS]
        self.plugins._run_init(base, None)
        self.assertFalse(any([p.name == 'disabled-plugin'
                              for p in self.plugins.plugins]))
        self.assertLength(self.plugins.plugin_cls, 1)
        self.assertEqual(self.plugins.plugin_cls[0].name, 'lucky')

class PluginSkipsTest(tests.support.TestCase):
    def test_skip(self):
        self.plugins = dnf.plugin.Plugins()
        self.plugins._load(testconf(), ('luck*',), ())
        self.assertLength(self.plugins.plugin_cls, 0)

    def tearDown(self):
        self.plugins._unload()

class PluginNonExistentTest(tests.support.TestCase):

    """Tests with a non-existent plugin."""

    def test_logs_traceback(self):
        """Test whether the traceback is logged if a plugin cannot be imported."""
        package = dnf.pycomp.ModuleType('testpkg')
        package.__path__ = []
        stream = dnf.pycomp.StringIO()

        with tests.support.wiretap_logs('dnf', dnf.logging.SUBDEBUG, stream):
            dnf.plugin._import_modules(package, ('nonexistent.py',))

        end = ('Error: No module named \'testpkg\'\n' if dnf.pycomp.PY3
               else 'Error: No module named testpkg.nonexistent\n')
        self.assertTracebackIn(end, stream.getvalue())
