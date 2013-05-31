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

from __future__ import print_function
import rpm
import types
import gzip
import os
import sys
import locale
import signal

from error import RpmUtilsError
import transaction

def rpmOutToStr(arg):
    if type(arg) != types.StringType:
    # and arg is not None:
        arg = str(arg)

    return arg


def compareEVR((e1, v1, r1), (e2, v2, r2)):
    # return 1: a is newer than b
    # 0: a and b are the same version
    # -1: b is newer than a
    if e1 is None:
        e1 = '0'
    else:
        e1 = str(e1)
    v1 = str(v1)
    r1 = str(r1)
    if e2 is None:
        e2 = '0'
    else:
        e2 = str(e2)
    v2 = str(v2)
    r2 = str(r2)
    #print('%s, %s, %s vs %s, %s, %s' % (e1, v1, r1, e2, v2, r2))
    rc = rpm.labelCompare((e1, v1, r1), (e2, v2, r2))
    #print('%s, %s, %s vs %s, %s, %s = %s' % (e1, v1, r1, e2, v2, r2, rc))
    return rc

def compareVerOnly(v1, v2):
    """compare version strings only using rpm vercmp"""
    return compareEVR(('', v1, ''), ('', v2, ''))

def checkSig(ts, package):
    """Takes a transaction set and a package, check it's sigs,
    return 0 if they are all fine
    return 1 if the gpg key can't be found
    return 2 if the header is in someway damaged
    return 3 if the key is not trusted
    return 4 if the pkg is not gpg or pgp signed"""

    value = 0
    currentflags = ts.setVSFlags(0)
    fdno = os.open(package, os.O_RDONLY)
    try:
        hdr = ts.hdrFromFdno(fdno)
    except rpm.error, e:
        if str(e) == "public key not availaiable":
            value = 1
        if str(e) == "public key not available":
            value = 1
        if str(e) == "public key not trusted":
            value = 3
        if str(e) == "error reading package header":
            value = 2
    else:
        error, siginfo = getSigInfo(hdr)
        if error == 101:
            os.close(fdno)
            del hdr
            value = 4
        else:
            del hdr

    try:
        os.close(fdno)
    except OSError, e: # if we're not opened, don't scream about it
        pass

    ts.setVSFlags(currentflags) # put things back like they were before
    return value

def getSigInfo(hdr):
    """checks signature from an hdr hand back signature information and/or
       an error code"""

    locale.setlocale(locale.LC_ALL, 'C')
    string = '%|DSAHEADER?{%{DSAHEADER:pgpsig}}:{%|RSAHEADER?{%{RSAHEADER:pgpsig}}:{%|SIGGPG?{%{SIGGPG:pgpsig}}:{%|SIGPGP?{%{SIGPGP:pgpsig}}:{(none)}|}|}|}|'
    siginfo = hdr.sprintf(string)
    if siginfo != '(none)':
        error = 0
        sigtype, sigdate, sigid = siginfo.split(',')
    else:
        error = 101
        sigtype = 'MD5'
        sigdate = 'None'
        sigid = 'None'

    infotuple = (sigtype, sigdate, sigid)
    return error, infotuple

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


def splitFilename(filename):
    """
    Pass in a standard style rpm fullname

    Return a name, version, release, epoch, arch, e.g.::
        foo-1.0-1.i386.rpm returns foo, 1.0, 1, i386
        1:bar-9-123a.ia64.rpm returns bar, 9, 123a, 1, ia64
    """

    if filename[-4:] == '.rpm':
        filename = filename[:-4]

    archIndex = filename.rfind('.')
    arch = filename[archIndex+1:]

    relIndex = filename[:archIndex].rfind('-')
    rel = filename[relIndex+1:archIndex]

    verIndex = filename[:relIndex].rfind('-')
    ver = filename[verIndex+1:relIndex]

    epochIndex = filename.find(':')
    if epochIndex == -1:
        epoch = ''
    else:
        epoch = filename[:epochIndex]

    name = filename[epochIndex + 1:verIndex]
    return name, ver, rel, epoch, arch


def rpm2cpio(fdno, out=sys.stdout, bufsize=2048):
    """Performs roughly the equivalent of rpm2cpio(8).
       Reads the package from fdno, and dumps the cpio payload to out,
       using bufsize as the buffer size."""
    ts = transaction.initReadOnlyTransaction()
    hdr = ts.hdrFromFdno(fdno)
    del ts

    compr = hdr[rpm.RPMTAG_PAYLOADCOMPRESSOR] or 'gzip'
    #XXX FIXME
    #if compr == 'bzip2':
        # TODO: someone implement me!
    #el
    if compr != 'gzip':
        raise RpmUtilsError, \
              'Unsupported payload compressor: "%s"' % compr
    f = gzip.GzipFile(None, 'rb', None, os.fdopen(fdno, 'rb', bufsize))
    while 1:
        tmp = f.read(bufsize)
        if tmp == "": break
        out.write(tmp)
    f.close()

def flagToString(flags):
    flags = flags & 0xf

    if flags == 0: return None
    elif flags == 2: return 'LT'
    elif flags == 4: return 'GT'
    elif flags == 8: return 'EQ'
    elif flags == 10: return 'LE'
    elif flags == 12: return 'GE'

    return flags

def stringToVersion(verstring):
    if verstring in [None, '']:
        return (None, None, None)
    i = verstring.find(':')
    if i != -1:
        try:
            epoch = str(long(verstring[:i]))
        except ValueError:
            # look, garbage in the epoch field, how fun, kill it
            epoch = '0' # this is our fallback, deal
    else:
        epoch = '0'
    j = verstring.find('-')
    if j != -1:
        if verstring[i + 1:j] == '':
            version = None
        else:
            version = verstring[i + 1:j]
        release = verstring[j + 1:]
    else:
        if verstring[i + 1:] == '':
            version = None
        else:
            version = verstring[i + 1:]
        release = None
    return (epoch, version, release)

def hdrFromPackage(ts, package):
    """hand back the rpm header or raise an Error if the pkg is fubar"""
    try:
        fdno = os.open(package, os.O_RDONLY)
    except OSError, e:
        raise RpmUtilsError, 'Unable to open file'

    # XXX: We should start a readonly ts here, so we don't get the options
    # from the other one (sig checking, etc)
    try:
        hdr = ts.hdrFromFdno(fdno)
    except rpm.error, e:
        os.close(fdno)
        raise RpmUtilsError, "RPM Error opening Package"
    if type(hdr) != rpm.hdr:
        os.close(fdno)
        raise RpmUtilsError, "RPM Error opening Package (type)"

    os.close(fdno)
    return hdr

def headerFromFilename(filename):
    ts = transaction.initReadOnlyTransaction()
    hdr = hdrFromPackage(ts, filename)
    return hdr

def checkSignals():
    if hasattr(rpm, "checkSignals") and hasattr(rpm, 'signalsCaught'):
        if rpm.signalsCaught([signal.SIGINT,
                              signal.SIGTERM,
                              signal.SIGPIPE,
                              signal.SIGQUIT,
                              signal.SIGHUP]):
            sys.exit(1)

