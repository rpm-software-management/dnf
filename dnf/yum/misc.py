# misc.py
# Copyright (C) 2012-2014  Red Hat, Inc.
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

"""
Assorted utility functions for yum.
"""

from __future__ import print_function, absolute_import
from __future__ import unicode_literals
from dnf.exceptions import MiscError
from dnf.pycomp import basestring, unicode, long
import os
import os.path
from io import StringIO
import base64
import binascii
import struct
import re
import errno
import dnf.exceptions
from . import pgpmsg
import tempfile
import glob
import pwd
import bz2
import gzip
import shutil
_available_compression = ['gz', 'bz2']
try:
    import lzma
    _available_compression.append('xz')
except ImportError:
    lzma = None

from stat import *
try:
    import gpgme
    import gpgme.editutil
except ImportError:
    gpgme = None

import hashlib
_available_checksums = set(['md5', 'sha1', 'sha256', 'sha384', 'sha512'])
_default_checksums = ['sha256']

import dnf.i18n
import dnf.const

_re_compiled_glob_match = None
def re_glob(s):
    """ Tests if a string is a shell wildcard. """
    # TODO/FIXME maybe consider checking if it is a stringsType before going on - otherwise
    # returning None
    global _re_compiled_glob_match
    if _re_compiled_glob_match is None:
        _re_compiled_glob_match = re.compile('[*?]|\[.+\]').search
    return _re_compiled_glob_match(s)

_re_compiled_full_match = None
def re_full_search_needed(s):
    """ Tests if a string needs a full nevra match, instead of just name. """
    global _re_compiled_full_match
    if _re_compiled_full_match is None:
        # A glob, or a "." or "-" separator, followed by something (the ".")
        one = re.compile('.*([-.*?]|\[.+\]).').match
        # Any epoch, for envra
        two = re.compile('[0-9]+:').match
        _re_compiled_full_match = (one, two)
    for rec in _re_compiled_full_match:
        if rec(s):
            return True
    return False


class Checksums(object):
    """ Generate checksum(s), on given pieces of data. Producing the
        Length and the result(s) when complete. """

    def __init__(self, checksums=None, ignore_missing=False, ignore_none=False):
        if checksums is None:
            checksums = _default_checksums
        self._sumalgos = []
        self._sumtypes = []
        self._len = 0

        done = set()
        for sumtype in checksums:
            if sumtype == 'sha':
                sumtype = 'sha1'
            if sumtype in done:
                continue

            if sumtype in _available_checksums:
                sumalgo = hashlib.new(sumtype)
            elif ignore_missing:
                continue
            else:
                raise MiscError('Error Checksumming, bad checksum type %s' % sumtype)
            done.add(sumtype)
            self._sumtypes.append(sumtype)
            self._sumalgos.append(sumalgo)
        if not done and not ignore_none:
            raise MiscError('Error Checksumming, no valid checksum type')

    def __len__(self):
        return self._len

    # Note that len(x) is assert limited to INT_MAX, which is 2GB on i686.
    length = property(fget=lambda self: self._len)

    def update(self, data):
        self._len += len(data)
        for sumalgo in self._sumalgos:
            data = data.encode('utf-8') if isinstance(data, unicode) else data
            sumalgo.update(data)

    def read(self, fo, size=2**16):
        data = fo.read(size)
        self.update(data)
        return data

    def hexdigests(self):
        ret = {}
        for sumtype, sumdata in zip(self._sumtypes, self._sumalgos):
            ret[sumtype] = sumdata.hexdigest()
        return ret

    def hexdigest(self, checksum=None):
        if checksum is None:
            if not self._sumtypes:
                return None
            checksum = self._sumtypes[0]
        if checksum == 'sha':
            checksum = 'sha1'
        return self.hexdigests()[checksum]

    def digests(self):
        ret = {}
        for sumtype, sumdata in zip(self._sumtypes, self._sumalgos):
            ret[sumtype] = sumdata.digest()
        return ret

    def digest(self, checksum=None):
        if checksum is None:
            if not self._sumtypes:
                return None
            checksum = self._sumtypes[0]
        if checksum == 'sha':
            checksum = 'sha1'
        return self.digests()[checksum]

def get_default_chksum_type():
    return _default_checksums[0]

def checksum(sumtype, file, CHUNK=2**16, datasize=None):
    """takes filename, hand back Checksum of it
       sumtype = md5 or sha/sha1/sha256/sha512 (note sha == sha1)
       filename = /path/to/file
       CHUNK=65536 by default"""

    # chunking brazenly lifted from Ryan Tomayko

    if isinstance(file, basestring):
        try:
            with open(file, 'rb', CHUNK) as fo:
                return checksum(sumtype, fo, CHUNK, datasize)
        except (IOError, OSError) as e:
            raise MiscError('Error opening file for checksum: %s' % file)

    try:
        # assumes file is a file-like-object
        data = Checksums([sumtype])
        while data.read(file, CHUNK):
            if datasize is not None and data.length > datasize:
                break

        # This screws up the length, but that shouldn't matter. We only care
        # if this checksum == what we expect.
        if datasize is not None and datasize != data.length:
            return '!%u!%s' % (datasize, data.hexdigest(sumtype))

        return data.hexdigest(sumtype)
    except (IOError, OSError) as e:
        raise MiscError('Error reading file for checksum: %s' % file)

def getFileList(path, ext, filelist):
    """Return all files in path matching ext, store them in filelist,
       recurse dirs return list object"""

    extlen = len(ext)
    try:
        dir_list = os.listdir(path)
    except OSError as e:
        raise MiscError(('Error accessing directory %s, %s') % (path, e))

    for d in dir_list:
        if os.path.isdir(path + '/' + d):
            filelist = getFileList(path + '/' + d, ext, filelist)
        else:
            if not ext or d[-extlen:].lower() == '%s' % (ext):
                newpath = os.path.normpath(path + '/' + d)
                filelist.append(newpath)

    return filelist

class GenericHolder(object):
    """Generic Holder class used to hold other objects of known types
       It exists purely to be able to do object.somestuff, object.someotherstuff
       or object[key] and pass object to another function that will
       understand it"""

    def __init__(self, iter=None):
        self.__iter = iter

    def __iter__(self):
        if self.__iter is not None:
            return iter(self[self.__iter])

    def __getitem__(self, item):
        if hasattr(self, item):
            return getattr(self, item)
        else:
            raise KeyError(item)

    def all_lists(self):
        """Return a dictionary of all lists."""
        return {key: list_ for key, list_ in vars(self).items()
                if type(list_) is list}

    def merge_lists(self, other):
        """ Concatenate the list attributes from 'other' to ours. """
        for (key, val) in other.all_lists().items():
            vars(self).setdefault(key, []).extend(val)
        return self

def procgpgkey(rawkey):
    '''Convert ASCII armoured GPG key to binary
    '''
    # TODO: CRC checking? (will RPM do this anyway?)

    # Normalise newlines
    rawkey = re.sub('\r\n?', '\n', rawkey)

    # Extract block
    block = StringIO()
    inblock = 0
    pastheaders = 0
    for line in rawkey.split('\n'):
        if line.startswith('-----BEGIN PGP PUBLIC KEY BLOCK-----'):
            inblock = 1
        elif inblock and line.strip() == '':
            pastheaders = 1
        elif inblock and line.startswith('-----END PGP PUBLIC KEY BLOCK-----'):
            # Hit the end of the block, get out
            break
        elif pastheaders and line.startswith('='):
            # Hit the CRC line, don't include this and stop
            break
        elif pastheaders:
            block.write(line+'\n')

    # Decode and return
    return base64.decodestring(block.getvalue().encode('utf-8'))

def gpgkey_fingerprint_ascii(info, chop=4):
    ''' Given a key_info data from getgpgkeyinfo(), return an ascii
    fingerprint. Chop every 4 ascii values, as that is what GPG does. '''
    # First "duh" ... it's a method...
    fp = info['fingerprint']()
    fp = binascii.hexlify(fp).decode()
    if chop:
        fp = [fp[i:i+chop] for i in range(0, len(fp), chop)]
        fp = " ".join(fp)
    return fp

def getgpgkeyinfo(rawkey, multiple=False):
    '''Return a dict of info for the given ASCII armoured key text

    Returned dict will have the following keys: 'userid', 'keyid', 'timestamp'

    Will raise ValueError if there was a problem decoding the key.
    '''
    # Catch all exceptions as there can be quite a variety raised by this call
    key_info_objs = []
    try:
        keys = pgpmsg.decode_multiple_keys(rawkey)
    except Exception as e:
        raise ValueError(str(e))
    if len(keys) == 0:
        raise ValueError('No key found in given key data')

    for key in keys:
        keyid_blob = key.public_key.key_id()

        info = {
            'userid': key.user_id,
            'keyid': struct.unpack(b'>Q', keyid_blob)[0],
            'timestamp': key.public_key.timestamp,
            'fingerprint' : key.public_key.fingerprint,
            'raw_key' : key.raw_key,
            'has_sig' : False,
            'valid_sig': False,
        }

        # Retrieve the timestamp from the matching signature packet
        # (this is what RPM appears to do)
        for userid in key.user_ids[0]:
            if not isinstance(userid, pgpmsg.signature):
                continue

            if userid.key_id() == keyid_blob:
                # Get the creation time sub-packet if available
                if hasattr(userid, 'hashed_subpaks'):
                    tspkt = \
                        userid.get_hashed_subpak(pgpmsg.SIG_SUB_TYPE_CREATE_TIME)
                    if tspkt != None:
                        info['timestamp'] = int(tspkt[1])
                        break
        key_info_objs.append(info)
    if multiple:
        return key_info_objs
    else:
        return key_info_objs[0]


def keyIdToRPMVer(keyid):
    '''Convert an integer representing a GPG key ID to the hex version string
    used by RPM
    '''
    return "%08x" % (keyid & long(0xffffffff))


def keyInstalled(ts, keyid, timestamp):
    '''
    Return if the GPG key described by the given keyid and timestamp are
    installed in the rpmdb.

    The keyid and timestamp should both be passed as integers.
    The ts is an rpm transaction set object

    Return values:
        - -1      key is not installed
        - 0       key with matching ID and timestamp is installed
        - 1       key with matching ID is installed but has a older timestamp
        - 2       key with matching ID is installed but has a newer timestamp

    No effort is made to handle duplicates. The first matching keyid is used to
    calculate the return result.
    '''
    # Convert key id to 'RPM' form
    keyid = keyIdToRPMVer(keyid)

    # Search
    for hdr in ts.dbMatch('name', 'gpg-pubkey'):
        if hdr['version'] == keyid:
            installedts = int(hdr['release'], 16)
            if installedts == timestamp:
                return 0
            elif installedts < timestamp:
                return 1
            else:
                return 2

    return -1

def import_key_to_pubring(rawkey, keyid, cachedir=None, gpgdir=None, make_ro_copy=True):
    # FIXME - cachedir can be removed from this method when we break api
    if gpgme is None:
        return False

    if not gpgdir:
        gpgdir = '%s/gpgdir' % cachedir

    if not os.path.exists(gpgdir):
        os.makedirs(gpgdir)

    key_fo = StringIO(rawkey)
    os.environ['GNUPGHOME'] = gpgdir
    # import the key
    ctx = gpgme.Context()
    fp = open(os.path.join(gpgdir, 'gpg.conf'), 'wb')
    fp.write('')
    fp.close()
    ctx.import_(key_fo)
    key_fo.close()
    # ultimately trust the key or pygpgme is definitionally stupid
    k = ctx.get_key(keyid)
    gpgme.editutil.edit_trust(ctx, k, gpgme.VALIDITY_ULTIMATE)

    if make_ro_copy:

        rodir = gpgdir + '-ro'
        if not os.path.exists(rodir):
            os.makedirs(rodir, mode=0o755)
            for f in glob.glob(gpgdir + '/*'):
                basename = os.path.basename(f)
                ro_f = rodir + '/' + basename
                shutil.copy(f, ro_f)
                os.chmod(ro_f, 0o755)
            fp = open(rodir + '/gpg.conf', 'w', 0o755)
            # yes it is this stupid, why do you ask?
            opts="""lock-never
no-auto-check-trustdb
trust-model direct
no-expensive-trust-checks
no-permission-warning
preserve-permissions
"""
            fp.write(opts)
            fp.close()


    return True

def return_keyids_from_pubring(gpgdir):
    if gpgme is None or not os.path.exists(gpgdir):
        return []

    os.environ['GNUPGHOME'] = gpgdir
    ctx = gpgme.Context()
    keyids = []
    for k in ctx.keylist():
        for subkey in k.subkeys:
            if subkey.can_sign:
                keyids.append(subkey.keyid)

    return keyids

def valid_detached_sig(sig_file, signed_file, gpghome=None):
    """takes signature , file that was signed and an optional gpghomedir"""

    if gpgme is None:
        return False

    if gpghome:
        if not os.path.exists(gpghome):
            return False
        os.environ['GNUPGHOME'] = gpghome

    if hasattr(sig_file, 'read'):
        sig = sig_file
    else:
        sig = open(sig_file, 'r')
    if hasattr(signed_file, 'read'):
        signed_text = signed_file
    else:
        signed_text = open(signed_file, 'r')
    plaintext = None
    ctx = gpgme.Context()

    try:
        sigs = ctx.verify(sig, signed_text, plaintext)
    except gpgme.GpgmeError as e:
        return False
    else:
        if not sigs:
            return False
        # is there ever a case where we care about a sig beyond the first one?
        thissig = sigs[0]
        if not thissig:
            return False

        if thissig.validity in (gpgme.VALIDITY_FULL, gpgme.VALIDITY_MARGINAL,
                                gpgme.VALIDITY_ULTIMATE):
            return True

    return False

def getCacheDir():
    """return a path to a valid and safe cachedir - only used when not running
       as root or when --tempcache is set"""

    uid = os.geteuid()
    try:
        usertup = pwd.getpwuid(uid)
        username = usertup[0]
    except KeyError:
        return None # if it returns None then, well, it's bollocksed

    # check for /var/tmp/dnf-username-* -
    prefix = '%s-%s-' % (dnf.const.PREFIX, username)
    dirpath = '%s/%s*' % (dnf.const.TMPDIR, prefix)
    cachedirs = sorted(glob.glob(dirpath))
    for thisdir in cachedirs:
        stats = os.lstat(thisdir)
        if S_ISDIR(stats[0]) and S_IMODE(stats[0]) == 448 and stats[4] == uid:
            return thisdir

    # make the dir (tempfile.mkdtemp())
    cachedir = tempfile.mkdtemp(prefix=prefix, dir=dnf.const.TMPDIR)
    return cachedir

def sortPkgObj(pkg1 ,pkg2):
    """sorts a list of yum package objects by name"""
    if pkg1.name > pkg2.name:
        return 1
    elif pkg1.name == pkg2.name:
        return 0
    else:
        return -1

def version_tuple_to_string(evrTuple):
    """
    Convert a tuple representing a package version to a string.

    @param evrTuple: A 3-tuple of epoch, version, and release.

    Return the string representation of evrTuple.
    """
    (e, v, r) = evrTuple
    s = ""

    if e not in [0, '0', None]:
        s += '%s:' % e
    if v is not None:
        s += '%s' % v
    if r is not None:
        s += '-%s' % r
    return s

def prco_tuple_to_string(prcoTuple):
    """returns a text string of the prco from the tuple format"""

    (name, flag, evr) = prcoTuple
    flags = {'GT':'>', 'GE':'>=', 'EQ':'=', 'LT':'<', 'LE':'<='}
    if flag is None:
        return name

    return '%s %s %s' % (name, flags[flag], version_tuple_to_string(evr))

def _decompress_chunked(source, dest, ztype):

    if ztype not in _available_compression:
        msg = "%s compression not available" % ztype
        raise dnf.exceptions.MiscError(msg)

    if ztype == 'bz2':
        s_fn = bz2.BZ2File(source, 'r')
    elif ztype == 'xz':
        s_fn = lzma.LZMAFile(source, 'r')
    elif ztype == 'gz':
        s_fn = gzip.GzipFile(source, 'r')


    destination = open(dest, 'wb')

    while True:
        try:
            data = s_fn.read(1024000)
        except IOError:
            break

        if not data: break

        try:
            destination.write(data)
        except (OSError, IOError) as e:
            msg = "Error writing to file %s: %s" % (dest, str(e))
            raise dnf.exceptions.MiscError(msg)

    destination.close()
    s_fn.close()

def bunzipFile(source,dest):
    """ Extract the bzipped contents of source to dest. """
    _decompress_chunked(source, dest, ztype='bz2')

def seq_max_split(seq, max_entries):
    """ Given a seq, split into a list of lists of length max_entries each. """
    ret = []
    num = len(seq)
    seq = list(seq) # Trying to use a set/etc. here is bad
    beg = 0
    while num > max_entries:
        end = beg + max_entries
        ret.append(seq[beg:end])
        beg += max_entries
        num -= max_entries
    ret.append(seq[beg:])
    return ret

def unlink_f(filename):
    """ Call os.unlink, but don't die if the file isn't there. This is the main
        difference between "rm -f" and plain "rm". """
    try:
        os.unlink(filename)
    except OSError as e:
        if e.errno != errno.ENOENT:
            raise

def stat_f(filename, ignore_EACCES=False):
    """ Call os.stat(), but don't die if the file isn't there. Returns None. """
    try:
        return os.stat(filename)
    except OSError as e:
        if e.errno in (errno.ENOENT, errno.ENOTDIR):
            return None
        if ignore_EACCES and e.errno == errno.EACCES:
            return None
        raise

def _getloginuid():
    """ Get the audit-uid/login-uid, if available. None is returned if there
        was a problem. Note that no caching is done here. """
    #  We might normally call audit.audit_getloginuid(), except that requires
    # importing all of the audit module. And it doesn't work anyway: BZ 518721
    try:
        with open("/proc/self/loginuid") as fo:
            data = fo.read()
            return int(data)
    except (IOError, ValueError):
        return None

_cached_getloginuid = None
def getloginuid():
    """ Get the audit-uid/login-uid, if available. None is returned if there
        was a problem. The value is cached, so you don't have to save it. """
    global _cached_getloginuid
    if _cached_getloginuid is None:
        _cached_getloginuid = _getloginuid()
    return _cached_getloginuid


# ---------- i18n ----------
import locale

def get_my_lang_code():
    try:
        mylang = locale.getlocale(locale.LC_MESSAGES)
    except ValueError as e:
        # This is RHEL-5 python crack, Eg. en_IN can't be parsed properly
        mylang = (None, None)
    if mylang == (None, None): # odd :)
        mylang = 'C'
    else:
        mylang = '.'.join(mylang)

    return mylang

def return_running_pids():
    """return list of running processids, excluding this one"""
    mypid = os.getpid()
    pids = []
    for fn in glob.glob('/proc/[0123456789]*'):
        if mypid == os.path.basename(fn):
            continue
        pids.append(os.path.basename(fn))
    return pids

def decompress(filename, dest=None, fn_only=False, check_timestamps=False):
    """take a filename and decompress it into the same relative location.
       if the file is not compressed just return the file"""

    out = dest
    if not dest:
        out = filename

    if filename.endswith('.gz'):
        ztype='gz'
        if not dest:
            out = filename.replace('.gz', '')

    elif filename.endswith('.bz') or filename.endswith('.bz2'):
        ztype='bz2'
        if not dest:
            if filename.endswith('.bz'):
                out = filename.replace('.bz','')
            else:
                out = filename.replace('.bz2', '')

    elif filename.endswith('.xz'):
        ztype='xz'
        if not dest:
            out = filename.replace('.xz', '')

    else:
        out = filename # returning the same file since it is not compressed
        ztype = None

    if ztype and not fn_only:
        if check_timestamps:
            fi = stat_f(filename)
            fo = stat_f(out)
            if fi and fo and fo.st_mtime == fi.st_mtime:
                return out

        _decompress_chunked(filename, out, ztype)
        if check_timestamps and fi:
            os.utime(out, (fi.st_mtime, fi.st_mtime))

    return out

def calculate_repo_gen_dest(filename, generated_name):
    dest = os.path.dirname(filename)
    dest += '/gen'
    if not os.path.exists(dest):
        os.makedirs(dest, mode=0o755)
    return dest + '/' + generated_name

def repo_gen_decompress(filename, generated_name, cached=False):
    """ This is a wrapper around decompress, where we work out a cached
        generated name, and use check_timestamps. filename _must_ be from
        a repo. and generated_name is the type of the file. """

    dest = calculate_repo_gen_dest(filename, generated_name)
    return decompress(filename, dest=dest, check_timestamps=True,fn_only=cached)

def read_in_items_from_dot_dir(thisglob, line_as_list=True):
    """ Takes a glob of a dir (like /etc/foo.d/\*.foo) returns a list of all the
       lines in all the files matching that glob, ignores comments and blank
       lines, optional paramater 'line_as_list tells whether to treat each line
       as a space or comma-separated list, defaults to True.
    """
    results = []
    for fname in glob.glob(thisglob):
        with open(fname) as f:
            for line in f:
                if re.match('\s*(#|$)', line):
                    continue
                line = line.rstrip() # no more trailing \n's
                line = line.lstrip() # be nice
                if not line:
                    continue
                if line_as_list:
                    line = line.replace('\n', ' ')
                    line = line.replace(',', ' ')
                    results.extend(line.split())
                    continue
                results.append(line)
    return results
