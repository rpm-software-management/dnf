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


import os, sys, rpm, string,getopt
import clientStuff
import callback
import nevral
import pkgaction
from config import conf
from logger import logger

##############################################################

#setup log class
logfile = open(conf.logfile,'w')
loglevel = conf.debuglevel
log=logger(verbosity=loglevel,default=2,prefix='',preprefix='')

#push the logs into the other namespaces
pkgaction.log=log
clientStuff.log=log


def main():
	"""This does all the real work"""
	#make remote nevral class
	HeaderInfo = nevral.nevral()
	#who are we:
	uid=os.geteuid()

	#parse commandline options here - leave the user instructions (cmds) until after the startup stuff is done
	args = sys.argv[1:]
	userask=1
	try:
		gopts,cmds = getopt.getopt(args, 'd:y')
	except getopt.error, e:
		print "Options Error: %s" % e
		sys.exit(1)
			
	for o,a in gopts:
		if o =='-d':
			log.verbosity=int(a)
		if o =='-y':
			userask=0
	if cmds[0] not in ('update','install','list','erase','grouplist','groupupdate','groupinstall','clean','remove'):
		usage()

	log("Gathering package information from servers")
	for serverid in conf.servers:
		baseurl = conf.serverurl[serverid]
		servername = conf.servername[serverid]
		serverheader = os.path.join(baseurl,'headers/header.info')
		servercache = conf.servercache[serverid]
		log(4,'server name/cachedir:' + servername + '-' + servercache)
		localpkgs = conf.serverpkgdir[serverid]
		localhdrs = conf.serverhdrdir[serverid]
		localheaderinfo = os.path.join(servercache,'header.info')
		if not os.path.exists(servercache):
			os.mkdir(servercache)
		if not os.path.exists(localpkgs):
			os.mkdir(localpkgs)
		if not os.path.exists(localhdrs):
			os.mkdir(localhdrs)
		headerinfofn = clientStuff.urlgrab(serverheader, localheaderinfo)
		log(4,'headerinfofn: ' + headerinfofn)
		clientStuff.HeaderInfoNevralLoad(headerinfofn,HeaderInfo,serverid)

	#make local nevral class
	rpmDBInfo = nevral.nevral()
	clientStuff.rpmdbNevralLoad(rpmDBInfo)

	#create transaction set nevral class
	tsInfo = nevral.nevral()

	#download all the headers we don't have or the server has newer of
	#don't do anything fancy here - just download the headers not in our db
	(uplist,newlist) = clientStuff.getupdatedhdrlist(HeaderInfo,rpmDBInfo)
	nulist = uplist + newlist
	log("Downloading needed headers")
	for (name,arch) in nulist:
		#this should do something real, like, oh I dunno, check the header - but I'll be damned if I know how
		if os.path.exists(HeaderInfo.localHdrPath(name, arch)):
			log(4,"cached %s" % (HeaderInfo.hdrfn(name,arch)))
			pass
		else:
			log(2,"getting %s" % (HeaderInfo.hdrfn(name,arch)))
			clientStuff.urlgrab(HeaderInfo.remoteHdrUrl(name,arch), HeaderInfo.localHdrPath(name,arch))
	log("Finding updated and obsoleted packages")
	obslist=clientStuff.returnObsoletes(HeaderInfo,rpmDBInfo,nulist)

	
	log(4,"nulist = %s" % len(nulist))
	log(4,"uplist = %s" % len(uplist))
	log(4,"newlist = %s" % len(newlist))
	log(4,"obslist = %s" % len(obslist))
	

##################################################################
#at this point we have all the prereq info we could ask for. we know whats in the rpmdb
#whats available, whats updated and what obsoletes. We should be able to do everything we 
#want from here w/o getting anymore header info
##################################################################

	
	if cmds[0] == "install":
		cmds.remove(cmds[0])
		if len(cmds)==0:
			print"\nNeed to pass a list of pkgs to install\n"
			usage()
		else:
			pkgaction.installpkgs(tsInfo,nulist,cmds,HeaderInfo,rpmDBInfo)
	elif cmds[0] == "update":
		cmds.remove(cmds[0])
		if len(cmds)==0:
			pkgaction.updatepkgs(tsInfo,HeaderInfo,nulist,uplist,obslist,'all')
		else:
			pkgaction.updatepkgs(tsInfo,HeaderInfo,nulist,uplist,obslist,cmds)
			
	elif cmds[0] == "erase" or cmds[0] == "remove":
		cmds.remove(cmds[0])
		if len(cmds)==0:
			print"\nNeed to pass a list of pkgs to erase\n"
			usage()
		else:
			pkgaction.erasepkgs(tsInfo,rpmDBInfo,cmds)
	elif cmds[0] == "list":
		cmds.remove(cmds[0])
		if len(cmds)==0:
			pkgaction.listpkgs(nulist,'all',HeaderInfo)
			sys.exit(0)
		else:
			pkgaction.listpkgs(nulist,cmds,HeaderInfo)
			sys.exit(0)
	else:
		usage()
	

	#at this point we should have a tsInfo nevral with all we need to complete our task.
	#if for some reason we've gotten all the way through this step with an empty tsInfo then exit and be confused :)
	if len(tsInfo.NAkeys()) < 1:
		print "No actions to take"
		sys.exit(0)
		
	#put available pkgs in tsInfonevral in state 'a'
	for (name,arch) in nulist:
		if not tsInfo.exists(name, arch):
			((e, v, r, a, l, i), s)=HeaderInfo._get_data(name,arch)
			log(6,"making available: %s" % name)
			tsInfo.add((name,e,v,r,arch,l,i),'a')   

	##need to change kernels into 'i' if they are in state 'u'
	log("Resolving dependencies")
	(code, msgs) = tsInfo.resolvedeps()
	if code == 1:
		for msg in msgs:
			print msg
		sys.exit(1)
	log("Dependencies resolved")
	
	#prompt for use permission to do stuff in tsInfo - list all the actions (i, u, e)
	#confirm w/the user
	clientStuff.printactions(tsInfo)
	if userask==1:
		if clientStuff.userconfirm():
			print "Exiting on user command."
			sys.exit(1)
	

	#download the pkgs to the local paths and add them to final transaction set
	if uid==0:
		dbfin = clientStuff.openrpmdb(1,'/')
	else:
		dbfin = clientStuff.openrpmdb(0,'/')

	tsfin=rpm.TransactionSet('/', dbfin)
	for (name, arch) in tsInfo.NAkeys():
		pkghdr=tsInfo.getHeader(name,arch)
		rpmloc=tsInfo.localRpmPath(name,arch)
		if tsInfo.state(name, arch) == 'u' or tsInfo.state(name,arch) == 'ud':
			if os.path.exists(tsInfo.localRpmPath(name, arch)):
				print "Using cached %s" % (os.path.basename(tsInfo.localRpmPath(name,arch)))
			else:
				print "getting %s" % (os.path.basename(tsInfo.localRpmPath(name,arch)))
				clientStuff.urlgrab(tsInfo.remoteRpmUrl(name,arch), tsInfo.localRpmPath(name,arch))
			tsfin.add(pkghdr,(pkghdr,rpmloc),'u')
		elif tsInfo.state(name,arch) == 'i':
			if os.path.exists(tsInfo.localRpmPath(name, arch)):
				print "Using cached %s" % (os.path.basename(tsInfo.localRpmPath(name,arch)))
			else:
				print "getting %s" % (os.path.basename(tsInfo.localRpmPath(name,arch)))
				clientStuff.urlgrab(tsInfo.remoteRpmUrl(name,arch), tsInfo.localRpmPath(name,arch))
			#print 'installing %s, %s' % (name, arch)
			tsfin.add(pkghdr,(pkghdr,rpmloc),'i')
			#theoretically, at this point, we shouldn't need to make pkgs available
		elif tsInfo.state(name,arch) == 'a':
			pass
		elif tsInfo.state(name,arch) == 'e':
			tsfin.remove(name)

	#one last test run for diskspace
	errors = tsfin.run(rpm.RPMTRANS_FLAG_TEST, ~rpm.RPMPROB_FILTER_DISKSPACE, callback.install_callback, 'test')
	if errors:
		print "You appear to have insufficient disk space to handle these packages"
		sys.exit(1)
	if uid == 0:
		errors == tsfin.run(0, 0, callback.install_callback, '')
		if errors:
			print "Errors installing:"
			for error in errors:
				print error
		
		del dbfin
		del tsfin
		#Check to see if we've got a new kernel and put it in the right place in grub/lilo
		pkgaction.kernelupdate(tsInfo)
		
	else:
		print "You're not root, we can't install things"
		sys.exit(0)
		
	print "Transaction(s) Complete"
	sys.exit(0)




def usage():
	print """
	Usage:  yum [options] <update | install | erase | groupinstall
	| groupupdate | list | grouplist | clean>
	Options:
	-d [debug level] - set the debugging verbosity level
	-y answer yes to all questions
	"""
	sys.exit(1)
	
if __name__ == "__main__":
    main()

