# crypto.py
# Keys and signatures.
#
# Copyright (C) 2014  Red Hat, Inc.
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

from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from dnf.i18n import _
import contextlib
import dnf.i18n
import dnf.util
import dnf.yum.misc
import gpgme
import io
import logging
import os
import tempfile


GPG_HOME_ENV = 'GNUPGHOME'
logger = logging.getLogger('dnf')


def _extract_signing_subkey(key):
    return dnf.util.first(subkey for subkey in key.subkeys if subkey.can_sign)


def _printable_fingerprint(fpr_hex):
    segments = (fpr_hex[i:i + 4] for i in range(0, len(fpr_hex), 4))
    return " ".join(segments)


def import_repo_keys(repo):
    gpgdir = repo._pubring_dir
    known_keys = keyids_from_pubring(gpgdir)
    for keyurl in repo.gpgkey:
        for keyinfo in retrieve(keyurl):
            keyid = keyinfo.id_
            if keyid in known_keys:
                logger.debug('repo %s: 0x%s already imported', repo.id, keyid)
                continue
            if not repo._key_import._confirm(keyinfo):
                continue
            dnf.yum.misc.import_key_to_pubring(
                keyinfo.raw_key, keyinfo.short_id, gpgdir=gpgdir,
                make_ro_copy=False)
            logger.debug('repo %s: imported key 0x%s.', repo.id, keyid)


def keyids_from_pubring(gpgdir):
    if not os.path.exists(gpgdir):
        return []

    with pubring_dir(gpgdir):
        ctx = gpgme.Context()
        keyids = []
        for k in ctx.keylist():
            subkey = _extract_signing_subkey(k)
            if subkey is not None:
                keyids.append(subkey.keyid)
        return keyids


def log_key_import(keyinfo):
    msg = (_('Importing GPG key 0x%s:\n'
             ' Userid     : "%s"\n'
             ' Fingerprint: %s\n'
             ' From       : %s') %
           (keyinfo.short_id, dnf.i18n.ucd(keyinfo.userid),
            _printable_fingerprint(keyinfo.fingerprint),
            keyinfo.url.replace("file://", "")))
    logger.critical("%s", msg)


@contextlib.contextmanager
def pubring_dir(pubring_dir):
    orig = os.environ.get(GPG_HOME_ENV, None)
    os.environ[GPG_HOME_ENV] = pubring_dir
    yield
    if orig is None:
        del os.environ[GPG_HOME_ENV]
    else:
        os.environ[GPG_HOME_ENV] = orig


def rawkey2infos(key_fo):
    pb_dir = tempfile.mkdtemp()
    keyinfos = []
    with pubring_dir(pb_dir):
        ctx = gpgme.Context()
        ctx.import_(key_fo)
        for key in ctx.keylist():
            subkey = _extract_signing_subkey(key)
            if subkey is None:
                continue
            keyinfos.append(Key(key, subkey))
        ctx.armor = True
        for info in keyinfos:
            buf = io.BytesIO()
            ctx.export(info.id_, buf)
            info.raw_key = buf.getvalue()
    dnf.util.rm_rf(pb_dir)
    return keyinfos


def retrieve(keyurl, repo=None):
    with dnf.util._urlopen(keyurl, repo=repo) as handle:
        keyinfos = rawkey2infos(handle)
    for keyinfo in keyinfos:
        keyinfo.url = keyurl
    return keyinfos


class Key(object):
    def __init__(self, key, subkey):
        self.id_ = subkey.keyid
        self.fingerprint = subkey.fpr
        self.raw_key = None
        self.timestamp = subkey.timestamp
        self.url = None
        self.userid = key.uids[0].uid

    @property
    def short_id(self):
        return self.id_[-8:].rjust(8, '0')

    @property
    def rpm_id(self):
        return self.short_id.lower()
