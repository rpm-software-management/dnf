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
		#print "%s %s %s %s" % (name, arch, i, l)
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
				
	def resolvedeps(self,rpmDBInfo):
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
		while CheckDeps==1 or (conflicts != 1 and unresolvable != 1 ):
			errors=[]
			db = clientStuff.openrpmdb(0)
			ts = rpm.TransactionSet('/',db)
			for (name, arch) in self.NAkeys(): 
				if self.state(name, arch) in ('u','ud','iu'):
					log(4,'Updating: %s, %s' % (name, arch))
					rpmloc = self.rpmlocation(name, arch)
					pkghdr = self.getHeader(name, arch)
					if name == 'kernel' or name == 'kernel-bigmem' or name == 'kernel-enterprise' or name == 'kernel-smp' or name == 'kernel-debug':
						kernarchlist = archwork.availablearchs(self,name)
						bestarch = archwork.bestarch(kernarchlist)
						if arch == bestarch:
							log(3, "Found best kernel arch: %s" %(arch))
							ts.add(pkghdr,(pkghdr,rpmloc),'i')
							((e, v, r, a, l, i), s)=self._get_data(name,arch)
							self.add((name,e,v,r,arch,l,i),'i')
						else:
							log(3, "Removing dumb kernel with silly arch %s" %(arch))
							ts.add(pkghdr,(pkghdr,rpmloc),'a')
							((e,v,r,a,l,i),s)=self._get_data(name,arch)
							self.add((name,e,v,r,arch,l,i),'a')
					else:
						ts.add(pkghdr,(pkghdr,rpmloc),'u')
					
				elif self.state(name,arch) == 'i':
					log(4,'Installing: %s, %s' % (name, arch))
					rpmloc = self.rpmlocation(name, arch)
					pkghdr = self.getHeader(name, arch)
					ts.add(pkghdr,(pkghdr,rpmloc),'i')
				elif self.state(name,arch) == 'a':
					rpmloc = self.rpmlocation(name, arch)
					pkghdr = self.getHeader(name, arch)
					ts.add(pkghdr,(pkghdr,rpmloc),'a')
				elif self.state(name,arch) == 'e' or self.state(name,arch) == 'ed':
					log(4,'Erasing: %s-%s' % (name,arch))
					ts.remove(name)
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
						log(4,"Got dep: %s, %s" % (name,arch))
						CheckDeps = 1
					else:
						if self.exists(reqname):
							if self.state(reqname) in ('e', 'ed'):
								#this is probably an erase depedency
								archlist = archwork.availablearchs(rpmDBInfo,name)
								arch = archwork.bestarch(archlist)
								((e, v, r, a, l, i), s)=rpmDBInfo._get_data(name,arch)
								self.add((name,e,v,r,arch,l,i),'ed')
								log(4,"Got Erase Dep: %s, %s" %(name,arch))
							else:
								archlist = archwork.availablearchs(self,name)
								arch = archwork.bestarch(archlist)
								((e, v, r, a, l, i), s)=self._get_data(name,arch)
								self.add((name,e,v,r,arch,l,i),'ud')								
								log(4,"Got Extra Dep: %s, %s" %(name,arch))
							CheckDeps=1
						else:
							#this is horribly ugly but I have to find some way to see if what it needed is provided
							#by what we are removing - if it is thien remove it -otherwise its a real dep problem - move along
							whatprovides = db.findbyprovides(reqname)
							if len(whatprovides)>0:
								for provide in whatprovides:
									provhdr=db[provide]
									if self.state(provhdr[rpm.RPMTAG_NAME],provhdr[rpm.RPMTAG_ARCH]) in ('e','ed'):
										((e,v,r,a,l,i),s)=rpmDBInfo._get_data(name)
										self.add((name,e,v,r,a,l,i),'ed')
										log(4,"Got Erase Dep: %s, %s" %(name,arch))
										CheckDeps=1
									else:
										unresolvable = 1
										if reqname in conf.excludes:
											errors.append("package %s needs %s that has been excluded" % (name, reqname))
										else:
											errors.append("package %s needs %s (not provided)" % (name, clientStuff.formatRequire(reqname, reqversion, flags)))
							else:
								unresolvable = 1
								if reqname in conf.excludes:
									errors.append("package %s needs %s that has been excluded" % (name, reqname))
								else:
									errors.append("package %s needs %s (not provided)" % (name, clientStuff.formatRequire(reqname, reqversion, flags)))
				elif sense == rpm.RPMDEP_SENSE_CONFLICTS:
					#much more shit should happen here. specifically:
					#if you have a conflict b/t two pkgs, try to upgrade the reqname pkg. - see if that solves the problem
					#also something like a "this isn't our fault and we can't help it, continue on" should happen.like in anaconda
					#more even than the below should happen here - but its getting closer - I need to flesh out all the horrible
					#states it could be in.
					log(4,"conflict: %s %s %s" % (name, reqname, reqversion))
					if rpmDBInfo.exists(reqname) and self.exists(reqname) and self.state(reqname) not in ('i','iu','u','ud'):
						archlist = archwork.availablearchs(rpmDBInfo,reqname)
						arch = archwork.bestarch(archlist)
						(e1, v1, r1) = rpmDBInfo.evr(reqname,arch)
						(e2, v2, r2) = self.evr(reqname,arch)
						rc = clientStuff.compareEVR((e1,v1,r1), (e2,v2,r2))
						if rc<0:
							log(4, "conflict: setting %s to upgrade" % (reqname))
							((e,v,r,a,l,i),s)=tsInfo._get_data(reqname,arch)
							self.add((name,e,v,r,a,l,i),'ud')
							CheckDeps=1
						else:
							errors.append("conflict between %s and %s" % (name, reqname))
							conflicts=1
					else:
						errors.append("conflict between %s and %s" % (name, reqname))
						conflicts=1
			log(4,"whee dep loop")
			del ts
			del db
			if len(errors) > 0:
				return(1, errors)
			

   
