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
from __future__ import unicode_literals
from tests import support
from tests.support import mock

import dnf.cli.commands
import dnf.cli.commands.group
import dnf.cli.commands.install
import dnf.cli.commands.reinstall
import dnf.cli.commands.upgrade
import dnf.repo
import itertools
import logging
import tests.support
import unittest

logger = logging.getLogger('dnf')


class CommandsCliTest(support.TestCase):
    def setUp(self):
        self.base = support.MockBase()
        self.cli = self.base.mock_cli()

    def test_erase_configure(self):
        erase_cmd = dnf.cli.commands.EraseCommand(self.cli)
        erase_cmd.configure([])
        self.assertTrue(self.cli.demands.allow_erasing)

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    def test_history_get_error_output_rollback_transactioncheckerror(self):
        """Test get_error_output with the history rollback and a TransactionCheckError."""
        cmd = dnf.cli.commands.HistoryCommand(self.cli)
        self.base.basecmd = 'history'
        self.base.extcmds = ('rollback', '1')

        lines = cmd.get_error_output(dnf.exceptions.TransactionCheckError())

        self.assertEqual(
            lines,
            ('Cannot rollback transaction 1, doing so would result in an '
             'inconsistent package database.',))

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    def test_history_get_error_output_undo_transactioncheckerror(self):
        """Test get_error_output with the history undo and a TransactionCheckError."""
        cmd = dnf.cli.commands.HistoryCommand(self.cli)
        self.base.basecmd = 'history'
        self.base.extcmds = ('undo', '1')

        lines = cmd.get_error_output(dnf.exceptions.TransactionCheckError())

        self.assertEqual(
            lines,
            ('Cannot undo transaction 1, doing so would result in an '
             'inconsistent package database.',))

    @staticmethod
    @mock.patch('dnf.Base.fill_sack')
    def _do_makecache(cmd, fill_sack):
        return cmd.run(['timer'])

    def assertLastInfo(self, logger, msg):
        self.assertEqual(logger.info.mock_calls[-1],
                         mock.call(msg))

    @mock.patch('dnf.cli.commands.logger', new_callable=tests.support.mock_logger)
    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.util.on_ac_power', return_value=True)
    def test_makecache_timer(self, _on_ac_power, logger):
        cmd = dnf.cli.commands.MakeCacheCommand(self.cli)

        self.base.conf.metadata_timer_sync = 0
        self.assertFalse(self._do_makecache(cmd))
        self.assertLastInfo(logger, u'Metadata timer caching disabled.')

        self.base.conf.metadata_timer_sync = 5 # resync after 5 seconds
        self.base._persistor.since_last_makecache = mock.Mock(return_value=3)
        self.assertFalse(self._do_makecache(cmd))
        self.assertLastInfo(logger, u'Metadata cache refreshed recently.')

        self.base._persistor.since_last_makecache = mock.Mock(return_value=10)
        self.base._sack = 'nonempty'
        r = support.MockRepo("glimpse", None)
        self.base.repos.add(r)

        # regular case 1: metadata is already expired:
        r.metadata_expire_in = mock.Mock(return_value=(False, 0))
        r.sync_strategy = dnf.repo.SYNC_TRY_CACHE
        self.assertTrue(self._do_makecache(cmd))
        self.assertLastInfo(logger, u'Metadata cache created.')
        self.assertEqual(r.sync_strategy, dnf.repo.SYNC_EXPIRED)

        # regular case 2: metadata is cached and will expire later than
        # metadata_timer_sync:
        r.metadata_expire_in = mock.Mock(return_value=(True, 100))
        r.sync_strategy = dnf.repo.SYNC_TRY_CACHE
        self.assertTrue(self._do_makecache(cmd))
        self.assertLastInfo(logger, u'Metadata cache created.')
        self.assertEqual(r.sync_strategy, dnf.repo.SYNC_TRY_CACHE)

        # regular case 3: metadata is cached but will eqpire before
        # metadata_timer_sync:
        r.metadata_expire_in = mock.Mock(return_value=(True, 4))
        r.sync_strategy = dnf.repo.SYNC_TRY_CACHE
        self.assertTrue(self._do_makecache(cmd))
        self.assertLastInfo(logger, u'Metadata cache created.')
        self.assertEqual(r.sync_strategy, dnf.repo.SYNC_EXPIRED)

    @mock.patch('dnf.cli.commands.logger', new_callable=tests.support.mock_logger)
    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.util.on_ac_power', return_value=False)
    def test_makecache_timer_battery(self, _on_ac_power, logger):
        cmd = dnf.cli.commands.MakeCacheCommand(self.cli)
        self.base.conf.metadata_timer_sync = 5

        self.assertFalse(self._do_makecache(cmd))
        msg = u'Metadata timer caching disabled when running on a battery.'
        self.assertLastInfo(logger, msg)

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    @mock.patch('dnf.util.on_ac_power', return_value=None)
    def test_makecache_timer_battery2(self, _on_ac_power):
        cmd = dnf.cli.commands.MakeCacheCommand(self.cli)
        self.base.conf.metadata_timer_sync = 5
        self.assertTrue(self._do_makecache(cmd))

class CommandTest(support.TestCase):
    def test_canonical(self):
        cmd = dnf.cli.commands.upgrade.UpgradeCommand(None)
        (base, ext) = cmd.canonical(['update', 'cracker', 'filling'])
        self.assertEqual(base, 'upgrade')
        self.assertEqual(ext, ['cracker', 'filling'])

class EraseCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.EraseCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(EraseCommandTest, self).setUp()
        base = support.BaseCliStub()
        base.init_sack()
        self.cmd = dnf.cli.commands.EraseCommand(base.mock_cli())

    def test_run(self):
        """Test whether the package is installed."""
        self.cmd.run(['pepper'])

        self.assertResult(
            self.cmd.base,
            self.cmd.base.sack.query().installed().filter(name__neq='pepper'))

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    def test_run_notfound(self):
        """Test whether it fails if the package cannot be found."""
        stdout = dnf.pycomp.StringIO()

        with support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error, self.cmd.run, ['non-existent'])

        self.assertEqual(stdout.getvalue(),
                         'No match for argument: non-existent\n')
        self.assertResult(self.cmd.base, self.cmd.base.sack.query().installed())

class InstallCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.install.InstallCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(InstallCommandTest, self).setUp()
        base = support.BaseCliStub('main')
        base.repos['main'].metadata = mock.Mock(comps_fn=support.COMPS_PATH)
        base.init_sack()
        self._cmd = dnf.cli.commands.install.InstallCommand(base.mock_cli())

    def test_configure(self):
        cli = self._cmd.cli
        self._cmd.configure([])
        self.assertFalse(cli.demands.allow_erasing)
        self.assertTrue(cli.demands.sack_activation)

    def test_run_group(self):
        """Test whether a group is installed."""
        self._cmd.run(['@Solid Ground'])

        base = self._cmd.cli.base
        self.assertResult(base, itertools.chain(
              base.sack.query().installed(),
              dnf.subject.Subject('trampoline').get_best_query(base.sack)))

    @mock.patch('dnf.cli.commands.install._',
                dnf.pycomp.NullTranslations().ugettext)
    def test_run_group_notfound(self):
        """Test whether it fails if the group cannot be found."""
        stdout = dnf.pycomp.StringIO()

        with support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error,
                              self._cmd.run, ['@non-existent'])

        self.assertEqual(stdout.getvalue(),
                         "Warning: Group 'non-existent' does not exist.\n")
        self.assertResult(self._cmd.cli.base,
                          self._cmd.cli.base.sack.query().installed())

    def test_run_package(self):
        """Test whether a package is installed."""
        self._cmd.run(['lotus'])

        base = self._cmd.cli.base
        self.assertResult(base, itertools.chain(
              base.sack.query().installed(),
              dnf.subject.Subject('lotus.x86_64').get_best_query(base.sack)))

    @mock.patch('dnf.cli.commands.install._',
                dnf.pycomp.NullTranslations().ugettext)
    def test_run_package_notfound(self):
        """Test whether it fails if the package cannot be found."""
        stdout = dnf.pycomp.StringIO()

        with support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error,
                              self._cmd.run, ['non-existent'])

        self.assertEqual(stdout.getvalue(),
                         'No package non-existent available.\n')
        self.assertResult(self._cmd.cli.base,
                          self._cmd.cli.base.sack.query().installed())

class ReinstallCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.ReinstallCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(ReinstallCommandTest, self).setUp()
        base = support.BaseCliStub('main')
        base.init_sack()
        self._cmd = dnf.cli.commands.reinstall.ReinstallCommand(base.mock_cli())

    def test_run(self):
        """Test whether the package is installed."""
        self._cmd.run(['pepper'])

        base = self._cmd.cli.base
        self.assertResult(base, itertools.chain(
            base.sack.query().installed().filter(name__neq='pepper'),
            dnf.subject.Subject('pepper.x86_64').get_best_query(base.sack)
            .available()))

    @mock.patch('dnf.cli.commands.reinstall._',
                dnf.pycomp.NullTranslations().ugettext)
    def test_run_notinstalled(self):
        """Test whether it fails if the package is not installed."""
        stdout = dnf.pycomp.StringIO()

        with support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error, self._cmd.run, ['lotus'])

        self.assertEqual(stdout.getvalue(), 'No match for argument: lotus\n')
        self.assertResult(self._cmd.cli.base,
                          self._cmd.cli.base.sack.query().installed())

    @mock.patch('dnf.cli.commands.reinstall._',
                dnf.pycomp.NullTranslations().ugettext)
    def test_run_notavailable(self):
        """Test whether it fails if the package is not available."""
        base = self._cmd.cli.base
        holes_query = dnf.subject.Subject('hole').get_best_query(base.sack)
        for pkg in holes_query.installed():
            self._cmd.base.yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self._cmd.base.yumdb.get_package(pkg).from_repo = 'unknown'
        stdout = dnf.pycomp.StringIO()

        with support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error, self._cmd.run, ['hole'])

        self.assertEqual(
            stdout.getvalue(),
            'Installed package hole-1-1.x86_64 (from unknown) not available.\n')
        self.assertResult(base, base.sack.query().installed())

class RepoPkgsCommandTest(unittest.TestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsCommandTest, self).setUp()
        cli = support.BaseCliStub().mock_cli()
        self.cmd = dnf.cli.commands.RepoPkgsCommand(cli)

    def test_configure_badargs(self):
        """Test whether the method does not fail even in case of wrong args."""
        self.cmd.configure([])

class RepoPkgsCheckUpdateSubCommandTest(unittest.TestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.CheckUpdateSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsCheckUpdateSubCommandTest, self).setUp()
        cli = support.BaseCliStub('main', 'updates', 'third_party').mock_cli()
        self._cmd = dnf.cli.commands.RepoPkgsCommand.CheckUpdateSubCommand(cli)
        self.cli = cli

    @mock.patch('dnf.cli.cli._', dnf.pycomp.NullTranslations().ugettext)
    def test(self):
        """Test whether only upgrades in the repository are listed."""
        with support.patch_std_streams() as (stdout, _):
            self._cmd.run('updates', [])

        self.assertEqual(
            stdout.getvalue(),
            u'\n'
            u'hole.x86_64                               1-2'
            u'                            updates\n'
            u'hole.x86_64                               2-1'
            u'                            updates\n'
            u'pepper.x86_64                             20-1'
            u'                           updates\n'
            u'Obsoleting Packages\n'
            u'hole.i686                                 2-1'
            u'                            updates\n'
            u'    tour.noarch                           5-0'
            u'                            @System\n'
            u'hole.x86_64                               2-1'
            u'                            updates\n'
            u'    tour.noarch                           5-0'
            u'                            @System\n')
        self.assertEqual(self.cli.demands.success_exit_status, 100)

    def test_not_found(self):
        """Test whether exit code differs if updates are not found."""
        self._cmd.run('main', [])
        self.assertNotEqual(self.cli.demands.success_exit_status, 100)

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
                      u'License     : \n'
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
                        u'License     : \n'
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
                          u'License     : \n'
                          u'Description : \n\n')

    PEPPER_UPDATES_INFO = (u'Name        : pepper\n'
                           u'Arch        : x86_64\n'
                           u'Epoch       : 0\n'
                           u'Version     : 20\n'
                           u'Release     : 1\n'
                           u'Size        : 0.0  \n'
                           u'Repo        : updates\n'
                           u'Summary     : \n'
                           u'License     : \n'
                           u'Description : \n\n')

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsInfoSubCommandTest, self).setUp()
        base = support.BaseCliStub('main', 'updates', 'third_party')
        base.conf.recent = 7
        self._cmd = dnf.cli.commands.RepoPkgsCommand.InfoSubCommand(
                        base.mock_cli())

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
                u'License     : \n'
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
                u'License     : \n'
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
            u'License     : \n'
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
                u'License     : \n'
                u'Description : \n'
                u'\n',
                self.HOLE_X86_64_INFO,
                self.PEPPER_UPDATES_INFO)))

class RepoPkgsInstallSubCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.InstallSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsInstallSubCommandTest, self).setUp()
        base = support.BaseCliStub('main', 'third_party')
        base.repos['main'].metadata = mock.Mock(comps_fn=support.COMPS_PATH)
        base.repos['third_party'].enablegroups = False
        base.init_sack()
        self.cmd = dnf.cli.commands.RepoPkgsCommand.InstallSubCommand(
                       base.mock_cli())

    def test_all(self):
        """Test whether all packages from the repository are installed."""
        self.cmd.run('third_party', [])

        self.assertResult(self.cmd.base, itertools.chain(
            self.cmd.base.sack.query().installed().filter(name__neq='hole'),
            self.cmd.base.sack.query().available().filter(reponame='third_party',
                                                          arch='x86_64')))

class RepoPkgsMoveToSubCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.MoveToSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsMoveToSubCommandTest, self).setUp()
        base = support.BaseCliStub('distro', 'main')
        base.init_sack()
        self.cmd = dnf.cli.commands.RepoPkgsCommand.MoveToSubCommand(
                       base.mock_cli())

    def test_all(self):
        """Test whether only packages in the repository are installed."""
        self.cmd.run('distro', [])

        self.assertResult(self.cmd.base, itertools.chain(
            self.cmd.base.sack.query().installed().filter(name__neq='tour'),
            dnf.subject.Subject('tour-5-0').get_best_query(self.cmd.base.sack)
            .available()))

class RepoPkgsReinstallOldSubCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.ReinstallOldSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsReinstallOldSubCommandTest, self).setUp()
        base = support.BaseCliStub('main')
        base.init_sack()
        self.cmd = dnf.cli.commands.RepoPkgsCommand.ReinstallOldSubCommand(
                       base.mock_cli())

    def test_all(self):
        """Test whether all packages from the repository are reinstalled."""
        for pkg in self.cmd.base.sack.query().installed():
            reponame = 'main' if pkg.name != 'pepper' else 'non-main'
            self.cmd.base.yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self.cmd.base.yumdb.get_package(pkg).from_repo = reponame

        self.cmd.run('main', [])

        self.assertResult(self.cmd.base, itertools.chain(
              self.cmd.base.sack.query().installed().filter(name__neq='librita'),
              dnf.subject.Subject('librita.i686').get_best_query(self.cmd.base.sack)
              .installed(),
              dnf.subject.Subject('librita').get_best_query(self.cmd.base.sack)
              .available()))

class RepoPkgsReinstallSubCommandTest(unittest.TestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.ReinstallSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsReinstallSubCommandTest, self).setUp()
        base = support.BaseCliStub('main')
        self.cmd = dnf.cli.commands.RepoPkgsCommand.ReinstallSubCommand(
                       base.mock_cli())

        self.mock = mock.Mock()
        old_run_patcher = mock.patch(
            'dnf.cli.commands.RepoPkgsCommand.ReinstallOldSubCommand.run',
            self.mock.reinstall_old_run)
        move_run_patcher = mock.patch(
            'dnf.cli.commands.RepoPkgsCommand.MoveToSubCommand.run',
            self.mock.move_to_run)

        old_run_patcher.start()
        self.addCleanup(old_run_patcher.stop)
        move_run_patcher.start()
        self.addCleanup(move_run_patcher.stop)

    def test_all_fails(self):
        """Test whether it fails if everything fails."""
        self.mock.reinstall_old_run.side_effect = dnf.exceptions.Error('test')
        self.mock.move_to_run.side_effect = dnf.exceptions.Error('test')

        self.assertRaises(dnf.exceptions.Error, self.cmd.run, 'main', [])

        self.assertEqual(self.mock.mock_calls,
                         [mock.call.reinstall_old_run('main', []),
                          mock.call.move_to_run('main', [])])

    def test_all_moveto(self):
        """Test whether reinstall-old is called first and move-to next."""
        self.mock.reinstall_old_run.side_effect = dnf.exceptions.Error('test')

        self.cmd.run('main', [])

        self.assertEqual(self.mock.mock_calls,
                         [mock.call.reinstall_old_run('main', []),
                          mock.call.move_to_run('main', [])])

    def test_all_reinstallold(self):
        """Test whether only reinstall-old is called."""
        self.cmd.run('main', [])

        self.assertEqual(self.mock.mock_calls,
                         [mock.call.reinstall_old_run('main', [])])

class RepoPkgsRemoveOrDistroSyncSubCommandTest(support.ResultTestCase):

    """Tests of ``RemoveOrDistroSyncSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsRemoveOrDistroSyncSubCommandTest, self).setUp()
        self.cli = support.BaseCliStub('distro').mock_cli()
        self.cli.base.init_sack()

    def test_run_spec_sync(self):
        """Test running with a package which can be synchronized."""
        for pkg in self.cli.base.sack.query().installed():
            data = support.RPMDBAdditionalDataPackageStub()
            data.from_repo = 'non-distro' if pkg.name == 'pepper' else 'distro'
            self.cli.base.yumdb.db[str(pkg)] = data

        cmd = dnf.cli.commands.RepoPkgsCommand.RemoveOrDistroSyncSubCommand(
            self.cli)
        cmd.run('non-distro', ['pepper'])

        self.assertResult(self.cli.base, itertools.chain(
            self.cli.base.sack.query().installed().filter(name__neq='pepper'),
            dnf.subject.Subject('pepper').get_best_query(self.cli.base.sack)
            .available()))

    def test_run_spec_remove(self):
        """Test running with a package which must be removed."""
        for pkg in self.cli.base.sack.query().installed():
            data = support.RPMDBAdditionalDataPackageStub()
            data.from_repo = 'non-distro' if pkg.name == 'hole' else 'distro'
            self.cli.base.yumdb.db[str(pkg)] = data

        cmd = dnf.cli.commands.RepoPkgsCommand.RemoveOrDistroSyncSubCommand(
            self.cli)
        cmd.run('non-distro', ['hole'])

        self.assertResult(
            self.cli.base,
            self.cli.base.sack.query().installed().filter(name__neq='hole'))

    def test_run_all(self):
        """Test running without a package specification."""
        nondist = {'pepper', 'hole'}
        for pkg in self.cli.base.sack.query().installed():
            data = support.RPMDBAdditionalDataPackageStub()
            data.from_repo = 'non-distro' if pkg.name in nondist else 'distro'
            self.cli.base.yumdb.db[str(pkg)] = data

        cmd = dnf.cli.commands.RepoPkgsCommand.RemoveOrDistroSyncSubCommand(
            self.cli)
        cmd.run('non-distro', [])

        self.assertResult(self.cli.base, itertools.chain(
            self.cli.base.sack.query().installed().filter(name__neq='pepper')
            .filter(name__neq='hole'),
            dnf.subject.Subject('pepper').get_best_query(self.cli.base.sack)
            .available()))

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    def test_run_spec_notinstalled(self):
        """Test running with a package which is not installed."""
        stdout = dnf.pycomp.StringIO()

        cmd = dnf.cli.commands.RepoPkgsCommand.RemoveOrDistroSyncSubCommand(
            self.cli)
        with support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error,
                              cmd.run, 'non-distro', ['not-installed'])

        self.assertIn('No match for argument: not-installed\n', stdout.getvalue(),
                      'mismatch not logged')

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    def test_run_all_notinstalled(self):
        """Test running with a repository from which nothing is installed."""
        stdout = dnf.pycomp.StringIO()

        cmd = dnf.cli.commands.RepoPkgsCommand.RemoveOrDistroSyncSubCommand(
            self.cli)
        with support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error, cmd.run, 'non-distro', [])

        self.assertIn('No package installed from the repository.\n',
                      stdout.getvalue(), 'mismatch not logged')

class RepoPkgsRemoveOrReinstallSubCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.RemoveOrReinstallSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsRemoveOrReinstallSubCommandTest, self).setUp()
        base = support.BaseCliStub('distro')
        base.init_sack()
        self.cmd = dnf.cli.commands.RepoPkgsCommand.RemoveOrReinstallSubCommand(
                       base.mock_cli())

    def test_all_not_installed(self):
        """Test whether it fails if no package is installed from the repository."""
        self.assertRaises(dnf.exceptions.Error, self.cmd.run, 'non-distro', [])

        self.assertResult(self.cmd.base, self.cmd.base.sack.query().installed())

    def test_all_reinstall(self):
        """Test whether all packages from the repository are reinstalled."""
        for pkg in self.cmd.base.sack.query().installed():
            reponame = 'distro' if pkg.name != 'tour' else 'non-distro'
            self.cmd.base.yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self.cmd.base.yumdb.get_package(pkg).from_repo = reponame

        self.cmd.run('non-distro', [])

        self.assertResult(self.cmd.base, itertools.chain(
              self.cmd.base.sack.query().installed().filter(name__neq='tour'),
              dnf.subject.Subject('tour').get_best_query(self.cmd.base.sack)
              .available()))

    def test_all_remove(self):
        """Test whether all packages from the repository are removed."""
        for pkg in self.cmd.base.sack.query().installed():
            reponame = 'distro' if pkg.name != 'hole' else 'non-distro'
            self.cmd.base.yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self.cmd.base.yumdb.get_package(pkg).from_repo = reponame

        self.cmd.run('non-distro', [])

        self.assertResult(
            self.cmd.base,
            self.cmd.base.sack.query().installed().filter(name__neq='hole'))

class RepoPkgsRemoveSubCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.RemoveSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsRemoveSubCommandTest, self).setUp()
        base = support.BaseCliStub('main')
        base.init_sack()
        self.cmd = dnf.cli.commands.RepoPkgsCommand.RemoveSubCommand(
                       base.mock_cli())

    def test_all(self):
        """Test whether only packages from the repository are removed."""
        for pkg in self.cmd.base.sack.query().installed():
            reponame = 'main' if pkg.name == 'pepper' else 'non-main'
            self.cmd.base.yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self.cmd.base.yumdb.get_package(pkg).from_repo = reponame

        self.cmd.run('main', [])

        self.assertResult(
            self.cmd.base,
            self.cmd.base.sack.query().installed().filter(name__neq='pepper'))

class RepoPkgsUpgradeSubCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.UpgradeSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsUpgradeSubCommandTest, self).setUp()
        base = support.BaseCliStub('updates', 'third_party')
        base.init_sack()
        self.cmd = dnf.cli.commands.RepoPkgsCommand.UpgradeSubCommand(
                        base.mock_cli())

    def test_all(self):
        """Test whether all packages from the repository are installed."""
        self.cmd.run('third_party', [])

        self.assertResult(self.cmd.base, itertools.chain(
            self.cmd.base.sack.query().installed().filter(name__neq='hole'),
            self.cmd.base.sack.query().upgrades().filter(reponame='third_party',
                                                         arch='x86_64')))

class RepoPkgsUpgradeToSubCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.UpgradeToSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsUpgradeToSubCommandTest, self).setUp()
        base = support.BaseCliStub('updates', 'third_party')
        base.init_sack()
        self.cmd = dnf.cli.commands.RepoPkgsCommand.UpgradeToSubCommand(
                       base.mock_cli())

    def test_all(self):
        """Test whether the package from the repository is installed."""
        self.cmd.run('updates', ['hole-1-2'])

        self.assertResult(self.cmd.base, itertools.chain(
            self.cmd.base.sack.query().installed().filter(name__neq='hole'),
            dnf.subject.Subject('hole-1-2.x86_64').get_best_query(self.cmd.base.sack)
            .filter(reponame='updates')))

class UpgradeCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.upgrade.UpgradeCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(UpgradeCommandTest, self).setUp()
        base = support.BaseCliStub('updates')
        base.init_sack()
        self.cmd = dnf.cli.commands.upgrade.UpgradeCommand(base.mock_cli())

    def test_run(self):
        """Test whether a package is updated."""
        self.cmd.run(['pepper'])

        self.assertResult(self.cmd.base, itertools.chain(
            self.cmd.base.sack.query().installed().filter(name__neq='pepper'),
            self.cmd.base.sack.query().upgrades().filter(name='pepper')))

    @mock.patch('dnf.cli.commands.upgrade._',
                dnf.pycomp.NullTranslations().ugettext)
    def test_updatePkgs_notfound(self):
        """Test whether it fails if the package cannot be found."""
        stdout = dnf.pycomp.StringIO()

        with support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error,
                              self.cmd.run, ['non-existent'])

        self.assertEqual(stdout.getvalue(),
                         'No match for argument: non-existent\n')
        self.assertResult(self.cmd.base, self.cmd.base.sack.query().installed())
