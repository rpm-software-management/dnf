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

import os, sys, rpm, clientStuff

def installpkgs(tsnevral,nulist,userlist,hinevral,rpmnevral):
	#get the list of pkgs you want to install from userlist
	#check to see if they are already installed - if they are try to upgrade them
	#if they are the latest version then error and exit
	#if they are not, check to see if there is more than one arch, if so pass it to bestarch then use the bestone for this platform
	#add that one as 'i' to the tsinfo
	#if they are not a pkg and you can't find it at all error and exit
	import fnmatch, archwork
	if len(nulist) > 0:
		for n in userlist:
			foundit=0
			for (name,arch) in nulist:
				if n == name or fnmatch.fnmatch(name, n):
					#found it
					foundit=1
					archlist = archwork.availablearchs(hinevral,name)
					bestarch = archwork.bestarch(archlist)
					if rpmnevral.exists(name,bestarch):
						(e1,v1,r1)=rpmnevral.evr(name,bestarch)
						(e2,v2,r2)=hinevral.evr(name,bestarch)
						rc = clientStuff.compareEVR((e1,v1,r1),(e2,v2,r2))
						if rc < 0:
							#we should be upgrading this
							#print "Switching to upgrading %s" % (name)
							((e, v, r, a, l, i), s)=hinevral._get_data(name,bestarch)
							tsnevral.add((name,e,v,r,a,l,i),'u')            
						else:
							#this is the best there is :(
							print "%s is installed and is the latest version. Exiting" % (name)
							sys.exit(1)
					else:
						#we should install this
						((e, v, r, a, l, i), s)=hinevral._get_data(name,arch)
						tsnevral.add((name,e,v,r,a,l,i),'i')
			if foundit==0:
				if rpmnevral.exists(n):
					print "%s is installed and is the latest version. Exiting" % (n)
				else:
					print "Cannot find a package matching %s" % (n)
				sys.exit(1)
			
	else:
		print "No Packages Available for Update or Install"
		
	

def listpkgs(nulist, userlist, nevral):
	import types,fnmatch
	if len(nulist) > 0:
		nulist.sort(clientStuff.nasort)
		print "%-40s %-10s %s" %('Name','Arch','Version')
		print "-" * 80
		if type(userlist) is types.StringType and userlist=='all':
			for (name, arch) in nulist:
				(e,v,r)=nevral.evr(name,arch)
				print "%-40s %-10s %s-%s" %(name, arch,v, r)
		else:	
			for (name,arch) in nulist:
				for n in userlist:
					if n == name or fnmatch.fnmatch(name, n):
						(e,v,r)=nevral.evr(name,arch)
						print "%-40s %-10s %s-%s" %(name, arch,v, r)
	else:
		print "No Packages Available for Update or Install"
			
def updatepkgs(tsnevral,hinevral,nulist,uplist,obslist,userlist):
	#get the list of what people want upgraded, match like in install.
	#add as 'u' to the tsnevral if its already there, if its not then add as 'i' and warn
	#if its all then take obslist and uplist and iterate through the tsinfo'u'
	#
	import fnmatch, archwork, types
	if len(nulist) > 0 :
		if type(userlist) is types.StringType and userlist=='all':
			for (name,arch) in obslist:
				log(4,"Obsolete: %s" % name)
				((e, v, r, a, l, i), s)=hinevral._get_data(name,arch)
				tsnevral.add((name,e,v,r,a,l,i),'i')
			for (name,arch) in uplist:
				log(4,"Updating: %s" % name)
				((e, v, r, a, l, i), s)=hinevral._get_data(name,arch)
				tsnevral.add((name,e,v,r,a,l,i),'u')
		else:		
			for n in userlist:
				foundit=0
				for (name,arch) in nulist:
					if n == name or fnmatch.fnmatch(name, n):
						#found it
						foundit=1
						archlist = archwork.availablearchs(hinevral,name)
						bestarch = archwork.bestarch(archlist)
						for currarch in archlist:
							if uplist.count((name,currarch))>0:
								#its one of the archs we do and its in the uplist - update it
								log(4,"Updating %s" % (name))
								((e, v, r, a, l, i), s)=hinevral._get_data(name,currarch)
								tsnevral.add((name,e,v,r,a,l,i),'u')            
							elif uplist.count((name,currarch)) < 1 and nulist.count((name,currarch))>0:
								#its one of the archs we do and its not installed, install it but only the bestarch
								if currarch == bestarch:
									log(4,"Installing %s" % (name))
									((e, v, r, a, l, i), s)=hinevral._get_data(name,currarch)
									tsnevral.add((name,e,v,r,a,l,i),'i')
							elif uplist.count((name,currarch)) < 1 and nulist.count((name,currarch))<1:
								#its an arch we do, its not updated and its installed
								print "%s is the latest version" % (name)
								sys.exit(1)
				if foundit==0:
					print "Cannot find any package matching %s. Exiting" % (n)
					sys.exit(1)
	else:
		print "No Packages Available for Update or Install"
			

def erasepkgs(tsnevral,rpmnevral,userlist):
	#mark for erase iff the userlist item exists in the rpmnevral
	import fnmatch
	for n in userlist:
		foundit = 0
		for (name,arch) in rpmnevral.NAkeys():
			if n == name or fnmatch.fnmatch(name, n):
				foundit=1
				log(4,"Erasing %s" % (name))
				((e, v, r, a, l, i), s)=rpmnevral._get_data(name,arch)
				tsnevral.add((name,e,v,r,a,l,i),'e')				
		if foundit==0:
			print "Erase: No matches for %s" % n
			sys.exit(1)

def kernelupdate(tsnevral):
	#figure out if we have updated a kernel
	#do what up2date does to update lilo and/or grub
	kernel_list = []
    # reopen the database read/write
	for (name,arch) in tsnevral.NAkeys():
		s = tsnevral.state(name,arch)
		if s in ['i','u','ud']:
			if name in ['kernel','kernel-smp','kernel-enterprise','kernel-bigmem','kernel-BOOT']:
				hdr=tsnevral.getHeader(name,arch)
				if "kernel-smp" in hdr[rpm.RPMTAG_PROVIDES]:
					extraInfo = "kernel-smp"
				elif "kernel-enterprise" in hdr[rpm.RPMTAG_PROVIDES]:
					extraInfo = "kernel-enterprise"
				elif "kernel-bigmem" in hdr[rpm.RPMTAG_PROVIDES]:
					extraInfo = "kernel-bigmem"
				elif "kernel-BOOT" in hdr[rpm.RPMTAG_PROVIDES]:
					extraInfo = "kernel-BOOT"	
				else:
					extraInfo = "kernel"

				# this logics a bit weird
				if extraInfo == None:
					infoString = ""
				elif extraInfo == "kernel":
					infoString = ""
				elif extraInfo == "kernel-BOOT":
					infoString = "BOOT"
				elif extraInfo == "kernel-enterprise":
					infoString = "enterprise"  
				elif extraInfo == "kernel-bigmem":
					infoString = "bigmem"  
				elif extraInfo == "kernel-smp":
					infoString = "smp"
				else:
					infoString = ""
				verRel = "%s-%s%s" % (hdr[rpm.RPMTAG_VERSION], hdr[rpm.RPMTAG_RELEASE],infoString)
				kernel_list.append((verRel, extraInfo))
		
	if len(kernel_list) > 0:
		# code from up2date/up2date.py
		#figure out which bootloader, run the script for that bootloader
		import checkbootloader
		bootloader = checkbootloader.whichBootLoader()
		import up2datetheft
		if bootloader == "LILO":
			up2datetheft.install_lilo(kernel_list)
		elif bootloader == "GRUB":
			# at the moment, kernel rpms are supposed to grok grub
			# and do the Right Thing. Just a placeholder for doc purposes and
			#to put the kernels in the right order
			up2datetheft.install_grub(kernel_list)

