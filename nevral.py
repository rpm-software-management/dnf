#!/usr/bin/python
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

import os
import config
import clientStuff
import rpm
import string

class nevral:

	def __init__(self):
		import string
		self.rpmbyname = {}
		self.rpmbynamearch = {}
			
	def add(self,(name,epoch,ver,rel,arch,rpmloc,serverid),state):
#		if self.rpmbyname.haskey(name):
#			((e,v,r,a,l,i),state) = self._get_data(name)
#			goodarch = clientStuff.betterarch(arch,a)
#			if goodarch != None:
#				if goodarch == arch:
#					self.rpmbyname[name]=((epoch,ver,rel,arch,rpmloc,serverid), state)
		self.rpmbyname[name]=((epoch,ver,rel,arch,rpmloc,serverid), state)
		self.rpmbynamearch[(name,arch)]=((epoch,ver,rel,arch,rpmloc,serverid), state)
		
	def _get_data(self, name, arch=None):
		if arch != None: # search by name and arch
			if self.rpmbynamearch and self.rpmbynamearch.has_key((name, arch)):
				return self.rpmbynamearch[(name, arch)]
			else: 
				return ((None,None,None,None,None,None),None)
		else:            # search by name only
			if self.rpmbyname and self.rpmbyname.has_key(name):
				return self.rpmbyname[name]
			else: 
				return ((None,None,None,None,None,None),None)

	def getHeader(self, name, arch=None):
		((e,v,r,a,l,i),state) = self._get_data(name, arch)
		if state == None: 
			return None
		else: 
			if l == 'in_rpm_db':
				#we're in the rpmdb - get the header from there
				db = clientStuff.openrpmdb()
				rpms = db.findbyname(name)
				#this needs to do A LOT MORE if it find multiples
				for rpm in rpms:
					pkghdr = db[rpm]
					return pkghdr
			else:
				#we're in a .hdr file
				#         print '%s, %s' % (name, arch)
				pkghdr = clientStuff.readHeader(self.localHdrPath(name, arch))
				return pkghdr  

	def NAkeys(self):
		keys = self.rpmbynamearch.keys()
		return keys

	def Nkeys(self):
		keys = self.rpmbyname.keys()
		return keys

	def hdrfn(self, name, arch=None):
		((e,v,r,a,l,i),state) = self._get_data(name, arch)
		if state == None: 
			return None
		else: 
			return "%s-%s-%s-%s.%s.hdr" % (name, e, v, r, a)

	def rpmlocation(self, name, arch=None):
		((e,v,r,a,l,i),state) = self._get_data(name, arch)
		if state == None: 
			return None
		else:
			return l
      
	def evr(self, name, arch=None):
		((e,v,r,a,l,i),state) = self._get_data(name, arch)
		if state == None: 
			return None
		else:
			return (e, v, r)

	def exists(self, name, arch=None):
		((e,v,r,a,l,i),state) = self._get_data(name, arch)
		if state == None: 
			return 0
		else:
			return 1

	def state(self, name, arch=None):
		((e,v,r,a,l,i),state) = self._get_data(name, arch)
		if state == None: 
			return None
		else:
			return state
			
	def serverid(self, name, arch=None):
		((e,v,r,a,l,i),state) = self._get_data(name, arch)
		if state == None: 
			return None
		else:
			return i
			
	def nafromloc(self, loc):
		keys = self.rpmbynamearch.keys()
		for (name, arch) in keys:
			((e,v,r,a,l,i),state) = self._get_data(name, arch)
			if state == None: 
				return None
			else:
				if l == loc:
					return (name,arch)
	
	def remoteHdrUrl(self, name, arch=None):
		((e,v,r,a,l,i),state) = self._get_data(name, arch)
		if state == None:
			return None
		if l == 'in_rpm_db':
			return l
		hdrfn = self.hdrfn(name,arch)
		base = config.conf.serverurl[i]
		return base + '/headers/' + hdrfn
	
	def localHdrPath(self, name, arch=None):
		((e,v,r,a,l,i),state) = self._get_data(name, arch)
		if state == None:
			return None
		if l == 'in_rpm_db':
			return l
		hdrfn = self.hdrfn(name,arch)
		base = config.conf.serverhdrdir[i]
		return base + '/' + hdrfn
		
	def remoteRpmUrl(self, name, arch=None):
		((e,v,r,a,l,i),state) = self._get_data(name, arch)
		if state == None:
			return None
		if l == 'in_rpm_db':
			return l
		base = config.conf.serverurl[i]
		return base +'/'+ l
	
	def localRpmPath(self, name, arch=None):
		((e,v,r,a,l,i),state) = self._get_data(name, arch)
		if state == None:
			return None
		if l == 'in_rpm_db':
			return l
		rpmfn = os.path.basename(l)
		base = config.conf.serverpkgdir[i]
		return base + '/' + rpmfn
				
	def resolvedeps(self):
		#self == tsnevral
		#create db
		#create ts
		#populate ts
		#depcheck
		#parse deps, if they exist, change nevral pkg states
		#die if:
		#	no suggestions
		#	conflicts
		#return 0 and a message if all is fine
		#return 1 and a list of error messages if shit breaks
		import clientStuff, rpm, archwork
		CheckDeps = 1
		conflicts = 0
		unresolvable = 0
		errors=[]
		while CheckDeps==1 or (conflicts != 1 and unresolvable != 1 ):
			db = clientStuff.openrpmdb(0)
			ts = rpm.TransactionSet('/',db)
			for (name, arch) in self.NAkeys(): 
				rpmloc = self.rpmlocation(name, arch)
				pkghdr = self.getHeader(name, arch)
				if self.state(name, arch) == 'u' or self.state(name,arch) == 'ud':
					#print 'updating %s, %s' % (name, arch)
					if name == 'kernel' or name == 'kernel-bigmem' or name == 'kernel-enterprise' or name == 'kernel-smp' or name == 'kernel-debug':
						ts.add(pkghdr,(pkghdr,rpmloc),'i')
						((e, v, r, a, l, i), s)=self._get_data(name,arch)
						self.add((name,e,v,r,arch,l,i),'i')            
					else:
						ts.add(pkghdr,(pkghdr,rpmloc),'u')
					
				elif self.state(name,arch) == 'i':
					#print 'installing %s, %s' % (name, arch)
					ts.add(pkghdr,(pkghdr,rpmloc),'i')
				elif self.state(name,arch) == 'a':
					ts.add(pkghdr,(pkghdr,rpmloc),'a')
				elif self.state(name,arch) == 'e':
					ts.remove(name)
				#   state = self.state(name,arch)
				#   ts.add(pkghdr,(pkghdr,rpmloc),state)   
			deps=ts.depcheck()
			CheckDeps = 0
			if not deps:
				return (0, "Success - deps resolved")
						
			for ((name, version, release), (reqname, reqversion),
								flags, suggest, sense) in deps:
				if sense == rpm.RPMDEP_SENSE_REQUIRES:
					if suggest:
						(header, sugname) = suggest
						(name, arch) = self.nafromloc(sugname)
						((e, v, r, a, l, i), s)=self._get_data(name,arch)
						self.add((name,e,v,r,arch,l,i),'ud')          
						#print "Got dep: %s, %s" % (name,arch)
						CheckDeps = 1
					else:
						if self.exists(reqname):
							archlist = archwork.availablearchs(self,name)
							arch = archwork.bestarch(archlist)
							((e, v, r, a, l, i), s)=self._get_data(name,arch)
							self.add((name,e,v,r,arch,l,i),'ud')          
						else:
							unresolvable = 1
							errors.append("package %s needs %s (not provided)" % (name, clientStuff.formatRequire(reqname, reqversion, flags)))
				elif sense == rpm.RPMDEP_SENSE_CONFLICTS:
					print reqname
					print reqversion
					conflicts = 1
					errors.append("conflict between %s and %s" % (name, reqname))
			del ts
			del db
			if len(errors) > 0:
				return(1, errors)
			

   
