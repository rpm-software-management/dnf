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
# Copyright 2005 Duke University 


import sys
from cElementTree import iterparse
import exceptions



class UpdateNoticeException(exceptions.Exception):
    pass
    
    
class UpdateNotice(object):
    def __init__(self, elem=None):
        self.cves = []
        self.urls = []
        self.packages = []
        self.description = ''
        self.update_id = None
        self.distribution = None
        self.release_date = None
        self.status = None
        self.type = None
        self.title = ''

        if elem:
            self.parse(elem)
    
    def __str__(self):
        cveinfo = pkglist = related = ''
        
        head = """
Type: %s
Status: %s
Distribution: %s
ID: %s
Release date: %s
Description: 
%s
        """ % (self.type, self.status, self.distribution, 
               self.update_id, self.release_date, self.description)

        if self.urls:
            related = '\nRelated URLS:\n'
            for url in self.urls:
                related = related + '  %s\n' % url
        
        if self.cves:
            cveinfo = '\nResolves CVES:\n'
            for cve in self.cves:
                cveinfo = cveinfo + '  %s\n' % cve
        
        if self.packages:
            pkglist = '\nPackages: \n'
            for pkg in self.packages:
                pkgstring = '%s-%s-%s.%s\t\t%s\n' % (pkg['name'], pkg['ver'],
                                                    pkg['rel'], pkg['arch'],
                                                    pkg['pkgid'])
                pkglist = pkglist + pkgstring
        
        msg = head + related + cveinfo + pkglist
        
        return msg

    def parse(self, elem):
        if elem.tag == 'update':
            id = elem.attrib.get('id')
            if not id:
                raise UpdateNoticeException
            self.update_id = id
            
            self.release_date = elem.attrib.get('release_date')
            self.status = elem.attrib.get('status')
            c = elem.attrib.get('type')
            if not c:
                self.type = 'update'
            else:
                self.type = c

        for child in elem:

            if child.tag == 'cve':
                self.cves.append(child.text)

            elif child.tag == 'url':
                self.urls.append(child.text)
            
            elif child.tag == 'description':
                self.description = child.text
            
            elif child.tag == 'distribution':
                self.distribution = child.text
            
            elif child.tag == 'title':
                self.title = child.text

            elif child.tag == 'package':
                self.parse_package(child)
        
    def parse_package(self, elem):
        
        pkg = {}
        pkg['pkgid'] = elem.attrib.get('pkgid')
        pkg['name']  = elem.attrib.get('name')
        pkg['arch'] = elem.attrib.get('arch')
        for child in elem:
            if child.tag == 'version':
                pkg['ver'] = child.attrib.get('ver')
                pkg['rel'] = child.attrib.get('rel')
                pkg['epoch'] = child.attrib.get('epoch')
        
        self.packages.append(pkg)



class UpdateMetadata(object):
    def __init__(self):
        self._notices = {}
        
    def get_notices(self):
        return self._notices.values()

    notices = property(get_notices)

    def get_notice(self, nvr):
        """ Retrieve an update notice for a given (name, version, release). """
        for notice in self._notices.values():
            for pkg in notice.packages:
                if pkg['name'] == nvr[0] and \
                   pkg['ver'] == nvr[1] and \
                   pkg['rel'] == nvr[2]:
                       return notice
        return None

    def add(self, srcfile):
        if not srcfile:
            raise UpdateNoticeException
            
        if type(srcfile) == type('str'):
            infile = open(srcfile, 'rt')
        else:   # srcfile is a file object
            infile = srcfile
        
        parser = iterparse(infile)

        for event, elem in parser:
            if elem.tag == 'update':
                un = UpdateNotice(elem)
                if not self._notices.has_key(un.update_id):
                    self._notices[un.update_id] = un


        del parser

    def dump(self):
        for notice in self.notices:
            print notice


def main():

    try:
        print sys.argv[1]
        um = UpdateMetadata()
        for srcfile in sys.argv[1:]:
            um.add(srcfile)

        um.dump()
        
    except IOError:
        print >> sys.stderr, "update_md.py: No such file:\'%s\'" % sys.argv[1:]
        sys.exit(1)
        
if __name__ == '__main__':
    main()
