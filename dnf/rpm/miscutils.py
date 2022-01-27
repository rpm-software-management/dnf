# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# Copyright 2003 Duke University

from __future__ import print_function, absolute_import, unicode_literals

import os
import subprocess
import logging
from shutil import which

from dnf.i18n import _

_logger = logging.getLogger('dnf')
_rpmkeys_binary = None

def _find_rpmkeys_binary():
    global _rpmkeys_binary
    if _rpmkeys_binary is None:
        _rpmkeys_binary = which("rpmkeys")
        _logger.debug(_('Using rpmkeys executable at %s to verify signatures'),
                      _rpmkeys_binary)
    return _rpmkeys_binary

def _process_rpm_output(data):
    # No signatures or digests = corrupt package.
    # There is at least one line for -: and another (empty) entry after the
    # last newline.
    if len(data) < 3 or data[0] != b'-:' or data[-1]:
        return 2
    seen_sig, missing_key, not_trusted, not_signed = False, False, False, False
    for i in data[1:-1]:
        if b': BAD' in i:
            return 2
        elif i.endswith(b': NOKEY'):
            missing_key = True
        elif i.endswith(b': NOTTRUSTED'):
            not_trusted = True
        elif i.endswith(b': NOTFOUND'):
            not_signed = True
        elif not i.endswith(b': OK'):
            return 2
    if not_trusted:
        return 3
    elif missing_key:
        return 1
    elif not_signed:
        return 4
    # we still check return code, so this is safe
    return 0

def _verifyPackageUsingRpmkeys(package, installroot):
    rpmkeys_binary = _find_rpmkeys_binary()
    if rpmkeys_binary is None or not os.path.isfile(rpmkeys_binary):
        _logger.critical(_('Cannot find rpmkeys executable to verify signatures.'))
        return 2

    # "--define=_pkgverify_level signature" enforces signature checking;
    # "--define=_pkgverify_flags 0x0" ensures that all signatures are checked.
    args = ('rpmkeys', '--checksig', '--root', installroot, '--verbose',
            '--define=_pkgverify_level signature', '--define=_pkgverify_flags 0x0',
            '-')
    env = dict(os.environ)
    env['LC_ALL'] = 'C'
    with subprocess.Popen(
            args=args,
            executable=rpmkeys_binary,
            env=env,
            stdout=subprocess.PIPE,
            cwd='/',
            stdin=package) as p:
        data = p.communicate()[0]
    returncode = p.returncode
    if type(returncode) is not int:
        raise AssertionError('Popen set return code to non-int')
    # rpmkeys can return something other than 0 or 1 in the case of a
    # fatal error (OOM, abort() called, SIGSEGV, etc)
    if returncode >= 2 or returncode < 0:
        return 2
    ret = _process_rpm_output(data.split(b'\n'))
    if ret:
        return ret
    return 2 if returncode else 0

def checkSig(ts, package):
    """Takes a transaction set and a package, check it's sigs,
    return 0 if they are all fine
    return 1 if the gpg key can't be found
    return 2 if the header is in someway damaged
    return 3 if the key is not trusted
    return 4 if the pkg is not gpg or pgp signed"""

    fdno = os.open(package, os.O_RDONLY|os.O_NOCTTY|os.O_CLOEXEC)
    try:
        value = _verifyPackageUsingRpmkeys(fdno, ts.ts.rootDir)
    finally:
        os.close(fdno)
    return value
