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

import os
import sys
import libxml2
import cPickle

import Errors


class RepodataParser:
    def __init__(self, storedir, callback=None):
        self.storedir = storedir
        self.callback = callback
        self.repodata = {
            'metadata': {}, 
            'filelists': {},
            'otherdata': {}
        }
        self.debug = 0
    
    def __del__(self):
        for item in self.repodata.keys():
            del self.repodata[item]
        
        self.repodata = {}
        self.storedir = None
        
        
        
        
    def debugprint(self, msg):
        if self.debug:
            print msg
        
    def _piklFileName(self, location, checksum):
        filename = os.path.basename(location)
        piklfile = os.path.join(self.storedir, filename)
        piklfile = '%s.%s.pickle' % (piklfile, checksum)
        self.debugprint('piklfile=%s' % piklfile)
        return piklfile

    def _pickle(self, outfile, obj):
        self.debugprint('Trying to pickle into %s' % outfile)
        try: outfh = open(outfile, 'w')
        except IOError, e: 
            raise cPickle.PicklingError(e)
        try: cPickle.dump(obj, outfh, cPickle.HIGHEST_PROTOCOL)
        except AttributeError: cPickle.dump(obj, outfh, 1)
        self.debugprint('Pickle successful!')
        outfh.close()

    def _unpickle(self, infile):
        self.debugprint('Trying to unpickle from %s' % infile)
        try: infh = open(infile)
        except IOError, e: raise cPickle.UnpicklingError(e)
        obj = cPickle.load(infh)
        infh.close()
        self.debugprint('Unpickle successful!')
        return obj

    def _killold(self, location):
        filename = os.path.basename(location)
        dirfiles = os.listdir(self.storedir)
        for dirfile in dirfiles:
            if dirfile[-7:] == '.pickle':
                if dirfile[:len(filename)] == filename:
                    oldpickle = os.path.join(self.storedir, dirfile)
                    self.debugprint('removing old pickle file %s' % oldpickle)
                    try: os.unlink(oldpickle)
                    except OSError:
                        ## Give an error or something
                        pass
        
    def _getGeneric(self, ident, location, checksum):
        databank = self.repodata[ident]
        if databank: return databank
        if checksum is None:
            ##
            # Pass checksum as None to ignore pickling. This will
            # Go straight to xml files.
            return self.parseDataFromXml(location)
        piklfile = self._piklFileName(location, checksum)
        try: 
            databank = self._unpickle(piklfile)
            self.repodata[ident] = databank
            return databank
        except cPickle.UnpicklingError, e: 
            self.debugprint('Could not unpickle: %s!' % e)
            databank = self.parseDataFromXml(location)
            self._killold(location)
            try: self._pickle(piklfile, databank)
            except cPickle.PicklingError:
                self.debugprint('Could not pickle %s data in %s' % (ident, piklfile))
            return databank
        
    def getPrimary(self, location, checksum):
        return self._getGeneric('metadata', location, checksum)

    def getFilelists(self, location, checksum):
        return self._getGeneric('filelists', location, checksum)

    def getOtherdata(self, location, checksum):
        return self._getGeneric('otherdata', location, checksum)

    def parseDataFromXml(self, fileloc):
        ## TODO: Fail sanely.
        self.debugprint('Parsing data from %s' % fileloc)
        reader = libxml2.newTextReaderFilename(fileloc)
        count = 0
        total = 9999
        mode = None
        databank = None
        while reader.Read():
            if reader.NodeType() != 1: continue
            name = reader.LocalName()
            if name in ('metadata', 'filelists', 'otherdata'):
                mode = name
                databank = self.repodata[mode]
                try: total = int(reader.GetAttribute('packages'))
                except ValueError: pass
            elif name == 'package':
                count += 1
                if mode == 'metadata':
                    obj = PrimaryEntry(reader)
                    pkgid = obj.checksum['value']
                    #if pkgid in databank.keys():
                    #    print 'double detected!'
                    #    print databank[pkgid].nevra, 'vs', obj.nevra
                    if pkgid: databank[pkgid] = obj
                elif mode == 'filelists':
                    pkgid = reader.GetAttribute('pkgid')
                    if pkgid:
                        obj = FilelistsEntry(reader)
                        databank[pkgid] = obj
                elif mode == 'otherdata':
                    pkgid = reader.GetAttribute('pkgid')
                    if pkgid:
                        obj = OtherEntry(reader)
                        databank[pkgid] = obj
                if self.callback is not None: self.callback(count, total, 'MD Read')
        self.debugprint('Parsed %s packages' % count)
        reader.Close()
        return databank

class BaseEntry:
    def _props(self, reader):
        if not reader.HasAttributes(): return {}
        propdict = {}
        reader.MoveToFirstAttribute()
        while 1:
            propdict[reader.LocalName()] = reader.Value()
            if not reader.MoveToNextAttribute(): break
        reader.MoveToElement()
        return propdict
        
    def _value(self, reader):
        if reader.IsEmptyElement(): return ''
        val = ''
        while reader.Read():
            if reader.NodeType() == 3: val += reader.Value()
            else: break
        return val

    def _getFileEntry(self, reader):
        type = 'file'
        props = self._props(reader)
        if props.has_key('type'): type = props['type']
        value = self._value(reader)
        return (type, value)

class PrimaryEntry(BaseEntry):
    def __init__(self, reader):
        self.nevra = (None, None, None, None, None)
        self.checksum = {'type': None, 'pkgid': None, 'value': None}
        self.info = {
            'summary': None,
            'description': None,
            'packager': None,
            'url': None,
            'license': None,
            'vendor': None,
            'group': None,
            'buildhost': None,
            'sourcerpm': None
        }
        self.time = {'file': None, 'build': None}
        self.size = {'package': None, 'installed': None, 'archive': None}
        self.location = {'href': None, 'value': None}
        self.hdrange = {'start': None, 'end': None}
        self.prco = {}
        self.files = {}

        n = e = v = r = a = None
        while reader.Read():
            if reader.NodeType() == 15 and reader.LocalName() == 'package':
                break
            if reader.NodeType() != 1: continue
            name = reader.LocalName()
            if name == 'name': n = self._value(reader)
            elif name == 'arch': a = self._value(reader)
            elif name == 'version': 
                evr = self._props(reader)
                (e, v, r) = (evr['epoch'], evr['ver'], evr['rel'])
            elif name in ('summary', 'description', 'packager', 'url'): 
                self.info[name] = self._value(reader)
            elif name == 'checksum': 
                self.checksum = self._props(reader)
                self.checksum['value'] = self._value(reader)
            elif name == 'location': 
                self.location = self._props(reader)
                self.location['value'] = self._value(reader)
            elif name == 'time':
                self.time = self._props(reader)
            elif name == 'size':
                self.size = self._props(reader)
            elif name == 'format': self.setFormat(reader)
        self.nevra = (n, e, v, r, a)

    def dump(self):
        print 'nevra=%s,%s,%s,%s,%s' % self.nevra
        print 'checksum=%s' % self.checksum
        print 'info=%s' % self.info
        print 'time=%s' % self.time
        print 'size=%s' % self.size
        print 'location=%s' % self.location
        print 'hdrange=%s' % self.hdrange
        print 'prco=%s' % self.prco
        print 'files=%s' % self.files

    def setFormat(self, reader):
        while reader.Read():
            if reader.NodeType() == 15 and reader.LocalName() == 'format':
                break
            if reader.NodeType() != 1: continue
            name = reader.LocalName()
            if name in ('license', 'vendor', 'group', 'buildhost',
                        'sourcerpm'):
                self.info[name] = self._value(reader)
            elif name in ('provides', 'requires', 'conflicts', 
                          'obsoletes'):
                self.setPrco(reader)
            elif name == 'header-range':
                self.hdrange = self._props(reader)
            elif name == 'file':
                (type, value) = self._getFileEntry(reader)
                self.files[value] = type

    def setPrco(self, reader):
        members = []
        myname = reader.LocalName()
        while reader.Read():
            if reader.NodeType() == 15 and reader.LocalName() == myname:
                break
            if reader.NodeType() != 1: continue
            name = reader.LocalName()
            members.append(self._props(reader))
        self.prco[myname] = members

class FilelistsEntry(BaseEntry):
    def __init__(self, reader):
        self.files = {}
        while reader.Read():
            if reader.NodeType() == 15 and reader.LocalName() == 'package':
                break
            if reader.NodeType() != 1: continue
            name = reader.LocalName()
            if name == 'file':
                (type, value) = self._getFileEntry(reader)
                self.files[value] = type
                
    def dump(self):
        print 'files=%s' % self.files

class OtherEntry(BaseEntry):
    def __init__(self, reader):
        self.changelog = []
        while reader.Read():
            if reader.NodeType() == 15 and reader.LocalName() == 'package':
                break
            if reader.NodeType() != 1: continue
            name = reader.LocalName()
            if name == 'changelog':
                entry = self._props(reader)
                entry['value'] = self._value(reader)
                self.changelog.append(entry)

    def dump(self):
        print 'changelog=%s' % self.changelog

def test(level, repodir, storedir, checksum):
    import time
    primary = os.path.join(repodir, 'primary.xml')
    filelists = os.path.join(repodir, 'filelists.xml')
    otherdata = os.path.join(repodir, 'other.xml')
    tick = time.time()
    bigtick = tick
    rp = RepodataParser(storedir)
    rp.getPrimary(primary, checksum)
    print 'operation took: %d seconds' % (time.time() - tick)
    print 'primary has %s entries' % len(rp.repodata['metadata'].keys())
    tick = time.time()
    if level == 'filelists' or level == 'other':
        rp.getFilelists(filelists, checksum)
        print 'operation took: %d seconds' % (time.time() - tick)
        print 'filelists has %s entries' % len(rp.repodata['filelists'].keys())
        tick = time.time()
    if level == 'other':
        rp.getOtherdata(otherdata, checksum)
        print 'operation took: %d seconds' % (time.time() - tick)
        print 'otherdata has %s entries' % len(rp.repodata['otherdata'].keys())
    print
    print 'total operation time: %d seconds' % (time.time() - bigtick)

def testusage():
    print 'Usage: %s level repodir storedir checksum' % sys.argv[0]
    print 'level can be primary, filelists, other'
    print 'repodir is the location of .xml files'
    print 'storedir is where pickles will be saved'
    print 'checksum can be anything you want it to be'
    sys.exit(1)
    
if __name__ == '__main__':
    try: (level, repodir, storedir, checksum) = sys.argv[1:]
    except ValueError: testusage()
    if level not in ('primary', 'filelists', 'other'): testusage()
    if checksum == 'None': checksum = None
    test(level, repodir, storedir, checksum)
