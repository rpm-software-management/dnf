# -*- coding: utf-8 -*-

# Copyright (C) 2014-2018 Red Hat, Inc.
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

import dnf.automatic.main

import tests.support


FILE = tests.support.resource_path('etc/automatic.conf')


class TestConfig(tests.support.TestCase):
    def test_load(self):
        # test values from config file take effect if no overrides
        # note: config file specifies download = no apply = yes,
        # test expects implication to turn download into True
        conf = dnf.automatic.main.AutomaticConfig(FILE)
        self.assertTrue(conf.commands.apply_updates)
        self.assertTrue(conf.commands.download_updates)
        self.assertEqual(conf.commands.random_sleep, 300)
        self.assertEqual(conf.email.email_from, 'staring@crowd.net')

        # test overriding installupdates
        conf = dnf.automatic.main.AutomaticConfig(FILE, installupdates=False)
        # as per above, download is set false in config
        self.assertFalse(conf.commands.download_updates)
        self.assertFalse(conf.commands.apply_updates)

        # test overriding installupdates and downloadupdates
        conf = dnf.automatic.main.AutomaticConfig(FILE, downloadupdates=True, installupdates=False)
        self.assertTrue(conf.commands.download_updates)
        self.assertFalse(conf.commands.apply_updates)
