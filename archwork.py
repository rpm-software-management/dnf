#!/usr/bin/python -t

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
# Copyright 2002 Duke University 

import os
import rpm
import re

def getArch():
    arch = os.uname()[4]
    if re.search('86', arch):
        arch = 'i386'
    if re.search('sparc', arch) or re.search('sun', arch):
        arch = 'sparc'
    if re.search('alpha', arch):
        arch = 'alpha'
    if re.search('ppc', arch):
        arch = 'ppc'
    return arch

def betterarch(arch1, arch2):
    """Take two archs, return the better of the two, returns none if both \
    of them come out to 0, returns either if they are the same archscore"""
    score1 = rpm.archscore(arch1)  
    score2 = rpm.archscore(arch2)  
    if score1 == 0 and score2 == 0:
        return None
    if score1 < score2:
        if score1 != 0:
            return arch1
        else:
            return arch2  
    if score2 < score1:
        if score2 != 0:
            return arch2
        else:
            return arch1   
    if score1 == score2:
        return arch1
    del score1
    del score2

def bestarch(archlist):
    currentarch = archlist[0]
    for arch in archlist[1:]:
        currentarch = betterarch(currentarch, arch)
    return currentarch


def compatArchList():
    archdict = {}
    archdict['i386']=['i386','i486','i586','i686','athlon','noarch']
    archdict['alpha']=['alpha','alphaev6','noarch']
    archdict['sparc']=['sparc','sparc64','noarch','sun4c','sun4u','sun4d','sun4m','sparcv9']
    archdict['ppc']=['ppc','noarch','ppc64','powerpc','powerppc','osfmach3_ppc','ppciseries','ppcpseries','rs6000']
    archdict['ia64']=['ia64','noarch', 'i686']
    archdict['s390']=['noarch','s390']
    archdict['s390x']=['noarch','s390','s390x']
    archdict['x86_64']=['noarch','x86_64']
    archdict['parisc']=['hppa2.0','hppa1.2','hppa1.2','hppa1.1','hppa1.0','paris','noarch']
    myarch=getArch()
    if archdict.has_key(myarch):
        archlist = archdict[myarch]
    else:
        archlist = [myarch, 'noarch']
    return archlist
    
def availablearchs(nevral, name):
    archlist = compatArchList()
    finalarchs = []
    for arch in archlist:
        if nevral.exists(name, arch):
            finalarchs.append(arch)
    return finalarchs


