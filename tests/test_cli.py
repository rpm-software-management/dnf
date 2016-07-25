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
from argparse import Namespace
from tests import support
from tests.support import TestCase
from tests.support import mock

import dnf.cli.cli
import dnf.conf
import dnf.goal
import dnf.repo
import dnf.repodict
import os
import re

VERSIONS_OUTPUT = """\
  Installed: pepper-0:20-0.x86_64 at 1970-01-01 00:00
  Built    :  at 1970-01-01 00:00

  Installed: tour-0:5-0.noarch at 1970-01-01 00:00
  Built    :  at 1970-01-01 00:00
"""


class VersionStringTest(TestCase):
    def test_print_versions(self):
        base = support.MockBase()
        output = support.MockOutput()
        with mock.patch('sys.stdout') as stdout,\
                mock.patch('dnf.sack.rpmdb_sack', return_value=base.sack):
            dnf.cli.cli.print_versions(['pepper', 'tour'], base, output)
        written = ''.join([mc[1][0] for mc in stdout.method_calls
                           if mc[0] == 'write'])
        self.assertEqual(written, VERSIONS_OUTPUT)


@mock.patch('dnf.cli.cli.logger', new_callable=support.mock_logger)
class BaseCliTest(support.ResultTestCase):
    def setUp(self):
        self._base = dnf.cli.cli.BaseCli()
        self._base._sack = support.mock_sack('main', 'updates')
        self._base._goal = dnf.goal.Goal(self._base.sack)
        self._base.output.term = support.MockTerminal()
        self._base.downgrade_to = mock.Mock(wraps=self._base.downgrade_to)

    def test_downgradePkgs(self, logger):
        self._base.downgradePkgs(('tour',))

        self.assertEqual(self._base.downgrade_to.mock_calls, [mock.call('tour')])
        self.assertEqual(logger.mock_calls, [])

    def test_downgradePkgs_notfound(self, logger):
        with self.assertRaises(dnf.exceptions.Error) as ctx:
            self._base.downgradePkgs(('non-existent',))
        self.assertEqual(str(ctx.exception), 'Nothing to do.')

        self.assertEqual(self._base.downgrade_to.mock_calls,
                         [mock.call('non-existent')])
        self.assertEqual(logger.mock_calls,
                         [mock.call.info('No package %s%s%s available.', '',
                                         'non-existent', '')])

    @mock.patch('dnf.cli.cli._', dnf.pycomp.NullTranslations().ugettext)
    def test_downgradePkgs_notinstalled(self, logger):
        pkg = support.ObjectMatcher(dnf.package.Package, {'name': 'lotus'})

        with self.assertRaises(dnf.exceptions.Error) as ctx:
            self._base.downgradePkgs(('lotus',))
        self.assertEqual(str(ctx.exception), 'Nothing to do.')

        self.assertEqual(self._base.downgrade_to.mock_calls, [mock.call('lotus')])
        self.assertEqual(logger.mock_calls, [
            mock.call.info('No match for available package: %s', pkg)] * 2)

    def test_transaction_id_or_offset_bad(self, _):
        """Test transaction_id_or_offset with a bad input."""
        self.assertRaises(ValueError,
                          dnf.cli.cli.BaseCli.transaction_id_or_offset, 'bad')

    def test_transaction_id_or_offset_last(self, _):
        """Test transaction_id_or_offset with the zero offset."""
        id_or_offset = dnf.cli.cli.BaseCli.transaction_id_or_offset('--last')
        self.assertEqual(id_or_offset, -1)

    def test_transaction_id_or_offset_negativeid(self, _):
        """Test transaction_id_or_offset with a negative ID."""
        self.assertRaises(ValueError,
                          dnf.cli.cli.BaseCli.transaction_id_or_offset, '-1')

    def test_transaction_id_or_offset_offset(self, _):
        """Test transaction_id_or_offset with an offset."""
        id_or_offset = dnf.cli.cli.BaseCli.transaction_id_or_offset('--last-1')
        self.assertEqual(id_or_offset, -2)

    def test_transaction_id_or_offset_positiveid(self, _):
        """Test transaction_id_or_offset with a positive ID."""
        id_or_offset = dnf.cli.cli.BaseCli.transaction_id_or_offset('1')
        self.assertEqual(id_or_offset, 1)


@mock.patch('dnf.cli.cli.Cli.read_conf_file')
class CliTest(TestCase):
    def setUp(self):
        self.base = support.MockBase("main")
        self.base.output = support.MockOutput()
        self.cli = dnf.cli.cli.Cli(self.base)

    def test_knows_upgrade(self, _):
        upgrade = self.cli.cli_commands['upgrade']
        update = self.cli.cli_commands['update']
        self.assertIs(upgrade, update)

    def test_simple(self, _):
        self.assertFalse(self.base.conf.assumeyes)
        self.cli.configure(['update', '-y'])
        self.assertTrue(self.base.conf.assumeyes)

    def test_glob_options_cmds(self, _):
        params = [
            ['install', '-y', 'pkg1', 'pkg2'],
            ['install', 'pkg1', '-y', 'pkg2'],
            ['install', 'pkg1', 'pkg2', '-y'],
            ['-y', 'install', 'pkg1', 'pkg2']
        ]
        for param in params:
            self.cli.configure(args=param)
            self.assertTrue(self.base.conf.assumeyes)
            self.assertEqual(self.cli.command.opts.command, ["install"])
            self.assertEqual(self.cli.command.opts.pkg_specs, ["pkg1", "pkg2"])

    def test_configure_repos(self, _):
        opts = Namespace()
        opts.repo = []
        opts.repos_ed = [('*', 'disable'), ('comb', 'enable')]
        opts.cacheonly = True
        opts.repofrompath = {}
        self.base._repos = dnf.repodict.RepoDict()
        self.base._repos.add(support.MockRepo('one', None))
        self.base._repos.add(support.MockRepo('two', None))
        self.base._repos.add(support.MockRepo('comb', None))
        self.cli.nogpgcheck = True
        self.cli._configure_repos(opts)
        self.assertFalse(self.base.repos['one'].enabled)
        self.assertFalse(self.base.repos['two'].enabled)
        self.assertTrue(self.base.repos['comb'].enabled)
        self.assertFalse(self.base.repos["comb"].gpgcheck)
        self.assertFalse(self.base.repos["comb"].repo_gpgcheck)
        self.assertEqual(self.base.repos["comb"].sync_strategy,
                         dnf.repo.SYNC_ONLY_CACHE)

    def test_configure_repos_expired(self, _):
        """Ensure that --cacheonly beats the expired status."""
        opts = Namespace()
        opts.repo = []
        opts.repos_ed = []
        opts.cacheonly = True
        opts.repofrompath = {}

        pers = self.base._repo_persistor
        pers.get_expired_repos = mock.Mock(return_value=('one',))
        self.base._repos = dnf.repodict.RepoDict()
        self.base._repos.add(support.MockRepo('one', None))
        self.cli._configure_repos(opts)
        # _process_demands() should respect --cacheonly in spite of modified demands
        self.cli.demands.fresh_metadata = False
        self.cli._process_demands()
        self.assertEqual(self.base.repos['one'].sync_strategy,
                         dnf.repo.SYNC_ONLY_CACHE)

@mock.patch('dnf.logging.Logging.setup', new=mock.MagicMock)
class ConfigureTest(TestCase):
    def setUp(self):
        self.base = support.MockBase("main")
        self.base._conf = dnf.conf.Conf()
        self.base.output = support.MockOutput()
        self.base._plugins = mock.Mock()
        self.cli = dnf.cli.cli.Cli(self.base)
        self.cli.command = mock.Mock()
        self.conffile = os.path.join(support.dnf_toplevel(), "etc/dnf/dnf.conf")

    @mock.patch('dnf.util.am_i_root', lambda: False)
    def test_configure_user(self):
        """ Test Cli.configure as user."""
        self.cli.configure(['update', '-c', self.conffile])
        reg = re.compile('^/var/tmp/dnf-[a-zA-Z0-9_-]+$')
        self.assertIsNotNone(reg.match(self.base.conf.cachedir))
        self.assertEqual(self.cli.cmdstring, "dnf update -c %s " % self.conffile)

    @mock.patch('dnf.util.am_i_root', lambda: True)
    def test_configure_root(self):
        """ Test Cli.configure as root."""
        self.cli.configure(['update', '--nogpgcheck', '-c', self.conffile])
        reg = re.compile('^/var/cache/dnf$')
        self.assertIsNotNone(reg.match(self.base.conf.cachedir))
        self.assertEqual(self.cli.cmdstring,
                         "dnf update --nogpgcheck -c %s " % self.conffile)

    def test_configure_verbose(self):
        self.cli.configure(['-v', 'update', '-c', self.conffile])
        self.assertEqual(self.cli.cmdstring, "dnf -v update -c %s " %
                         self.conffile)
        self.assertEqual(self.base.conf.debuglevel, 6)
        self.assertEqual(self.base.conf.errorlevel, 6)

    @mock.patch('dnf.cli.cli.Cli.read_conf_file')
    @mock.patch('dnf.cli.cli.Cli._parse_commands', new=mock.MagicMock)
    def test_installroot_explicit(self, read_conf_file):
        self.cli.base.basecmd = 'update'
        self.cli.base.extcmds = []

        self.cli.configure(['--installroot', '/roots/dnf', 'update'])
        read_conf_file.assert_called_with('/etc/dnf/dnf.conf', '/roots/dnf', None,
                                          {'conffile': '/etc/dnf/dnf.conf',
                                           'installroot': '/roots/dnf'})

    @mock.patch('dnf.cli.cli.Cli.read_conf_file')
    @mock.patch('dnf.cli.cli.Cli._parse_commands', new=mock.MagicMock)
    def test_installroot_with_etc(self, read_conf_file):
        """Test that conffile is detected in a new installroot."""
        self.cli.base.basecmd = 'update'
        self.cli.base.extcmds = []

        tlv = support.dnf_toplevel()
        self.cli.configure(['--installroot', tlv, 'update'])
        read_conf_file.assert_called_with(
            '%s/etc/dnf/dnf.conf' % tlv, tlv, None,
            {'conffile': '%s/etc/dnf/dnf.conf' % tlv,
             'installroot': tlv})

    def test_installroot_configurable(self):
        """Test that conffile is detected in a new installroot."""
        self.cli.base.basecmd = 'update'

        conf = os.path.join(support.dnf_toplevel(), "tests/etc/installroot.conf")
        self.cli.configure(['-c', conf, '--nogpgcheck', '--releasever', '17', 'update'])
        self.assertEqual(self.base.conf.installroot, '/roots/dnf')
