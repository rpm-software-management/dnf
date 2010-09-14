#! /usr/bin/python -tt

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
# Copyright 2005 Duke University 

import gzip
try:
    from xml.etree import cElementTree
except ImportError:
    import cElementTree
iterparse = cElementTree.iterparse

from cStringIO import StringIO
import warnings

import Errors

#TODO: document everything here

class MDParser:

    def __init__(self, filename):

        # Set up mapping of meta types to handler classes 
        handlers = {
            '{http://linux.duke.edu/metadata/common}metadata': PrimaryEntry,
            '{http://linux.duke.edu/metadata/filelists}filelists': FilelistsEntry,
            '{http://linux.duke.edu/metadata/other}otherdata': OtherEntry,
        }
            
        self.total = None
        self.count = 0
        self._handlercls = None

        # Read in type, set package node handler and get total number of
        # packages
        if filename[-3:] == '.gz': fh = gzip.open(filename, 'r')
        else: fh = open(filename, 'r')
        parser = iterparse(fh, events=('start', 'end'))
        self.reader = parser.__iter__()
        event, elem = self.reader.next()
        self._handlercls = handlers.get(elem.tag, None)
        if not self._handlercls:
            raise ValueError('Unknown repodata type "%s" in %s' % (
                elem.tag, filename))
        # Get the total number of packages
        self.total = int(elem.get('packages', 0))

    def __iter__(self):
        return self

    def next(self):
        for event, elem in self.reader:
            if event == 'end' and elem.tag[-7:] == 'package':
                self.count += 1
                return self._handlercls(elem)
        raise StopIteration


class BaseEntry:
    def __init__(self, elem):
        self._p = {} 

    def __getitem__(self, k):
        return self._p[k]

    def keys(self):
        return self._p.keys()

    def values(self):
        return self._p.values()

    def has_key(self, k):
        warnings.warn('has_key() will go away in a future version of Yum.\n',
                      Errors.YumFutureDeprecationWarning, stacklevel=2)
        return k in self._p

    def __iter__(self):
        return iter(self._p)

    def __str__(self):
        out = StringIO()
        keys = self.keys()
        keys.sort()
        for k in keys:
            line = u'%s=%s\n' % (k, self[k])
            out.write(line.encode('utf8'))
        return out.getvalue()

    def _bn(self, qn):
        if qn.find('}') == -1: return qn 
        return qn.split('}')[1]
        
    def _prefixprops(self, elem, prefix):
        ret = {}
        for key in elem.attrib:
            ret[prefix + '_' + self._bn(key)] = elem.attrib[key]
        return ret

class PrimaryEntry(BaseEntry):
    def __init__(self, elem):
        BaseEntry.__init__(self, elem)
        # Avoid excess typing :)
        p = self._p

        self.prco = {}
        self.files = {}

        for child in elem:
            name = self._bn(child.tag)
            if name in ('name', 'arch', 'summary', 'description', 'url', 
                    'packager'): 
                p[name] = child.text

            elif name == 'version': 
                p.update(child.attrib)

            elif name in ('time', 'size'):
                p.update(self._prefixprops(child, name))

            elif name in ('checksum', 'location'): 
                p.update(self._prefixprops(child, name))
                p[name + '_value'] = child.text
                if name == 'location' and "location_base" not in p:
                    p["location_base"] = None
            
            elif name == 'format': 
                self.setFormat(child)

        p['pkgId'] = p['checksum_value']
        elem.clear()

    def setFormat(self, elem):

        # Avoid excessive typing :)
        p = self._p

        for child in elem:
            name = self._bn(child.tag)

            if name in ('license', 'vendor', 'group', 'buildhost',
                        'sourcerpm'):
                p[name] = child.text

            elif name in ('provides', 'requires', 'conflicts', 
                          'obsoletes'):
                self.prco[name] = self.getPrco(child)

            elif name == 'header-range':
                p.update(self._prefixprops(child, 'rpm_header'))

            elif name == 'file':
                file_type = child.get('type', 'file')
                path = child.text
                self.files[path] = file_type

    def getPrco(self, elem):
        members = []
        for child in elem:
            members.append(child.attrib)
        return members
        
        
class FilelistsEntry(BaseEntry):
    def __init__(self, elem):
        BaseEntry.__init__(self, elem)
        self._p['pkgId'] = elem.attrib['pkgid']
        self.files = {}
        for child in elem:
            name = self._bn(child.tag)
            if name == 'file':
                file_type = child.get('type', 'file')
                path = child.text
                self.files[path] = file_type
        elem.clear()
                
class OtherEntry(BaseEntry):
    def __init__(self, elem):
        BaseEntry.__init__(self, elem)
        self._p['pkgId'] = elem.attrib['pkgid']
        self._p['changelog'] = []
        for child in elem:
            name = self._bn(child.tag)
            if name == 'changelog':
                entry = child.attrib
                entry['value'] = child.text
                self._p['changelog'].append(entry)
        elem.clear()



def test():
    import sys

    parser = MDParser(sys.argv[1])

    for pkg in parser:
        print '-' * 40
        print pkg

    print 'read: %s packages (%s suggested)' % (parser.count, parser.total)

if __name__ == '__main__':
    test()
