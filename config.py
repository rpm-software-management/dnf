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
# Copyright 2002 Duke University 

import ConfigParser
import sys
import os
import urlparse
import string
import urllib

class yumConfigParser(ConfigParser.ConfigParser):
    def readfp(self, fp, filename=None):
        """Like read() but the argument must be a file-like object.
        The `fp' argument must have a `readline' method.  Optional
        second argument is the `filename', which if not given, is
        taken from fp.name.  If fp has no `name' attribute, `<???>' is
        used.
        """
        if filename is None:
            try:
                filename = fp.name
            except AttributeError:
                filename = '<???>'
        self.__read(fp, filename)

    def __read(self, fp, filename):
        """Parse a sectioned setup file.

        The sections in setup file contains a title line at the top,
        indicated by a name in square brackets (`[]'), plus key/value
        options lines, indicated by `name: value' format lines.
        Continuation are represented by an embedded newline then
        leading whitespace.  Blank lines, lines beginning with a '#',
        and just about everything else is ignored.
        """
        cursect = None                            # None, or a dictionary
        optname = None
        lineno = 0
        e = None                                  # None, or an exception
        while 1:
            line = fp.readline()
            if not line:
                break
            lineno = lineno + 1
            # comment or blank line?
            if string.strip(line) == '' or line[0] in '#;':
                continue
            if string.lower(string.split(line)[0]) == 'rem' \
               and line[0] == "r":      # no leading whitespace
                continue
            # continuation line?
            if line[0] in ' \t' and cursect is not None and optname:
                value = string.strip(line)
                if value:
                    cursect[optname] = cursect[optname] + '\n ' + value
            # a section header or option header?
            else:
                # is it a section header?
                mo = self.__SECTCRE.match(line)
                if mo:
                    sectname = mo.group('header')
                    if self.__sections.has_key(sectname):
                        cursect = self.__sections[sectname]
                    elif sectname == DEFAULTSECT:
                        cursect = self.__defaults
                    else:
                        cursect = {'__name__': sectname}
                        self.__sections[sectname] = cursect
                    # So sections can't start with a continuation line
                    optname = None
                # no section header in the file?
                elif cursect is None:
                    raise MissingSectionHeaderError(filename, lineno, `line`)
                # an option line?
                else:
                    mo = self.__OPTCRE.match(line)
                    if mo:
                        optname, optval = mo.group('option', 'value')
                        optname = string.lower(optname)
                        optval = string.strip(optval)
                        # allow empty values
                        if optval == '""':
                            optval = ''
                        cursect[optname] = optval
                    else:
                        # a non-fatal parsing error occurred.  set up the
                        # exception but keep going. the exception will be
                        # raised at the end of the file and will contain a
                        # list of all bogus lines
                        if not e:
                            e = ParsingError(filename)
                        e.append(lineno, `line`)
        # if any parsing errors occurred, raise an exception
        if e:
            raise e
            
class yumconf:
    def __init__(self, configfile = '/etc/yum.conf'):
        self.cfg = yumConfigParser()
        (s,b,p,q,f,o) = urlparse.urlparse(configfile)
        if s in ('http', 'ftp','file'):
            configfh = urllib.urlopen(configfile)
            try:
                self.cfg.readfp(configfh)
            except ConfigParser.MissingSectionHeaderError, e:
                print ('Error accessing URL: %s') % configfile
                sys.exit(1)
        else:
            if os.access(configfile, os.R_OK):
                self.cfg.read(configfile)
            else:
                print ('Error accessing File: %s') % configfile
                sys.exit(1)

        self.servers = []
        self.servername = {}
        self.serverurl = {}
        self.serverpkgdir = {}
        self.serverhdrdir = {}
        self.servercache = {}
        self.servergpgcheck={}
        self.excludes=[]
        
        #defaults
        self.cachedir='/var/cache/yum'
        self.debuglevel=2
        self.logfile='/var/log/yum.log'
        self.pkgpolicy='newest'
        self.gpghome='/root/.gnupg'
        self.gpgkeyring=None
        self.assumeyes=0
        self.errorlevel=2
        self.cache=0
        self.uid=0
        self.exactarch = 0
        
        if self._getoption('main','cachedir') != None:
            self.cachedir=self._getoption('main','cachedir')
        if self._getoption('main','debuglevel') != None:
            self.debuglevel=self._getoption('main','debuglevel')
        if self._getoption('main','logfile') != None:
            self.logfile=self._getoption('main','logfile')
        if self._getoption('main','pkgpolicy') != None:
            self.pkgpolicy=self._getoption('main','pkgpolicy')
        if self._getoption('main','exclude') != None:
            self.excludes=string.split(self._getoption('main','exclude'), ' ')
        if self._getoption('main','assumeyes') != None:
            self.assumeyes=self.cfg.getboolean('main','assumeyes')
        if self._getoption('main','errorlevel') != None:
            self.errorlevel=self._getoption('main','errorlevel')
        if self._getoption('main','gpghome') != None:
            self.gpghome=self._getoption('main','gpghome')
        if self._getoption('main','gpgkeyring') != None:
            self.gpgkeyring=self._getoption('main','gpgkeyring')
        if self._getoption('main','exactarch') != None:
            self.exactarch=self.cfg.getboolean('main','exactarch')
            
        if len(self.cfg.sections()) > 1:
            for section in self.cfg.sections(): # loop through the list of sections
                if section != 'main': # must be a serverid
                    name = self._getoption(section,'name')
                    url = self._getoption(section,'baseurl')
                    if name != None and url != None:
                        self.servers.append(section)
                        self.servername[section] = name
                        self.serverurl[section] = url
                        if self._getoption(section,'gpgcheck') != None:
                            self.servergpgcheck[section]=self.cfg.getboolean(section,'gpgcheck')
                        else:
                            self.servergpgcheck[section]=0
                        (s,b,p,q,f,o) = urlparse.urlparse(self.serverurl[section])
                        # currently only allowing http and ftp servers 
                        if s not in ['http', 'ftp']:
                            print 'Not using ftp or http for servers, Aborting - %s' % (self.serverurl[section])
                            sys.exit(1)
                        cache = os.path.join(self.cachedir,section)
                        pkgdir = os.path.join(cache, 'packages')
                        hdrdir = os.path.join(cache, 'headers')
                        self.servercache[section] = cache
                        self.serverpkgdir[section] = pkgdir
                        self.serverhdrdir[section] = hdrdir
                    else:
                        print 'Error: Cannot find baseurl or name for server \'%s\'. Skipping' %(section)    
        else:
            print 'Insufficient server config - no servers found. Aborting.'
            sys.exit(1)

    def _getoption(self, section, option):
        try:
            return self.cfg.get(section, option)
        except ConfigParser.NoSectionError, e:
            print 'Failed to find section: %s' % section
        except ConfigParser.NoOptionError, e:
            return None
        
   
