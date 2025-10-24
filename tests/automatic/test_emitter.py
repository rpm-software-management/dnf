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
# GNU General Public License along with this program; if not, see
# <https://www.gnu.org/licenses/>.  Any Red Hat trademarks that are
# incorporated in the source code or documentation are not subject to the GNU
# General Public License and may only be used or replicated with the express
# permission of Red Hat, Inc.
#

from __future__ import absolute_import
from __future__ import unicode_literals

import dnf.automatic.emitter

import tests.support
from tests.support import mock, mock_open


MSG = """\
downloaded on myhost:
packages..."""


class TestEmitter(tests.support.TestCase):
    def test_prepare_msg(self):
        emitter = dnf.automatic.emitter.Emitter('myhost')
        emitter.notify_available('packages...')
        emitter.notify_downloaded()
        with mock.patch('dnf.automatic.emitter.DOWNLOADED', 'downloaded on %s:'):
            self.assertEqual(emitter._prepare_msg(), MSG)


class TestMotdEmitter(tests.support.TestCase):
    def test_motd(self):
        m = mock_open()
        with mock.patch('dnf.automatic.emitter.open', m, create=True):
            emitter = dnf.automatic.emitter.MotdEmitter('myhost')
            emitter.notify_available('packages...')
            emitter.notify_downloaded()
            with mock.patch('dnf.automatic.emitter.DOWNLOADED', 'downloaded on %s:'):
                emitter.commit()
            handle = m()
            handle.write.assert_called_once_with(MSG)
