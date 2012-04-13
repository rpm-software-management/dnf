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
#
# Copyright 2008 Red Hat
#
# James Antill <james@fedoraproject.org>

# Parse the new MirrorManager metalink output:

import sys
import os
import time
from urlgrabber.progress import format_number

import Errors

from yum.misc import cElementTree_xmlparse as xmlparse

class MetaLinkRepoErrorParseFail(Errors.RepoError):
    """ An exception thrown for an unparsable MetaLinkRepoMD file. """
    pass

__XML_NS_ML__ = 'http://www.metalinker.org/'
__XML_NS_MM__ = 'http://fedorahosted.org/mirrormanager'
__XML_FMT__   = {'ml' : __XML_NS_ML__,
                 'mm' : __XML_NS_MM__}

__ML_FILE_ELEMENT__ = """\
{%(ml)s}files/{%(ml)s}file\
""" % __XML_FMT__
__ML_OLD_FILE_ELEMENTS__ = """\
{%(mm)s}alternates/{%(mm)s}alternate\
""" % __XML_FMT__
__ML_RESOURCES__ = """\
{%(ml)s}resources\
""" % __XML_FMT__

class MetaLinkFile:
    """ Parse the file metadata out of a metalink file. """

    def __init__(self, elem):
        # We aren't "using" any of these, just storing them.
        chksums = set(["md5", 'sha1', 'sha256', 'sha512'])

        for celem in elem:
            if False: pass
            elif celem.tag == "{%s}timestamp" % __XML_NS_MM__:
                self.timestamp = int(celem.text)
            elif celem.tag == "{%s}size" % __XML_NS_ML__:
                self.size = int(celem.text)
            elif celem.tag == "{%s}verification" % __XML_NS_ML__:
                self.chksums = {}
                for helem in celem:
                    if (helem.tag == "{%s}hash"  % __XML_NS_ML__ and
                        helem.get("type") in chksums):
                        self.chksums[helem.get("type").lower()] = helem.text

        if not hasattr(self, 'timestamp'):
            raise MetaLinkRepoErrorParseFail, "No timestamp for file"
        if not hasattr(self, 'size'):
            raise MetaLinkRepoErrorParseFail, "No size for file"
        if not hasattr(self, 'chksums'):
            raise MetaLinkRepoErrorParseFail, "No verifications for file"

    def __str__(self):
        return """\
Timestamp: %s
Size:      %5s (%d)
MD5:       %s
SHA1:      %s
SHA256:    %s
SHA512:    %s
""" % (time.ctime(self.timestamp), format_number(self.size), self.size,
       self.md5, self.sha1, self.sha256, self.sha512)

    def _get_md5(self):
        return self.chksums.get('md5', '')
    md5 = property(_get_md5)
    def _get_sha1(self):
        return self.chksums.get('sha1', '')
    sha1 = property(_get_sha1)
    def _get_sha256(self):
        return self.chksums.get('sha256', '')
    sha256 = property(_get_sha256)
    def _get_sha512(self):
        return self.chksums.get('sha512', '')
    sha512 = property(_get_sha512)

    def __cmp__(self, other):
        if other is None:
            return 1
        ret = cmp(self.timestamp, other.timestamp)
        if ret:
            return -ret
        ret = cmp(self.size, other.size)
        if ret:
            return ret
        ret = cmp(self.md5, other.md5)
        if ret:
            return ret
        ret = cmp(self.sha1, other.sha1)
        if ret:
            return ret
        ret = cmp(self.sha256, other.sha256)
        if ret:
            return ret
        ret = cmp(self.sha512, other.sha512)
        if ret:
            return ret
        return 0


class MetaLinkURL:
    """ Parse the URL metadata out of a metalink file. """

    def __init__(self, elem, max_connections):
        assert elem.tag == '{%s}url' % __XML_NS_ML__

        self.max_connections = max_connections

        self.url        = elem.text
        self.preference = int(elem.get("preference", -1))
        self.protocol   = elem.get("type") # This is the "std" attribute name
        self.location   = elem.get("location")
        self.private    = elem.get("{%s}private" % __XML_NS_MM__, "false")
        self.private    = self.private.lower() == "true"

        if self.protocol is None: # Try for the old MM protocol attribute
            self.protocol   = elem.get("protocol")

    def __str__(self):
        return """\
URL:             %s
Preference:      %d
Max-Connections: %d
Protocol:        %s
Location:        %s
Private:         %s
""" % (self.url, self.preference, self.max_connections,
       self.protocol, self.location, self.private)

    def __cmp__(self, other):
        if other is None:
            return 1
        ret = cmp(self.preference, other.preference)
        if ret:
            return -ret
        ret = cmp(self.protocol == "https", other.protocol == "https")
        if ret:
            return -ret
        ret = cmp(self.protocol == "http", other.protocol == "http")
        if ret:
            return -ret
        return cmp(self.url, other.url)

    def usable(self):
        if self.protocol is None:
            return False
        if not self.url:
            return False
        return True

class MetaLinkRepoMD:
    """ Parse a metalink file for repomd.xml. """

    def __init__(self, filename):
        self.name   = None
        self.repomd = None
        self.old_repomds = []
        self.mirrors = []
        if not os.path.exists(filename):
            raise MetaLinkRepoErrorParseFail, "File %s does not exist" %filename
        try:
            root = xmlparse(filename)
        except SyntaxError:
            raise MetaLinkRepoErrorParseFail, "File %s is not XML" % filename

        for elem in root.findall(__ML_FILE_ELEMENT__):
            name = elem.get('name')
            if os.path.basename(name) != 'repomd.xml':
                continue

            if self.name is not None and self.name != name:
                raise MetaLinkRepoErrorParseFail, "Different paths for repomd file"
            self.name = name

            repomd = MetaLinkFile(elem)

            if self.repomd is not None and self.repomd != repomd:
                raise MetaLinkRepoErrorParseFail, "Different data for repomd file"
            self.repomd = repomd

            for celem in elem.findall(__ML_OLD_FILE_ELEMENTS__):
                self.old_repomds.append(MetaLinkFile(celem))

            for celem in elem.findall(__ML_RESOURCES__):
                max_connections = int(celem.get("maxconnections"))
                for uelem in celem:
                    if uelem.tag == "{%s}url"  % __XML_NS_ML__:
                        self.mirrors.append(MetaLinkURL(uelem, max_connections))

        self.old_repomds.sort()
        self.mirrors.sort()

        if self.repomd is None:
            raise MetaLinkRepoErrorParseFail, "No repomd file"
        if len(self.mirrors) < 1:
            raise MetaLinkRepoErrorParseFail, "No mirror"

    def urls(self):
        """ Iterate plain urls for the mirrors, like the old mirrorlist. """

        # Get the hostname from a url, stripping away any usernames/passwords
        # Borrowd from fastestmirror
        url2host = lambda url: url.split('/')[2].split('@')[-1]
        hosts = set() # Don't want multiple urls for one host in plain mode
                      # The list of URLs is sorted, so http is before ftp

        for mirror in self.mirrors:
            url = mirror.url

            # This is what yum supports atm. ... no rsync etc.
            if url.startswith("file:"):
                pass
            elif (url.startswith("http:") or url.startswith("ftp:") or
                  url.startswith("https:")):
                host = url2host(url)
                if host in hosts:
                    continue
                hosts.add(host)
            else:
                continue

            #  The mirror urls in the metalink file are for repomd.xml so it
            # gives a list of mirrors for that one file, but we want the list
            # of mirror baseurls. Joy of reusing other people's stds. :)
            if not url.endswith("/repodata/repomd.xml"):
                continue
            yield url[:-len("/repodata/repomd.xml")]

    def __str__(self):
        ret = str(self.repomd)
        done = False
        for orepomd in self.old_repomds:
            if not done: ret += "%s\n" % ("-" * 79)
            if done:     ret += "\n"
            done = True
            ret += str(orepomd)
        done = False
        for url in self.mirrors:
            if not done: ret += "%s\n" % ("-" * 79)
            if done:     ret += "\n"
            done = True
            ret += str(url)
        return ret


def main():
    """ MetaLinkRepoMD test function. """

    def usage():
        print >> sys.stderr, "Usage: %s <metalink> ..." % sys.argv[0]
        sys.exit(1)

    if len(sys.argv) < 2:
        usage()

    for filename in sys.argv[1:]:
        if not os.path.exists(filename):
            print "No such file:", filename
            continue

        print "File:", filename
        print MetaLinkRepoMD(filename)
        print ''

if __name__ == '__main__':
    main()
