"""
Assorted utility functions for yum.
"""

import types
import os
import os.path
from cStringIO import StringIO
import base64
import struct
import re
import pgpmsg
import tempfile
import glob
import pwd
import fnmatch
import bz2
from stat import *
import gpgme

from Errors import MiscError

###########
# Title: Remove duplicates from a sequence
# Submitter: Tim Peters 
# From: http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/52560                      
    
def unique(s):
    """Return a list of the elements in s, but without duplicates.

    For example, unique([1,2,3,1,2,3]) is some permutation of [1,2,3],
    unique("abcabc") some permutation of ["a", "b", "c"], and
    unique(([1, 2], [2, 3], [1, 2])) some permutation of
    [[2, 3], [1, 2]].

    For best speed, all sequence elements should be hashable.  Then
    unique() will usually work in linear time.

    If not possible, the sequence elements should enjoy a total
    ordering, and if list(s).sort() doesn't raise TypeError it's
    assumed that they do enjoy a total ordering.  Then unique() will
    usually work in O(N*log2(N)) time.

    If that's not possible either, the sequence elements must support
    equality-testing.  Then unique() will usually work in quadratic
    time.
    """

    n = len(s)
    if n == 0:
        return []

    # Try using a dict first, as that's the fastest and will usually
    # work.  If it doesn't work, it will usually fail quickly, so it
    # usually doesn't cost much to *try* it.  It requires that all the
    # sequence elements be hashable, and support equality comparison.
    u = {}
    try:
        for x in s:
            u[x] = 1
    except TypeError:
        del u  # move on to the next method
    else:
        return u.keys()

    # We can't hash all the elements.  Second fastest is to sort,
    # which brings the equal elements together; then duplicates are
    # easy to weed out in a single pass.
    # NOTE:  Python's list.sort() was designed to be efficient in the
    # presence of many duplicate elements.  This isn't true of all
    # sort functions in all languages or libraries, so this approach
    # is more effective in Python than it may be elsewhere.
    try:
        t = list(s)
        t.sort()
    except TypeError:
        del t  # move on to the next method
    else:
        assert n > 0
        last = t[0]
        lasti = i = 1
        while i < n:
            if t[i] != last:
                t[lasti] = last = t[i]
                lasti += 1
            i += 1
        return t[:lasti]

    # Brute force is all that's left.
    u = []
    for x in s:
        if x not in u:
            u.append(x)
    return u

def checksum(sumtype, file, CHUNK=2**16):
    """takes filename, hand back Checksum of it
       sumtype = md5 or sha
       filename = /path/to/file
       CHUNK=65536 by default"""
       
    # chunking brazenly lifted from Ryan Tomayko
    try:
        if type(file) not in types.StringTypes:
            fo = file # assume it's a file-like-object
        else:           
            fo = open(file, 'r', CHUNK)
            
        if sumtype == 'md5':
            import md5
            sumalgo = md5.new()
        elif sumtype == 'sha':
            import sha
            sumalgo = sha.new()
        else:
            raise MiscError, 'Error Checksumming file, bad checksum type %s' % sumtype
        chunk = fo.read
        while chunk: 
            chunk = fo.read(CHUNK)
            sumalgo.update(chunk)

        if type(file) is types.StringType:
            fo.close()
            del fo
            
        return sumalgo.hexdigest()
    except (IOError, OSError), e:
        raise MiscError, 'Error opening file for checksum: %s' % file

def getFileList(path, ext, filelist):
    """Return all files in path matching ext, store them in filelist, 
       recurse dirs return list object"""
    
    extlen = len(ext)
    try:
        dir_list = os.listdir(path)
    except OSError, e:
        raise MiscError, ('Error accessing directory %s, %s') % (path, e)
        
    for d in dir_list:
        if os.path.isdir(path + '/' + d):
            filelist = getFileList(path + '/' + d, ext, filelist)
        else:
            if d[-extlen:].lower() == '%s' % (ext):
               newpath = os.path.normpath(path + '/' + d)
               filelist.append(newpath)
                    
    return filelist

class GenericHolder:
    """Generic Holder class used to hold other objects of known types
       It exists purely to be able to do object.somestuff, object.someotherstuff
       or object[key] and pass object to another function that will 
       understand it"""
       
    def __getitem__(self, item):
        if hasattr(self, item):
            return getattr(self, item)
        else:
            raise KeyError, item

def procgpgkey(rawkey):
    '''Convert ASCII armoured GPG key to binary
    '''
    # TODO: CRC checking? (will RPM do this anyway?)
    
    # Normalise newlines
    rawkey = re.compile('(\n|\r\n|\r)').sub('\n', rawkey)

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
    return base64.decodestring(block.getvalue())

def getgpgkeyinfo(rawkey):
    '''Return a dict of info for the given ASCII armoured key text

    Returned dict will have the following keys: 'userid', 'keyid', 'timestamp'

    Will raise ValueError if there was a problem decoding the key.
    '''
    # Catch all exceptions as there can be quite a variety raised by this call
    try:
        key = pgpmsg.decode_msg(rawkey)
    except Exception, e:
        raise ValueError(str(e))
    if key is None:
        raise ValueError('No key found in given key data')

    keyid_blob = key.public_key.key_id()

    info = {
        'userid': key.user_id,
        'keyid': struct.unpack('>Q', keyid_blob)[0],
        'timestamp': key.public_key.timestamp,
        'fingerprint' : key.public_key.fingerprint,
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
        
    return info

def keyIdToRPMVer(keyid):
    '''Convert an integer representing a GPG key ID to the hex version string
    used by RPM
    '''
    return "%08x" % (keyid & 0xffffffffL)


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

def import_key_to_pubring(rawkey, repo_cachedir):
    gpgdir = '%s/gpgdir' % repo_cachedir
    if not os.path.exists(gpgdir):
        os.makedirs(gpgdir)
    
    key_fo = StringIO(rawkey) 
    ctx = gpgme.Context()
    os.environ['GNUPGHOME'] = gpgdir
    fp = open(os.path.join(gpgdir, 'gpg.conf'), 'wb')
    fp.write('')
    fp.close()
    ctx.import_(key_fo)
    key_fo.close()
    
def return_keyids_from_pubring(gpgdir):
    ctx = gpgme.Context()
    if not os.path.exists(gpgdir):
        return []
        
    os.environ['GNUPGHOME'] = gpgdir
    keyids = []
    for k in ctx.keylist():
        for subkey in k.subkeys:
            if subkey.can_sign:
                keyids.append(subkey.keyid)

    return keyids
        
def getCacheDir(tmpdir='/var/tmp'):
    """return a path to a valid and safe cachedir - only used when not running
       as root or when --tempcache is set"""
    
    uid = os.geteuid()
    try:
        usertup = pwd.getpwuid(uid)
        username = usertup[0]
    except KeyError:
        return None # if it returns None then, well, it's bollocksed

    # check for /var/tmp/yum-username-* - 
    prefix = 'yum-%s-' % username    
    dirpath = '%s/%s*' % (tmpdir, prefix)
    cachedirs = glob.glob(dirpath)
    
    for thisdir in cachedirs:
        stats = os.lstat(thisdir)
        if S_ISDIR(stats[0]) and S_IMODE(stats[0]) == 448 and stats[4] == uid:
            return thisdir

    # make the dir (tempfile.mkdtemp())
    cachedir = tempfile.mkdtemp(prefix=prefix, dir=tmpdir)
    return cachedir

def sortPkgObj(pkg1 ,pkg2):
    """sorts a list of yum package objects by name"""
    if pkg1.name > pkg2.name:
        return 1
    elif pkg1.name == pkg2.name:
        return 0
    else:
        return -1
        
def newestInList(pkgs):
    """ Return the newest in the list of packages. """
    ret = [ pkgs.pop() ]
    newest = ret[0]
    for pkg in pkgs:
        if pkg.EVR > newest.EVR:
            ret = [ pkg ]
            newest = pkg
        elif pkg.EVR == newest.EVR:
            ret.append(pkg)
    return ret

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
    
def refineSearchPattern(arg):
    """Takes a search string from the cli for Search or Provides
       and cleans it up so it doesn't make us vomit"""
    
    if re.match('.*[\*,\[,\],\{,\},\?,\+].*', arg):
        restring = fnmatch.translate(arg)
    else:
        restring = re.escape(arg)
        
    return restring
    
def bunzipFile(source,dest):
    """ Extract the bzipped contents of source to dest. """
    s_fn = bz2.BZ2File(source, 'r')
    destination = open(dest, 'w')

    while True:
        try:
            data = s_fn.read(1024000)
        except IOError:
            break
        
        if not data: break
        destination.write(data)

    destination.close()
    s_fn.close()

def get_running_kernel_version_release(ts):
    """This takes the output of uname and figures out the (version, release)
    tuple for the running kernel."""
    ver = os.uname()[2]
    reduced = ver
    # FIXME this should probably get passed this list from somewhere in config
    # possibly from the kernelpkgnames option
    for s in ("bigmem", "enterprise", "smp", "hugemem", "PAE", "rt",
              "guest", "hypervisor", "xen0", "xenU", "xen", "debug",
              "PAE-debug"):
        if ver.endswith(s):
            reduced = ver.replace(s, "")
            
    if reduced.find("-") != -1:
        (v, r) = reduced.split("-", 1)
        return (v, r)
    
    # we've got nothing so far, so... we glob for the file that MIGHT have
    # this kernels and then look up the file in our rpmdb
    fns = glob.glob('/boot/vmlinuz*%s*' % ver)
    for fn in fns:
        mi = ts.dbMatch('basenames', fn)
        for h in mi:
            return (h['version'], h['release'])
    
    return (None, None)
 

def find_unfinished_transactions(yumlibpath='/var/lib/yum'):
    """returns a list of the timestamps from the filenames of the unfinished 
       transactions remaining in the yumlibpath specified.
    """
    timestamps = []    
    tsallg = '%s/%s' % (yumlibpath, 'transaction-all*')
    tsdoneg = '%s/%s' % (yumlibpath, 'transaction-done*')
    tsalls = glob.glob(tsallg)
    tsdones = glob.glob(tsdoneg)

    for fn in tsalls:
        trans = os.path.basename(fn)
        timestamp = trans.replace('transaction-all.','')
        timestamps.append(timestamp)

    timestamps.sort()
    return timestamps
    
def find_ts_remaining(timestamp, yumlibpath='/var/lib/yum'):
    """this function takes the timestamp of the transaction to look at and 
       the path to the yum lib dir (defaults to /var/lib/yum)
       returns a list of tuples(action, pkgspec) for the unfinished transaction
       elements. Returns an empty list if none.

    """
    
    to_complete_items = []
    tsallpath = '%s/%s.%s' % (yumlibpath, 'transaction-all', timestamp)    
    tsdonepath = '%s/%s.%s' % (yumlibpath,'transaction-done', timestamp)
    tsdone_items = []

    if not os.path.exists(tsallpath):
        # something is wrong, here, probably need to raise _something_
        return to_complete_items    

            
    if os.path.exists(tsdonepath):
        tsdone_fo = open(tsdonepath, 'r')
        tsdone_items = tsdone_fo.readlines()
        tsdone_fo.close()     
    
    tsall_fo = open(tsallpath, 'r')
    tsall_items = tsall_fo.readlines()
    tsall_fo.close()
    
    for item in tsdone_items:
        # this probably shouldn't happen but it's worth catching anyway
        if item not in tsall_items:
            continue        
        tsall_items.remove(item)
        
    for item in tsall_items:
        item = item.replace('\n', '')
        if item == '':
            continue
        (action, pkgspec) = item.split()
        to_complete_items.append((action, pkgspec))
    
    return to_complete_items
    
        
