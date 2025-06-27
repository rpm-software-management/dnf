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
from __future__ import unicode_literals

import dnf.conf
from libdnf.conf import ConfigParser

import tests.support

substitute = ConfigParser.substitute


class ParserTest(tests.support.TestCase):
    def test_substitute(self):
        substs = {'lies': 'fact'}
        # Test a single word without braces
        rawstr = '$Substitute some $lies.'
        result = '$Substitute some fact.'
        self.assertEqual(substitute(rawstr, substs), result)
        # And with braces
        rawstr = '$Substitute some ${lies}.'
        self.assertEqual(substitute(rawstr, substs), result)

        # Test a word with braces without space
        rawstr = '$Substitute some ${lies}withoutspace.'
        result = '$Substitute some factwithoutspace.'
        self.assertEqual(substitute(rawstr, substs), result)

        # Tests a single brace before (no substitution)
        rawstr = '$Substitute some ${lieswithoutspace.'
        result = '$Substitute some ${lieswithoutspace.'
        self.assertEqual(substitute(rawstr, substs), result)

        # Tests a single brace after (substitution and leave the brace)
        rawstr = '$Substitute some $lies}withoutspace.'
        result = '$Substitute some fact}withoutspace.'
        self.assertEqual(substitute(rawstr, substs), result)

        # Test ${variable:-word} and ${variable:+word} shell-like expansion
        rawstr = '${lies:+alternate}-${unset:-default}-${nn:+n${nn:-${nnn:}'
        result = 'alternate-default-${nn:+n${nn:-${nnn:}'
        self.assertEqual(substitute(rawstr, substs), result)

    def test_empty_option(self):
        # Parser is able to read config file with option without value
        FN = tests.support.resource_path('etc/empty_option.conf')
        conf = dnf.conf.Conf()
        conf.config_file_path = FN
        conf.read()
        self.assertEqual(conf.reposdir, '')
