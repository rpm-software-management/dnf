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

import mdUtils

# consider making an XMLPackageObject
# BasePackageObject - with just methods and the init'd storage dicts
# XMLPackageobject will be used to build the rpmXMLPAckageObject - which is 
# formatnode stuff for rpm.


class PackageObject:
    """Base Package Object - sets up the default storage dicts and the
       most common returns"""
       
    def __init__(self):
        self.simple = {} # simple things, name, arch, e,v,r, size, etc
        self.checksums = [] # (type, checksum, id(0,1)

    def __str__(self):
        return self.returnNevraPrintable()

    def returnSimple(self, varname):
        return self.simple[varname]

    def simpleItems(self):
        return self.simple.keys()            

    def returnID(self):
        return self.returnSimple('id')

    def returnNevraTuple(self):
        return (self.returnSimple('name'), self.returnSimple('epoch'), 
                self.returnSimple('version'),self.returnSimple('release'), 
                self.returnSimple('arch'))
    
    def returnNevraPrintable(self):
        """return printable string for the pkgname/object
           name - epoch:ver-rel.arch"""
        if self.returnSimple('epoch') == '0':
            string = '%s - %s-%s.%s' % (self.returnSimple('name'), 
                                        self.returnSimple('version'),
                                        self.returnSimple('release'), 
                                        self.returnSimple('arch'))
        else:
            string = '%s - %s:%s-%s.%s' % (self.returnSimple('name'), 
                                           self.returnSimple('epoch'), 
                                           self.returnSimple('version'), 
                                           self.returnSimple('release'), 
                                           self.returnSimple('arch'))
        return string                                           

    def returnEVR(self):
        """returns a tuple of epoch, ver, rel"""
        return (self.returnSimple('epoch'), self.returnSimple('version'), self.returnSimple('release'))
        
        return                            



class XMLPackageObject(PackageObject):
    """inherits from PackageObject, does the functions to parse an xml package format
       file to pull packages in"""

    def __init__(self):
        PackageObject.__init__(self)
        
    def parseVersion(self, node):
        """takes a version element, returns a tuple of (epoch, ver, rel)"""
        epoch = node.GetAttribute('epoch')
        ver = node.GetAttribute('ver')
        rel = node.GetAttribute('rel')
        return (epoch, ver, rel)
        
    def parseChecksum(self, node):
        """takes a checksum element, returns a tuple of (type, checksum, 
           if it is the checksum to be used for the the package id)"""
           
        csumtype = node.GetAttribute('type')
        csumid = node.GetAttribute('pkgid')
        if csumid is None or csumid.upper() == 'NO':
            csumid = 0
        elif csumid.upper() == 'YES':
            csumid = 1
        else:
            #FIXME - raise an exception
            print 'broken csumid - invalid document'
            csumid = 0
        node.Read()
        csum = node.Value()
        return (csumtype, csum, csumid)
        
    def parseSize(self, node):
        """takes a size element, returns  package, 
           installed and archive size"""
           
        pkg = node.GetAttribute('package')
        installed = node.GetAttribute('installed')
        archive = node.GetAttribute('archive')
        return pkg, installed, archive

    def parseTime(self, node):
        """takes a time element, returns buildtime, filetime(mtime)"""
         
        build = node.GetAttribute('build')
        mtime = node.GetAttribute('file')
        return build, mtime

    def parseLocation(self, node):
        """takes a location element, returnsbase url path, relative path to package"""
        
        base = node.GetAttribute('base')
        relative = node.GetAttribute('href')
        return base, relative
        
    def parseSimple(self, node):
        """takes a simple unattributed CDATA element and returns its value"""
        if node.IsEmptyElement():
            return ''
        node.Read() # get the next node
        return node.Value()
        
    def readPkgNode(self, reader):
        """primary package node reading and dumping"""
        
        mydepth = reader.Depth()
        ret = reader.Read()        
        while ret:
            if reader.NodeType() == 14:
                ret = reader.Read()
                continue

            if reader.NodeType() == 15 and reader.Depth() == mydepth:
                return
                
            if reader.NodeType() == 1:
                if reader.Depth() == mydepth:
                    #print 'oh crap - we are outside - how did that happen??'
                    return

                nodeName = reader.LocalName()

                if nodeName in ['name', 'arch', 'summary', 'description', 
                                'url', 'packager', 'buildtime', 'filetime']:
                                     
                    self.simple[nodeName] = self.parseSimple(reader)

                elif nodeName == 'version': 
                    (self.simple['epoch'], self.simple['version'], 
                     self.simple['release']) = self.parseVersion(reader)
            
                elif nodeName == 'size':
                    self.simple['packagesize'], self.simple['installedsize'], \
                     self.simple['archivesize'] = self.parseSize(reader)
            
                elif nodeName == 'time':
                    self.simple['buildtime'], self.simple['filetime'], = \
                     self.parseTime(reader)
                     
                
                elif nodeName == 'location':
                    self.simple['basepath'], self.simple['relativepath'] = \
                     self.parseLocation(reader)
    
                elif nodeName == 'checksum':
                    (sumtype, sumdata, sumid) = self.parseChecksum(reader)
                    self.checksums.append((sumtype, sumdata, sumid))
                    if sumid:
                        self.simple['id'] = sumdata
                    
                elif nodeName == 'format':
                    try:
                        self.readFormatNode(reader)
                    except AttributeError:
                        # FIXME - should raise an exception
                        print 'No method to handle format element'
                else:
                    pass
                    # FIXME - should raise an exception
                    print 'unknown element in package: %s' % nodeName
    
            ret = reader.Read()
            continue
    

class RpmBase:
    """return functions and storage for rpm-specific data"""

    def __init__(self):
        self.prco = {}
        self.prco['obsoletes'] = [] # (name, flag, (e,v,r))
        self.prco['conflicts'] = [] # (name, flag, (e,v,r))
        self.prco['requires'] = [] # (name, flag, (e,v,r))
        self.prco['provides'] = [] # (name, flag, (e,v,r))
        self.files = {}
        self.files['file'] = []
        self.files['dir'] = []
        self.files['ghost'] = []
        self.changelog = [] # (ctime, cname, ctext)
        self.licenses = []
    
    def returnPrco(self, prcotype):
        """return list of provides, requires, conflicts or obsoletes"""
        if self.prco.has_key(prcotype):
            return self.prco[prcotype]
        else:
            return []

    def checkPrco(self, prcotype, prcotuple):
        """returns 1 or 0 if the pkg contains the requested tuple/tuple range"""
        # get rid of simple cases - nothing
        if not self.prco.has_key(prcotype):
            return 0
        # exact match    
        if prcotuple in self.prco[prcotype]:
            return 1
        else:
            # make us look it up and compare
            (reqn, reqf, (reqe, reqv ,reqr)) = prcotuple
            if reqf is not None:
                if self.inPrcoRange(prcotype, prcotuple):
                    return 1
                else:
                    return 0
            else:
                for (n, f, (e, v, r)) in self.returnPrco(prcotype):
                    if reqn == n:
                        return 1

        return 0
                
    def inPrcoRange(self, prcotype, reqtuple):
        """returns true if the package has a the prco that satisfies 
           the reqtuple range, assume false.
           Takes: prcotype, requested prco tuple"""
        # we only ever get here if we have a versioned prco
        # nameonly shouldn't ever raise it
        (reqn, reqf, (reqe, reqv, reqr)) = reqtuple
        # find the named entry in pkgobj, do the comparsion
        for (n, f, (e, v, r)) in self.returnPrco(prcotype):
            if reqn == n:
                # found it
                if f != 'EQ':
                    # isn't this odd, it's not 'EQ' - it really should be
                    # use the pkgobj's evr for the comparison
                    (e, v, r) = self.returnEVR()
                # and you thought we were done having fun
                # if the requested release is left out then we have
                # to remove release from the package prco to make sure the match
                # is a success - ie: if the request is EQ foo 1:3.0.0 and we have 
                # foo 1:3.0.0-15 then we have to drop the 15 so we can match
                if reqr is None:
                    r = None
                if reqe is None:
                    e = None
                if reqv is None: # just for the record if ver is None then we're going to segfault
                    v = None
                rc = mdUtils.compareEVR((e, v, r), (reqe, reqv, reqr))
                
                if rc >= 1:
                    if reqf in ['GT', 'GE', 4, 12]:
                        return 1
                if rc == 0:
                    if reqf in ['GE', 'LE', 'EQ', 8, 10, 12]:
                        return 1
                if rc <= -1:
                    if reqf in ['LT', 'LE', 2, 10]:
                        return 1
        return 0
        
        
    def returnFileEntries(self, ftype='file'):
        """return list of files based on type"""
        if self.files.has_key(ftype):
            return self.files[ftype]
        else:
            return []
            
    def returnFileTypes(self):
        """return list of types of files in the package"""
        return self.files.keys()
    
    
    
class RpmXMLPackageObject(XMLPackageObject, RpmBase):
    """used class - inherits from XMLPackageObject, which inherits from 
       Package Object also inherits from RpmBase for return functions"""
       
    def __init__(self, node, repoid):
        XMLPackageObject.__init__(self)
        RpmBase.__init__(self)

        self.simple['repoid'] = repoid

        self.readPkgNode(node)
        # quick defs for commonly used things
        self.name = self.returnSimple('name')
        self.epoch = self.returnSimple('epoch')
        self.version = self.returnSimple('version')
        self.release = self.returnSimple('release')
        self.arch = self.returnSimple('arch')
        
        
    def dumpPkg(self):
        fconv = { 'EQ':'=', 'LT':'<', 'LE':'<=',
                  'GT':'>', 'GE':'>='} 
        for item in self.simpleItems():
            print '%s = %s' % (item, self.returnSimple(item))
        for csum in self.checksums:
            print csum
        for thing in ['requires', 'provides', 'obsoletes', 'conflicts']:
            if len(self.prco[thing]) > 0:
                print '%s:' % thing
                for (n,f,(e,v,r)) in self.prco[thing]:
                    if f is None:
                        print '\t%s ' % n
                    else:
                        print '\t',
                        print n,
                        print fconv[f],
                        print '%s:%s-%s' %(e,v,r)
                print ''
                    
                    
    
    def readFormatNode(self, reader):
        """reads the <format> element and hands off the elements to be 
           parsed elsewhere"""
           
        mydepth = reader.Depth()
        ret = reader.Read()        
        while ret:
            if reader.NodeType() == 14:
                ret = reader.Read()
                continue

            if reader.NodeType() == 15 and reader.Depth() == mydepth:
                return
                
            if reader.NodeType() == 1:
                if reader.Depth() == mydepth:
                    #print 'oh crap - we are outside - how did that happen??'
                    return

                nodeName = reader.LocalName()

                if nodeName in ['vendor', 'group', 'buildhost', 'sourcerpm']:
                    self.simple[nodeName] = self.parseSimple(reader)
                    
                elif nodeName == 'license':
                    self.licenses.append(self.parseSimple(reader))
                
                elif nodeName == 'header-range':
                    self.simple['hdrstart'], self.simple['hdrend'] = \
                     self.parseHdrRange(reader)
                
                elif nodeName in ['obsoletes', 'provides', 'requires', 'conflicts']:
                    objlist = self.parsePrco(reader)
                    self.prco[nodeName].extend(objlist)
                    
                elif nodeName == 'file':
                    self.loadFileEntry(reader)
                    
                    
                else:
                    # FIXME - should raise an exception
                    print 'unknown element in format: %s' % nodeName
                    #pass

            ret = reader.Read()
            continue

    
    def parseHdrRange(self, node):
        """parse header-range, returns (start, end) tuple"""
        
        start = node.GetAttribute('start')
        end = node.GetAttribute('end')
        return start, end
        
    def parsePrco(self, reader):
        """parse a provides,requires,obsoletes,conflicts element"""
        objlist = []
        mydepth = reader.Depth()
        ret = reader.Read()        
        while ret:
            if reader.NodeType() == 14:
                ret = reader.Read()
                continue

            if reader.NodeType() == 15 and reader.Depth() == mydepth:
                return objlist
                
            if reader.NodeType() == 1:
                if reader.Depth() == mydepth:
                    #print 'oh crap - we are outside - how did that happen??'
                    return objlist

                prcoName = reader.LocalName()
                
                if prcoName == 'entry':
                    name = reader.GetAttribute('name')
                    flag = reader.GetAttribute('flags')
                    e = reader.GetAttribute('epoch')
                    v = reader.GetAttribute('ver')
                    r = reader.GetAttribute('rel')
                    objlist.append((name, flag, (e, v, r)))

            ret = reader.Read()
            continue
            
        return objlist

    def loadFileEntry(self, node):
        """load a file/dir entry"""
        ftype = node.GetAttribute('type')
        node.Read() # content is file
        file = node.Value()
        if not ftype:
            ftype = 'file'
        if not self.files.has_key(ftype):
            self.files[ftype] = []
        #if file not in self.files[ftype]:
        self.files[ftype].append(file)

        return (ftype, file)
            
    def loadChangeLogEntry(self, node):
        """load changelog data"""
        time = node.GetAttribute('date')
        author = node.GetAttribute('author')
        node.Read()
        content = node.Value()
        self.changelog.append((time, author, content))
        
