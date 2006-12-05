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
# Copyright 2006 Duke University

try:
    from xml.etree import cElementTree
except ImportError:
    import cElementTree
iterparse = cElementTree.iterparse
from Errors import RepoMDError

import sys

def ns_cleanup(qn):
    if qn.find('}') == -1: return qn 
    return qn.split('}')[1]

class RepoData:
    """represents anything beneath a <data> tag"""
    def __init__(self, elem):
        self.type = elem.attrib.get('type')
        self.location = (None, None)
        self.checksum = (None,None) # type,value
        self.openchecksum = (None,None) # type,value
        self.timestamp = None
    
        self.parse(elem)

    def parse(self, elem):
        
        for child in elem:
            child_name = ns_cleanup(child.tag)
            if child_name == 'location':
                relative = child.attrib.get('href')
                base = child.attrib.get('base')
                self.location = (base, relative)
            
            elif child_name == 'checksum':
                csum_value = child.text
                csum_type = child.attrib.get('type')
                self.checksum = (csum_type,csum_value)

            elif child_name == 'open-checksum':
                csum_value = child.text
                csum_type = child.attrib.get('type')
                self.openchecksum = (csum_type, csum_value)
            
            elif child_name == 'timestamp':
                self.timestamp = child.text
    
        
class RepoMD:
    """represents the repomd xml file"""
    
    def __init__(self, repoid, srcfile):
        """takes a repoid and a filename for the repomd.xml"""
        
        self.repoid = repoid
        self.repoData = {}
        
        if type(srcfile) == type('str'):
            # srcfile is a filename string
            infile = open(srcfile, 'rt')
        else:
            # srcfile is a file object
            infile = srcfile
        
        parser = iterparse(infile)
        
        try:
            for event, elem in parser:
                elem_name = ns_cleanup(elem.tag)
                
                if elem_name == "data":
                    thisdata = RepoData(elem=elem)
                    self.repoData[thisdata.type] = thisdata
        except SyntaxError, e:
            raise RepoMDError, "Damaged repomd.xml file"
            
    def fileTypes(self):
        """return list of metadata file types available"""
        return self.repoData.keys()
    
    def getData(self, type):
        if self.repoData.has_key(type):
            return self.repoData[type]
        else:
            raise RepoMDError, "Error: requested datatype %s not available" % type
            
    def dump(self):
        """dump fun output"""
        
        for ft in self.fileTypes():
            thisdata = self.repoData[ft]
            print 'datatype: %s' % thisdata.type
            print 'location: %s %s' % thisdata.location
            print 'timestamp: %s' % thisdata.timestamp
            print 'checksum: %s -%s' % thisdata.checksum
            print 'open checksum: %s - %s' %  thisdata.openchecksum

def main():

    try:
        print sys.argv[1]
        p = RepoMD('repoid', sys.argv[1])
        p.dump()
        
    except IOError:
        print >> sys.stderr, "newcomps.py: No such file:\'%s\'" % sys.argv[1]
        sys.exit(1)
        
if __name__ == '__main__':
    main()

