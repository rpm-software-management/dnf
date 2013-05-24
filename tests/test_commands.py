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
from tests import mock
from tests import support
import dnf.cli.commands
import dnf.repo
import unittest

class CommandsTest(unittest.TestCase):
    def setUp(self):
        self.yumbase = support.MockYumBase()
        self.cli = self.yumbase.mock_cli()

    def test_erase_configure(self):
        erase_cmd = dnf.cli.commands.EraseCommand(self.cli)
        erase_cmd.configure()
        self.assertTrue(self.yumbase.goal_parameters.allow_uninstall)

    def test_install_configure(self):
        erase_cmd = dnf.cli.commands.InstallCommand(self.cli)
        erase_cmd.configure()
        self.assertFalse(self.yumbase.goal_parameters.allow_uninstall)

    @staticmethod
    @mock.patch('dnf.yum.base.Base.activate_sack')
    def _do_makecache(cmd, activate_sack):
        return cmd.doCommand('makecache', ['timer'])

    @mock.patch('dnf.util.on_ac_power', return_value=True)
    def test_makecache_timer(self, _on_ac_power):
        cmd = dnf.cli.commands.MakeCacheCommand(self.cli)

        self.yumbase.conf.metadata_timer_sync = 0
        self.assertEqual((0, [u'Metadata timer caching disabled.']),
                         self._do_makecache(cmd))

        self.yumbase.conf.metadata_timer_sync = 5 # resync after 5 seconds
        self.yumbase._persistor.since_last_makecache = mock.Mock(return_value=3)
        self.assertEqual((0, [u'Metadata cache refreshed recently.']),
                         self._do_makecache(cmd))

        self.yumbase._persistor.since_last_makecache = mock.Mock(return_value=10)
        self.yumbase._sack = 'nonempty'
        r = dnf.repo.Repo("glimpse")
        self.yumbase.repos.add(r)

        # regular case 1: metadata is already expired:
        r.metadata_expire_in = mock.Mock(return_value=(False, 0))
        r.sync_strategy = dnf.repo.SYNC_TRY_CACHE
        self.assertEqual((0, [u'Metadata Cache Created']),
                         self._do_makecache(cmd))
        self.assertEqual(r.sync_strategy, dnf.repo.SYNC_EXPIRED)

        # regular case 2: metadata is cached and will expire later than
        # metadata_timer_sync:
        r.metadata_expire_in = mock.Mock(return_value=(True, 100))
        r.sync_strategy = dnf.repo.SYNC_TRY_CACHE
        self.assertEqual((0, [u'Metadata Cache Created']),
                         self._do_makecache(cmd))
        self.assertEqual(r.sync_strategy, dnf.repo.SYNC_TRY_CACHE)

        # regular case 3: metadata is cached but will eqpire before
        # metadata_timer_sync:
        r.metadata_expire_in = mock.Mock(return_value=(True, 4))
        r.sync_strategy = dnf.repo.SYNC_TRY_CACHE
        self.assertEqual((0, [u'Metadata Cache Created']),
                         self._do_makecache(cmd))
        self.assertEqual(r.sync_strategy, dnf.repo.SYNC_EXPIRED)

    @mock.patch('dnf.util.on_ac_power', return_value=False)
    def test_makecache_timer_battery(self, _on_ac_power):
        cmd = dnf.cli.commands.MakeCacheCommand(self.cli)
        self.yumbase.conf.metadata_timer_sync = 5
        self.assertEqual((0, [u'Metadata timer caching disabled when '
                              'running on a battery.']),
                         self._do_makecache(cmd))

    @mock.patch('dnf.util.on_ac_power', return_value=None)
    def test_makecache_timer_battery2(self, _on_ac_power):
        cmd = dnf.cli.commands.MakeCacheCommand(self.cli)
        self.yumbase.conf.metadata_timer_sync = 5
        self.assertEqual((0, [u'Metadata Cache Created']),
                         self._do_makecache(cmd))
