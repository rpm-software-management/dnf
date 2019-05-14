# -*- coding: utf-8 -*-

# Copyright (C) 2012-2018 Red Hat, Inc.
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

import itertools
import logging
import tempfile

import libdnf.transaction

import dnf.cli.commands
import dnf.cli.commands.group
import dnf.cli.commands.install
import dnf.cli.commands.reinstall
import dnf.cli.commands.upgrade
import dnf.pycomp
import dnf.repo

import tests.support
from tests.support import mock


class CommandsCliTest(tests.support.DnfBaseTestCase):

    REPOS = []
    CLI = "mock"

    def setUp(self):
        super(CommandsCliTest, self).setUp()
        self.base.conf.persistdir = tempfile.mkdtemp()

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    def test_history_get_error_output_rollback_transactioncheckerror(self):
        """Test get_error_output with the history rollback and a TransactionCheckError."""
        cmd = dnf.cli.commands.HistoryCommand(self.cli)
        tests.support.command_configure(cmd, ['rollback', '1'])

        lines = cmd.get_error_output(dnf.exceptions.TransactionCheckError())

        self.assertEqual(
            lines,
            ('Cannot rollback transaction 1, doing so would result in an '
             'inconsistent package database.',))

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    def test_history_get_error_output_undo_transactioncheckerror(self):
        """Test get_error_output with the history undo and a TransactionCheckError."""
        cmd = dnf.cli.commands.HistoryCommand(self.cli)
        tests.support.command_configure(cmd, ['undo', '1'])

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
        tests.support.command_configure(cmd, ['list', '1..5', 'last', 'last-10', 'kernel'])
        self.assertEqual(cmd._args2transaction_ids(), [123, 113, 99, 5, 4, 3, 2, 1])


class CommandTest(tests.support.DnfBaseTestCase):

    REPOS = ["main"]
    BASE_CLI = True

    def test_canonical(self):
        cmd = dnf.cli.commands.upgrade.UpgradeCommand(self.base.mock_cli())

        try:
            tests.support.command_run(cmd, ['cracker', 'filling'])
        except dnf.exceptions.Error as e:
            if e.value != 'No packages marked for upgrade.':
                raise
        self.assertEqual(cmd._basecmd, 'upgrade')
        self.assertEqual(cmd.opts.pkg_specs, ['cracker', 'filling'])


class InstallCommandTest(tests.support.ResultTestCase):

    """Tests of ``dnf.cli.commands.install.InstallCommand`` class."""

    REPOS = ["main"]
    BASE_CLI = True
    CLI = "mock"

    def setUp(self):
        """Prepare the test fixture."""
        super(InstallCommandTest, self).setUp()
        self._cmd = dnf.cli.commands.install.InstallCommand(self.cli)

    def test_configure(self):
        tests.support.command_configure(self._cmd, ['pkg'])
        self.assertFalse(self.cli.demands.allow_erasing)
        self.assertTrue(self.cli.demands.sack_activation)

    @mock.patch('dnf.cli.commands.install._',
                dnf.pycomp.NullTranslations().ugettext)
    def test_run_group_notfound(self):
        """Test whether it fails if the group cannot be found."""
        stdout = dnf.pycomp.StringIO()

        with tests.support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error,
                              tests.support.command_run, self._cmd, ['@non-existent'])

        self.assertEqual(stdout.getvalue(), "Module or Group 'non-existent' is not available.\n")
        self.assertResult(self._cmd.cli.base,
                          self._cmd.cli.base.sack.query().installed())

    def test_run_package(self):
        """Test whether a package is installed."""
        tests.support.command_run(self._cmd, ['lotus'])

        self.assertResult(self.base, itertools.chain(
            self.base.sack.query().installed(),
            dnf.subject.Subject('lotus.x86_64').get_best_query(self.base.sack))
        )

    @mock.patch('dnf.cli.commands.install._',
                dnf.pycomp.NullTranslations().ugettext)
    def test_run_package_notfound(self):
        """Test whether it fails if the package cannot be found."""
        stdout = dnf.pycomp.StringIO()

        with tests.support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error,
                              tests.support.command_run, self._cmd, ['non-existent', 'lotus'])

        self.assertEqual(stdout.getvalue(),
                         'No match for argument: non-existent\n')
        self.assertResult(self.base, itertools.chain(
            self.base.sack.query().installed(),
            dnf.subject.Subject('lotus.x86_64').get_best_query(self.base.sack))
        )


class ReinstallCommandTest(tests.support.ResultTestCase):

    """Tests of ``dnf.cli.commands.ReinstallCommand`` class."""

    REPOS = ["main"]
    BASE_CLI = True
    CLI = "mock"

    def setUp(self):
        """Prepare the test fixture."""
        super(ReinstallCommandTest, self).setUp()
        self._cmd = dnf.cli.commands.reinstall.ReinstallCommand(self.cli)

    def test_run(self):
        """Test whether the package is installed."""
        tests.support.command_run(self._cmd, ['pepper'])
        self.assertResult(self.base, itertools.chain(
            self.base.sack.query().installed().filter(name__neq='pepper'),
            dnf.subject.Subject('pepper.x86_64').get_best_query(self.base.sack)
            .available()))

    @mock.patch('dnf.cli.commands.reinstall._',
                dnf.pycomp.NullTranslations().ugettext)
    def test_run_notinstalled(self):
        """Test whether it fails if the package is not installed."""
        stdout = dnf.pycomp.StringIO()

        with tests.support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error, tests.support.command_run, self._cmd, ['lotus'])

        self.assertEqual(stdout.getvalue(), 'Package lotus available, but not installed.\n'
                                            'No match for argument: lotus\n')
        self.assertResult(self._cmd.cli.base,
                          self._cmd.cli.base.sack.query().installed())

    @mock.patch('dnf.cli.commands.reinstall._', dnf.pycomp.NullTranslations().ugettext)
    def test_run_notavailable(self):
        """ Test whether it fails if the package is not available. """
        holes_query = dnf.subject.Subject('hole').get_best_query(self.base.sack)
        tsis = []
        for pkg in holes_query.installed():
            pkg._force_swdb_repoid = "unknown"
            self.history.rpm.add_install(pkg)
#            tsi = dnf.transaction.TransactionItem(
#                dnf.transaction.INSTALL,
#                installed=pkg,
#                reason=libdnf.transaction.TransactionItemReason_USER
#            )
#            tsis.append(tsi)
        self._swdb_commit(tsis)

        stdout = dnf.pycomp.StringIO()

        with tests.support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error, tests.support.command_run, self._cmd, ['hole'])

        self.assertEqual(
            stdout.getvalue(),
            'Installed package hole-1-1.x86_64 (from unknown) not available.\n')
        self.assertResult(self.base, self.base.sack.query().installed())


class RepoPkgsCommandTest(tests.support.DnfBaseTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand`` class."""

    REPOS = []
    BASE_CLI = True
    CLI = "mock"

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsCommandTest, self).setUp()
        self.cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)

    def test_configure_badargs(self):
        """Test whether the command fail in case of wrong args."""
        with self.assertRaises(SystemExit) as exit, \
                tests.support.patch_std_streams() as (stdout, stderr), \
                mock.patch('logging.Logger.critical'):
            tests.support.command_configure(self.cmd, [])
        self.assertEqual(exit.exception.code, 2)


class RepoPkgsCheckUpdateSubCommandTest(tests.support.DnfBaseTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.CheckUpdateSubCommand`` class."""

    REPOS = ['main', 'updates', 'third_party']
    BASE_CLI = True
    CLI = "mock"

    @mock.patch('dnf.cli.term._real_term_width', return_value=80)
    def test(self, _real_term_width):
        """ Test whether only upgrades in the repository are listed. """
        tsis = []
        for pkg in self.base.sack.query().installed().filter(name='tour'):
            pkg._force_swdb_repoid = "updates"
            self.history.rpm.add_install(pkg)
#            tsi = dnf.transaction.TransactionItem(
#                dnf.transaction.INSTALL,
#                installed=pkg,
#                reason=libdnf.transaction.TransactionItemReason_USER
#            )
#            tsis.append(tsi)
        self._swdb_commit(tsis)

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with tests.support.patch_std_streams() as (stdout, _):
            tests.support.command_run(cmd, ['updates', 'check-update'])

        self.assertEqual(
            stdout.getvalue(),
            u'\n'
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
        tests.support.command_run(cmd, ['main', 'check-update'])
#        self.assertNotEqual(self.cli.demands.success_exit_status, 100)


class RepoPkgsInfoSubCommandTest(tests.support.DnfBaseTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.InfoSubCommand`` class."""

    AVAILABLE_TITLE = u'Available Packages\n'

    HOLE_I686_INFO = (u'Name         : hole\n'
                      u'Version      : 2\n'
                      u'Release      : 1\n'
                      u'Architecture : i686\n'
                      u'Size         : 0.0  \n'
                      u'Source       : None\n'
                      u'Repository   : updates\n'
                      u'Summary      : \n'
                      u'License      : \n'
                      u'Description  : \n'
                      u'\n')

    HOLE_X86_64_INFO = (u'Name         : hole\n'
                        u'Version      : 2\n'
                        u'Release      : 1\n'
                        u'Architecture : x86_64\n'
                        u'Size         : 0.0  \n'
                        u'Source       : None\n'
                        u'Repository   : updates\n'
                        u'Summary      : \n'
                        u'License      : \n'
                        u'Description  : \n\n')

    INSTALLED_TITLE = u'Installed Packages\n'

    PEPPER_SYSTEM_INFO = (u'Name         : pepper\n'
                          u'Version      : 20\n'
                          u'Release      : 0\n'
                          u'Architecture : x86_64\n'
                          u'Size         : 0.0  \n'
                          u'Source       : None\n'
                          u'Repository   : @System\n'
                          u'From repo    : main\n'
                          u'Summary      : \n'
                          u'License      : \n'
                          u'Description  : \n\n')

    PEPPER_UPDATES_INFO = (u'Name         : pepper\n'
                           u'Version      : 20\n'
                           u'Release      : 1\n'
                           u'Architecture : x86_64\n'
                           u'Size         : 0.0  \n'
                           u'Source       : None\n'
                           u'Repository   : updates\n'
                           u'Summary      : \n'
                           u'License      : \n'
                           u'Description  : \n\n')

    REPOS = ['main', 'updates', 'third_party']
    BASE_CLI = True
    CLI = "mock"

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsInfoSubCommandTest, self).setUp()
        self.base.conf.recent = 7

    def test_info_all(self):
        """Test whether only packages related to the repository are listed."""
        tsis = []
        for pkg in self.base.sack.query().installed().filter(name='pepper'):
            pkg._force_swdb_repoid = "main"
            self.history.rpm.add_install(pkg)
#            tsi = dnf.transaction.TransactionItem(
#                dnf.transaction.INSTALL,
#                installed=pkg,
#                reason=libdnf.transaction.TransactionItemReason_USER
#            )
#            tsis.append(tsi)
        self._swdb_commit(tsis)

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with tests.support.patch_std_streams() as (stdout, _):
            tests.support.command_run(cmd, ['main', 'info', 'all', '*p*'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((
                self.INSTALLED_TITLE,
                self.PEPPER_SYSTEM_INFO,
                self.AVAILABLE_TITLE,
                u'Name         : pepper\n'
                u'Version      : 20\n'
                u'Release      : 0\n'
                u'Architecture : src\n'
                u'Size         : 0.0  \n'
                u'Source       : None\n'
                u'Repository   : main\n'
                u'Summary      : \n'
                u'License      : \n'
                u'Description  : \n'
                u'\n',
                u'Name         : trampoline\n'
                u'Version      : 2.1\n'
                u'Release      : 1\n'
                u'Architecture : noarch\n'
                u'Size         : 0.0  \n'
                u'Source       : None\n'
                u'Repository   : main\n'
                u'Summary      : \n'
                u'License      : \n'
                u'Description  : \n'
                u'\n')))

    def test_info_available(self):
        """Test whether only packages in the repository are listed."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with tests.support.patch_std_streams() as (stdout, _):
            tests.support.command_run(cmd, ['updates', 'info', 'available'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((
                self.AVAILABLE_TITLE,
                self.HOLE_I686_INFO,
                self.HOLE_X86_64_INFO,
                self.PEPPER_UPDATES_INFO)))

    def test_info_extras(self):
        """Test whether only extras installed from the repository are listed."""
        tsis = []
        for pkg in self.base.sack.query().installed().filter(name='tour'):
            pkg._force_swdb_repoid = "main"
            self.history.rpm.add_install(pkg)
#            tsi = dnf.transaction.TransactionItem(
#                dnf.transaction.INSTALL,
#                installed=pkg,
#                reason=libdnf.transaction.TransactionItemReason_USER
#            )
#            tsis.append(tsi)
        self._swdb_commit(tsis)

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with tests.support.patch_std_streams() as (stdout, _):
            tests.support.command_run(cmd, ['main', 'info', 'extras'])

        self.assertEqual(
            stdout.getvalue(),
            u'Extra Packages\n'
            u'Name         : tour\n'
            u'Version      : 5\n'
            u'Release      : 0\n'
            u'Architecture : noarch\n'
            u'Size         : 0.0  \n'
            u'Source       : None\n'
            u'Repository   : @System\n'
            u'From repo    : main\n'
            u'Summary      : \n'
            u'License      : \n'
            u'Description  : \n\n')

    def test_info_installed(self):
        """Test whether only packages installed from the repository are listed."""
        tsis = []
        for pkg in self.base.sack.query().installed().filter(name='pepper'):
            pkg._force_swdb_repoid = "main"
            self.history.rpm.add_install(pkg)
#            tsi = dnf.transaction.TransactionItem(
#                dnf.transaction.INSTALL,
#                installed=pkg,
#                reason=libdnf.transaction.TransactionItemReason_USER
#            )
#            tsis.append(tsi)
        self._swdb_commit(tsis)

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with tests.support.patch_std_streams() as (stdout, _):
            tests.support.command_run(cmd, ['main', 'info', 'installed'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((self.INSTALLED_TITLE, self.PEPPER_SYSTEM_INFO)))

    def test_info_obsoletes(self):
        """Test whether only obsoletes in the repository are listed."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with tests.support.patch_std_streams() as (stdout, _):
            tests.support.command_run(cmd, ['updates', 'info', 'obsoletes'])

        self.assertEqual(
            stdout.getvalue(),
            ''.join((
                u'Obsoleting Packages\n',
                self.HOLE_I686_INFO,
                self.HOLE_X86_64_INFO)))

    def test_info_upgrades(self):
        """Test whether only upgrades in the repository are listed."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with tests.support.patch_std_streams() as (stdout, _):
            tests.support.command_run(cmd, ['updates', 'info', 'upgrades'])
        self.assertEqual(stdout.getvalue(), ''.join((
            u'Available Upgrades\n', self.HOLE_X86_64_INFO, self.PEPPER_UPDATES_INFO)))


class RepoPkgsInstallSubCommandTest(tests.support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.InstallSubCommand`` class."""

    REPOS = ['main', 'third_party']
    BASE_CLI = True
    CLI = "mock"

    def test_all(self):
        """Test whether all packages from the repository are installed."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        tests.support.command_run(cmd, ['third_party', 'install'])

        q = self.base.sack.query()
        self.assertResult(self.base, itertools.chain(
            q.installed(),
            q.available().filter(reponame='third_party', arch='x86_64', name__neq='hole'))
        )


class RepoPkgsMoveToSubCommandTest(tests.support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.MoveToSubCommand`` class."""

    REPOS = ['distro', 'main']
    BASE_CLI = True
    CLI = "mock"

    def test_all(self):
        """Test whether only packages in the repository are installed."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        tests.support.command_run(cmd, ['distro', 'move-to'])

        self.assertResult(self.base, itertools.chain(
            self.base.sack.query().installed().filter(name__neq='tour'),
            dnf.subject.Subject('tour-5-0').get_best_query(self.base.sack)
            .available()))


class RepoPkgsReinstallOldSubCommandTest(tests.support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.ReinstallOldSubCommand`` class."""

    REPOS = ["main"]
    BASE_CLI = True
    CLI = "mock"

    def test_all(self):
        """Test whether all packages from the repository are reinstalled."""
        tsis = []
        for pkg in self.base.sack.query().installed():
            reponame = 'main' if pkg.name != 'pepper' else 'non-main'
            pkg._force_swdb_repoid = reponame
            self.history.rpm.add_install(pkg)
#            tsi = dnf.transaction.TransactionItem(
#                dnf.transaction.INSTALL,
#                installed=pkg,
#                reason=libdnf.transaction.TransactionItemReason_USER
#            )
#            tsis.append(tsi)
        self._swdb_commit(tsis)

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        tests.support.command_run(cmd, ['main', 'reinstall-old'])

        self.assertResult(self.base, itertools.chain(
            self.base.sack.query().installed().filter(name__neq='librita'),
            dnf.subject.Subject('librita.i686').get_best_query(self.base.sack).installed(),
            dnf.subject.Subject('librita').get_best_query(self.base.sack).available())
        )


class RepoPkgsReinstallSubCommandTest(tests.support.DnfBaseTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.ReinstallSubCommand`` class."""

    REPOS = ["main"]
    BASE_CLI = True
    CLI = "mock"

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsReinstallSubCommandTest, self).setUp()

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
        self.assertRaises(
            dnf.exceptions.Error,
            tests.support.command_run,
            cmd,
            ['main', 'reinstall']
        )

        self.assertEqual(self.mock.mock_calls,
                         [mock.call.reinstall_old_run(),
                          mock.call.move_to_run()])

    def test_all_moveto(self):
        """Test whether reinstall-old is called first and move-to next."""
        self.mock.reinstall_old_run.side_effect = dnf.exceptions.Error('test')

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        tests.support.command_run(cmd, ['main', 'reinstall'])

        self.assertEqual(self.mock.mock_calls,
                         [mock.call.reinstall_old_run(),
                          mock.call.move_to_run()])

    def test_all_reinstallold(self):
        """Test whether only reinstall-old is called."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        tests.support.command_run(cmd, ['main', 'reinstall'])

        self.assertEqual(self.mock.mock_calls,
                         [mock.call.reinstall_old_run()])


class RepoPkgsRemoveOrDistroSyncSubCommandTest(tests.support.ResultTestCase):

    """Tests of ``RemoveOrDistroSyncSubCommand`` class."""

    REPOS = ["distro"]
    BASE_CLI = True
    CLI = "mock"

    def test_run_on_repo_spec_sync(self):
        """Test running with a package which can be synchronized."""
        tsis = []
        for pkg in self.base.sack.query().installed():
            reponame = 'non-distro' if pkg.name == 'pepper' else 'distro'
            pkg._force_swdb_repoid = reponame
            self.history.rpm.add_install(pkg)
#            tsi = dnf.transaction.TransactionItem(
#                dnf.transaction.INSTALL,
#                installed=pkg,
#                reason=libdnf.transaction.TransactionItemReason_USER
#            )
#            tsis.append(tsi)
        self._swdb_commit(tsis)

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        tests.support.command_run(cmd, ['non-distro', 'remove-or-distro-sync', 'pepper'])

        self.assertResult(self.base, itertools.chain(
            self.base.sack.query().installed().filter(name__neq='pepper'),
            dnf.subject.Subject('pepper').get_best_query(self.base.sack)
            .available()))

    def test_run_on_repo_spec_remove(self):
        """Test running with a package which must be removed."""
        tsis = []
        for pkg in self.base.sack.query().installed():
            reponame = 'non-distro' if pkg.name == 'hole' else 'distro'
            pkg._force_swdb_repoid = reponame
            self.history.rpm.add_install(pkg)
#            tsi = dnf.transaction.TransactionItem(
#                dnf.transaction.INSTALL,
#                installed=pkg,
#                reason=libdnf.transaction.TransactionItemReason_USER
#            )
#            tsis.append(tsi)
        self._swdb_commit(tsis)

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        tests.support.command_run(cmd, ['non-distro', 'remove-or-distro-sync', 'hole'])

        self.assertResult(
            self.base,
            self.base.sack.query().installed().filter(name__neq='hole'))

    def test_run_on_repo_all(self):
        """Test running without a package specification."""
        nondist = {'pepper', 'hole'}
        tsis = []
        for pkg in self.base.sack.query().installed():
            reponame = 'non-distro' if pkg.name in nondist else 'distro'
            pkg._force_swdb_repoid = reponame
            self.history.rpm.add_install(pkg)
#            tsi = dnf.transaction.TransactionItem(
#                dnf.transaction.INSTALL,
#                installed=pkg,
#                reason=libdnf.transaction.TransactionItemReason_USER
#            )
#            tsis.append(tsi)
        self._swdb_commit(tsis)

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        tests.support.command_run(cmd, ['non-distro', 'remove-or-distro-sync'])

        self.assertResult(self.base, itertools.chain(
            self.base.sack.query().installed().filter(name__neq='pepper')
            .filter(name__neq='hole'),
            dnf.subject.Subject('pepper').get_best_query(self.base.sack)
            .available()))

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    def test_run_on_repo_spec_notinstalled(self):
        """Test running with a package which is not installed."""
        stdout = dnf.pycomp.StringIO()

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with tests.support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error,
                              tests.support.command_run, cmd,
                              ['non-distro', 'remove-or-distro-sync', 'not-installed'])

        self.assertIn('No match for argument: not-installed\n', stdout.getvalue(),
                      'mismatch not logged')

    @mock.patch('dnf.cli.commands._', dnf.pycomp.NullTranslations().ugettext)
    def test_run_on_repo_all_notinstalled(self):
        """Test running with a repository from which nothing is installed."""
        stdout = dnf.pycomp.StringIO()

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        with tests.support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error,
                              tests.support.command_run, cmd,
                              ['non-distro', 'remove-or-distro-sync'])

        self.assertIn('No package installed from the repository.\n',
                      stdout.getvalue(), 'mismatch not logged')


class RepoPkgsRemoveOrReinstallSubCommandTest(tests.support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.RemoveOrReinstallSubCommand`` class."""

    REPOS = ["distro"]
    BASE_CLI = True

    def setUp(self):
        """Prepare the test fixture."""
        super(RepoPkgsRemoveOrReinstallSubCommandTest, self).setUp()
        self.cli = self.base.mock_cli()

    def test_all_not_installed(self):
        """Test whether it fails if no package is installed from the repository."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        self.assertRaises(dnf.exceptions.Error,
                          tests.support.command_run, cmd,
                          ['non-distro', 'remove-or-distro-sync'])

        self.assertResult(self.base, self.base.sack.query().installed())

    def test_all_reinstall(self):
        """Test whether all packages from the repository are reinstalled."""
        tsis = []
        for pkg in self.base.sack.query().installed():
            reponame = 'distro' if pkg.name != 'tour' else 'non-distro'
            pkg._force_swdb_repoid = reponame
            self.history.rpm.add_install(pkg)
#            tsi = dnf.transaction.TransactionItem(
#                dnf.transaction.INSTALL,
#                installed=pkg,
#                reason=libdnf.transaction.TransactionItemReason_USER
#            )
#            tsis.append(tsi)
        self._swdb_commit(tsis)

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        tests.support.command_run(cmd, ['non-distro', 'remove-or-reinstall'])

        self.assertResult(self.base, itertools.chain(
            self.base.sack.query().installed().filter(name__neq='tour'),
            dnf.subject.Subject('tour').get_best_query(self.base.sack).available())
        )

    def test_all_remove(self):
        """Test whether all packages from the repository are removed."""
        tsis = []
        for pkg in self.base.sack.query().installed():
            reponame = 'distro' if pkg.name != 'hole' else 'non-distro'
            pkg._force_swdb_repoid = reponame
            self.history.rpm.add_install(pkg)
#            tsi = dnf.transaction.TransactionItem(
#                dnf.transaction.INSTALL,
#                installed=pkg,
#                reason=libdnf.transaction.TransactionItemReason_USER
#            )
#            tsis.append(tsi)
        self._swdb_commit(tsis)

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        tests.support.command_run(cmd, ['non-distro', 'remove-or-reinstall'])

        self.assertResult(
            self.base,
            self.base.sack.query().installed().filter(name__neq='hole'))


class RepoPkgsRemoveSubCommandTest(tests.support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.RemoveSubCommand`` class."""

    REPOS = ["main"]
    BASE_CLI = True
    CLI = "mock"

    def test_all(self):
        """Test whether only packages from the repository are removed."""
        tsis = []
        for pkg in self.base.sack.query().installed():
            reponame = 'main' if pkg.name == 'pepper' else 'non-main'
            pkg._force_swdb_repoid = reponame
            self.history.rpm.add_install(pkg)
#            tsi = dnf.transaction.TransactionItem(
#                dnf.transaction.INSTALL,
#                installed=pkg,
#                reason=libdnf.transaction.TransactionItemReason_USER
#            )
#            tsis.append(tsi)
        self._swdb_commit(tsis)

        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        tests.support.command_run(cmd, ['main', 'remove'])

        self.assertResult(
            self.base,
            self.base.sack.query().installed().filter(name__neq='pepper')
        )


class RepoPkgsUpgradeSubCommandTest(tests.support.ResultTestCase):

    """Tests of ``dnf.cli.commands.RepoPkgsCommand.UpgradeSubCommand`` class."""

    REPOS = ["updates", "third_party"]
    BASE_CLI = True
    CLI = "mock"

    def test_all(self):
        """Test whether all packages from the repository are installed."""
        cmd = dnf.cli.commands.RepoPkgsCommand(self.cli)
        tests.support.command_run(cmd, ['third_party', 'upgrade'])

        q = self.base.sack.query()
        self.assertResult(self.base, itertools.chain(
            q.installed().filter(name__neq='hole'),
            q.upgrades().filter(reponame='third_party', arch='x86_64'))
        )


class UpgradeCommandTest(tests.support.ResultTestCase):

    """Tests of ``dnf.cli.commands.upgrade.UpgradeCommand`` class."""

    REPOS = ["updates"]
    BASE_CLI = True
    CLI = "mock"

    def setUp(self):
        super(UpgradeCommandTest, self).setUp()
        self.cmd = dnf.cli.commands.upgrade.UpgradeCommand(self.cli)

    def test_run(self):
        """Test whether a package is updated."""
        tests.support.command_run(self.cmd, ['pepper'])

        self.assertResult(self.cmd.base, itertools.chain(
            self.cmd.base.sack.query().installed().filter(name__neq='pepper'),
            self.cmd.base.sack.query().upgrades().filter(name='pepper')))

    @mock.patch('dnf.cli.commands.upgrade._',
                dnf.pycomp.NullTranslations().ugettext)
    def test_updatePkgs_notfound(self):
        """Test whether it fails if the package cannot be found."""
        stdout = dnf.pycomp.StringIO()

        with tests.support.wiretap_logs('dnf', logging.INFO, stdout):
            self.assertRaises(dnf.exceptions.Error,
                              tests.support.command_run, self.cmd, ['non-existent'])

        self.assertEqual(stdout.getvalue(),
                         'No match for argument: non-existent\n')
        self.assertResult(self.cmd.base, self.cmd.base.sack.query().installed())
