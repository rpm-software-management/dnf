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

import ConfigParser,sys,os, urlparse
class yumconf:

	def __init__(self):
		self.cfg = ConfigParser.ConfigParser()
		self.cfg.read(["/etc/yum.conf"])
		self.servers = []
		self.servername = {}
		self.serverurl = {}
		self.serverpkgdir = {}
		self.serverhdrdir = {}
		self.servercache = {}
		#defaults
		self.cachedir='/var/cache/yum'
		self.debuglevel=2
		self.logfile='/var/log/yum.log'
		self.pkgpolicy='newest'
		
		if self._getoption('main','cachedir') != None:
			self.cachedir=self._getoption('main','cachedir')
		if self._getoption('main','debuglevel') != None:
			self.debuglevel=self._getoption('main','debuglevel')
		if self._getoption('main','logfile') != None:
			self.logfile=self._getoption('main','logfile')
		if self._getoption('main','pkgpolicy') != None:
			self.pkgpolicy=self._getoption('main','pkgpolicy')
		
		if len(self.cfg.sections()) > 1:
			for section in self.cfg.sections(): # loop through the list of sections
				if section != 'main': #must be a serverid
					name = self._getoption(section,'name')
					url = self._getoption(section,'baseurl')
					if name != None and url != None:
						self.servers.append(section)
						self.servername[section] = name
						self.serverurl[section] = url
						(s,b,p,q,f,o) = urlparse.urlparse(self.serverurl[section])
						#currently only allowing http and ftp servers 
						if s not in ['http', 'ftp']:
							print "Not using ftp or http for servers, Aborting - %s" % (self.serverurl[section])
							sys.exit(1)
						cache = os.path.join(self.cachedir,section)
						pkgdir = os.path.join(cache,'packages')
						hdrdir = os.path.join(cache,'headers')
						self.servercache[section] = cache
						self.serverpkgdir[section] = pkgdir
						self.serverhdrdir[section] = hdrdir
					else:
						print "Error: Cannot find baseurl or name for server '%s'. Skipping" %(section)	
		else:
			print "Insufficient server config - no servers found. Aborting."
			sys.exit(1)

	def _getoption(self, section, option):
		try:
			return self.cfg.get(section, option)
		except ConfigParser.NoSectionError, e:
			print "Failed to find section: %s" % section
		except ConfigParser.NoOptionError, e:
			return None

conf=yumconf()
        
   