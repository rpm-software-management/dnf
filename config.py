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

from i18n import _


class yumconf:

    def __init__(self, configfile = '/etc/yum.conf'):
        self.cfg = ConfigParser.ConfigParser()
        (s,b,p,q,f,o) = urlparse.urlparse(configfile)
        if s in ('http', 'ftp','file'):
            configfh = urllib.urlopen(configfile)
            try:
                self.cfg.readfp(configfh)
            except ConfigParser.MissingSectionHeaderError, e:
                print _('Error accessing URL: %s') % configfile
                sys.exit(1)
        else:
            if os.access(configfile, os.R_OK):
                self.cfg.read(configfile)
            else:
                print _('Error accessing File: %s') % configfile
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
        self.retries = 3
        self.installroot = '/'
        self.installonlypkgs = ['kernel', 'kernel-bigmem', 'kernel-enterprise',
                           'kernel-smp', 'kernel-debug', 'kernel-unsupported']
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
            self.commands = self.commands.split(' ')

        if self._getoption('main','installonlypkgs') != None:
            self.installonlypkgs = self._getoption('main', 'installonlypkgs')
            self.installonlypkgs = self._doreplace(self.installonlypkgs)
            self.installonlypkgs = self.installonlypkgs.split(' ')

        if self._getoption('main','kernelpkgnames') != None:
            self.kernelpkgnames = self._getoption('main', 'kernelpkgnames')
            self.kernelpkgnames = self._doreplace(self.kernelpkgnames)
            self.kernelpkgnames = self.kernelpkgnames.split(' ')

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
        listrepl = re.compile('\n')
        (value, count) = listrepl.subn(' ', value)
        listvalue = string.split(value)
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
        idx = ts.dbMatch('name', self.distroverpkg)
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
