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
#
# Seth Vidal <skvidal@linux.duke.edu>
# Luke Macken <lmacken@redhat.com>

import sys
import gzip
import exceptions

from yum.yumRepo import YumRepository

from cElementTree import iterparse


class UpdateNoticeException(exceptions.Exception):
    pass


class UpdateNotice(object):
    def __init__(self, elem=None):
        self._md = {
            'from'             : '',
            'type'             : '',
            'status'           : '',
            'version'          : '',
            'pushcount'        : '',
            'update_id'        : '',
            'issued'           : '',
            'updated'          : '',
            'description'      : '',
            'references'       : [],
            'pkglist'          : [],
            'reboot_suggested' : False
        }

        if elem:
            self._parse(elem)

    def __getitem__(self, item):
        """ Allows scriptable metadata access (ie: un['update_id']). """
        return self._md.has_key(item) and self._md[item] or None

    def __str__(self):
        head = """
Id          : %s
Type        : %s
Status      : %s
Issued      : %s
Updated     : %s
Description :
%s
        """ % (self._md['update_id'], self._md['type'], self._md['status'],
               self._md['issued'], self._md['updated'], self._md['description'])

        refs = '\n== References ==\n'
        for ref in self._md['references']:
            type = ref['type']
            if type == 'cve':
                refs += '\n%s : %s\n%s\n' % (ref['id'], ref['href'],
                                             ref.has_key('summary') and 
                                             ref['summary'] or '')
            elif type == 'bugzilla':
                refs += '\nBug #%s : %s\n%s\n' % (ref['id'], ref['href'],
                                                  ref.has_key('summary') and
                                                  ref['summary'] or '')

        pkglist = '\n== Updated Packages ==\n'
        for pkg in self._md['pkglist']:
            pkglist += '\n%s\n' % pkg['name']
            for file in pkg['packages']:
                pkglist += '  %s  %s\n' % (file['sum'][1], file['filename'])

        msg = head + refs + pkglist

        return msg

    def get_metadata(self):
        """ Return the metadata dict. """
        return self._md

    def _parse(self, elem):
        """ Parse an update element.

            <!ELEMENT update (id, pushcount, synopsis?, issued, updated,
                              references, description, pkglist)>
                <!ATTLIST update type (errata|security) "errata">
                <!ATTLIST update status (final|testing) "final">
                <!ATTLIST update version CDATA #REQUIRED>
                <!ATTLIST update from CDATA #REQUIRED>
        """
        if elem.tag == 'update':
            for attrib in ('from', 'type', 'status', 'version'):
                self._md[attrib] = elem.attrib.get(attrib)
            for child in elem:
                if child.tag == 'id':
                    if not child.text:
                        raise UpdateNoticeException
                    self._md['update_id'] = child.text
                elif child.tag == 'pushcount':
                    self._md['pushcount'] = child.text
                elif child.tag == 'issued':
                    self._md['issued'] = child.attrib.get('date')
                elif child.tag == 'updated':
                    self._md['updated'] = child.attrib.get('date')
                elif child.tag == 'references':
                    self._parse_references(child)
                elif child.tag == 'description':
                    self._md['description'] = child.text
                elif child.tag == 'pkglist':
                    self._parse_pkglist(child)
        else:
            raise UpdateNoticeException('No update element found')

    def _parse_references(self, elem):
        """ Parse the update references.

            <!ELEMENT references (reference*)>
            <!ELEMENT reference (summary*)>
                <!ATTLIST reference href CDATA #REQUIRED>
                <!ATTLIST reference type (self|cve|bugzilla) "self">
                <!ATTLIST reference id CDATA #IMPLIED>
            <!ELEMENT cve (#PCDATA)>
            <!ELEMENT bugzilla (#PCDATA)>
            <!ELEMENT summary (#PCDATA)>
            <!ELEMENT description (#PCDATA)>
        """
        for reference in elem:
            if reference.tag == 'reference':
                data = {}
                for refattrib in ('id', 'href', 'type'):
                    data[refattrib] = reference.attrib.get(refattrib)
                for child in reference:
                    if child.tag == 'summary':
                        data['summary'] = child.text
                self._md['references'].append(data)
            else:
                raise UpdateNoticeException('No reference element found')

    def _parse_pkglist(self, elem):
        """ Parse the package list.

            <!ELEMENT pkglist (collection+)>
            <!ELEMENT collection (name?, package+)>
                <!ATTLIST collection short CDATA #IMPLIED>
                <!ATTLIST collection name CDATA #IMPLIED>
            <!ELEMENT name (#PCDATA)>
        """
        for collection in elem:
            data = { 'packages' : [] }
            if collection.attrib.has_key('short'):
                data['short'] = collection.attrib.get('short')
            for item in collection:
                if item.tag == 'name':
                    data['name'] = item.text
                elif item.tag == 'package':
                    data['packages'].append(self._parse_package(item))
            self._md['pkglist'].append(data)

    def _parse_package(self, elem):
        """ Parse an individual package.

            <!ELEMENT package (filename, sum, reboot_suggested)>
                <!ATTLIST package name CDATA #REQUIRED>
                <!ATTLIST package version CDATA #REQUIRED>
                <!ATTLIST package release CDATA #REQUIRED>
                <!ATTLIST package arch CDATA #REQUIRED>
                <!ATTLIST package epoch CDATA #REQUIRED>
                <!ATTLIST package src CDATA #REQUIRED>
            <!ELEMENT reboot_suggested (#PCDATA)>
            <!ELEMENT filename (#PCDATA)>
            <!ELEMENT sum (#PCDATA)>
                <!ATTLIST sum type (md5|sha1) "sha1">
        """
        package = {}
        for pkgfield in ('arch', 'epoch', 'name', 'version', 'release', 'src'):
            package[pkgfield] = elem.attrib.get(pkgfield)
        for child in elem:
            if child.tag == 'filename':
                package['filename'] = child.text
            elif child.tag == 'sum':
                package['sum'] = (child.attrib.get('type'), child.text)
            elif child.tag == 'reboot_suggested':
                self._md['reboot_suggested'] = True
        return package


class UpdateMetadata(object):
    def __init__(self):
        self._notices = {}
        self._cache = {}    # a pkg name => notice cache for quick lookups
        self._repos = []    # list of repo ids that we've parsed

    def get_notices(self):
        """ Return all notices. """
        return self._notices.values()

    notices = property(get_notices)

    def get_notice(self, nvr):
        """ Retrieve an update notice for a given (name, version, release). """
        nvr = '-'.join(nvr)
        return self._cache.has_key(nvr) and self._cache[nvr] or None

    def add(self, obj, mdtype='updateinfo'):
        """ Parse a metadata from a given YumRepository, file, or filename. """
        if not obj:
            raise UpdateNoticeException
        if type(obj) == type('str'):
            infile = obj.endswith('.gz') and gzip.open(obj) or open(obj, 'rt')
        elif isinstance(obj, YumRepository):
            if obj.id not in self._repos:
                self._repos.append(obj.id)
                md = obj.retrieveMD(mdtype)
                if not md:
                    raise UpdateNoticeException()
                infile = gzip.open(md)
        else:   # obj is a file object
            infile = obj

        for event, elem in iterparse(infile):
            if elem.tag == 'update':
                un = UpdateNotice(elem)
                if not self._notices.has_key(un['update_id']):
                    self._notices[un['update_id']] = un
                    for pkg in un['pkglist']:
                        for file in pkg['packages']:
                            self._cache['%s-%s-%s' % (file['name'],
                                                      file['version'],
                                                      file['release'])] = un

    def __str__(self):
        ret = ''
        for notice in self.notices:
            ret += str(notice)
        return ret


def main():
    def usage():
        print >> sys.stderr, "Usage: %s <update metadata> ..." % sys.argv[0]
        sys.exit(1)

    if len(sys.argv) < 2:
        usage()

    try:
        print sys.argv[1]
        um = UpdateMetadata()
        for srcfile in sys.argv[1:]:
            um.add(srcfile)
        print um
    except IOError:
        print >> sys.stderr, "%s: No such file:\'%s\'" % (sys.argv[0],
                                                          sys.argv[1:])
        usage()

if __name__ == '__main__':
    main()
