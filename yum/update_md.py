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

"""
Update metadata (updateinfo.xml) parsing.
"""

import sys
import gzip

from textwrap import wrap
from yum.yumRepo import YumRepository

try:
    from xml.etree import cElementTree
except ImportError:
    import cElementTree
iterparse = cElementTree.iterparse


class UpdateNoticeException(Exception):
    """ An exception thrown for bad UpdateNotice data. """
    pass


class UpdateNotice(object):

    """
    A single update notice (for instance, a security fix).
    """

    def __init__(self, elem=None):
        self._md = {
            'from'             : '',
            'type'             : '',
            'title'            : '',
            'release'          : '',
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
===============================================================================
  %(title)s
===============================================================================
  Update ID : %(update_id)s
    Release : %(release)s
       Type : %(type)s
     Status : %(status)s
     Issued : %(issued)s
""" % self._md

        if self._md['updated'] and self._md['updated'] != self._md['issued']:
            head += "    Updated : %(updated)s" % self._md['updated']

        # Add our bugzilla references
        bzs = filter(lambda r: r['type'] == 'bugzilla', self._md['references'])
        if len(bzs):
            buglist = "       Bugs :"
            for bz in bzs:
                buglist += " %s%s\n\t    :" % (bz['id'], bz.has_key('title')
                                               and ' - %s' % bz['title'] or '')
            head += buglist[:-1].rstrip() + '\n'

        # Add our CVE references
        cves = filter(lambda r: r['type'] == 'cve', self._md['references'])
        if len(cves):
            cvelist = "       CVEs :"
            for cve in cves:
                cvelist += " %s\n\t    :" % cve['id']
            head += cvelist[:-1].rstrip() + '\n'

        desc = wrap(self._md['description'], width=64,
                    subsequent_indent=' ' * 12 + ': ')
        head += "Description : %s\n" % '\n'.join(desc)

        filelist = "      Files :"
        for pkg in self._md['pkglist']:
            for file in pkg['packages']:
                filelist += " %s\n\t    :" % file['filename']
        head += filelist[:-1].rstrip()

        return head

    def get_metadata(self):
        """ Return the metadata dict. """
        return self._md

    def _parse(self, elem):
        """
        Parse an update element::

            <!ELEMENT update (id, synopsis?, issued, updated,
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
                        raise UpdateNoticeException("No id element found")
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
                elif child.tag == 'title':
                    self._md['title'] = child.text
                elif child.tag == 'release':
                    self._md['release'] = child.text
        else:
            raise UpdateNoticeException('No update element found')

    def _parse_references(self, elem):
        """
        Parse the update references::

            <!ELEMENT references (reference*)>
            <!ELEMENT reference>
                <!ATTLIST reference href CDATA #REQUIRED>
                <!ATTLIST reference type (self|cve|bugzilla) "self">
                <!ATTLIST reference id CDATA #IMPLIED>
                <!ATTLIST reference title CDATA #IMPLIED>
        """
        for reference in elem:
            if reference.tag == 'reference':
                data = {}
                for refattrib in ('id', 'href', 'type', 'title'):
                    data[refattrib] = reference.attrib.get(refattrib)
                self._md['references'].append(data)
            else:
                raise UpdateNoticeException('No reference element found')

    def _parse_pkglist(self, elem):
        """
        Parse the package list::

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
        """
        Parse an individual package::

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

    """
    The root update metadata object.
    """

    def __init__(self):
        self._notices = {}
        self._cache = {}    # a pkg name => notice cache for quick lookups
        self._repos = []    # list of repo ids that we've parsed

    def get_notices(self):
        """ Return all notices. """
        return self._notices.values()

    notices = property(get_notices)

    def get_notice(self, nvr):
        """
        Retrieve an update notice for a given (name, version, release) string
        or tuple.
        """
        if type(nvr) in (type([]), type(())):
            nvr = '-'.join(nvr)
        return self._cache.has_key(nvr) and self._cache[nvr] or None

    def add(self, obj, mdtype='updateinfo'):
        """ Parse a metadata from a given YumRepository, file, or filename. """
        if not obj:
            raise UpdateNoticeException
        if type(obj) in (type(''), type(u'')):
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
    """ update_md test function. """
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
