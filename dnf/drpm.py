# drpm.py
# Delta RPM support
#
# Copyright (C) 2012-2013  Red Hat, Inc.
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
from binascii import hexlify
from hawkey import chksum_name
import os.path

MAX_PERCENTAGE = 50

class DeltaPackage(object):
    def __init__(self, delta, po):
        self.location = delta.location
        self.baseurl = delta.baseurl
        self.size = delta.downloadsize
        self.chksum = delta.chksum
        self.rpm = po
        self.repo = po.repo

    def getDiscNum(self):
        return -2 # deltas first

    def returnIdSum(self):
        ctype, csum = self.chksum
        return chksum_name(ctype), hexlify(csum)

    def localPkg(self):
        return os.path.join(self.repo.pkgdir, os.path.basename(self.location))

class DeltaInfo(object):
    def __init__(self, query):
        '''A delta lookup and rebuild context
           query -- installed packages to use when looking up deltas
        '''
        self.query = query

    def delta(self, po):
        '''Turn a po to Delta RPM po, if possible'''
        if not po.repo.deltarpm:
            return po # deltas are disabled
        if os.path.exists(po.localPkg()):
            return po # already there

        best = po.size * MAX_PERCENTAGE / 100
        best_delta = None
        for ipo in self.query.filter(name=po.name, arch=po.arch):
            delta = po.get_delta_from_evr(ipo.evr)
            if delta and delta.downloadsize < best:
                best = delta.downloadsize
                best_delta = delta
        if best_delta:
            po = DeltaPackage(best_delta, po)
        return po
