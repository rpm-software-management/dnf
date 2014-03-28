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
from argparse import Namespace
from tests import support
from tests.support import PycompTestCase
from tests.support import mock

import dnf.cli.cli
import dnf.conf
import dnf.repo
import dnf.repodict
import hawkey
import os
import unittest

VERSIONS_OUTPUT="""\
  Installed: pepper-0:20-0.x86_64 at 1970-01-01 00:00
  Built    :  at 1970-01-01 00:00

  Installed: tour-0:5-0.noarch at 1970-01-01 00:00
  Built    :  at 1970-01-01 00:00
"""

class VersionStringTest(PycompTestCase):
    @mock.patch('dnf.cli.cli._', dnf.pycomp.NullTranslations().ugettext)
    def test_print_versions(self):
        base = support.MockBase()
        output = support.MockOutput()
        with mock.patch('sys.stdout') as stdout,\
                mock.patch('dnf.sack.rpmdb_sack', return_value=base.sack):
            dnf.cli.cli.print_versions(['pepper', 'tour'], base, output)
        written = ''.join([mc[1][0] for mc in stdout.method_calls
                           if mc[0] == 'write'])
        self.assertEqual(written, VERSIONS_OUTPUT)

class BaseCliTest(support.ResultTestCase):
    def setUp(self):
        self._base = dnf.cli.cli.BaseCli()
        self._base._sack = support.mock_sack('main', 'updates')
        self._base._goal = hawkey.Goal(self._base.sack)

        main_repo = support.MockRepo('main', None)
        main_repo.metadata = mock.Mock(comps_fn=support.COMPS_PATH)
        main_repo.enable()
        self._base.repos.add(main_repo)

        self._base.logger = mock.create_autospec(self._base.logger)
        self._base.output.term = support.MockTerminal()
        self._base._maybeYouMeant = mock.create_autospec(self._base._maybeYouMeant)
        self._base.downgrade = mock.Mock(wraps=self._base.downgrade)

    @mock.patch('dnf.cli.cli.P_', dnf.pycomp.NullTranslations().ungettext)
    def test_downgradePkgs(self):
        self._base.downgradePkgs(('tour',))

        self.assertEqual(self._base.downgrade.mock_calls, [mock.call('tour')])
        self.assertEqual(self._base.logger.mock_calls, [])
        self.assertEqual(self._base._maybeYouMeant.mock_calls, [])

    @mock.patch('dnf.cli.cli._', dnf.pycomp.NullTranslations().ugettext)
    def test_downgradePkgs_notfound(self):
        with self.assertRaises(dnf.exceptions.Error) as ctx:
            self._base.downgradePkgs(('non-existent',))
        self.assertEqual(str(ctx.exception), 'Nothing to do.')

        self.assertEqual(self._base.downgrade.mock_calls, [mock.call('non-existent')])
        self.assertEqual(self._base.logger.mock_calls,
                         [mock.call.info('No package %s%s%s available.', '', 'non-existent', '')])
        self.assertEqual(self._base._maybeYouMeant.mock_calls,
                         [mock.call('non-existent')])

    @mock.patch('dnf.cli.cli._', dnf.pycomp.NullTranslations().ugettext)
    def test_downgradePkgs_notinstalled(self):
        pkg = support.ObjectMatcher(dnf.package.Package, {'name': 'lotus'})

        with self.assertRaises(dnf.exceptions.Error) as ctx:
            self._base.downgradePkgs(('lotus',))
        self.assertEqual(str(ctx.exception), 'Nothing to do.')

        self.assertEqual(self._base.downgrade.mock_calls, [mock.call('lotus')])
        self.assertEqual(self._base.logger.mock_calls,
                         [mock.call.info('No match for available package: %s', pkg)] * 2)
        self.assertEqual(self._base._maybeYouMeant.mock_calls, [])

    def test_transaction_id_or_offset_bad(self):
        """Test transaction_id_or_offset with a bad input."""
        self.assertRaises(ValueError,
                          dnf.cli.cli.BaseCli.transaction_id_or_offset, 'bad')

    def test_transaction_id_or_offset_last(self):
        """Test transaction_id_or_offset with the zero offset."""
        id_or_offset = dnf.cli.cli.BaseCli.transaction_id_or_offset('last')
        self.assertEqual(id_or_offset, -1)

    def test_transaction_id_or_offset_negativeid(self):
        """Test transaction_id_or_offset with a negative ID."""
        self.assertRaises(ValueError,
                          dnf.cli.cli.BaseCli.transaction_id_or_offset, '-1')

    def test_transaction_id_or_offset_offset(self):
        """Test transaction_id_or_offset with an offset."""
        id_or_offset = dnf.cli.cli.BaseCli.transaction_id_or_offset('last-1')
        self.assertEqual(id_or_offset, -2)

    def test_transaction_id_or_offset_positiveid(self):
        """Test transaction_id_or_offset with a positive ID."""
        id_or_offset = dnf.cli.cli.BaseCli.transaction_id_or_offset('1')
        self.assertEqual(id_or_offset, 1)

class CliTest(PycompTestCase):
    def setUp(self):
        self.base = support.MockBase("main")
        self.base.output = support.MockOutput()
        self.cli = support.MockCli(self.base)

    def test_knows_upgrade(self):
        upgrade = self.cli.cli_commands['upgrade']
        update = self.cli.cli_commands['update']
        self.assertIs(upgrade, update)

    def test_simple(self):
        self.assertFalse(self.base.conf.assumeyes)
        self.cli.configure(['update', '-y'])
        self.assertTrue(self.base.conf.assumeyes)

    def test_opt_between_cmds(self):
        self.cli.configure(args=['install', 'pkg1', '-y', 'pkg2'])
        self.assertTrue(self.base.conf.assumeyes)
        self.assertEqual(self.base.basecmd, "install")
        self.assertEqual(self.base.extcmds, ["pkg1", "pkg2"])

    def test_configure_repos(self):
        opts = Namespace()
        opts.repos_ed = [('*', 'disable'), ('comb', 'enable')]
        opts.cacheonly = True
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

    def test_configure_repos_expired(self):
        """Ensure that --cacheonly beats the expired status."""
        opts = Namespace()
        opts.repos_ed = []
        opts.cacheonly = True

        pers = self.base._persistor
        pers.get_expired_repos = mock.Mock(return_value=('one',))
        self.base._repos = dnf.repodict.RepoDict()
        self.base._repos.add(support.MockRepo('one', None))
        self.cli._configure_repos(opts)
        self.assertEqual(self.base.repos['one'].sync_strategy,
                         dnf.repo.SYNC_ONLY_CACHE)

@mock.patch('dnf.logging.Logging.setup', new=mock.MagicMock)
class ConfigureTest(PycompTestCase):
    def setUp(self):
        self.base = support.MockBase("main")
        self.base._conf = dnf.conf.Conf()
        self.base.output = support.MockOutput()
        self.base.plugins = mock.Mock()
        self.cli = dnf.cli.cli.Cli(self.base)
        self.cli.command = mock.Mock()
        self.conffile = os.path.join(support.dnf_toplevel(), "etc/dnf/dnf.conf")

    def test_configure(self):
        """ Test Cli.configure.

            For now just see that the method runs.
        """
        self.cli.configure(['update', '-c', self.conffile])
        self.assertEqual(self.cli.cmdstring, "dnf update -c %s " % self.conffile)

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

        self.cli.configure(['--installroot', '/roots/dnf', 'update'])
        read_conf_file.assert_called_with('/etc/dnf/dnf.conf', '/roots/dnf', None,
                                          {'conffile': '/etc/dnf/dnf.conf',
                                           'installroot': '/roots/dnf'})

    @mock.patch('dnf.cli.cli.Cli.read_conf_file')
    @mock.patch('dnf.cli.cli.Cli._parse_commands', new=mock.MagicMock)
    def test_installroot_with_etc(self, read_conf_file):
        """Test that conffile is detected in a new installroot."""
        self.cli.base.basecmd = 'update'

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
        self.cli.configure(['-c', conf, '--releasever', '17', 'update'])
        self.assertEqual(self.base.conf.installroot, '/roots/dnf')

class SearchTest(PycompTestCase):
    def setUp(self):
        self.base = support.MockBase("search")
        self.cli = dnf.cli.cli.Cli(self.base)

        self.base.output = mock.MagicMock()
        self.base.output.fmtSection = lambda str: str

    def patched_search(self, *args, **kwargs):
        with support.patch_std_streams() as (stdout, stderr):
            self.cli.search(*args, **kwargs)
            call_args = self.base.output.matchcallback.call_args_list
            pkgs = [c[0][0] for c in call_args]
            return (stdout.getvalue(), pkgs)

    def test_search(self):
        (stdout, pkgs) = self.patched_search(['lotus'])
        pkg_names = list(map(str, pkgs))
        self.assertIn('lotus-3-16.i686', pkg_names)
        self.assertIn('lotus-3-16.x86_64', pkg_names)

    @mock.patch('dnf.cli.cli._', dnf.pycomp.NullTranslations().ugettext)
    def test_search_caseness(self):
        (stdout, pkgs) = self.patched_search(['LOTUS'])
        self.assertEqual(stdout, 'N/S Matched: LOTUS\n')
        pkg_names = map(str, pkgs)
        self.assertIn('lotus-3-16.i686', pkg_names)
        self.assertIn('lotus-3-16.x86_64', pkg_names)
