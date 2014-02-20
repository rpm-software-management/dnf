# Copyright (C) 2012-2014  Red Hat, Inc.
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
try:
    from unittest import mock
except ImportError:
    from tests import mock
from tests import support
import dnf.cli.commands
import dnf.repo
import unittest

class CommandsCliTest(support.TestCase):
    def setUp(self):
        self.yumbase = support.MockBase()
        self.cli = self.yumbase.mock_cli()

    def test_erase_configure(self):
        erase_cmd = dnf.cli.commands.EraseCommand(self.cli)
        erase_cmd.configure()
        self.assertTrue(self.yumbase.goal_parameters.allow_uninstall)

    def test_history_get_error_output_rollback_transactioncheckerror(self):
        """Test get_error_output with the history rollback and a TransactionCheckError."""
        cmd = dnf.cli.commands.HistoryCommand(self.cli)
        self.yumbase.basecmd = 'history'
        self.yumbase.extcmds = ('rollback', '1')

        lines = cmd.get_error_output(dnf.exceptions.TransactionCheckError())

        self.assertEqual(
            lines,
            ('Cannot rollback transaction 1, doing so would result in an '
             'inconsistent package database.',))

    def test_history_get_error_output_undo_transactioncheckerror(self):
        """Test get_error_output with the history undo and a TransactionCheckError."""
        cmd = dnf.cli.commands.HistoryCommand(self.cli)
        self.yumbase.basecmd = 'history'
        self.yumbase.extcmds = ('undo', '1')

        lines = cmd.get_error_output(dnf.exceptions.TransactionCheckError())

        self.assertEqual(
            lines,
            ('Cannot undo transaction 1, doing so would result in an '
             'inconsistent package database.',))

    def test_install_configure(self):
        erase_cmd = dnf.cli.commands.InstallCommand(self.cli)
        erase_cmd.configure()
        self.assertFalse(self.yumbase.goal_parameters.allow_uninstall)

    @staticmethod
    @mock.patch('dnf.Base.fill_sack')
    def _do_makecache(cmd, fill_sack):
        return cmd.run(['timer'])

    def assertLastInfo(self, cmd, msg):
        self.assertEqual(cmd.base.logger.info.mock_calls[-1],
                         mock.call(msg))

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.util.on_ac_power', return_value=True)
    def test_makecache_timer(self, _on_ac_power):
        cmd = dnf.cli.commands.MakeCacheCommand(self.cli)
        cmd.base.logger = mock.create_autospec(cmd.base.logger)

        self.yumbase.conf.metadata_timer_sync = 0
        self.assertFalse(self._do_makecache(cmd))
        self.assertLastInfo(cmd, u'Metadata timer caching disabled.')

        self.yumbase.conf.metadata_timer_sync = 5 # resync after 5 seconds
        self.yumbase._persistor.since_last_makecache = mock.Mock(return_value=3)
        self.assertFalse(self._do_makecache(cmd))
        self.assertLastInfo(cmd, u'Metadata cache refreshed recently.')

        self.yumbase._persistor.since_last_makecache = mock.Mock(return_value=10)
        self.yumbase._sack = 'nonempty'
        r = support.MockRepo("glimpse", None)
        self.yumbase.repos.add(r)

        # regular case 1: metadata is already expired:
        r.metadata_expire_in = mock.Mock(return_value=(False, 0))
        r.sync_strategy = dnf.repo.SYNC_TRY_CACHE
        self.assertTrue(self._do_makecache(cmd))
        self.assertLastInfo(cmd, u'Metadata cache created.')
        self.assertEqual(r.sync_strategy, dnf.repo.SYNC_EXPIRED)

        # regular case 2: metadata is cached and will expire later than
        # metadata_timer_sync:
        r.metadata_expire_in = mock.Mock(return_value=(True, 100))
        r.sync_strategy = dnf.repo.SYNC_TRY_CACHE
        self.assertTrue(self._do_makecache(cmd))
        self.assertLastInfo(cmd, u'Metadata cache created.')
        self.assertEqual(r.sync_strategy, dnf.repo.SYNC_TRY_CACHE)

        # regular case 3: metadata is cached but will eqpire before
        # metadata_timer_sync:
        r.metadata_expire_in = mock.Mock(return_value=(True, 4))
        r.sync_strategy = dnf.repo.SYNC_TRY_CACHE
        self.assertTrue(self._do_makecache(cmd))
        self.assertLastInfo(cmd, u'Metadata cache created.')
        self.assertEqual(r.sync_strategy, dnf.repo.SYNC_EXPIRED)

    @mock.patch('dnf.util.on_ac_power', return_value=False)
    def test_makecache_timer_battery(self, _on_ac_power):
        cmd = dnf.cli.commands.MakeCacheCommand(self.cli)
        cmd.base.logger = mock.create_autospec(cmd.base.logger)
        self.yumbase.conf.metadata_timer_sync = 5

        self.assertFalse(self._do_makecache(cmd))
        msg = u'Metadata timer caching disabled when running on a battery.'
        self.assertLastInfo(cmd, msg)

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.util.on_ac_power', return_value=None)
    def test_makecache_timer_battery2(self, _on_ac_power):
        cmd = dnf.cli.commands.MakeCacheCommand(self.cli)
        self.yumbase.conf.metadata_timer_sync = 5
        self.assertTrue(self._do_makecache(cmd))

class CommandTest(support.TestCase):
    def test_canonical(self):
        cmd = dnf.cli.commands.UpgradeCommand(None)
        (base, ext) = cmd.canonical(['update', 'cracker', 'filling'])
        self.assertEqual(base, 'upgrade')
        self.assertEqual(ext, ['cracker', 'filling'])

    def test_group_canonical(self):
        cmd = dnf.cli.commands.GroupsCommand(None)
        (basecmd, extcmds) = cmd.canonical(['grouplist', 'crack'])
        self.assertEqual(basecmd, 'groups')
        self.assertEqual(extcmds, ['list', 'crack'])

        (_, extcmds) = cmd.canonical(['groups'])
        self.assertEqual(extcmds, ['summary'])

        (_, extcmds) = cmd.canonical(['group', 'info', 'crack'])
        self.assertEqual(extcmds, ['info', 'crack'])

        (_, extcmds) = cmd.canonical(['group', 'update', 'crack'])
        self.assertEqual(extcmds, ['upgrade', 'crack'])

class RepoPkgsCheckUpdateSubCommandTest(unittest.TestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.CheckUpdateSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsCheckUpdateSubCommandTest, self).setUp()
        cli = support.BaseCliStub('main', 'updates', 'third_party').mock_cli()
        self._cmd = dnf.cli.commands.RepoPkgsCommand.CheckUpdateSubCommand(cli)

    @mock.patch('dnf.cli.cli._', dnf.pycomp.NullTranslations().ugettext)
    def test(self):
        """Test whether only upgrades in the repository are listed."""
        with support.patch_std_streams() as (stdout, _):
            self._cmd.run('updates', [])

        self.assertEqual(
            stdout.getvalue(),
            u'\n'
            u'hole.x86_64                               1-2                            updates\n'
            u'hole.x86_64                               2-1                            updates\n'
            u'pepper.x86_64                             20-1                           updates\n'
            u'Obsoleting Packages\n'
            u'hole.i686                                 2-1                            updates\n'
            u'    tour.noarch                           5-0                            @System\n'
            u'hole.x86_64                               2-1                            updates\n'
            u'    tour.noarch                           5-0                            @System\n')
        self.assertEqual(self._cmd.success_retval, 100)

    def test_not_found(self):
        """Test whether exit code differs if updates are not found."""
        self._cmd.run('main', [])
        self.assertNotEqual(self._cmd.success_retval, 100)

class RepoPkgsInfoSubCommandTest(unittest.TestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.InfoSubCommand`` class."""

    AVAILABLE_TITLE = u'Available Packages\n'

    HOLE_I686_INFO = (u'Name        : hole\n'
                      u'Arch        : i686\n'
                      u'Epoch       : 0\n'
                      u'Version     : 2\n'
                      u'Release     : 1\n'
                      u'Size        : 0.0  \n'
                      u'Repo        : updates\n'
                      u'Summary     : \n'
                      u'License     : None\n'
                      u'Description : \n'
                      u'\n')

    HOLE_X86_64_INFO = (u'Name        : hole\n'
                        u'Arch        : x86_64\n'
                        u'Epoch       : 0\n'
                        u'Version     : 2\n'
                        u'Release     : 1\n'
                        u'Size        : 0.0  \n'
                        u'Repo        : updates\n'
                        u'Summary     : \n'
                        u'License     : None\n'
                        u'Description : \n\n')

    INSTALLED_TITLE = u'Installed Packages\n'

    PEPPER_SYSTEM_INFO = (u'Name        : pepper\n'
                          u'Arch        : x86_64\n'
                          u'Epoch       : 0\n'
                          u'Version     : 20\n'
                          u'Release     : 0\n'
                          u'Size        : 0.0  \n'
                          u'Repo        : @System\n'
                          u'From repo   : main\n'
                          u'Summary     : \n'
                          u'License     : None\n'
                          u'Description : \n\n')

    PEPPER_UPDATES_INFO = (u'Name        : pepper\n'
                           u'Arch        : x86_64\n'
                           u'Epoch       : 0\n'
                           u'Version     : 20\n'
                           u'Release     : 1\n'
                           u'Size        : 0.0  \n'
                           u'Repo        : updates\n'
                           u'Summary     : \n'
                           u'License     : None\n'
                           u'Description : \n\n')

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsInfoSubCommandTest, self).setUp()
        base = support.BaseCliStub('main', 'updates', 'third_party')
        base.conf.recent = 7
        self._cmd = dnf.cli.commands.RepoPkgsCommand.InfoSubCommand(base.mock_cli())

    @mock.patch('dnf.cli.cli._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    def test_info_all(self):
        """Test whether only packages related to the repository are listed."""
        for pkg in self._cmd.base.sack.query().installed().filter(name='pepper'):
            self._cmd.base.yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self._cmd.base.yumdb.get_package(pkg).from_repo = 'main'

        with support.patch_std_streams() as (stdout, _):
            self._cmd.run('main', ['all', '*p*'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((
                self.INSTALLED_TITLE,
                self.PEPPER_SYSTEM_INFO,
                self.AVAILABLE_TITLE,
                u'Name        : pepper\n'
                u'Arch        : src\n'
                u'Epoch       : 0\n'
                u'Version     : 20\n'
                u'Release     : 0\n'
                u'Size        : 0.0  \n'
                u'Repo        : main\n'
                u'Summary     : \n'
                u'License     : None\n'
                u'Description : \n'
                u'\n',
                u'Name        : trampoline\n'
                u'Arch        : noarch\n'
                u'Epoch       : 0\n'
                u'Version     : 2.1\n'
                u'Release     : 1\n'
                u'Size        : 0.0  \n'
                u'Repo        : main\n'
                u'Summary     : \n'
                u'License     : None\n'
                u'Description : \n'
                u'\n')))

    @mock.patch('dnf.cli.cli._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    def test_info_available(self):
        """Test whether only packages in the repository are listed."""
        with support.patch_std_streams() as (stdout, _):
            self._cmd.run('updates', ['available'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((
                self.AVAILABLE_TITLE,
                self.HOLE_I686_INFO,
                self.HOLE_X86_64_INFO,
                self.PEPPER_UPDATES_INFO)))

    @mock.patch('dnf.cli.cli._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    def test_info_extras(self):
        """Test whether only extras installed from the repository are listed."""
        for pkg in self._cmd.base.sack.query().installed().filter(name='tour'):
            self._cmd.base.yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self._cmd.base.yumdb.get_package(pkg).from_repo = 'unknown'

        with support.patch_std_streams() as (stdout, _):
            self._cmd.run('unknown', ['extras'])

        self.assertEqual(
            stdout.getvalue(),
            u'Extra Packages\n'
            u'Name        : tour\n'
            u'Arch        : noarch\n'
            u'Epoch       : 0\n'
            u'Version     : 5\n'
            u'Release     : 0\n'
            u'Size        : 0.0  \n'
            u'Repo        : @System\n'
            u'From repo   : unknown\n'
            u'Summary     : \n'
            u'License     : None\n'
            u'Description : \n\n')

    @mock.patch('dnf.cli.cli._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    def test_info_installed(self):
        """Test whether only packages installed from the repository are listed."""
        for pkg in self._cmd.base.sack.query().installed().filter(name='pepper'):
            self._cmd.base.yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self._cmd.base.yumdb.get_package(pkg).from_repo = 'main'

        with support.patch_std_streams() as (stdout, _):
            self._cmd.run('main', ['installed'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((self.INSTALLED_TITLE, self.PEPPER_SYSTEM_INFO)))

    @mock.patch('dnf.cli.cli._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    def test_info_obsoletes(self):
        """Test whether only obsoletes in the repository are listed."""
        with support.patch_std_streams() as (stdout, _):
            self._cmd.run('updates', ['obsoletes'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((
                u'Obsoleting Packages\n',
                self.HOLE_I686_INFO,
                self.HOLE_X86_64_INFO)))

    @mock.patch('dnf.cli.cli._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    def test_info_recent(self):
        """Test whether only packages in the repository are listed."""
        with mock.patch('time.time', return_value=0), \
                support.patch_std_streams() as (stdout, _):
            self._cmd.run('updates', ['recent'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((
                u'Recently Added Packages\n',
                self.HOLE_I686_INFO,
                self.HOLE_X86_64_INFO,
                self.PEPPER_UPDATES_INFO)))

    @mock.patch('dnf.cli.cli._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.cli.output._', dnf.pycomp.NullTranslations().ugettext)
    def test_info_upgrades(self):
        """Test whether only upgrades in the repository are listed."""
        with support.patch_std_streams() as (stdout, _):
            self._cmd.run('updates', ['upgrades'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((
                u'Upgraded Packages\n'
                u'Name        : hole\n'
                u'Arch        : x86_64\n'
                u'Epoch       : 0\n'
                u'Version     : 1\n'
                u'Release     : 2\n'
                u'Size        : 0.0  \n'
                u'Repo        : updates\n'
                u'Summary     : \n'
                u'License     : None\n'
                u'Description : \n'
                u'\n',
                self.HOLE_X86_64_INFO,
                self.PEPPER_UPDATES_INFO)))
