# Copyright (C) 2013  Red Hat, Inc.
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

import dnf.plugin
import tests.support

PLUGINS = "%s/tests/plugins" % tests.support.dnf_toplevel()

class PluginTest(tests.support.TestCase):
    def setUp(self):
        self.plugins = dnf.plugin.Plugins()
        self.plugins.load([PLUGINS])

    def tearDown(self):
        self.plugins.unload()

    def test_load(self):
        self.assertLength(self.plugins.plugin_cls, 1)
        cls = self.plugins.plugin_cls[0]
        assert(issubclass(cls, dnf.plugin.Plugin))
        self.assertEqual(cls.name, 'lucky')

    def test_runs(self):
        self.assertLength(self.plugins.plugins, 0)
        self.plugins.run_init(None, None)
        self.assertLength(self.plugins.plugins, 1)
        self.plugins.run_config()
        lucky = self.plugins.plugins[0]
        self.assertTrue(lucky._config)

    def test_config(self):
        base = tests.support.MockBase()
        base.conf.pluginconfpath = PLUGINS
        self.plugins.run_init(base, None)
        lucky = self.plugins.plugins[0]
        conf = lucky.read_config(base.conf)
        self.assertTrue(conf.getboolean('main', 'enabled'))
        self.assertEqual(conf.get('main', 'wanted'), '/to/be/haunted')
