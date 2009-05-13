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
import types
from misc import AutoFileChecksums

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
        self.dbversion = None
        self.size      = None
        self.opensize  = None
    
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
            elif child_name == 'database_version':
                self.dbversion = child.text
            elif child_name == 'size':
                self.size = child.text
            elif child_name == 'open-size':
                self.opensize = child.text
        
class RepoMD:
    """represents the repomd xml file"""
    
    def __init__(self, repoid, srcfile):
        """takes a repoid and a filename for the repomd.xml"""
        
        self.timestamp = 0
        self.repoid    = repoid
        self.repoData  = {}
        self.checksums = {}
        self.length    = 0
        self.revision  = None
        self.tags      = {'content' : set(), 'distro' : {}}
        
        if type(srcfile) in types.StringTypes:
            # srcfile is a filename string
            try:
                infile = open(srcfile, 'rt')
            except IOError:
                raise RepoMDError, "Unable to open %s" %(srcfile,)
        else:
            # srcfile is a file object
            infile = srcfile
        
        infile = AutoFileChecksums(infile, ['md5', 'sha1', 'sha256'],
                                   ignore_missing=True)
        parser = iterparse(infile)
        
        try:
            for event, elem in parser:
                elem_name = ns_cleanup(elem.tag)
                
                if elem_name == "data":
                    thisdata = RepoData(elem=elem)
                    self.repoData[thisdata.type] = thisdata
                    try:
                        nts = int(thisdata.timestamp)
                        if nts > self.timestamp: # max() not in old python
                            self.timestamp = nts
                    except:
                        pass
                elif elem_name == "revision":
                    self.revision = elem.text
                elif elem_name == "tags":
                    for child in elem:
                        child_name = ns_cleanup(child.tag)
                        if child_name == 'content':
                            self.tags['content'].add(child.text)
                        if child_name == 'distro':
                            cpeid = child.attrib.get('cpeid', '')
                            distro = self.tags['distro'].setdefault(cpeid,set())
                            distro.add(child.text)

            self.checksums = infile.checksums.hexdigests()
            self.length    = len(infile.checksums)
        except SyntaxError, e:
            raise RepoMDError, "Damaged repomd.xml file"
            
    def fileTypes(self):
        """return list of metadata file types available"""
        return self.repoData.keys()
    
    def getData(self, type):
        if self.repoData.has_key(type):
            return self.repoData[type]
        else:
            raise RepoMDError, "requested datatype %s not available" % type
            
    def dump(self):
        """dump fun output"""

        print "file timestamp: %s" % self.timestamp
        print "file length   : %s" % self.length
        for csum in sorted(self.checksums):
            print "file checksum : %s/%s" % (csum, self.checksums[csum])
        if self.revision is not None:
            print 'revision: %s' % self.revision
        if self.tags['content']:
            print 'tags content: %s' % ", ".join(sorted(self.tags['content']))
        if self.tags['distro']:
            for distro in sorted(self.tags['distro']):
                print 'tags distro: %s' % distro
                tags = self.tags['distro'][distro]
                print '  tags: %s' % ", ".join(sorted(tags))
        print '\n---- Data ----'
        for ft in sorted(self.fileTypes()):
            thisdata = self.repoData[ft]
            print '  datatype: %s' % thisdata.type
            print '    location     : %s %s' % thisdata.location
            print '    timestamp    : %s' % thisdata.timestamp
            print '    size         : %s' % thisdata.size
            print '    open size    : %s' % thisdata.opensize
            print '    checksum     : %s - %s' % thisdata.checksum
            print '    open checksum: %s - %s' %  thisdata.openchecksum
            print '    dbversion    : %s' % thisdata.dbversion
            print ''

def main():

    try:
        print "file          : %s" % sys.argv[1]
        p = RepoMD('repoid', sys.argv[1])
        p.dump()
        
    except IOError:
        print >> sys.stderr, "newcomps.py: No such file:\'%s\'" % sys.argv[1]
        sys.exit(1)
        
if __name__ == '__main__':
    main()

