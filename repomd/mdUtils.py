#!/usr/bin/python -tt

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
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
# Copyright 2003 Duke University

import rpm
import types

def rpmOutToStr(arg):
    if type(arg) != types.StringType:
    # and arg is not None:
        arg = str(arg)
        
    return arg
    

def compareEVR((e1, v1, r1), (e2, v2, r2)):
    # return 1: a is newer than b
    # 0: a and b are the same version
    # -1: b is newer than a
    e1 = rpmOutToStr(e1)
    v1 = rpmOutToStr(v1)
    r1 = rpmOutToStr(r1)
    e2 = rpmOutToStr(e2)
    v2 = rpmOutToStr(v2)
    r2 = rpmOutToStr(r2)
    #print '%s, %s, %s vs %s, %s, %s' % (e1, v1, r1, e2, v2, r2)
    rc = rpm.labelCompare((e1, v1, r1), (e2, v2, r2))
    #print '%s, %s, %s vs %s, %s, %s = %s' % (e1, v1, r1, e2, v2, r2, rc)
    return rc

def newestInList(pkgs):
    # return the newest in the list of packages
    ret = [ pkgs.pop() ]
    newest = ret[0].returnEVR()
    for pkg in pkgs:
        rc = compareEVR(pkg.returnEVR(), newest)
        if rc > 0:
            ret = [ pkg ]
            newest = pkg.returnEVR()
        elif rc == 0:
            ret.append(pkg)
    return ret

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
