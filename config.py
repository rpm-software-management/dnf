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
import os.path
import urlparse
import string
import urllib
import rpm
import re
import failover
import archwork
import rpmUtils
import progress_meter
import urlgrabber

from i18n import _


class yumconf:

    def __init__(self, configfile = '/etc/yum.conf'):
        self.cfg = ConfigParser.ConfigParser()
        configh = confpp(configfile)
        try:
            self.cfg.readfp(configh)
        except ConfigParser.MissingSectionHeaderError, e:
            print _('Error accessing config file: %s') % configfile
            sys.exit(1)
        
        self.servers = []
        self.servername = {}
        self.serverurl = {}
        self.serverpkgdir = {}
        self.serverhdrdir = {}
        self.servercache = {}
        self.servergpgcheck={}
        self.serverexclude={}
        self.failoverclass = {}
        self.excludes=[]
        
        #defaults
        self.cachedir = '/var/cache/yum'
        self.debuglevel = 2
        self.logfile = '/var/log/yum.log'
        self.pkgpolicy = 'newest'
        self.assumeyes = 0
        self.errorlevel = 2
        self.cache = 0
        self.uid = 0
        self.yumversion = 'unversioned'
        self.commands = None
        self.exactarch = 0
        self.overwrite_groups = 0
        self.groups_enabled = 0
        self.diskspacecheck = 1
        self.tolerant = 0
        self.yumvar = self._getEnvVar()
        self.distroverpkg = 'redhat-release'
        self.yumvar['basearch'] = archwork.getArch()
        self.yumvar['arch'] = os.uname()[4]
        self.bandwidth = None
        self.throttle = None
        self.retries = 6
        self.progress_obj = progress_meter.text_progress_meter(fo=sys.stdout)
        self.installroot = '/'
        self.installonlypkgs = ['kernel', 'kernel-bigmem', 'kernel-enterprise',
                           'kernel-smp', 'kernel-debug', 'kernel-unsupported', 
                           'kernel-source']
        self.kernelpkgnames = ['kernel','kernel-smp','kernel-enterprise',
                           'kernel-bigmem','kernel-BOOT']
      
        if self._getoption('main','cachedir') != None:
            self.cachedir = self._getoption('main','cachedir')
        if self._getoption('main','debuglevel') != None:
            self.debuglevel = self._getoption('main','debuglevel')
        if self._getoption('main','logfile') != None:
            self.logfile = self._getoption('main','logfile')
        if self._getoption('main','pkgpolicy') != None:
            self.pkgpolicy = self._getoption('main','pkgpolicy')
        if self._getoption('main','assumeyes') != None:
            self.assumeyes = self.cfg.getboolean('main', 'assumeyes')
        if self._getoption('main','errorlevel') != None:
            self.errorlevel = self._getoption('main', 'errorlevel')
        if self._getoption('main','exactarch') != None:
            self.exactarch = self.cfg.getboolean('main', 'exactarch')
        if self._getoption('main','overwrite_groups') != None:
            self.overwrite_groups = self.cfg.getboolean('main', 'overwrite_groups')
        if self._getoption('main','diskspacecheck') != None:
            self.diskspacecheck = self.cfg.getboolean('main', 'diskspacecheck')
        if self._getoption('main','tolerant') != None:
            self.tolerant = self.cfg.getboolean('main', 'tolerant')
        if self._getoption('main', 'distroverpkg') != None:
            self.distroverpkg = self._getoption('main','distroverpkg')
        if self._getoption('main', 'bandwidth') != None:
            self.bandwidth = self._getoption('main','bandwidth')
        if self._getoption('main', 'throttle') != None:
            self.throttle = self._getoption('main','throttle')
        if self._getoption('main', 'retries') != None:
            self.retries = self.cfg.getint('main','retries')
        if self._getoption('main', 'installroot') != None:
            self.installroot = self._getoption('main','installroot')

            
        # figure out what the releasever really is from the distroverpkg
        self.yumvar['releasever'] = self._getsysver()
        
        if self._getoption('main','commands') != None:
            self.commands = self._getoption('main', 'commands')
            self.commands = self._doreplace(self.commands)
            self.commands = self.parseList(self.commands)

        if self._getoption('main','installonlypkgs') != None:
            self.installonlypkgs = self._getoption('main', 'installonlypkgs')
            self.installonlypkgs = self._doreplace(self.installonlypkgs)
            self.installonlypkgs = self.parseList(self.installonlypkgs)

        if self._getoption('main','kernelpkgnames') != None:
            self.kernelpkgnames = self._getoption('main', 'kernelpkgnames')
            self.kernelpkgnames = self._doreplace(self.kernelpkgnames)
            self.kernelpkgnames = self.parseList(self.kernelpkgnames)

        # get the global exclude lists.
        if self._getoption('main','exclude') != None:
            self.excludes = self._getoption('main','exclude')
            self.excludes = self._doreplace(self.excludes)
            self.excludes = self.parseList(self.excludes)
            

        if len(self.cfg.sections()) > 1:
            for section in self.cfg.sections(): # loop through the list of sections
                if section != 'main': # must be a serverid
                    if self._getoption(section, 'baseurl') != None:
                        name = self._getoption(section, 'name')
                        urls = self._getoption(section, 'baseurl')
                        urls = self._doreplace(urls)
                        urls = self.parseList(urls)
                    else:
                        name = None
                        urls = []
                        
                    if name != None and len(urls) > 0 and urls[0] != None:
                        self.servers.append(section)
                        name = self._doreplace(name)
                        self.servername[section] = name
                        self.serverurl[section] = urls
                        
                        failmeth = self._getoption(section,'failovermethod')
                        if failmeth == 'roundrobin':
                            failclass = failover.roundRobin(self, section)
                        elif failmeth == 'priority':
                            failclass = failover.priority(self, section)
                        else:
                            failclass = failover.roundRobin(self, section)
                        self.failoverclass[section] = failclass
                        
                        if self._getoption(section,'gpgcheck') != None:
                            self.servergpgcheck[section]=self.cfg.getboolean(section,'gpgcheck')
                        else:
                            self.servergpgcheck[section]=0
                        if self._getoption(section, 'exclude') != None:
                            srvexcludelist = self._getoption(section, 'exclude')
                            srvexcludelist = self._doreplace(srvexcludelist)
                            srvexcludelist = self.parseList(srvexcludelist)
                        else:
                            srvexcludelist = []
                        self.serverexclude[section] = srvexcludelist
                        
                        for url in self.serverurl[section]:
                            (s,b,p,q,f,o) = urlparse.urlparse(url)
                            # currently only allowing http and ftp servers 
                            if s not in ['http', 'ftp', 'file', 'https']:
                                print _('using ftp, http[s], or file for servers, Aborting - %s') % (url)
                                sys.exit(1)

                        cache = os.path.join(self.cachedir,section)
                        pkgdir = os.path.join(cache, 'packages')
                        hdrdir = os.path.join(cache, 'headers')
                        self.servercache[section] = cache
                        self.serverpkgdir[section] = pkgdir
                        self.serverhdrdir[section] = hdrdir
                    else:
                        print _('Error: Cannot find baseurl or name for server \'%s\'. Skipping') %(section)    
        else:
            print _('Insufficient server config - no servers found. Aborting.')
            sys.exit(1)

    def _getoption(self, section, option):
        try:
            return self.cfg.get(section, option)
        except ConfigParser.NoSectionError, e:
            print _('Failed to find section: %s') % section
        except ConfigParser.NoOptionError, e:
            return None
            
    def parseList(self, value):
        listvalue = []
        # we need to allow for the '\n[whitespace]' continuation - easier
        # to sub the \n with a space and then read the lines
        slashnrepl = re.compile('\n')
        commarepl = re.compile(',')
        (value, count) = slashnrepl.subn(' ', value)
        (value, count) = commarepl.subn(' ', value)
        listvalue = value.split()
        return listvalue

    def remoteGroups(self, serverid):
        return os.path.join(self.baseURL(serverid), 'yumgroups.xml')
    
    def localGroups(self, serverid):
        return os.path.join(self.servercache[serverid], 'yumgroups.xml')
        
    def baseURL(self, serverid):
        return self.get_failClass(serverid).get_serverurl()
        
    def server_failed(self, serverid):
        self.failoverclass[serverid].server_failed()
    
    def get_failClass(self, serverid):
        return self.failoverclass[serverid]
        
    def remoteHeader(self, serverid):
        return os.path.join(self.baseURL(serverid), 'headers/header.info')
        
    def localHeader(self, serverid):
        return os.path.join(self.servercache[serverid], 'header.info')

    def _getsysver(self):
        ts = rpm.TransactionSet()
        ts.setVSFlags(~(rpm._RPMVSF_NOSIGNATURES|rpm._RPMVSF_NODIGESTS))
        idx = ts.dbMatch('provides', self.distroverpkg)
        # we're going to take the first one - if there is more than one of these
        # then the user needs a beating
        if idx.count() == 0:
            releasever = 'Null'
        else:
            hdr = idx.next()
            releasever = hdr['version']
            del hdr
        del idx
        del ts
        return releasever
    
    def _getEnvVar(self):
        yumvar = {}
        yumvar[0] = os.environ.get('YUM0','$YUM0')
        yumvar[1] = os.environ.get('YUM1','$YUM1')
        yumvar[2] = os.environ.get('YUM2','$YUM2')
        yumvar[3] = os.environ.get('YUM3','$YUM3')
        yumvar[4] = os.environ.get('YUM4','$YUM4')
        yumvar[5] = os.environ.get('YUM5','$YUM5')
        yumvar[6] = os.environ.get('YUM6','$YUM6')
        yumvar[7] = os.environ.get('YUM7','$YUM7')
        yumvar[8] = os.environ.get('YUM8','$YUM8')
        yumvar[9] = os.environ.get('YUM9','$YUM9')
        
        return yumvar
        
    def _doreplace(self, string):
        """ do the replacement of yumvar, release, arch and basearch on any 
            string passed to it"""
        if string is None:
            return string
        basearch_reg = re.compile('\$basearch')
        arch_reg = re.compile('\$arch')
        releasever_reg = re.compile('\$releasever')
        yum0_reg = re.compile('\$YUM0')
        yum1_reg = re.compile('\$YUM1')
        yum2_reg = re.compile('\$YUM2')
        yum3_reg = re.compile('\$YUM3')
        yum4_reg = re.compile('\$YUM4')
        yum5_reg = re.compile('\$YUM5')
        yum6_reg = re.compile('\$YUM6')
        yum7_reg = re.compile('\$YUM7')
        yum8_reg = re.compile('\$YUM8')
        yum9_reg = re.compile('\$YUM9')
        
        (string, count) = basearch_reg.subn(self.yumvar['basearch'], string)
        (string, count) = arch_reg.subn(self.yumvar['arch'], string)
        (string, count) = releasever_reg.subn(self.yumvar['releasever'], string)
        (string, count) = yum0_reg.subn(self.yumvar[0], string)
        (string, count) = yum1_reg.subn(self.yumvar[1], string)
        (string, count) = yum2_reg.subn(self.yumvar[2], string)
        (string, count) = yum3_reg.subn(self.yumvar[3], string)
        (string, count) = yum4_reg.subn(self.yumvar[4], string)
        (string, count) = yum5_reg.subn(self.yumvar[5], string)
        (string, count) = yum6_reg.subn(self.yumvar[6], string)
        (string, count) = yum7_reg.subn(self.yumvar[7], string)
        (string, count) = yum8_reg.subn(self.yumvar[8], string)
        (string, count) = yum9_reg.subn(self.yumvar[9], string)
        
        return string


# Issues/Concerns:
#   * There are a couple of places that call sys.exit.. it may
#     be preferable to throw a exception instead and let yumconf
#     handle the exit
class confpp:
    """
    ConfigParser Include Pre-Processor
    
        File-like Object capable of pre-processing include= lines for
        a ConfigParser. 
        
        The readline function expands lines matching include=(url)
        into lines from the url specified. Includes may occur in
        included files as well. 
        
        Suggested Usage:
            cfg = ConfigParser.ConfigParser()
            fileobj = confpp( fileorurl )
            cfg.readfp(fileobj)
    """
    
    
    def __init__(self, configfile):
        # set some file-like object attributes for ConfigParser
        # these just make confpp look more like a real file object.
        self.mode = 'r' 
        
        # establish whether to use urlgrabber or urllib
        # we want to use urlgrabber if it supports urlopen
        if hasattr(urlgrabber,'urlopen'):   self._urlresolver = urlgrabber
        else: self._urlresolver = urllib
        
        # first make configfile a url even if it points to 
        # a local file
        scheme = urlparse.urlparse(configfile)[0]
        if scheme == '':
            url = 'file://' + configfile
        else:
            url = configfile
        
        # these are used to maintain the include stack and check
        # for recursive/duplicate includes
        self._incstack = []
        self._alreadyincluded = []
        
        # _pushfile will return None if he couldn't open the file
        fo = self._pushfile( url )
        if fo is None: 
            print _('Error accessing file: %s') % url
            sys.exit(1)
        
    
    def readline( self, size=0 ):
        """
        Implementation of File-Like Object readline function. This should be
        the only function called by ConfigParser according to the python docs.
        We maintain a stack of real FLOs and delegate readline calls to the 
        FLO on top of the stack. When EOF occurs on the topmost FLO, it is 
        popped off the stack and the next FLO takes over. include= lines 
        found anywhere cause a new FLO to be opened and pushed onto the top 
        of the stack. Finally, we return EOF when the bottom-most (configfile
        arg to __init__) FLO returns EOF.
        
        Very Technical Pseudo Code:
        
        def confpp.readline() [this is called by ConfigParser]
            open configfile, push on stack
            while stack has some stuff on it
                line = readline from file on top of stack
                pop and continue if line is EOF
                if line starts with 'include=' then
                    error if file is recursive or duplicate
                    otherwise open file, push on stack
                    continue
                else
                    return line
            
            return EOF
        """
        
        # set line to EOF initially. 
        line=''
        while len(self._incstack) > 0:
            # peek at the file like object on top of the stack
            fo = self._incstack[-1]
            line = fo.readline()
            if len(line) > 0:
                m = re.match( r'\s*include\s*=\s*(?P<url>.*)', line )
                if m:
                    url = m.group('url')
                    if len(url) == 0:
                        print _('Error parsing config %s: include must specify '
                                ' file to include.') % (self.name)
                        sys.exit(1)
                    else:
                        # whooohoo a valid include line.. push it on the stack
                        fo = self._pushfile( url )
                else:
                    # line didn't match include=, just return it as is
                    # for the ConfigParser
                    break
            else:
                # the current file returned EOF, pop it off the stack.
                self._popfile()
        
        # at this point we have a line from the topmost file on the stack
        # or EOF if the stack is empty
        return line
    
    
    def _absurl( self, url ):
        """
        Returns an absolute url for the (possibly) relative
        url specified. The base url used to resolve the
        missing bits of url is the url of the file currently
        being included (i.e. the top of the stack).
        """
        
        if len(self._incstack) == 0:
            # it's the initial config file. No base url to resolve against.
            return url
        else:
            return urlparse.urljoin( self.geturl(), url )
    
    
    def _pushfile( self, url ):
        """
        Opens the url specified, pushes it on the stack, and 
        returns a file like object. Returns None if the url 
        has previously been included.
        If the file can not be opened this function exits.
        """
        
        # absolutize this url using the including files url
        # as a base url.
        absurl = self._absurl(url)
        # check if this has previously been included.
        if self._urlalreadyincluded(absurl):
            print _('Warning: Config file %s tried to include %s' 
                    ' but it has already been included (possible recursion).' 
                    ' Skipping..') % (self.name,absurl)
            return None
        
        fo = self._urlresolver.urlopen(absurl)
        if not fo is None:
            print _('Including %s in config') % absurl
            self.name = absurl
            self._incstack.append( fo )
            self._alreadyincluded.append(absurl)
        else:
            print _('Error accessing file: Config file %s tried ' 
                    'to include %s') % (self.name, absurl)
            sys.exit(1)
        return fo
    
    
    def _popfile( self ):
        """
        Pop a file off the stack signaling completion of including that file.
        """
        fo = self._incstack.pop()
        fo.close()
        if len(self._incstack) > 0:
            self.name = self._incstack[-1].geturl()
        else:
            self.name = None
    
    
    def _urlalreadyincluded( self, url ):
        """
        Checks if the url has already been included at all.. this 
        does not necessarily have to be recursive
        """
        for eurl in self._alreadyincluded:
            if eurl == url: return 1
        return 0
    
    
    def geturl(self): return self.name
