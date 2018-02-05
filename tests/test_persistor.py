# -*- coding: utf-8 -*-

# Copyright (C) 2013-2018 Red Hat, Inc.
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

import tempfile

import dnf.comps
import dnf.persistor
import dnf.pycomp

import tests.support


IDS = set(['one', 'two', 'three'])


class RepoPersistorTest(tests.support.TestCase):
    def setUp(self):
        self.persistdir = tempfile.mkdtemp(prefix="dnf-persistor-test-")
        self.persistor = dnf.persistor.RepoPersistor(self.persistdir)

    def tearDown(self):
        dnf.util.rm_rf(self.persistdir)

    def test_expired_repos(self):
        self.assertLength(self.persistor.get_expired_repos(), 0)
        self.persistor.expired_to_add = IDS
        self.persistor.save()
        self.assertEqual(self.persistor.get_expired_repos(), IDS)

        persistor = dnf.persistor.RepoPersistor(self.persistdir)
        self.assertEqual(persistor.get_expired_repos(), IDS)
