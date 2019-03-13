# -*- coding: utf-8 -*-

# Copyright (C) 2019 Red Hat, Inc.
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

import os

import dnf.conf

import tests.support


FN = tests.support.resource_path('etc/repos.conf')


class SubstitutionsFromEnvironmentTest(tests.support.TestCase):
    def test_numeric(self):
        env = os.environ
        os.environ['DNF0'] = 'the_zero'
        conf = dnf.conf.Conf()
        os.environ = env
        self.assertIn('DNF0', conf.substitutions)
        self.assertEqual('the_zero', conf.substitutions['DNF0'])

    def test_named(self):
        env = os.environ
        os.environ['DNF_VAR_GENRE'] = 'opera'
        os.environ['DNF_VAR_EMPTY'] = ''
        os.environ['DNF_VAR_MAL$FORMED'] = 'not this'
        os.environ['DNF_VARMALFORMED'] = 'not this'
        os.environ['DNF_VAR_MALFORMED '] = 'not this'
        conf = dnf.conf.Conf()
        os.environ = env
        self.assertCountEqual(
            conf.substitutions.keys(),
            ['basearch', 'arch', 'DNF_VAR_GENRE', 'DNF_VAR_EMPTY'])
        self.assertEqual('opera', conf.substitutions['DNF_VAR_GENRE'])
