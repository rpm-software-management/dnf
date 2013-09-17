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
from dnf.cli.format import format_time, format_number
import dnf.cli.progress
import dnf.repo
import dnf.repodict
import optparse
import os
import sys
import time
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
        self.yumbase = dnf.cli.cli.YumBaseCli()
        self.pkg = support.MockPackage('tour-5-0.noarch')
        self.pkg.from_system = False
        self.pkg.size = 0
        self.pkg.pkgid = None
        self.pkg.repoid = None
        self.pkg.e = self.pkg.epoch
        self.pkg.v = self.pkg.version
        self.pkg.r = self.pkg.release
        self.pkg.summary = 'A summary of the package.'
        self.pkg.url = 'http://example.com'
        self.pkg.license = 'GPL+'
        self.pkg.description = None

    def test_infoOutput_with_none_description(self):
        with mock.patch('sys.stdout') as stdout:
            self.yumbase.infoOutput(self.pkg)
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

class FormatTest(unittest.TestCase):
    def test_format_time(self):
        self.assertEquals(format_time(None), '--:--')
        self.assertEquals(format_time(-1), '--:--')
        self.assertEquals(format_time(12*60+34), '12:34')
        self.assertEquals(format_time(12*3600+34*60+56), '754:56')
        self.assertEquals(format_time(12*3600+34*60+56, use_hours=True), '12:34:56')
    def test_format_number(self):
        self.assertEquals(format_number(None), '0.0  ')
        self.assertEquals(format_number(-1), '-1  ')
        self.assertEquals(format_number(1.0), '1.0  ')
        self.assertEquals(format_number(999.0), '999  ')
        self.assertEquals(format_number(1000.0), '1.0 k')
        self.assertEquals(format_number(1 << 20), '1.0 M')
        self.assertEquals(format_number(1 << 30), '1.0 G')
        self.assertEquals(format_number(1e6, SI=1), '1.0 M')
        self.assertEquals(format_number(1e9, SI=1), '1.0 G')

class ProgressTest(unittest.TestCase):
    def test_single(self):
        now = 1379406823.9
        out = []
        with mock.patch('dnf.cli.progress._term_width', return_value=60), \
             mock.patch('dnf.cli.progress.time', lambda: now), \
             mock.patch('sys.stdout.write', lambda s: out.append(s)):

            p = dnf.cli.progress.LibrepoCallbackAdaptor(sys.stdout)
            p.begin('dummy-text')
            for i in range(6):
                p.librepo_cb(None, 5, i)
                self.assertEquals(len(out), i + 1) # always update
                now += 1.0
            p.end()

        # this is straightforward..
        self.assertEquals(out, [
            'dummy-text  0% [          ] ---  B/s |   0  B     --:-- ETA\r',
            'dummy-text 20% [==        ] 1.0  B/s |   1  B     00:04 ETA\r',
            'dummy-text 40% [====      ] 1.0  B/s |   2  B     00:03 ETA\r',
            'dummy-text 60% [======    ] 1.0  B/s |   3  B     00:02 ETA\r',
            'dummy-text 80% [========  ] 1.0  B/s |   4  B     00:01 ETA\r',
            'dummy-text                  1.0  B/s |   5  B     00:05    \n'])

    def test_restart(self):
        now = 1379406823.9
        out = []
        with mock.patch('dnf.cli.progress._term_width', return_value=60), \
             mock.patch('dnf.cli.progress.time', lambda: now), \
             mock.patch('sys.stdout.write', lambda s: out.append(s)):

            p = dnf.cli.progress.LibrepoCallbackAdaptor(sys.stdout)
            p.begin('dummy-text')
            for i in range(6):
                p.librepo_cb(None, 2 if i < 3 else 5, i)
                now += 1
            p.end()

        # when librepo downloads multiple metadata files, it changes the total
        # size reported by the callback. we should calculate progress with
        # the current total, and report both "finished" events.
        self.assertEquals(out, [
            'dummy-text  0% [          ] ---  B/s |   0  B     --:-- ETA\r',
            'dummy-text 50% [=====     ] 1.0  B/s |   1  B     00:01 ETA\r',
            'dummy-text                  1.0  B/s |   2  B     00:02    \n',
            'dummy-text 60% [======    ] 1.0  B/s |   3  B     00:02 ETA\r',
            'dummy-text 80% [========  ] 1.0  B/s |   4  B     00:01 ETA\r',
            'dummy-text                  1.0  B/s |   5  B     00:05    \n'])

    def test_multi(self):
        now = 1379406823.9
        out = []
        with mock.patch('dnf.cli.progress._term_width', return_value=60), \
             mock.patch('dnf.cli.progress.time', lambda: now), \
             mock.patch('sys.stdout.write', lambda s: out.append(s)):

            p = dnf.cli.progress.MultiFileProgressMeter(sys.stdout)
            p.start(2, 30)
            for i in range(11):
                # emit 1 update, or <end> & update
                n = len(out) + 1 + (i == 10)
                p('foo', 10.0, float(i))
                self.assertEquals(len(out), n)
                now += 0.5

                # on <end>, there should be no active dl
                n = len(out) + 1
                p('bar', 20.0, float(i*2))
                self.assertEquals(len(out), n)
                now += 0.5

        # check "end" events
        self.assertEquals([o for o in out if o.endswith('\n')], [
'(1/2): foo                  1.0  B/s |  10  B     00:10    \n',
'(2/2): bar                  2.0  B/s |  20  B     00:10    \n'])
        # verify we estimated a sane rate (should be around 3 B/s)
        self.assertTrue(2.0 < p.rate < 4.0)
