# -*- coding: utf-8 -*-

# Copyright (C) 2014-2018  Red Hat, Inc.
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
import tempfile

import dnf.crypto
import dnf.util
import dnf.yum.misc

import tests.support


FINGERPRINT = '88FBCE424BA9952A141A6A297B5443AEAA6F01F3'
KEYFILE = tests.support.resource_path('keys/key.pub')
KEYFILE_URL = 'file://%s' % KEYFILE


class CryptoTest(tests.support.TestCase):
    PUBRING_DIR = None

    @classmethod
    def setUpClass(cls):
        cls.PUBRING_DIR = tempfile.mkdtemp()
        with open(KEYFILE, 'rb') as keyfile:
            keyinfo = dnf.crypto.rawkey2infos(keyfile)[0]
        dnf.yum.misc.import_key_to_pubring(
            keyinfo.raw_key, keyinfo.short_id, gpgdir=cls.PUBRING_DIR,
            make_ro_copy=False)

    @classmethod
    def tearDownClass(cls):
        dnf.util.rm_rf(cls.PUBRING_DIR)

    def test_keyids_from_pubring(self):
        ids = dnf.crypto.keyids_from_pubring(self.PUBRING_DIR)
        self.assertIn('7B5443AEAA6F01F3', ids)

    def test_printable_fingerprint(self):
        self.assertEqual(dnf.crypto._printable_fingerprint(FINGERPRINT),
                         '88FB CE42 4BA9 952A 141A 6A29 7B54 43AE AA6F 01F3')

    def test_pubring_dir(self):
        self.assertNotEqual(os.environ.get('GNUPGHOME'), self.PUBRING_DIR)
        with dnf.crypto.pubring_dir(self.PUBRING_DIR):
            self.assertEqual(os.environ['GNUPGHOME'], self.PUBRING_DIR)

    def test_rawkey2infos(self):
        with open(KEYFILE, 'rb') as keyfile:
            info = dnf.crypto.rawkey2infos(keyfile)[0]
        self.assertEqual(info.fingerprint, FINGERPRINT)
        self.assertEqual(info.short_id, 'AA6F01F3')
        self.assertEqual(info.rpm_id, 'aa6f01f3')
        self.assertIn(b'E4bO2zVZwe\n', info.raw_key)
        self.assertEqual(info.timestamp, 1721738657)
        self.assertEqual(info.userid, 'Dandy Fied <dnf@example.com>')

    def test_retrieve(self):
        keyinfos = dnf.crypto.retrieve(KEYFILE_URL)
        self.assertLength(keyinfos, 1)
        keyinfo = keyinfos[0]
        self.assertEqual(keyinfo.url, KEYFILE_URL)
