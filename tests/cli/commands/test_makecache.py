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

import dnf.cli.commands.makecache as makecache
import dnf.pycomp

import tests.support
from tests.support import mock


class MakeCacheCommandTest(tests.support.DnfBaseTestCase):

    REPOS = ['main']
    CLI = "mock"

    def setUp(self):
        super(MakeCacheCommandTest, self).setUp()
        for r in self.base.repos.values():
            r.basecachedir = self.base.conf.cachedir

    @staticmethod
    @mock.patch('dnf.Base.fill_sack', new=mock.MagicMock())
    def _do_makecache(cmd):
        return tests.support.command_run(cmd, ['timer'])

    def assert_last_info(self, logger, msg):
        self.assertEqual(logger.info.mock_calls[-1], mock.call(msg))

    @mock.patch('dnf.base.logger',
                new_callable=tests.support.mock_logger)
    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.util.on_ac_power', return_value=True)
    @mock.patch('dnf.util.on_metered_connection', return_value=False)
    def test_makecache_timer(self, _on_ac_power, _on_metered_connection, logger):
        cmd = makecache.MakeCacheCommand(self.cli)

        self.base.conf.metadata_timer_sync = 0
        self.assertFalse(self._do_makecache(cmd))
        self.assert_last_info(logger, u'Metadata timer caching disabled.')

        self.base.conf.metadata_timer_sync = 5  # resync after 5 seconds
        self.base._repo_persistor.since_last_makecache = mock.Mock(return_value=3)
        self.assertFalse(self._do_makecache(cmd))
        self.assert_last_info(logger, u'Metadata cache refreshed recently.')

    @mock.patch('dnf.base.logger',
                new_callable=tests.support.mock_logger)
    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.util.on_ac_power', return_value=False)
    @mock.patch('dnf.util.on_metered_connection', return_value=False)
    def test_makecache_timer_battery(self, _on_ac_power, _on_metered_connection, logger):
        cmd = makecache.MakeCacheCommand(self.cli)
        self.base.conf.metadata_timer_sync = 5

        self.assertFalse(self._do_makecache(cmd))
        msg = u'Metadata timer caching disabled when running on a battery.'
        self.assert_last_info(logger, msg)

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.util.on_ac_power', return_value=None)
    @mock.patch('dnf.util.on_metered_connection', return_value=False)
    def test_makecache_timer_battery2(self, _on_ac_power, _on_metered_connection):
        cmd = makecache.MakeCacheCommand(self.cli)
        self.base.conf.metadata_timer_sync = 5
        self.assertTrue(self._do_makecache(cmd))

    @mock.patch('dnf.base.logger',
                new_callable=tests.support.mock_logger)
    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.util.on_ac_power', return_value=False)
    @mock.patch('dnf.util.on_metered_connection', return_value=True)
    def test_makecache_timer_metered(self, _on_ac_power, _on_metered_connection, logger):
        cmd = makecache.MakeCacheCommand(self.cli)
        self.base.conf.metadata_timer_sync = 5

        self.assertFalse(self._do_makecache(cmd))
        msg = u'Metadata timer caching disabled when running on metered connection.'
        self.assert_last_info(logger, msg)
