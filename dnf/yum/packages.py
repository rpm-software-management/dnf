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
# Copyright 2004 Duke University
# Written by Seth Vidal <skvidal at phy.duke.edu>

"""
Classes and functions dealing with rpm package representations.
"""

from __future__ import absolute_import
from __future__ import unicode_literals
from . import misc
import re
import fnmatch

def buildPkgRefDict(pkgs, casematch=True):
    """take a list of pkg objects and return a dict the contains all the possible
       naming conventions for them eg: for (name,i386,0,1,1)
       dict[name] = (name, i386, 0, 1, 1)
       dict[name.i386] = (name, i386, 0, 1, 1)
       dict[name-1-1.i386] = (name, i386, 0, 1, 1)
       dict[name-1] = (name, i386, 0, 1, 1)
       dict[name-1-1] = (name, i386, 0, 1, 1)
       dict[0:name-1-1.i386] = (name, i386, 0, 1, 1)
       dict[name-0:1-1.i386] = (name, i386, 0, 1, 1)
       """
    pkgdict = {}
    for pkg in pkgs:
        (n, a, e, v, r) = pkg.pkgtup
        if not casematch:
            n = n.lower()
            a = a.lower()
            e = e.lower()
            v = v.lower()
            r = r.lower()
        name = n
        nameArch = '%s.%s' % (n, a)
        nameVerRelArch = '%s-%s-%s.%s' % (n, v, r, a)
        nameVer = '%s-%s' % (n, v)
        nameVerRel = '%s-%s-%s' % (n, v, r)
        envra = '%s:%s-%s-%s.%s' % (e, n, v, r, a)
        nevra = '%s-%s:%s-%s.%s' % (n, e, v, r, a)
        for item in [name, nameArch, nameVerRelArch, nameVer, nameVerRel, envra, nevra]:
            if item not in pkgdict:
                pkgdict[item] = []
            pkgdict[item].append(pkg)

    return pkgdict

def parsePackages(pkgs, usercommands, casematch=0):
    """matches up the user request versus a pkg list:
       for installs/updates available pkgs should be the 'others list'
       for removes it should be the installed list of pkgs
       takes an optional casematch option to determine if case should be matched
       exactly. Defaults to not matching."""

    pkgdict = buildPkgRefDict(pkgs, bool(casematch))
    exactmatch = set()
    matched = set()
    unmatched = set()
    for command in usercommands:
        if not casematch:
            command = command.lower()
        if command in pkgdict:
            exactmatch.update(pkgdict[command])
            del pkgdict[command]
        else:
            # anything we couldn't find a match for
            # could mean it's not there, could mean it's a wildcard
            if misc.re_glob(command):
                trylist = pkgdict.keys()
                # command and pkgdict are already lowered if not casematch
                # so case sensitive is always fine
                restring = fnmatch.translate(command)
                regex = re.compile(restring)
                foundit = 0
                for item in trylist:
                    if regex.match(item):
                        matched.update(pkgdict[item])
                        del pkgdict[item]
                        foundit = 1

                if not foundit:
                    unmatched.add(command)

            else:
                unmatched.add(command)

    return exactmatch, matched, unmatched
