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
import dnf.cli.cli
import dnf.repo
import dnf.repodict
import hawkey
import optparse
import os
import unittest

INFOOUTPUT_OUTPUT="""\
Name        : tour
Arch        : noarch
Epoch       : 0
Version     : 5
Release     : 0
Size        : 0.0  
Repo        : None
Summary     : A summary of the package.
URL         : http://example.com
License     : GPL+
Description : 

"""

VERSIONS_OUTPUT="""\
  Installed: pepper-0:20-0.x86_64 at 1970-01-01 00:00
  Built    :  at 1970-01-01 00:00

  Installed: tour-0:5-0.noarch at 1970-01-01 00:00
  Built    :  at 1970-01-01 00:00
"""

class VersionStringTest(unittest.TestCase):
    def test_print_versions(self):
        yumbase = support.MockYumBase()
        with mock.patch('sys.stdout') as stdout,\
                mock.patch('dnf.sack.rpmdb_sack', return_value=yumbase.sack):
            dnf.cli.cli.print_versions(['pepper', 'tour'], yumbase)
        written = ''.join([mc[1][0] for mc in stdout.method_calls
                           if mc[0] == 'write'])
        self.assertEqual(written, VERSIONS_OUTPUT)

class YumBaseCliTest(unittest.TestCase):
    def setUp(self):
        self._yumbase = dnf.cli.cli.YumBaseCli()
        self._yumbase._sack = support.mock_sack('main')
        self._yumbase._goal = hawkey.Goal(self._yumbase.sack)
        self._yumbase.logger = mock.create_autospec(self._yumbase.logger)
        self._yumbase.term = support.FakeTerm()
        self._yumbase._checkMaybeYouMeant = mock.create_autospec(self._yumbase._checkMaybeYouMeant)
        self._yumbase._maybeYouMeant = mock.create_autospec(self._yumbase._maybeYouMeant)
        self._yumbase.downgrade = mock.Mock(wraps=self._yumbase.downgrade)
        self._yumbase.reinstall = mock.Mock(wraps=self._yumbase.reinstall)
        self._yumbase.remove = mock.Mock(wraps=self._yumbase.remove)
        self._yumbase.update = mock.Mock(wraps=self._yumbase.update)

    def test_updatePkgs(self):
        result, resultmsgs = self._yumbase.updatePkgs(('pepper',))

        self.assertEqual(self._yumbase.update.mock_calls, [mock.call('pepper')])
        self.assertEqual(self._yumbase.logger.mock_calls, [])
        self.assertEqual(self._yumbase._checkMaybeYouMeant.mock_calls, [])
        self.assertEqual(result, 2)
        self.assertEqual(resultmsgs, ['1 package marked for upgrade'])

    def test_updatePkgs_notfound(self):
        result, resultmsgs = self._yumbase.updatePkgs(('non-existent',))

        self.assertEqual(self._yumbase.update.mock_calls, [mock.call('non-existent')])
        self.assertEqual(self._yumbase.logger.mock_calls,
                         [mock.call.info('No match for argument: %s', 'non-existent')])
        self.assertEqual(self._yumbase._checkMaybeYouMeant.mock_calls,
                         [mock.call('non-existent')])
        self.assertEqual(result, 0)
        self.assertEqual(resultmsgs, ['No packages marked for upgrade'])

    def test_erasePkgs(self):
        result, resultmsgs = self._yumbase.erasePkgs(('pepper',))

        self.assertEqual(self._yumbase.remove.mock_calls, [mock.call('pepper')])
        self.assertEqual(self._yumbase.logger.mock_calls, [])
        self.assertEqual(self._yumbase._checkMaybeYouMeant.mock_calls, [])
        self.assertEqual(result, 2)
        self.assertEqual(resultmsgs, ['1 package marked for removal'])

    def test_erasePkgs_notfound(self):
        result, resultmsgs = self._yumbase.erasePkgs(('non-existent',))

        self.assertEqual(self._yumbase.remove.mock_calls, [mock.call('non-existent')])
        self.assertEqual(self._yumbase.logger.mock_calls,
                         [mock.call.info('No match for argument: %s', 'non-existent')])
        self.assertEqual(self._yumbase._checkMaybeYouMeant.mock_calls,
                         [mock.call('non-existent', always_output=False, rpmdb_only=True)])
        self.assertEqual(result, 0)
        self.assertEqual(resultmsgs, ['No Packages marked for removal'])

    def test_downgradePkgs(self):
        result, resultmsgs = self._yumbase.downgradePkgs(('tour',))

        self.assertEqual(self._yumbase.downgrade.mock_calls, [mock.call('tour')])
        self.assertEqual(self._yumbase.logger.mock_calls, [])
        self.assertEqual(self._yumbase._maybeYouMeant.mock_calls, [])
        self.assertEqual(result, 2)
        self.assertEqual(resultmsgs, ['1 package to downgrade'])

    def test_downgradePkgs_notinstalled(self):
        result, resultmsgs = self._yumbase.downgradePkgs(('lotus',))

        self.assertEqual(self._yumbase.downgrade.mock_calls, [mock.call('lotus')])
        self.assertEqual(self._yumbase.logger.mock_calls, [])
        self.assertEqual(self._yumbase._maybeYouMeant.mock_calls,
                         [mock.call('lotus')])
        self.assertEqual(result, 0)
        self.assertEqual(resultmsgs, ['Nothing to do'])

    def test_reinstallPkgs(self):
        result, resultmsgs = self._yumbase.reinstallPkgs(('pepper',))
        
        self.assertEqual(self._yumbase.reinstall.mock_calls, [mock.call('pepper')])
        self.assertEqual(self._yumbase.logger.mock_calls, [])
        self.assertEqual(self._yumbase._checkMaybeYouMeant.mock_calls, [])
        self.assertEqual(result, 2)
        self.assertEqual(resultmsgs, ['1 package to reinstall'])

    def test_reinstallPkgs_notinstalled(self):
        result, resultmsgs = self._yumbase.reinstallPkgs(('lotus',))
        
        self.assertEqual(self._yumbase.reinstall.mock_calls, [mock.call('lotus')])
        self.assertEqual(self._yumbase.logger.mock_calls,
                         [mock.call.info('No match for argument: %s', 'lotus')])
        self.assertEqual(self._yumbase._checkMaybeYouMeant.mock_calls,
                         [mock.call('lotus', always_output=False)])
        self.assertEqual(result, 1)
        self.assertEqual(resultmsgs, ['Nothing to do'])

    def test_reinstallPkgs_notavailable(self):
        pkg = support.PackageMatcher(name='hole')
        
        result, resultmsgs = self._yumbase.reinstallPkgs(('hole',))
        
        self.assertEqual(self._yumbase.reinstall.mock_calls, [mock.call('hole')])
        self.assertEqual(self._yumbase.logger.mock_calls,
                         [mock.call.info('Installed package %s%s%s%s not available.', '', pkg, '', '')])
        self.assertEqual(self._yumbase._checkMaybeYouMeant.mock_calls, [])
        self.assertEqual(result, 1)
        self.assertEqual(resultmsgs, ['Nothing to do'])

    def test_infoOutput_with_none_description(self):
        pkg = support.MockPackage('tour-5-0.noarch')
        pkg.from_system = False
        pkg.size = 0
        pkg.pkgid = None
        pkg.repoid = None
        pkg.e = pkg.epoch
        pkg.v = pkg.version
        pkg.r = pkg.release
        pkg.summary = 'A summary of the package.'
        pkg.url = 'http://example.com'
        pkg.license = 'GPL+'
        pkg.description = None
        
        with mock.patch('sys.stdout') as stdout:
            self._yumbase.infoOutput(pkg)
        written = ''.join([mc[1][0] for mc in stdout.method_calls
                          if mc[0] == 'write'])
        self.assertEqual(written, INFOOUTPUT_OUTPUT)

class CliTest(unittest.TestCase):
    def setUp(self):
        self.yumbase = support.MockYumBase("main")
        self.cli = dnf.cli.cli.Cli(self.yumbase)

    def test_knows_upgrade(self):
        upgrade = self.cli.cli_commands['upgrade']
        update = self.cli.cli_commands['update']
        self.assertIs(upgrade, update)

    def test_configure_repos(self):
        opts = optparse.Values()
        opts.repos_ed = [('*', 'disable'), ('comb', 'enable')]
        opts.cacheonly = True
        calls = mock.Mock()
        self.yumbase._repos = dnf.repodict.RepoDict()
        self.yumbase._repos.add(support.MockRepo('one'))
        self.yumbase._repos.add(support.MockRepo('two'))
        self.yumbase._repos.add(support.MockRepo('comb'))
        self.cli.nogpgcheck = True
        self.cli._configure_repos(opts)
        self.assertFalse(self.yumbase.repos['one'].enabled)
        self.assertFalse(self.yumbase.repos['two'].enabled)
        self.assertTrue(self.yumbase.repos['comb'].enabled)
        self.assertFalse(self.yumbase.repos["comb"].gpgcheck)
        self.assertFalse(self.yumbase.repos["comb"].repo_gpgcheck)
        self.assertEqual(self.yumbase.repos["comb"].sync_strategy,
                         dnf.repo.SYNC_ONLY_CACHE)

@mock.patch('dnf.logging.Logging.setup', new=mock.MagicMock)
class ConfigureTest(unittest.TestCase):
    def setUp(self):
        self.yumbase = support.MockYumBase("main")
        self.cli = dnf.cli.cli.Cli(self.yumbase)
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
        self.assertEqual(self.yumbase.conf.debuglevel, 6)
        self.assertEqual(self.yumbase.conf.errorlevel, 6)

    @mock.patch('dnf.yum.base.Base.read_conf_file')
    @mock.patch('dnf.cli.cli.Cli._parse_commands', new=mock.MagicMock)
    def test_installroot_explicit(self, read_conf_file):
        self.cli.base.basecmd = 'update'

        self.cli.configure(['--installroot', '/roots/dnf', 'update'])
        read_conf_file.assert_called_with('/etc/dnf/dnf.conf', '/roots/dnf', None,
                                          {'conffile': '/etc/dnf/dnf.conf',
                                           'installroot': '/roots/dnf'})

    @mock.patch('dnf.yum.base.Base.read_conf_file')
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
        self.assertEqual(self.yumbase.conf.installroot, '/roots/dnf')

class SearchTest(unittest.TestCase):
    def setUp(self):
        self.yumbase = support.MockYumBase("search")
        self.cli = dnf.cli.cli.Cli(self.yumbase)

        self.yumbase.fmtSection = lambda str: str
        self.yumbase.matchcallback = mock.MagicMock()

    def patched_search(self, *args, **kwargs):
        with mock.patch('sys.stdout') as stdout:
            self.cli.search(*args, **kwargs)
            pkgs = [c[0][0] for c in self.yumbase.matchcallback.call_args_list]
            return (stdout, pkgs)

    def test_search(self):
        (stdout, pkgs) = self.patched_search(['lotus'])
        pkg_names = map(str, pkgs)
        self.assertIn('lotus-3-16.i686', pkg_names)
        self.assertIn('lotus-3-16.x86_64', pkg_names)

    def test_search_caseness(self):
        (stdout, pkgs) = self.patched_search(['LOTUS'])
        self.assertEqual(stdout.write.mock_calls,
                         [mock.call(u'N/S Matched: LOTUS'), mock.call('\n')])
        pkg_names = map(str, pkgs)
        self.assertIn('lotus-3-16.i686', pkg_names)
        self.assertIn('lotus-3-16.x86_64', pkg_names)
