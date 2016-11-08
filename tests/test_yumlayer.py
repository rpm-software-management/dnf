# Copyright (C) 2016  Red Hat, Inc.
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

"""Tests of the Yum compatible layer."""

from __future__ import unicode_literals
from tests.support import mock
import dnf.cli
import dnf.conf.config
import dnf.yum.option_parser
import dnf.yum.config
import dnf.yum.cli
import dnf.logging
import dnf.pycomp
import dnf.yum.cli
import dnf.yum.config
import dnf.yum.option_parser
import tests.support



def _parse(command, args):
    parser = dnf.yum.option_parser.YumOptionParser()
    return parser.parse_main_args(args), parser.parse_command_args(command, args)


def _compare_options(test, options):
    for option in options:
        test.assertNotEqual(test.conf._get_option(option),
                            test.dnf_conf._get_option(option),
                            option + " is equal in yum and dnf config")


class YumConfigTest(tests.support.TestCase):
    def setUp(self):
        self.conf = dnf.yum.config.YumConf()
        self.dnf_conf = dnf.conf.config.MainConf()

    def test_different_options(self):
        self.assertNotEqual(self.conf, self.dnf_conf)
        _compare_options(self,
                         ['exclude', 'persistdir',
                          'system_cachedir', 'keepcache', 'installonly_limit',
                          'timeout', 'metadata_expire', 'best',
                          'clean_requirements_on_remove'])


class YumArgumentParserTest(tests.support.TestCase):
    def setUp(self):
        self.cli = mock.Mock()
        self.command = TestCommand(self.cli)

    def test_skip_broken(self):
        arg_opts, command_opts = _parse(self.command, ['update', '--skip-broken'])
        self.assertEqual(command_opts.command, ['update'])
        self.assertIsNone(arg_opts.best)

    def test_skip_broken_none(self):
        arg_opts, command_opts = _parse(self.command, ['update'])
        self.assertEqual(command_opts.command, ['update'])
        self.assertTrue(arg_opts.best)


class YumProvidesCommandTest(tests.support.TestCase):
    def setUp(self):
        self.cli = mock.Mock()
        self.command = dnf.cli.commands.ProvidesCommand(self.cli)

    def test_provides_command(self):
        _parse(self.command, [u'provides', u'nf'])
        self.assertEqual(self.command.opts.dependency, [u'*nf*'])

        _parse(self.command, [u'provides', u'nf*'])
        self.assertEqual(self.command.opts.dependency, [u'*nf*'])

        _parse(self.command, [u'provides', u'*nf'])
        self.assertEqual(self.command.opts.dependency, [u'*nf*'])

        _parse(self.command, [u'provides', u'*nf*'])
        self.assertEqual(self.command.opts.dependency, [u'*nf*'])


class YumCustomCommandTest(tests.support.TestCase):
    def setUp(self):
        self.conf = dnf.yum.config.YumConf()
        self.base = dnf.cli.cli.BaseCli(self.conf)
        self.cli = dnf.yum.cli.YumCli(self.base)
        self.command = TestCommand(self.cli)

        self.cli.register_command(TestCommand)
        pass

    def test_custom_command(self):
        args = [u'test-cmd']
        opts, _ = _parse(self.command, args)
        self.cli._parse_commands(opts, args)

    def test_unknown_command(self):
        args = [u'unknown']
        opts, _ = _parse(self.command, args)
        try:
            self.cli._parse_commands(opts, args)
        except dnf.cli.CliError:
            return

        self.fail("Not existing command should not be recognized.")


class TestCommand(dnf.cli.commands.Command):
    aliases = ["test-cmd"]
    summary = 'summary'

    def __init__(self, cli):
        dnf.cli.commands.Command.__init__(self, cli)
