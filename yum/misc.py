import types
import string
import os
import os.path
from cStringIO import StringIO
import base64
import struct
import re
import pgpmsg
import rpm
import rpmUtils

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
        if type(file) is not types.StringType:
            fo = file # assume it's a file-like-object
        else:           
            fo = open(file, 'r', CHUNK)
            
        if sumtype == 'md5':
            import md5
            sum = md5.new()
        elif sumtype == 'sha':
            import sha
            sum = sha.new()
        else:
            raise MiscError, 'Error Checksumming file, bad checksum type %s' % sumtype
        chunk = fo.read
        while chunk: 
            chunk = fo.read(CHUNK)
            sum.update(chunk)

        if type(file) is types.StringType:
            fo.close()
            del fo
            
        return sum.hexdigest()
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
            if string.lower(d[-extlen:]) == '%s' % (ext):
               newpath = os.path.normpath(path + '/' + d)
               filelist.append(newpath)
                    
    return filelist

class GenericHolder:
    """Generic Holder class used to hold other objects of known types
       It exists purely to be able to do object.somestuff, object.someotherstuff
       and pass object to another function that will understand it"""
       
    pass


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

    info = {
        'userid': key.user_id,
        'keyid': key.public_key.key_id,
        'timestamp': key.public_key.timestamp,
    }

    # Retrieve the timestamp from the matching signature packet 
    # (this is what RPM appears to do) 
    for userid in key.user_ids[0]:
        if not isinstance(userid, pgpmsg.signature):
            continue

        keyid = struct.unpack(">Q", userid.key_id())[0]

        if keyid == key.public_key.key_id:
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


def keyInstalled(keyid, timestamp):
    '''Return if the GPG key described by the given keyid and timestamp are
    installed in the rpmdb.  

    The keyid and timestamp should both be passed as integers.

    Return values:
        -1      key is not installed
        0       key with matching ID and timestamp is installed
        1       key with matching ID is installed but has a older timestamp
        2       key with matching ID is installed but has a newer timestamp

    No effort is made to handle duplicates. The first matching keyid is used to 
    calculate the return result.
    '''
    # Convert key id to 'RPM' form
    keyid = keyIdToRPMVer(keyid)

    # Init transaction
    ts = rpmUtils.transaction.initReadOnlyTransaction()
    ts.pushVSFlags(~(rpm._RPMVSF_NOSIGNATURES|rpm._RPMVSF_NODIGESTS))

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
