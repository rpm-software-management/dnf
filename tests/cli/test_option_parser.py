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
from dnf.cli.option_parser import OptionParser
from tests import support
from tests.support import mock

import argparse
import dnf.util


class OptionParserTest(support.TestCase):
    def test_parse(self):
        parser = OptionParser()
        opts, cmds = parser.parse_known_args(['update', '--nogpgcheck'])
        self.assertEqual(cmds, ['update'])
        self.assertTrue(opts.nogpgcheck)
        self.assertIsNone(opts.color)

    def test_configure_from_options(self):
        parser = OptionParser()
        opts, _ = parser.parse_known_args(['update', '-y', '--allowerasing'])
        conf = dnf.util.Bunch()
        conf.color = 'auto'
        demands = dnf.util.Bunch()
        parser.configure_from_options(opts, conf, demands, None)
        self.assertTrue(demands.allow_erasing)
        self.assertTrue(conf.assumeyes)

    def test_non_nones2dict(self):
        parser = OptionParser()
        values = parser.parse_args(args=['-y'])
        self.assertIsInstance(values, argparse.Namespace)
        dct = parser._non_nones2dict(values.__dict__)
        self.assertTrue(dct['assumeyes'])


class MyTestCommand(dnf.cli.commands.Command):

    aliases = ["test-cmd"]
    summary = 'summary'
    usage = 'usage'

    def __init__(self, cli):
        dnf.cli.commands.Command.__init__(self, cli)


@mock.patch('dnf.logging.Logging.setup', new=mock.MagicMock)
class UsageTest(support.TestCase):

    def setUp(self):
        self.base = support.MockBase("main")
        self.base._conf = dnf.conf.Conf()
        self.base.output = support.MockOutput()
        self.base.plugins = mock.Mock()
        self.cli = dnf.cli.cli.Cli(self.base)
        self.cli.command = mock.Mock()

    @mock.patch('dnf.cli.cli.Cli.read_conf_file')
    def test_OptParserAddCommand(self, read_conf_file):
        self.cli.configure(['info', 'foobar'])
        cmd = MyTestCommand(self.cli)
        self.cli.register_command(cmd)
        self.cli.optparser.add_commands(self.cli.cli_commands, "plugin")
        name = 'test-cmd'
        self.assertTrue(name in self.cli.optparser._cmd_usage)
        group, summary = self.cli.optparser._cmd_usage[name]
        self.assertEqual(group, 'plugin')
        self.assertEqual(summary, 'summary')

    @mock.patch('dnf.cli.cli.Cli.read_conf_file')
    def test_OptParserGetUsage(self, read_conf_file):
        self.cli.configure(['info', 'foobar'])
        cmd = MyTestCommand(self.cli)
        self.cli.register_command(cmd)
        self.cli.optparser.add_commands(self.cli.cli_commands, "plugin")
        usage = self.cli.optparser.get_usage().split('\n')
        self.assertEqual(usage[-2], 'test-cmd                  summary')

    def test_OptParserHelp(self):
        with self.assertRaises(SystemExit):
            self.cli.configure(['--help'])
