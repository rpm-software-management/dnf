# -*- coding: utf-8 -*-

# Copyright (C) 2014-2018 Red Hat, Inc.
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
from __future__ import print_function
from __future__ import unicode_literals


import dnf.cli.commands.repoquery
import dnf.exceptions

import tests.support
from tests.support import mock


EXPECTED_INFO_FORMAT = """\
Name        : foobar
Version     : 1.0.1
Release     : 1.f20
Architecture: x86_64
Size        : 100
License     : BSD
Source RPM  : foo-1.0.1-1.f20.src.rpm
Build Date  : 1970-01-01 00:02
Packager    : Eastford
URL         : foorl.net
Summary     : it.
Description :
A desc.A desc.A desc.A desc.A desc.A desc.A desc.A desc.\n"""

EXPECTED_FILELIST_FORMAT = """\
/tmp/foobar
/var/foobar\
"""

EXPECTED_SOURCERPM_FORMAT = """\
foo-1.0.1-1.f20.src.rpm"""


class PkgStub(object):
    def __init__(self):
        self.arch = 'x86_64'
        self.buildtime = 120
        self.description = 'A desc.' * 8
        self.license = 'BSD'
        self.name = 'foobar'
        self.packager = 'Eastford'
        self.release = '1.f20'
        self.reponame = '@System'
        self._size = 100
        self.sourcerpm = 'foo-1.0.1-1.f20.src.rpm'
        self.summary = 'it.'
        self.url = 'foorl.net'
        self.version = '1.0.1'
        self.files = ['/tmp/foobar', '/var/foobar']


class ArgParseTest(tests.support.TestCase):
    def setUp(self):
        self.cmd = dnf.cli.commands.repoquery.RepoQueryCommand(
            tests.support.CliStub(tests.support.BaseCliStub()))

    def test_parse(self):
        tests.support.command_configure(self.cmd, ['--whatrequires', 'prudence'])
        self.assertEqual(self.cmd.opts.whatprovides, [])
        self.assertEqual(self.cmd.opts.whatrequires, ['prudence'])
        self.assertEqual(self.cmd.opts.queryformat,
                         dnf.cli.commands.repoquery.QFORMAT_DEFAULT)

    @mock.patch('argparse.ArgumentParser.print_help', lambda x: x)
    def test_conflict(self):
        with self.assertRaises(SystemExit) as sysexit, \
                tests.support.patch_std_streams() as (stdout, stderr):
                tests.support.command_configure(self.cmd, ['--conflicts', '%{name}', '--provides'])
        self.assertEqual(sysexit.exception.code, 1)

    def test_options(self):
        for arg in ('conflicts', 'enhances', 'provides',
                    'recommends', 'requires', 'suggests', 'supplements'):
            tests.support.command_configure(self.cmd, ['--' + arg])
            self.assertEqual(self.cmd.opts.packageatr, arg)

    def test_file(self):
        tests.support.command_configure(self.cmd, ['/var/foobar'])
        self.assertIsNone(self.cmd.opts.file)


class FilelistFormatTest(tests.support.TestCase):
    def test_filelist(self):
        self.cmd = dnf.cli.commands.repoquery.RepoQueryCommand(
            tests.support.CliStub(tests.support.BaseCliStub()))
        tests.support.command_configure(self.cmd, ['-l'])
        pkg = dnf.cli.commands.repoquery.PackageWrapper(PkgStub())
        self.assertEqual(self.cmd.build_format_fn(self.cmd.opts, pkg),
                         EXPECTED_FILELIST_FORMAT)


class SourceRPMFormatTest(tests.support.TestCase):
    def test_info(self):
        self.cmd = dnf.cli.commands.repoquery.RepoQueryCommand(
            tests.support.CliStub(tests.support.BaseCliStub()))
        tests.support.command_configure(self.cmd, ['--source'])
        pkg = dnf.cli.commands.repoquery.PackageWrapper(PkgStub())
        self.assertEqual(self.cmd.build_format_fn(self.cmd.opts, pkg),
                         EXPECTED_SOURCERPM_FORMAT)


class OutputTest(tests.support.TestCase):
    def test_output(self):
        pkg = dnf.cli.commands.repoquery.PackageWrapper(PkgStub())
        fmt = dnf.cli.commands.repoquery.rpm2py_format(
            '%{NAME}-%{version}-%{RELEASE}.%{arch} (%{REPONAME})')
        self.assertEqual(fmt.format(pkg), 'foobar-1.0.1-1.f20.x86_64 (@System)')

    def test_nonexistant_attr(self):
        """
        dnf.package.Package does not have a 'notfound' attribute.
        Therefore, rpm2py_format should leave a %{notfound}
        """
        pkg = dnf.cli.commands.repoquery.PackageWrapper(PkgStub())
        fmt = dnf.cli.commands.repoquery.rpm2py_format('%{notfound}').format(pkg)
        self.assertEqual(fmt, "%{notfound}")

    def test_illegal_attr(self):
        """
        dnf.package.Package has a 'base' attribute,
        but it isn't allowed in queryformat strings and
        should also leave a literal %{base}.
        """
        pkg = dnf.cli.commands.repoquery.PackageWrapper(PkgStub())
        fmt = dnf.cli.commands.repoquery.rpm2py_format("%{base}").format(pkg)
        self.assertEqual(fmt, "%{base}")

    def test_combo_attr(self):
        """
        Ensure that illegal attributes in a queryformat string along with legal
        attributes are properly escaped.
        """
        pkg = dnf.cli.commands.repoquery.PackageWrapper(PkgStub())
        fmt = dnf.cli.commands.repoquery.rpm2py_format(
            "%{name} | %{base} | {brackets}").format(pkg)
        self.assertEqual(fmt, "foobar | %{base} | {brackets}")


class Rpm2PyFormatTest(tests.support.TestCase):
    def test_rpm2py_format(self):
        fmt = dnf.cli.commands.repoquery.rpm2py_format('%{name}')
        self.assertEqual(fmt, '{0.name}')
        fmt = dnf.cli.commands.repoquery.rpm2py_format('%40{name}')
        self.assertEqual(fmt, '{0.name:<40}')
        fmt = dnf.cli.commands.repoquery.rpm2py_format('%-40{name}')
        self.assertEqual(fmt, '{0.name:>40}')
        fmt = dnf.cli.commands.repoquery.rpm2py_format(
            '%{name}-%{repoid} :: %-40{arch}')
        self.assertEqual(fmt, '{0.name}-{0.repoid} :: {0.arch:>40}')
