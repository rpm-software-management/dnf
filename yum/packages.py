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
# Copyright 2004 Duke University 
# Written by Seth Vidal <skvidal at phy.duke.edu>

import rpm
import os
import os.path

import metadata.packageObject
base=None # will be filled with the baseclass

class YumPackage(metadata.packageObject.RpmXMLPackageObject):
    """super class for the metadata packageobject we use"""
       

    def getHeader(self):
        """returns an rpm header object from the package object"""
        # this function sucks - it should use the urlgrabber
        # testfunction to check the headers and loop on that

        rel = self.returnSimple('relativepath')
        pkgname = os.path.basename(rel)
        hdrname = pkgname[:-4] + '.hdr'
        url = self.returnSimple('basepath')
        start = self.returnSimple('hdrstart')
        end = self.returnSimple('hdrend')
        repoid = self.returnSimple('repoid')
        repo = base.repos.getRepo(self.returnSimple('repoid'))
        hdrpath = repo.hdrdir + '/' + hdrname
        if os.path.exists(hdrpath):
            base.log(4, 'Cached header %s exists, checking' % hdrpath)
            try: 
                hlist = rpm.readHeaderListFromFile(hdrpath)
            except rpm.error:
                os.unlink(hdrpath)
                hdrpath = repo.get(url=url, relative=rel, local=hdrpath, 
                               start=start, end=end)
                hlist = rpm.readHeaderListFromFile(hdrpath)
        else:
            hdrpath = repo.get(url=url, relative=rel, local=hdrpath, 
                            start=start, end=end)
            hlist = rpm.readHeaderListFromFile(hdrpath)

        hdr = hlist[0]
       
        return hdr                                   

    def getProvidesNames(self):
        """returns a list of providesNames"""
        
        provnames = []
        prov = self.returnPrco('provides')
        
        for (name, flag, vertup) in prov:
            provnames.append(name)

        return provnames
       

