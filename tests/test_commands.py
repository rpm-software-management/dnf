# Copyright (C) 2012-2016 Red Hat, Inc.
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
import dnf.pycomp
import dnf.repo
import itertools
import logging
import tempfile
import unittest


class CommandsCliTest(support.TestCase):
    def setUp(self):
        self.base = support.MockBase()
        self.cli = self.base.mock_cli()
        self.base.conf.persistdir = tempfile.mkdtemp()

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    def test_history_get_error_output_rollback_transactioncheckerror(self):
        """Test get_error_output with the history rollback and a TransactionCheckError."""
        cmd = dnf.cli.commands.HistoryCommand(self.cli)
        support.command_configure(cmd, ['rollback', '1'])

        lines = cmd.get_error_output(dnf.exceptions.TransactionCheckError())

        self.assertEqual(
            lines,
            ('Cannot rollback transaction 1, doing so would result in an '
             'inconsistent package database.',))

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    def test_history_get_error_output_undo_transactioncheckerror(self):
        """Test get_error_output with the history undo and a TransactionCheckError."""
        cmd = dnf.cli.commands.HistoryCommand(self.cli)
        support.command_configure(cmd, ['undo', '1'])

        lines = cmd.get_error_output(dnf.exceptions.TransactionCheckError())

        self.assertEqual(
            lines,
            ('Cannot undo transaction 1, doing so would result in an '
             'inconsistent package database.',))

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    def test_history_convert_tids(self):
        """Test history _convert_tids()."""
        cmd = dnf.cli.commands.HistoryCommand(self.cli)
        cmd.cli.base.output = mock.MagicMock()
        cmd.cli.base.output.history.last().tid = 123
        cmd.cli.base.output.history.search = mock.MagicMock(return_value=[99])
        support.command_configure(cmd, ['list', '1..5', 'last', 'last-10', 'kernel'])
        self.assertEqual(cmd._convert_tids(), [1, 2, 3, 4, 5, 99, 113, 123])


class CommandTest(support.TestCase):
    def test_canonical(self):
        cmd = dnf.cli.commands.upgrade.UpgradeCommand(
                                support.BaseCliStub('main').mock_cli())
        try:
            support.command_run(cmd, ['cracker', 'filling'])
        except dnf.exceptions.Error as e:
            if e.value != 'No packages marked for upgrade.':
                raise
        self.assertEqual(cmd._basecmd, 'upgrade')
        self.assertEqual(cmd.opts.pkg_specs, ['cracker', 'filling'])


class InstallCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.install.InstallCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(InstallCommandTest, self).setUp()
        base = support.BaseCliStub('main')
        base.repos['main'].metadata = mock.Mock(_comps_fn=support.COMPS_PATH)
        base.init_sack()
        self._cmd = dnf.cli.commands.install.InstallCommand(base.mock_cli())

    def test_configure(self):
        cli = self._cmd.cli
        support.command_configure(self._cmd, ['pkg'])
        self.assertFalse(cli.demands.allow_erasing)
        self.assertTrue(cli.demands.sack_activation)

    def test_run_group(self):
        """Test whether a group is installed."""
        support.command_run(self._cmd, ['@Solid Ground'])

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
                              support.command_run, self._cmd, ['@non-existent'])

        self.assertEqual(stdout.getvalue(),
                         "Warning: Group 'non-existent' does not exist.\n")
        self.assertResult(self._cmd.cli.base,
                          self._cmd.cli.base.sack.query().installed())

    def test_run_package(self):
        """Test whether a package is installed."""
        support.command_run(self._cmd, ['lotus'])

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
                              support.command_run, self._cmd, ['non-existent', 'lotus'])

        self.assertEqual(stdout.getvalue(),
                         'No package non-existent available.\n')
        base = self._cmd.cli.base
        self.assertResult(base, itertools.chain(
              base.sack.query().installed(),
              dnf.subject.Subject('lotus.x86_64').get_best_query(base.sack)))

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
        support.command_run(self._cmd, ['pepper'])

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
            self.assertRaises(dnf.exceptions.Error, support.command_run, self._cmd, ['lotus'])

        self.assertEqual(stdout.getvalue(), 'Package lotus available, but not installed.\n'
                                            'No match for argument: lotus\n')
        self.assertResult(self._cmd.cli.base,
                          self._cmd.cli.base.sack.query().installed())

    @mock.patch('dnf.cli.commands.reinstall._',
                dnf.pycomp.NullTranslations().ugettext)
    def test_run_notavailable(self):
        """Test whether it fails if the package is not available."""
        base = self._cmd.cli.base
        holes_query = dnf.subject.Subject('hole').get_best_query(base.sack)
        for pkg in holes_query.installed():
            self._cmd.base._yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self._cmd.base._yumdb.get_package(pkg).from_repo = 'unknown'
        stdout = dnf.pycomp.StringIO()

        with support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error, support.command_run, self._cmd, ['hole'])

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
        """Test whether the command fail in case of wrong args."""
        with self.assertRaises(SystemExit) as exit, \
            support.patch_std_streams() as (stdout, stderr), \
            mock.patch('logging.Logger.critical') as clog:
            support.command_configure(self.cmd, [])
        self.assertEqual(exit.exception.code, 1)

class RepoPkgsCheckUpdateSubCommandTest(unittest.TestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.CheckUpdateSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsCheckUpdateSubCommandTest, self).setUp()
        base = support.BaseCliStub('main', 'updates', 'third_party')
        self.cli = base.mock_cli()

    def test(self):
        """Test whether only upgrades in the repository are listed."""
        for pkg in self.cli.base.sack.query().installed().filter(name='tour'):
            self.cli.base._yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self.cli.base._yumdb.get_package(pkg).from_repo = 'updates'

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with support.patch_std_streams() as (stdout, _):
            support.command_run(cmd, ['updates', 'check-update'])

        self.assertEqual(
            stdout.getvalue(),
            u'\n'
            u'hole.x86_64                              1-2'
            u'                            updates \n'
            u'hole.x86_64                              2-1'
            u'                            updates \n'
            u'pepper.x86_64                            20-1'
            u'                           updates \n'
            u'Obsoleting Packages\n'
            u'hole.i686                                2-1'
            u'                            updates \n'
            u'    tour.noarch                          5-0'
            u'                            @updates\n'
            u'hole.x86_64                              2-1'
            u'                            updates \n'
            u'    tour.noarch                          5-0'
            u'                            @updates\n')
        self.assertEqual(self.cli.demands.success_exit_status, 100)

    def test_not_found(self):
        """Test whether exit code differs if updates are not found."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        support.command_run(cmd, ['main', 'check-update'])
        self.assertNotEqual(self.cli.demands.success_exit_status, 100)

class RepoPkgsInfoSubCommandTest(unittest.TestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.InfoSubCommand`` class."""

    AVAILABLE_TITLE = u'Available Packages\n'

    HOLE_I686_INFO = (u'Name         : hole\n'
                      u'Version      : 2\n'
                      u'Release      : 1\n'
                      u'Arch         : i686\n'
                      u'Size         : 0.0  \n'
                      u'Source       : None\n'
                      u'Repo         : updates\n'
                      u'Summary      : \n'
                      u'License      : \n'
                      u'Description  : \n'
                      u'\n')

    HOLE_X86_64_INFO = (u'Name         : hole\n'
                        u'Version      : 2\n'
                        u'Release      : 1\n'
                        u'Arch         : x86_64\n'
                        u'Size         : 0.0  \n'
                        u'Source       : None\n'
                        u'Repo         : updates\n'
                        u'Summary      : \n'
                        u'License      : \n'
                        u'Description  : \n\n')

    INSTALLED_TITLE = u'Installed Packages\n'

    PEPPER_SYSTEM_INFO = (u'Name         : pepper\n'
                          u'Version      : 20\n'
                          u'Release      : 0\n'
                          u'Arch         : x86_64\n'
                          u'Size         : 0.0  \n'
                          u'Source       : None\n'
                          u'Repo         : @System\n'
                          u'From repo    : main\n'
                          u'Summary      : \n'
                          u'License      : \n'
                          u'Description  : \n\n')

    PEPPER_UPDATES_INFO = (u'Name         : pepper\n'
                           u'Version      : 20\n'
                           u'Release      : 1\n'
                           u'Arch         : x86_64\n'
                           u'Size         : 0.0  \n'
                           u'Source       : None\n'
                           u'Repo         : updates\n'
                           u'Summary      : \n'
                           u'License      : \n'
                           u'Description  : \n\n')

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsInfoSubCommandTest, self).setUp()
        base = support.BaseCliStub('main', 'updates', 'third_party')
        base.conf.recent = 7
        self.cli = base.mock_cli()

    def test_info_all(self):
        """Test whether only packages related to the repository are listed."""
        for pkg in self.cli.base.sack.query().installed().filter(name='pepper'):
            self.cli.base._yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self.cli.base._yumdb.get_package(pkg).from_repo = 'main'

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with support.patch_std_streams() as (stdout, _):
            support.command_run(cmd, ['main', 'info', 'all', '*p*'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((
                self.INSTALLED_TITLE,
                self.PEPPER_SYSTEM_INFO,
                self.AVAILABLE_TITLE,
                u'Name         : pepper\n'
                u'Version      : 20\n'
                u'Release      : 0\n'
                u'Arch         : src\n'
                u'Size         : 0.0  \n'
                u'Source       : None\n'
                u'Repo         : main\n'
                u'Summary      : \n'
                u'License      : \n'
                u'Description  : \n'
                u'\n',
                u'Name         : trampoline\n'
                u'Version      : 2.1\n'
                u'Release      : 1\n'
                u'Arch         : noarch\n'
                u'Size         : 0.0  \n'
                u'Source       : None\n'
                u'Repo         : main\n'
                u'Summary      : \n'
                u'License      : \n'
                u'Description  : \n'
                u'\n')))

    def test_info_available(self):
        """Test whether only packages in the repository are listed."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with support.patch_std_streams() as (stdout, _):
            support.command_run(cmd, ['updates', 'info', 'available'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((
                self.AVAILABLE_TITLE,
                self.HOLE_I686_INFO,
                self.HOLE_X86_64_INFO,
                self.PEPPER_UPDATES_INFO)))

    def test_info_extras(self):
        """Test whether only extras installed from the repository are listed."""
        for pkg in self.cli.base.sack.query().installed().filter(name='tour'):
            self.cli.base._yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self.cli.base._yumdb.get_package(pkg).from_repo = 'unknown'

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with support.patch_std_streams() as (stdout, _):
            support.command_run(cmd, ['unknown', 'info', 'extras'])

        self.assertEqual(
            stdout.getvalue(),
            u'Extra Packages\n'
            u'Name         : tour\n'
            u'Version      : 5\n'
            u'Release      : 0\n'
            u'Arch         : noarch\n'
            u'Size         : 0.0  \n'
            u'Source       : None\n'
            u'Repo         : @System\n'
            u'From repo    : unknown\n'
            u'Summary      : \n'
            u'License      : \n'
            u'Description  : \n\n')

    def test_info_installed(self):
        """Test whether only packages installed from the repository are listed."""
        for pkg in self.cli.base.sack.query().installed().filter(name='pepper'):
            self.cli.base._yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self.cli.base._yumdb.get_package(pkg).from_repo = 'main'

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with support.patch_std_streams() as (stdout, _):
            support.command_run(cmd, ['main', 'info', 'installed'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((self.INSTALLED_TITLE, self.PEPPER_SYSTEM_INFO)))

    def test_info_obsoletes(self):
        """Test whether only obsoletes in the repository are listed."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with support.patch_std_streams() as (stdout, _):
            support.command_run(cmd, ['updates', 'info', 'obsoletes'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((
                u'Obsoleting Packages\n',
                self.HOLE_I686_INFO,
                self.HOLE_X86_64_INFO)))

    def test_info_recent(self):
        """Test whether only packages in the repository are listed."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with mock.patch('time.time', return_value=0), \
                support.patch_std_streams() as (stdout, _):
            support.command_run(cmd, ['updates', 'info', 'recent'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((
                u'Recently Added Packages\n',
                self.HOLE_I686_INFO,
                self.HOLE_X86_64_INFO,
                self.PEPPER_UPDATES_INFO)))

    def test_info_upgrades(self):
        """Test whether only upgrades in the repository are listed."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with support.patch_std_streams() as (stdout, _):
            support.command_run(cmd, ['updates', 'info', 'upgrades'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((
                u'Upgraded Packages\n'
                u'Name         : hole\n'
                u'Version      : 1\n'
                u'Release      : 2\n'
                u'Arch         : x86_64\n'
                u'Size         : 0.0  \n'
                u'Source       : None\n'
                u'Repo         : updates\n'
                u'Summary      : \n'
                u'License      : \n'
                u'Description  : \n'
                u'\n',
                self.HOLE_X86_64_INFO,
                self.PEPPER_UPDATES_INFO)))

class RepoPkgsInstallSubCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.InstallSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsInstallSubCommandTest, self).setUp()
        base = support.BaseCliStub('main', 'third_party')
        base.repos['main'].metadata = mock.Mock(_comps_fn=support.COMPS_PATH)
        base.repos['third_party'].enablegroups = False
        base.init_sack()
        self.cli = base.mock_cli()

    def test_all(self):
        """Test whether all packages from the repository are installed."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        support.command_run(cmd, ['third_party', 'install'])

        self.assertResult(self.cli.base, itertools.chain(
            self.cli.base.sack.query().installed().filter(name__neq='hole'),
            self.cli.base.sack.query().available().filter(reponame='third_party',
                                                          arch='x86_64')))

class RepoPkgsMoveToSubCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.MoveToSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsMoveToSubCommandTest, self).setUp()
        base = support.BaseCliStub('distro', 'main')
        base.init_sack()
        self.cli = base.mock_cli()

    def test_all(self):
        """Test whether only packages in the repository are installed."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        support.command_run(cmd, ['distro', 'move-to'])

        self.assertResult(self.cli.base, itertools.chain(
            self.cli.base.sack.query().installed().filter(name__neq='tour'),
            dnf.subject.Subject('tour-5-0').get_best_query(self.cli.base.sack)
            .available()))

class RepoPkgsReinstallOldSubCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.ReinstallOldSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsReinstallOldSubCommandTest, self).setUp()
        base = support.BaseCliStub('main')
        base.init_sack()
        self.cli = base.mock_cli()

    def test_all(self):
        """Test whether all packages from the repository are reinstalled."""
        for pkg in self.cli.base.sack.query().installed():
            reponame = 'main' if pkg.name != 'pepper' else 'non-main'
            self.cli.base._yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self.cli.base._yumdb.get_package(pkg).from_repo = reponame

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        support.command_run(cmd, ['main', 'reinstall-old'])

        self.assertResult(self.cli.base, itertools.chain(
              self.cli.base.sack.query().installed().filter(name__neq='librita'),
              dnf.subject.Subject('librita.i686').get_best_query(self.cli.base.sack)
              .installed(),
              dnf.subject.Subject('librita').get_best_query(self.cli.base.sack)
              .available()))

class RepoPkgsReinstallSubCommandTest(unittest.TestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.ReinstallSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsReinstallSubCommandTest, self).setUp()
        self.cli = support.BaseCliStub('main').mock_cli()

        self.mock = mock.Mock()
        old_run_patcher = mock.patch(
            'dnf.cli.commands.RepoPkgsCommand.ReinstallOldSubCommand.run_on_repo',
            self.mock.reinstall_old_run)
        move_run_patcher = mock.patch(
            'dnf.cli.commands.RepoPkgsCommand.MoveToSubCommand.run_on_repo',
            self.mock.move_to_run)

        old_run_patcher.start()
        self.addCleanup(old_run_patcher.stop)
        move_run_patcher.start()
        self.addCleanup(move_run_patcher.stop)

    def test_all_fails(self):
        """Test whether it fails if everything fails."""
        self.mock.reinstall_old_run.side_effect = dnf.exceptions.Error('test')
        self.mock.move_to_run.side_effect = dnf.exceptions.Error('test')

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        self.assertRaises(dnf.exceptions.Error, support.command_run, cmd, ['main', 'reinstall'])

        self.assertEqual(self.mock.mock_calls,
                         [mock.call.reinstall_old_run(),
                          mock.call.move_to_run()])

    def test_all_moveto(self):
        """Test whether reinstall-old is called first and move-to next."""
        self.mock.reinstall_old_run.side_effect = dnf.exceptions.Error('test')

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        support.command_run(cmd, ['main', 'reinstall'])

        self.assertEqual(self.mock.mock_calls,
                         [mock.call.reinstall_old_run(),
                          mock.call.move_to_run()])

    def test_all_reinstallold(self):
        """Test whether only reinstall-old is called."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        support.command_run(cmd, ['main', 'reinstall'])

        self.assertEqual(self.mock.mock_calls,
                         [mock.call.reinstall_old_run()])

class RepoPkgsRemoveOrDistroSyncSubCommandTest(support.ResultTestCase):

    """Tests of ``RemoveOrDistroSyncSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsRemoveOrDistroSyncSubCommandTest, self).setUp()
        self.cli = support.BaseCliStub('distro').mock_cli()
        self.cli.base.init_sack()

    def test_run_on_repo_spec_sync(self):
        """Test running with a package which can be synchronized."""
        for pkg in self.cli.base.sack.query().installed():
            data = support.RPMDBAdditionalDataPackageStub()
            data.from_repo = 'non-distro' if pkg.name == 'pepper' else 'distro'
            self.cli.base._yumdb.db[str(pkg)] = data

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        support.command_run(cmd, ['non-distro', 'remove-or-distro-sync', 'pepper'])

        self.assertResult(self.cli.base, itertools.chain(
            self.cli.base.sack.query().installed().filter(name__neq='pepper'),
            dnf.subject.Subject('pepper').get_best_query(self.cli.base.sack)
            .available()))

    def test_run_on_repo_spec_remove(self):
        """Test running with a package which must be removed."""
        for pkg in self.cli.base.sack.query().installed():
            data = support.RPMDBAdditionalDataPackageStub()
            data.from_repo = 'non-distro' if pkg.name == 'hole' else 'distro'
            self.cli.base._yumdb.db[str(pkg)] = data

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        support.command_run(cmd, ['non-distro', 'remove-or-distro-sync', 'hole'])

        self.assertResult(
            self.cli.base,
            self.cli.base.sack.query().installed().filter(name__neq='hole'))

    def test_run_on_repo_all(self):
        """Test running without a package specification."""
        nondist = {'pepper', 'hole'}
        for pkg in self.cli.base.sack.query().installed():
            data = support.RPMDBAdditionalDataPackageStub()
            data.from_repo = 'non-distro' if pkg.name in nondist else 'distro'
            self.cli.base._yumdb.db[str(pkg)] = data

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        support.command_run(cmd, ['non-distro', 'remove-or-distro-sync'])

        self.assertResult(self.cli.base, itertools.chain(
            self.cli.base.sack.query().installed().filter(name__neq='pepper')
            .filter(name__neq='hole'),
            dnf.subject.Subject('pepper').get_best_query(self.cli.base.sack)
            .available()))

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    def test_run_on_repo_spec_notinstalled(self):
        """Test running with a package which is not installed."""
        stdout = dnf.pycomp.StringIO()

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error,
                              support.command_run, cmd,
                              ['non-distro', 'remove-or-distro-sync', 'not-installed'])

        self.assertIn('No match for argument: not-installed\n', stdout.getvalue(),
                      'mismatch not logged')

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    def test_run_on_repo_all_notinstalled(self):
        """Test running with a repository from which nothing is installed."""
        stdout = dnf.pycomp.StringIO()

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error,
                              support.command_run, cmd,
                              ['non-distro', 'remove-or-distro-sync'])

        self.assertIn('No package installed from the repository.\n',
                      stdout.getvalue(), 'mismatch not logged')

class RepoPkgsRemoveOrReinstallSubCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.RemoveOrReinstallSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsRemoveOrReinstallSubCommandTest, self).setUp()
        base = support.BaseCliStub('distro')
        base.init_sack()
        self.cli = base.mock_cli()

    def test_all_not_installed(self):
        """Test whether it fails if no package is installed from the repository."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        self.assertRaises(dnf.exceptions.Error,
                          support.command_run, cmd,
                          ['non-distro', 'remove-or-distro-sync'])

        self.assertResult(self.cli.base, self.cli.base.sack.query().installed())

    def test_all_reinstall(self):
        """Test whether all packages from the repository are reinstalled."""
        for pkg in self.cli.base.sack.query().installed():
            reponame = 'distro' if pkg.name != 'tour' else 'non-distro'
            self.cli.base._yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self.cli.base._yumdb.get_package(pkg).from_repo = reponame

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        support.command_run(cmd, ['non-distro', 'remove-or-reinstall'])

        self.assertResult(self.cli.base, itertools.chain(
              self.cli.base.sack.query().installed().filter(name__neq='tour'),
              dnf.subject.Subject('tour').get_best_query(self.cli.base.sack)
              .available()))

    def test_all_remove(self):
        """Test whether all packages from the repository are removed."""
        for pkg in self.cli.base.sack.query().installed():
            reponame = 'distro' if pkg.name != 'hole' else 'non-distro'
            self.cli.base._yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self.cli.base._yumdb.get_package(pkg).from_repo = reponame

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        support.command_run(cmd, ['non-distro', 'remove-or-reinstall'])

        self.assertResult(
            self.cli.base,
            self.cli.base.sack.query().installed().filter(name__neq='hole'))

class RepoPkgsRemoveSubCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.RemoveSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsRemoveSubCommandTest, self).setUp()
        base = support.BaseCliStub('main')
        base.init_sack()
        self.cli = base.mock_cli()

    def test_all(self):
        """Test whether only packages from the repository are removed."""
        for pkg in self.cli.base.sack.query().installed():
            reponame = 'main' if pkg.name == 'pepper' else 'non-main'
            self.cli.base._yumdb.db[str(pkg)] = support.RPMDBAdditionalDataPackageStub()
            self.cli.base._yumdb.get_package(pkg).from_repo = reponame

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        support.command_run(cmd, ['main', 'remove'])

        self.assertResult(
            self.cli.base,
            self.cli.base.sack.query().installed().filter(name__neq='pepper'))

class RepoPkgsUpgradeSubCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.UpgradeSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsUpgradeSubCommandTest, self).setUp()
        base = support.BaseCliStub('updates', 'third_party')
        base.init_sack()
        self.cli = base.mock_cli()

    def test_all(self):
        """Test whether all packages from the repository are installed."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        support.command_run(cmd, ['third_party', 'upgrade'])

        self.assertResult(self.cli.base, itertools.chain(
            self.cli.base.sack.query().installed().filter(name__neq='hole'),
            self.cli.base.sack.query().upgrades().filter(reponame='third_party',
                                                         arch='x86_64')))

class RepoPkgsUpgradeToSubCommandTest(support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.UpgradeToSubCommand`` class."""

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsUpgradeToSubCommandTest, self).setUp()
        base = support.BaseCliStub('updates', 'third_party')
        base.init_sack()
        self.cli = base.mock_cli()

    def test_all(self):
        """Test whether the package from the repository is installed."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        support.command_run(cmd, ['updates', 'upgrade', 'hole-1-2'])

        self.assertResult(self.cli.base, itertools.chain(
            self.cli.base.sack.query().installed().filter(name__neq='hole'),
            dnf.subject.Subject('hole-1-2.x86_64').get_best_query(self.cli.base.sack)
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
        support.command_run(self.cmd, ['pepper'])

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
                              support.command_run, self.cmd, ['non-existent'])

        self.assertEqual(stdout.getvalue(),
                         'No match for argument: non-existent\n')
        self.assertResult(self.cmd.base, self.cmd.base.sack.query().installed())
