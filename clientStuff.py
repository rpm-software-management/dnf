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

import string
import rpm
import os
import sys
import config

def stripENVRA(foo):
  archIndex = string.rfind(foo, ".")
  arch = foo[archIndex+1:]
  relIndex = string.rfind(foo[:archIndex], "-")
  rel = foo[relIndex+1:archIndex]
  verIndex = string.rfind(foo[:relIndex], "-")
  ver = foo[verIndex+1:relIndex]
  epochIndex = string.find(foo, ":")
  epoch = foo[:epochIndex]
  name = foo[epochIndex + 1:verIndex]
  return (epoch, name, ver, rel, arch)

def stripEVR(str):
   epochIndex = string.find(str, ':')
   epoch = str[:epochIndex]
   relIndex = string.rfind(str, "-")
   rel = str[relIndex+1:]
   verIndex = string.rfind(str[:relIndex], "-")
   ver = str[epochIndex+1:relIndex]  
   return (epoch, ver, rel)

def stripNA(str):
    archIndex = string.rfind(str, ".")
    arch = str[archIndex+1:]
    name = str[:archIndex]
    return (name, arch)

def compareEVR((e1,v1,r1), (e2,v2,r2)):
   # return 1: a is newer than b 
   # 0: a and b are the same version 
   # -1: b is newer than a */
    rc = rpm.labelCompare((e1,v1,r1), (e2,v2,r2))
    return rc

def getENVRA(header):
	if header[rpm.RPMTAG_EPOCH] == None:
		epoch = '0'
	else:
		epoch = '%s' % header[rpm.RPMTAG_EPOCH]
	name = header[rpm.RPMTAG_NAME]
	ver = header[rpm.RPMTAG_VERSION]
	rel = header[rpm.RPMTAG_RELEASE]
	arch = header[rpm.RPMTAG_ARCH]
	return (epoch, name, ver, rel, arch)

def str_to_version(str):
	import string
	i = string.find(str, ':')
	if i != -1:
		epoch = string.atol(str[:i])
	else:
		epoch = '0'
	j = string.find(str, '-')
	if j != -1:
		if str[i + 1:j] == '':
			version = None
		else:
			version = str[i + 1:j]
		release = str[j + 1:]
	else:
		if str[i + 1:] == '':
			version = None
		else:
			version = str[i + 1:]
		release = None
	return (epoch, version, release)

def HeaderInfoNevralLoad(filename,nevralClass,serverid):
	info = []
	in_file = open(filename,"r")
	while 1:
		in_line = in_file.readline()
		if in_line == "":
			break
		info.append(in_line)
	in_file.close()

	for line in info:
		(envraStr, rpmpath) = string.split(line,'=')
		(epoch, name, ver, rel, arch) = stripENVRA(envraStr)
		rpmpath = string.replace(rpmpath, "\n","")
		nevralClass.add((name,epoch,ver,rel,arch,rpmpath,serverid),'a')


def openrpmdb(option=0, dbpath=None):
	dbpath = "/var/lib/rpm/"
	rpm.addMacro("_dbpath", dbpath)

	try:
		db = rpm.opendb(option)
	except rpm.error, e:
		raise RpmError(_("Could not open RPM database for reading. Perhaps it is already in use?"))
	
	return db


def rpmdbNevralLoad(nevralClass):
   rpmdbdict = {}
   db = openrpmdb()
   serverid = "db"
   rpmloc = "in_rpm_db"
   index = db.firstkey()
   while index:
     rpmdbh = db[index]
     (epoch, name, ver, rel, arch) = getENVRA(rpmdbh)
     #deal with multiple versioned dupes and dupe entries in localdb
     if not rpmdbdict.has_key((name, arch)):
       rpmdbdict[(name,arch)] = (epoch, ver, rel)
     else:
       (e1, v1, r1) = (rpmdbdict[(name, arch)])
       (e2, v2, r2) = (epoch, ver, rel)    
       rc = rpm.labelCompare((e1,v1,r1), (e2,v2,r2))
       if (rc == -1):
        rpmdbdict[(name,arch)] = (epoch, ver, rel)
       elif (rc == 0):
         print "dupe entry in rpmdb %s\n" % key
     index = db.nextkey(index)
   for value in rpmdbdict.keys():
     (name, arch) = value
     (epoch,ver, rel) = rpmdbdict[value]
     nevralClass.add((name,epoch,ver,rel,arch,rpmloc,serverid),'n')

def readHeader(rpmfn):
   if string.lower(rpmfn[-4:]) == '.rpm':
     fd = open(rpmfn, "r")
     h = rpm.headerFromPackage(fd)[0]
     fd.close()
     return h
   else:
     fd = open(rpmfn, "r")
     h = rpm.headerLoad(fd.read())
     fd.close()
     return h


def returnObsoletes(headerNevral,rpmNevral,uninstNAlist):
	packages = []
	for (name,arch) in uninstNAlist:
		#print '%s, %s' % (name, arch)
		header = headerNevral.getHeader(name, arch)
		if not header:
			print "die on %s, %s" %(name, arch)
		obs = header[rpm.RPMTAG_OBSOLETES]
		if obs:
		#print "%s, %s obs something" % (name, arch)
		# if there is one its a nonversioned obsolete
		# if there are 3 its a versioned obsolete
		# nonversioned are obvious - check the rpmdb if it exists
		# then the pkg obsoletes something in the rpmdb
		# versioned obsolete - obvalue[0] is the name of the pkg
		#                      obvalue[1] is >,>=,<,<=,=
		#                      obvalue[2] is an e:v-r string
		# get the two version strings - labelcompare them
		# get the return value - then run through
		# an if/elif statement regarding obvalue[1] and determine
		# if the pkg obsoletes something in the rpmdb
			for ob in obs:
				obvalue = string.split(ob)
				if rpmNevral.exists(obvalue[0]):
					if len(obvalue) == 1:
						packages.append((name, arch))
						print "%s obsoleting %s" % (name,ob)
					elif len(obvalue) == 3:
						(e1,v1,r1) = rpmNevral.evr(name, arch)
						(e2,v2,r2) = str_to_version(obvalue[3])
						rc = rpm.labelCompare((e1,v1,r1), (e2,v2,r2))
						if obvalue[2] == '>':
							if rc == 1:
								packages.append((name, arch))
							elif rc == 0:
								pass
							elif rc == -1:
								pass
						elif obvalue[2] == '>=':
							if rc == 1:
								packages.append((name, arch))
							elif rc == 0:
								packages.append((name, arch))
							elif rc == -1:
								pass
						elif obvalue[2] == '=':
							if rc == 1:
								pass
							elif rc == 0:
								packages.append((name, arch))
							elif rc == -1:
								pass
						elif obvalue[2] == '<=':
							if rc == 1:
								pass
							elif rc == 0:
								packages.append((name, arch))
							elif rc == -1:
								packages.append((name, arch))
						elif obvalue[2] == '<':
							if rc == 1:
								pass
							elif rc == 0:
								pass
							elif rc == -1:
								packages.append((name, arch))
	#for (name, arch) in packages:
		#print "Dump - %s, %s" %(name, arch)
		#sys.exit(1)
	return packages

def urlgrab(url, filename=None):
	#so this should really do something with the callbacks. Specifically it needs to print a silly little percentage done thing
	import urllib, rfc822
	if filename:
		(fh, hdr) = urllib.urlretrieve(url, filename)
	else:
		fnindex = string.rfind(url, "/")
		filename = url[fnindex+1:]
		(fh, hdr) = urllib.urlretrieve(url, filename)    
		#this is a cute little hack - if there isn't a "Content-Length" header then its either a 404 or a directory list
		#either way its not what we want so I put this check in here as a little bit of sanity checking
		if hdr != None:
			if not hdr.has_key('Content-Length'):
				print "ERROR: Url Returns no Content-Length  - something is wrong"
				sys.exit(1)
		
	return fh


def getupdatedhdrlist(headernevral, rpmnevral): 
	"returns (name,arch) tuples of updated and uninstalled pkgs"
	uplist = []
	unlist = []
	for key in headernevral.NAkeys():
		(name, arch) = key
		hdrfile = headernevral.hdrfn(name, arch)
		serverid = headernevral.serverid(name, arch)
		if rpmnevral.exists(name, arch):
			rc = compareEVR(headernevral.evr(name, arch), rpmnevral.evr(name, arch))
			if (rc > 0):
				uplist.append((name,arch))
		else:
			unlist.append((name,arch))
	return (uplist,unlist)

    
def formatRequire (name, version, flags):
	string = name
	    
	if flags:
		if flags & (rpm.RPMSENSE_LESS | rpm.RPMSENSE_GREATER | rpm.RPMSENSE_EQUAL):
			string = string + " "
		if flags & rpm.RPMSENSE_LESS:
			string = string + "<"
		if flags & rpm.RPMSENSE_GREATER:
			string = string + ">"
		if flags & rpm.RPMSENSE_EQUAL:
			string = string + "="
			string = string + " %s" % version
	return string

def printactions(nevral):
	install_list = []
	update_list = []
	erase_list = []
	deps_list = []
	for (name, arch) in nevral.NAkeys():
		if nevral.state(name,arch) == 'i':
			install_list.append((name,arch))
		if nevral.state(name,arch) == 'u':
			update_list.append((name,arch))
		if nevral.state(name,arch) == 'e':
			erase_list.append((name,arch))
		if nevral.state(name,arch) == 'ud':
			deps_list.append((name,arch))
	print "I will do the following:"
	for pkg in install_list:
		(name,arch) = pkg
		print "[install: %s.%s]" % (name,arch)
	for pkg in update_list:
		(name,arch) = pkg
		print "[update: %s.%s]" % (name,arch)
	for pkg in erase_list:
		(name,arch) = pkg
		print "[erase: %s.%s]" % (name,arch)
	if len(deps_list) > 0:
		print "I will install/upgrade these to satisfy the depedencies:"
		for pkg in deps_list:
			(name,arch) = pkg
			print "[deps: %s.%s]" %(name,arch)
			


def userconfirm():
	"""gets a yes or no from the user, defaults to No"""
	choice = raw_input('Is this ok [y/N]: ')
	if len(choice) == 0:
		return 1
	else:
		if choice[0] != 'y' and choice[0] != 'Y':
			return 1
		else:
			return 0
		


def nasort((n1,a1), (n2, a2)):
	if n1 > n2:
		return 1
	elif n1 == n2:
		return 0
	else:
		return -1
		
		
