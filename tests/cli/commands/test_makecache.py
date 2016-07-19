# Copyright (C) 2014-2016 Red Hat, Inc.
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
from tests import support
from tests.support import mock
import dnf.cli.commands.makecache as makecache
import dnf.pycomp
import tempfile


class MakeCacheCommandTest(support.TestCase):
    def setUp(self):
        self.base = support.MockBase('main')
        self.cli = self.base.mock_cli()
        for r in self.base.repos.values():
            r.basecachedir = self.base.conf.cachedir

    @staticmethod
    @mock.patch('dnf.Base.fill_sack', new=mock.MagicMock())
    def _do_makecache(cmd):
        return support.command_run(cmd, ['timer'])

    def assert_last_info(self, logger, msg):
        self.assertEqual(logger.info.mock_calls[-1], mock.call(msg))

    @mock.patch('dnf.cli.commands.makecache.logger',
                new_callable=support.mock_logger)
    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.util.on_ac_power', return_value=True)
    def test_makecache_timer(self, _on_ac_power, logger):
        cmd = makecache.MakeCacheCommand(self.cli)

        self.base.conf.metadata_timer_sync = 0
        self.assertFalse(self._do_makecache(cmd))
        self.assert_last_info(logger, u'Metadata timer caching disabled.')

        self.base.conf.metadata_timer_sync = 5 # resync after 5 seconds
        self.base._repo_persistor.since_last_makecache = mock.Mock(return_value=3)
        self.assertFalse(self._do_makecache(cmd))
        self.assert_last_info(logger, u'Metadata cache refreshed recently.')

        self.base._repo_persistor.since_last_makecache = mock.Mock(return_value=10)
        self.base._sack = 'nonempty'
        r = support.MockRepo("glimpse", self.base.conf)
        self.base.repos.add(r)

        # regular case 1: metadata is already expired:
        r._metadata_expire_in = mock.Mock(return_value=(False, 0))
        r._sync_strategy = dnf.repo.SYNC_TRY_CACHE
        self.assertTrue(self._do_makecache(cmd))
        self.assert_last_info(logger, u'Metadata cache created.')
        self.assertTrue(r._expired)
        r._expired = False

        # regular case 2: metadata is cached and will expire later than
        # metadata_timer_sync:
        r._metadata_expire_in = mock.Mock(return_value=(True, 100))
        r._sync_strategy = dnf.repo.SYNC_TRY_CACHE
        self.assertTrue(self._do_makecache(cmd))
        self.assert_last_info(logger, u'Metadata cache created.')
        self.assertFalse(r._expired)

        # regular case 3: metadata is cached but will eqpire before
        # metadata_timer_sync:
        r._metadata_expire_in = mock.Mock(return_value=(True, 4))
        r._sync_strategy = dnf.repo.SYNC_TRY_CACHE
        self.assertTrue(self._do_makecache(cmd))
        self.assert_last_info(logger, u'Metadata cache created.')
        self.assertTrue(r._expired)

    @mock.patch('dnf.cli.commands.makecache.logger',
                new_callable=support.mock_logger)
    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.util.on_ac_power', return_value=False)
    def test_makecache_timer_battery(self, _on_ac_power, logger):
        cmd = makecache.MakeCacheCommand(self.cli)
        self.base.conf.metadata_timer_sync = 5

        self.assertFalse(self._do_makecache(cmd))
        msg = u'Metadata timer caching disabled when running on a battery.'
        self.assert_last_info(logger, msg)

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.util.on_ac_power', return_value=None)
    def test_makecache_timer_battery2(self, _on_ac_power):
        cmd = makecache.MakeCacheCommand(self.cli)
        self.base.conf.metadata_timer_sync = 5
        self.assertTrue(self._do_makecache(cmd))
