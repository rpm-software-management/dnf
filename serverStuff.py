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

import os, sys, rpm


def cleanHeader(header):
  # remove the below tags from all headers
  # dup stdout and stderr b/c the header rewriting spews a lot of crap
  # return the shortened header
	import os,rpm
	badtags = [rpm.RPMTAG_POSTIN, rpm.RPMTAG_POSTUN, rpm.RPMTAG_PREIN, rpm.RPMTAG_PREUN, rpm.RPMTAG_FILEUSERNAME, \
			rpm.RPMTAG_FILEGROUPNAME, rpm.RPMTAG_FILEVERIFYFLAGS, rpm.RPMTAG_FILERDEVS, rpm.RPMTAG_FILEMTIMES, \
			rpm.RPMTAG_FILEDEVICES, rpm.RPMTAG_FILEINODES, rpm.RPMTAG_TRIGGERSCRIPTS, rpm.RPMTAG_TRIGGERVERSION, rpm.RPMTAG_TRIGGERFLAGS, \
			rpm.RPMTAG_TRIGGERNAME, rpm.RPMTAG_CHANGELOGTIME, rpm.RPMTAG_CHANGELOGNAME, rpm.RPMTAG_CHANGELOGTEXT, rpm.RPMTAG_ICON, \
			rpm.RPMTAG_GIF, rpm.RPMTAG_VENDOR, rpm.RPMTAG_DISTRIBUTION, rpm.RPMTAG_VERIFYSCRIPT, \
			rpm.RPMTAG_SIGSIZE, rpm.RPMTAG_SIGGPG, rpm.RPMTAG_SIGPGP, rpm.RPMTAG_PACKAGER, rpm.RPMTAG_LICENSE, rpm.RPMTAG_BUILDTIME, \
			rpm.RPMTAG_BUILDHOST, rpm.RPMTAG_RPMVERSION, rpm.RPMTAG_POSTINPROG, rpm.RPMTAG_POSTUNPROG, rpm.RPMTAG_PREINPROG, \
			rpm.RPMTAG_PREUNPROG, rpm.RPMTAG_COOKIE, rpm.RPMTAG_OPTFLAGS, rpm.RPMTAG_PAYLOADFORMAT ]

	saveStdout = os.dup(1)
	saveStderr = os.dup(2)
	redirStdout = os.open("/dev/null", os.O_WRONLY | os.O_APPEND)
	redirStderr = os.open("/dev/null", os.O_WRONLY | os.O_APPEND)
	os.dup2(redirStdout, 1)
	os.dup2(redirStderr, 2)
	for tag in badtags:
		del header[tag]
		header[tag] = ''
	os.dup2(saveStdout, 1)
	os.dup2(saveStderr, 2)
	# close the redirect files.
	os.close(redirStdout)
	os.close(redirStderr)
	os.close(saveStdout)
	os.close(saveStderr)
	return header


def writeHeader(headerdir,header):
	# write the header out to a file with the format: name-epoch-ver-rel.arch.hdr
	# return the name of the file it just made - no real reason :)
	import os,rpm,sys
	name = header[rpm.RPMTAG_NAME]
	ver = header[rpm.RPMTAG_VERSION]
	rel = header[rpm.RPMTAG_RELEASE]
	arch = header[rpm.RPMTAG_ARCH]
	if header[rpm.RPMTAG_EPOCH] == None:
		epoch = '0'
	else:
		epoch = '%s' % header[rpm.RPMTAG_EPOCH]

	headerfn = "%s/%s-%s-%s-%s.%s.hdr" % (headerdir, name, epoch,ver, rel, arch)
	headerout = open(headerfn, "w")
	headerout.write(header.unload(1))
	headerout.close()
	return(headerfn)


def getfilelist(path, ext, list):
	# get all the files matching the 3 letter extension that is ext in path, recursively
	# store them in append them to list
	# return list
	# ignore symlinks
	import os
	import string

	dir_list = os.listdir(path)

	for d in dir_list:
		if os.path.isdir(path + '/' + d):
			list = getfilelist(path + '/' + d, ext, list)
		else:
			if string.lower(d[-4:]) == '%s' % (ext):
				if not os.path.islink( path + '/' + d): 
					newpath = os.path.normpath(path + '/' + d)
					list.append(newpath)
	return(list)


def readHeader(rpmfn):
	# read the header from the rpm if its an rpm, from a file its a file
	# return 'source' if its a src.rpm - something useful here would be good probably.
	import os,string, rpm
	if string.lower(rpmfn[-4:]) == '.rpm':
		fd = os.open(rpmfn, os.O_RDONLY)
		(h,src) = rpm.headerFromPackage(fd)
		os.close(fd)
		if src:
			return 'source'
		else:
			return h
	else:
		fd = open(rpmfn, "r")
		h = rpm.headerLoad(fd.read())
		fd.close()
		return h

def Usage():
	import sys
	print "Usage:"
	print "yum-arch [-v] [-c] [-n] [-d] (path of dir where headers/ should/does live)"
	print "\t-d = check dependencies and conflicts in tree"
	print "\t-v = print debugging information"
	print "\t-n = don't generate headers"
	print "\t-c = check pkgs with gpg and md5 checksums - cannot be used with -n"
	sys.exit(1)


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

def depchecktree(rpmlist):
	ts = rpm.TransactionSet('/')
	error=0
	msgs=[]
	currpm=0
	numrpms=len(rpmlist)
	for rpmfn in rpmlist:
		currpm=currpm + 1
		percent = (currpm*100)/numrpms
		sys.stdout.write('\r' + ' ' * 80)
		sys.stdout.write("\rChecking deps %d %% complete" %(percent))
		sys.stdout.flush()
		h = readHeader(rpmfn)
		
		if h != 'source':
			ts.add(h, h[rpm.RPMTAG_NAME], 'i')
			log("adding %s" % h[rpm.RPMTAG_NAME])       
	errors = ts.depcheck()
	if errors:
		for ((name, version, release), (reqname, reqversion), \
			flags, suggest, sense) in errors:
			if sense==rpm.RPMDEP_SENSE_REQUIRES:
				error=1
				msgs.append("depcheck: package %s needs %s" % ( name, formatRequire(reqname, reqversion, flags)))
			elif sense==rpm.RPMDEP_SENSE_CONFLICTS:
				error=1
				msgs.append("depcheck: package %s conflicts with %s" % (name, reqname))
	print ""	
	return (error,msgs)

def checkSig(package):
	check = rpm.CHECKSIG_GPG | rpm.CHECKSIG_MD5
	# RPM spews to stdout/stderr.  Redirect.
	# code for this from up2date.py
	saveStdout = os.dup(1)
	saveStderr = os.dup(2)
	redirStdout = os.open("/dev/null", os.O_WRONLY | os.O_APPEND)
	redirStderr = os.open("/dev/null", os.O_WRONLY | os.O_APPEND)
	os.dup2(redirStdout, 1)
	os.dup2(redirStderr, 2)
	# now do the rpm thing
	sigcheck = rpm.checksig(package, check)
	# restore normal stdout and stderr
	os.dup2(saveStdout, 1)
	os.dup2(saveStderr, 2)
	# close the redirect files.
	os.close(redirStdout)
	os.close(redirStderr)
	os.close(saveStdout)
	os.close(saveStderr)
	if sigcheck:
		sys.stderr.write('Error:  Signature check failed for %s\n' %(package))
		sys.stderr.write('Doing nothing.\n')
		sys.exit(1)
	return


