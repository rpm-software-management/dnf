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


import libxml2
from mdErrors import RepoMDError


class RepoMD:
    """represents the repomd xml file"""
    def __init__(self, repoid, file):
        """takes a repoid and a filename for the repomd.xml"""
        
        self.repoid = repoid
        self.repoData = {}
        
        doc = libxml2.parseFile(file)
        root = doc.getRootElement()
        xmlfiletype = root.name
        node = root.children
        if xmlfiletype == 'repomd':
            self.loadRepoMD(node)
        else:
            raise RepoMDError, 'Error: other unknown root element %s' % xmlfiletype 
        doc.freeDoc()

    def _returnData(self, mdtype, request):
        """ return the data from the repository Data"""
        if self.repoData.has_key(mdtype):
            ds = self.repoData[mdtype]
            if ds.has_key(request):
                return ds[request]
            else:
                raise RepoMDError, "Error: request %s not in %s data" % (request, mdtype)
        else:
            raise RepoMDError, "Error: odd MDtype requested: %s" % mdtype
            
            
            
    
    def _storeRepoData(self, mdtype, dataname, data):
        """stores repository data
           mdtype = primary, filelists, other, group
           dataname = checksum, timestamp, basepath, relativepath
        """
        if self.repoData.has_key(mdtype):
            ds = self.repoData[mdtype]
            if not ds.has_key(dataname):
                ds[dataname] = data
            else:
                raise RepoMDError, "Warning: duplicate data of %s description inputted" % dataname
        else:
            raise RepoMDError, "Warning: odd mdtype being put in %s" % mdtype
            
                
                
                
    def loadRepoDataNode(self, node):
        """loads a repository data node into the class"""
        mdtype = node.prop('type') # get the 'type' property for the datanode
        if not self.repoData.has_key(mdtype):
            self.repoData[mdtype] = {}
            
        datanode = node.children            
        while datanode is not None:
            if datanode.type != 'element':
                datanode = datanode.next
                continue
            
            if datanode.name  == 'location':
                base = datanode.prop('base')
                relative = datanode.prop('href')    
                self._storeRepoData(mdtype, 'basepath', base)
                self._storeRepoData(mdtype, 'relativepath', relative)
            elif datanode.name == 'checksum':
                csumType = datanode.prop('type')
                csum = datanode.content
                self._storeRepoData(mdtype, 'checksum', (csumType, csum))
            elif datanode.name == 'timestamp':
                timestamp = datanode.content
                self._storeRepoData(mdtype, 'timestamp', timestamp)

            datanode = datanode.next    
            continue

    def loadRepoMD(self, node):
        """iterates through the data nodes and populates some simple data areas"""
                
        while node is not None:
            if node.type != 'element':
                node = node.next
                continue
            
            if node.name == 'data':
                self.loadRepoDataNode(node)
                    
            node = node.next
            continue
                
    def _checksum(self, mdtype):
        """returns a tuple of (checksum type, checksum) for the specified Metadata
           file"""
        return self._returnData(mdtype, 'checksum')
        
        
    def _location(self, mdtype):
        """returns location to specified metadata file, (base, relative)"""
        base = self._returnData(mdtype, 'basepath')
        relative = self._returnData(mdtype, 'relativepath')
        
        return (base, relative)
        
    def _timestamp(self, mdtype):
        """returns timestamp for specified metadata file"""
        return self._returnData(mdtype, 'timestamp')
        
    def otherChecksum(self):
        """returns a tuple of (checksum type, checksum) for the other Metadata file"""
        return self._checksum('other')
        
    def otherLocation(self):
        """returns location to other metadata file, (base, relative)"""
        return self._location('other')
        
    def otherTimestamp(self):
        """returns timestamp for other metadata file"""
        return self._timestamp('other')
        
    def primaryChecksum(self):
        """returns a tuple of (checksum type, checksum) for the primary Metadata file"""
        return self._checksum('primary')
        
    def primaryLocation(self):
        """returns location to primary metadata file, (base, relative)"""
        return self._location('primary')
        
    def primaryTimestamp(self):
        """returns timestamp for primary metadata file"""
        return self._timestamp('primary')

    def filelistsChecksum(self):
        """returns a tuple of (checksum type, checksum) for the filelists Metadata file"""
        return self._checksum('filelists')
        
    def filelistsLocation(self):
        """returns location to filelists metadata file, (base, relative)"""
        return self._location('filelists')
        
    def filelistsTimestamp(self):
        """returns timestamp for filelists metadata file"""
        return self._timestamp('filelists')

    def groupChecksum(self):
        """returns a tuple of (checksum type, checksum) for the group Metadata file"""
        return self._checksum('group')
        
    def groupLocation(self):
        """returns location to group metadata file, (base, relative)"""
        return self._location('group')
        
    def groupTimestamp(self):
        """returns timestamp for group metadata file"""
        return self._timestamp('group')

    def fileTypes(self):
        """return list of metadata file types available"""
        return self.repoData.keys()
