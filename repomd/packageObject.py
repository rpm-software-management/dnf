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
        
        epoch = node.prop('epoch')
        ver = node.prop('ver')
        rel = node.prop('rel')
        return (epoch, ver, rel)
        
    def parseChecksum(self, node):
        """takes a checksum element, returns a tuple of (type, checksum, 
           if it is the checksum to be used for the the package id)"""
           
        csumtype = node.prop('type')
        csumid = node.prop('pkgid')
        if csumid is None or csumid.upper() == 'NO':
            csumid = 0
        elif csumid.upper() == 'YES':
            csumid = 1
        else:
            #FIXME - raise an exception
            print 'broken csumid - invalid document'
            csumid = 0
        csum = node.content
        return (csumtype, csum, csumid)
        
    def parseSize(self, node):
        """takes a size element, returns  package, 
           installed and archive size"""
           
        pkg = node.prop('package')
        installed = node.prop('installed')
        archive = node.prop('archive')
        return pkg, installed, archive

    def parseTime(self, node):
        """takes a time element, returns buildtime, filetime(mtime)"""
         
        build = node.prop('build')
        mtime = node.prop('file')
        return build, mtime

    def parseLocation(self, node):
        """takes a location element, returnsbase url path, relative path to package"""
        
        base = node.prop('base')
        relative = node.prop('href')    
        return base, relative
        
    def parseSimple(self, node):
        """takes a simple unattributed CDATA element and returns its value"""
        
        return node.content
        
    def readPkgNode(self, pkgnode):
        """primary package node reading and dumping"""
        
        node = pkgnode.children
        
        while node is not None:
            if node.type != 'element':
                node = node.next
                continue
            
            if node.name in ['name', 'arch', 'summary', 'description', 'url',
                          'packager', 'buildtime', 'filetime']:
                    self.simple[node.name] = self.parseSimple(node)

            elif node.name == 'version': 
                (self.simple['epoch'], self.simple['version'], 
                 self.simple['release']) = self.parseVersion(node)
            
            elif node.name == 'size':
                self.simple['packagesize'], self.simple['installedsize'], \
                 self.simple['archivesize'] = self.parseSize(node)
            
            elif node.name == 'time':
                self.simple['buildtime'], self.simple['filetime'], = \
                 self.parseTime(node)
                 
            
            elif node.name == 'location':
                self.simple['basepath'], self.simple['relativepath'] = \
                 self.parseLocation(node)

            elif node.name == 'checksum':
                (sumtype, sumdata, sumid) = self.parseChecksum(node)
                self.checksums.append((sumtype, sumdata, sumid))
                if sumid:
                    self.simple['id'] = sumdata
                
            elif node.name == 'format':
                try:
                    self.readFormatNode(node)
                except AttributeError:
                    # FIXME - should raise an exception
                    print 'No method to handle format element'
                
            else:
                # FIXME - should raise an exception
                print 'unknown element in package: %s' % node.name

            node = node.next
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
                    if reqf in ['GT', 'GE']:
                        return 1
                if rc == 0:
                    if reqf in ['GE', 'LE', 'EQ']:
                        return 1
                if rc <= -1:
                    if reqf in ['LT', 'LE']:
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
                    
                    
    
    def readFormatNode(self, fmtNode):
        """reads the <format> element and hands off the elements to be 
           parsed elsewhere"""
           
        node = fmtNode.children
        while node is not None:
            if node.type != 'element':
                node = node.next
                continue
            if node.name in ['vendor', 'group', 'buildhost', 'sourcerpm']:
                self.simple[node.name] = self.parseSimple(node)
                
            elif node.name == 'license':
                self.licenses.append(self.parseSimple(node))
            
            elif node.name == 'header-range':
                self.simple['hdrstart'], self.simple['hdrend'] = \
                 self.parseHdrRange(node)
            
            elif node.name in ['obsoletes', 'provides', 'requires', 'conflicts']:
                objlist = self.parsePrco(node)
                self.prco[node.name].extend(objlist)
                
            elif node.name == 'file':
                self.loadFileEntry(node)
                
                
            else:
                # FIXME - should raise an exception
                print 'unknown element in format: %s' % node.name
                
            node = node.next
            continue
    
    def parseHdrRange(self, node):
        """parse header-range, returns (start, end) tuple"""
        
        start = node.prop('start')
        end = node.prop('end')
        return start, end
        
    def parsePrco(self, node):
        """parse a provides,requires,obsoletes,conflicts element"""
        objlist = []
        prco = node.children
        while prco is not None:
            if prco.name == 'entry':
                e = None
                v = None
                r = None
                name = prco.prop('name')
                flag = prco.prop('flags')
                ver = prco.children
                while ver is not None:
                    if ver.name == 'version':
                        (e,v,r) = self.parseVersion(ver)
                    ver = ver.next
                objlist.append((name, flag, (e, v, r)))
            prco = prco.next                
        return objlist

    def loadFileEntry(self, node):
        """load a file/dir entry"""
        ftype = node.prop('type')
        file = node.content
        if ftype is None:
            ftype = 'file'
        if not self.files.has_key(ftype):
            self.files[ftype] = []
        #if file not in self.files[ftype]:
        self.files[ftype].append(file)
            
    def loadChangeLogEntry(self, node):
        """load changelog data"""
        time = node.prop('date')
        author = node.prop('author')
        content = node.content
        self.changelog.append((time, author, content))
        
