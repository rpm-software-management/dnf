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
from logger import Logger
##############################################################

#setup log classes
#used for the syslog-style log
def printtime():
	return time.strftime('%m/%d/%y %H:%M:%S ',time.localtime(time.time()))
#syslog-style log
logfile=open(conf.logfile,"w")
filelog=Logger(threshold=10, file_object=logfile,preprefix=printtime())
#errorlog - sys.stderr - always
errorlog=Logger(threshold=10, file_object=sys.stderr)
#normal printing/debug log - this is what -d # affects
log=Logger(threshold=conf.debuglevel, file_object=sys.stdout)

#push the logs into the other namespaces
pkgaction.log=log
clientStuff.log=log
nevral.log=log

pkgaction.errorlog=errorlog
clientStuff.errorlog=errorlog
nevral.errorlog=errorlog

pkgaction.filelog=filelog
clientStuff.filelog=filelog
nevral.filelog=filelog

#push the conf file into the other namespaces
nevral.conf=conf
clientStuff.conf=conf
pkgaction.conf=conf
callback.conf=conf

def get_package_info_from_servers(conf,HeaderInfo):
	#this function should be split into - server paths etc and getting the header info/populating the 
	#the HeaderInfo nevral class so we can do non-root runs of yum
	log(2,"Gathering package information from servers")
	#sorting the servers so that sort() will order them consistently
	serverlist=conf.servers
	serverlist.sort()
	for serverid in serverlist:
		baseurl = conf.serverurl[serverid]
		servername = conf.servername[serverid]
		serverheader = os.path.join(baseurl,'headers/header.info')
		servercache = conf.servercache[serverid]
		log(4,'server name/cachedir:' + servername + '-' + servercache)
		log(2,'Getting headers from: %s' % (servername))
		localpkgs = conf.serverpkgdir[serverid]
		localhdrs = conf.serverhdrdir[serverid]
		localheaderinfo = os.path.join(servercache,'header.info')
		if not os.path.exists(servercache):
			os.mkdir(servercache)
		if not os.path.exists(localpkgs):
			os.mkdir(localpkgs)
		if not os.path.exists(localhdrs):
			os.mkdir(localhdrs)
		headerinfofn = clientStuff.urlgrab(serverheader, localheaderinfo,'nohook')
		log(4,'headerinfofn: ' + headerinfofn)
		clientStuff.HeaderInfoNevralLoad(headerinfofn,HeaderInfo,serverid)


def download_headers(HeaderInfo,nulist):
	for (name,arch) in nulist:
		#this should do something real, like, oh I dunno, check the header - but I'll be damned if I know how
		if os.path.exists(HeaderInfo.localHdrPath(name, arch)):
			log(4,"cached %s" % (HeaderInfo.hdrfn(name,arch)))
			pass
		else:
			log(2,"getting %s" % (HeaderInfo.hdrfn(name,arch)))
			clientStuff.urlgrab(HeaderInfo.remoteHdrUrl(name,arch), HeaderInfo.localHdrPath(name,arch),'nohook')

def take_action(cmds,nulist,uplist,newlist,obslist,tsInfo,HeaderInfo,rpmDBInfo):
	if cmds[0] == "install":
		cmds.remove(cmds[0])
		if len(cmds)==0:
			errorlog(1,"Need to pass a list of pkgs to install")
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
			errorlog (1,"Need to pass a list of pkgs to erase")
			usage()
		else:
			pkgaction.erasepkgs(tsInfo,rpmDBInfo,cmds)
	elif cmds[0] == "list":
		cmds.remove(cmds[0])
		if len(cmds)==0:
			pkgaction.listpkgs(nulist,'all',HeaderInfo)
			sys.exit(0)
		else:
			if cmds[0] == 'updates':
				pkgaction.listpkgs(uplist+obslist,'updates',HeaderInfo)
			else:	
				pkgaction.listpkgs(nulist,cmds,HeaderInfo)
		sys.exit(0)
	elif cmds[0] == "clean":
		cmds.remove(cmds[0])
		if len(cmds)==0 or cmds[0]=='all':
			log(2,"Cleaning packages and old headers")
			clientStuff.clean_up_packages()
			clientStuff.clean_up_old_headers(rpmDBInfo,HeaderInfo)
		elif cmds[0]=='packages':
			log(2,"Cleaning packages")
			clientStuff.clean_up_packages()
		elif cmds[0]=='headers':
			log(2,"Cleaning all headers")
			clientStuff.clean_up_headers()
		elif cmds[0]=='oldheaders':
			log(2,"Cleaning old headers")
			clientStuff.clean_up_old_headers(rpmDBInfo,HeaderInfo)
		else:
			errorlog(1,"Invalid clean option %s" % cmds[0])
			sys.exit(1)
		sys.exit(0)	
	else:
		usage()

def create_final_ts(tsInfo, rpmdb):
	#download the pkgs to the local paths and add them to final transaction set
	#might be worth adding the sigchecking in here
	tsfin=rpm.TransactionSet('/', rpmdb)
	for (name, arch) in tsInfo.NAkeys():
		pkghdr=tsInfo.getHeader(name,arch)
		rpmloc=tsInfo.localRpmPath(name,arch)
		serverid=tsInfo.serverid(name,arch)
		if tsInfo.state(name, arch) in ('u','ud','iu'):
			if os.path.exists(tsInfo.localRpmPath(name, arch)):
				log(4,"Using cached %s" % (os.path.basename(tsInfo.localRpmPath(name,arch))))
			else:
				log(2,"Getting %s" % (os.path.basename(tsInfo.localRpmPath(name,arch))))
				clientStuff.urlgrab(tsInfo.remoteRpmUrl(name,arch), tsInfo.localRpmPath(name,arch))
			#sigcheck here :)
			if conf.servergpgcheck[serverid]:
				pkgaction.checkSig(rpmloc,'gpg')
			else:
				pkgaction.checkSig(rpmloc)
			tsfin.add(pkghdr,(pkghdr,rpmloc),'u')
		elif tsInfo.state(name,arch) == 'i':
			if os.path.exists(tsInfo.localRpmPath(name, arch)):
				log(4,"Using cached %s" % (os.path.basename(tsInfo.localRpmPath(name,arch))))
			else:
				log(2,"Getting %s" % (os.path.basename(tsInfo.localRpmPath(name,arch))))
				clientStuff.urlgrab(tsInfo.remoteRpmUrl(name,arch), tsInfo.localRpmPath(name,arch))
			#sigchecking we will go
			if conf.servergpgcheck[serverid]:
				pkgaction.checkSig(rpmloc,'gpg')
			else:
				pkgaction.checkSig(rpmloc)
			tsfin.add(pkghdr,(pkghdr,rpmloc),'i')
			#theoretically, at this point, we shouldn't need to make pkgs available
		elif tsInfo.state(name,arch) == 'a':
			pass
		elif tsInfo.state(name,arch) == 'e' or tsInfo.state(name,arch) == 'ed':
			tsfin.remove(name)

	#one last test run for diskspace
	log(2,"Calculating available disk space - this could take a bit")
	errors = tsfin.run(rpm.RPMTRANS_FLAG_TEST, ~rpm.RPMPROB_FILTER_DISKSPACE, callback.install_callback, '')
	
	if errors:
		errorlog(1,"You appear to have insufficient disk space to handle these packages")
		sys.exit(1)
	return tsfin
	

def main():
	"""This does all the real work"""
	#who are we:
	uid=os.geteuid()

	#parse commandline options here - leave the user instructions (cmds) 
	#until after the startup stuff is done
	#something else needs to happen here - I need the commandline options to
	#be available from the conf class ideally.
	
	args = sys.argv[1:]
	if len(args) < 1:
		usage()
	userask=1
	try:
		gopts,cmds = getopt.getopt(args, 'hd:y',['help'])
	except getopt.error, e:
		print "Options Error: %s" % e
		sys.exit(1)
			
	for o,a in gopts:
		if o =='-d':
			log.verbosity=int(a)
		if o =='-y':
			userask=0
		if o in ('-h', '--help'):
			usage()
	if cmds[0] not in ('update','install','list','erase','grouplist','groupupdate','groupinstall','clean','remove'):
		usage()
	process=cmds[0]

	#make remote nevral class
	HeaderInfo = nevral.nevral()
	
	#get the package info file
	get_package_info_from_servers(conf, HeaderInfo)
	
	#make local nevral class
	rpmDBInfo = nevral.nevral()
	clientStuff.rpmdbNevralLoad(rpmDBInfo)

	#create transaction set nevral class
	tsInfo = nevral.nevral()
	#################################################################################
	#generate all the lists we'll need to quickly iterate through the lists.
	#uplist == list of updated packages
	#newlist == list of uninstall/available NEW packages (ones we don't any copy of)
	#nulist == combination of the two
	#obslist == packages obsoleting a package we have installed
	################################################################################
	log(2,"Finding updated packages")
	(uplist,newlist,nulist) = clientStuff.getupdatedhdrlist(HeaderInfo,rpmDBInfo)
	log(2,"Downloading needed headers")
	download_headers(HeaderInfo, nulist)
	log(2,"Finding obsoleted packages")
	obslist=clientStuff.returnObsoletes(HeaderInfo,rpmDBInfo,nulist)

	log(4,"nulist = %s" % len(nulist))
	log(4,"uplist = %s" % len(uplist))
	log(4,"newlist = %s" % len(newlist))
	log(4,"obslist = %s" % len(obslist))
	
	##################################################################
	#at this point we have all the prereq info we could ask for. we 
	#know whats in the rpmdb whats available, whats updated and what 
	#obsoletes. We should be able to do everything we want from here 
	#w/o getting anymore header info
	##################################################################

	take_action(cmds,nulist,uplist,newlist,obslist,tsInfo,HeaderInfo,rpmDBInfo)
	
	#at this point we should have a tsInfo nevral with all we need to complete our task.
	#if for some reason we've gotten all the way through this step with an empty tsInfo then exit and be confused :)
	if len(tsInfo.NAkeys()) < 1:
		log(2,"No actions to take")
		sys.exit(0)
		
	if process not in ('erase','remove'):
		#put available pkgs in tsInfonevral in state 'a'
		for (name,arch) in nulist:
			if not tsInfo.exists(name, arch):
				((e, v, r, a, l, i), s)=HeaderInfo._get_data(name,arch)
				log(6,"making available: %s" % name)
				tsInfo.add((name,e,v,r,arch,l,i),'a')   

	log(2,"Resolving dependencies")
	(code, msgs) = tsInfo.resolvedeps(rpmDBInfo)
	if code == 1:
		for msg in msgs:
			print msg
		sys.exit(1)
	log(2,"Dependencies resolved")
	
	#prompt for use permission to do stuff in tsInfo - list all the actions 
	#(i, u, e, ud,iu(installing, but marking as 'u' in the actual ts, just in case) confirm w/the user
	clientStuff.printactions(tsInfo)
	if userask==1:
		if clientStuff.userconfirm():
			errorlog(1,"Exiting on user command.")
			sys.exit(1)
	
	if uid==0:
		dbfin = clientStuff.openrpmdb(1,'/')
	else:
		dbfin = clientStuff.openrpmdb(0,'/')
	
	tsfin = create_final_ts(tsInfo,dbfin)

	if uid == 0:
		#sigh - the magical "order" command - nice of this not to really be documented anywhere.
		tsfin.order()
		errors = tsfin.run(0, 0, callback.install_callback, '')
		if errors:
			errorlog(1,"Errors installing:")
			for error in errors:
				errorlog(1,error)
		
		del dbfin
		del tsfin
		
		#Check to see if we've got a new kernel and put it in the right place in grub/lilo
		pkgaction.kernelupdate(tsInfo)
		
	else:
		errorlog(1,"You're not root, we can't install things")
		sys.exit(0)
		
	log(2,"Transaction(s) Complete")
	sys.exit(0)




def usage():
	print """
    Usage:  yum [options] <update | install | erase | groupinstall
	            | groupupdate | list | grouplist | clean>
				
         Options:
          -d [debug level] - set the debugging verbosity level
          -y answer yes to all questions
          -h, --help this screen
	"""
	sys.exit(1)
	
if __name__ == "__main__":
    main()

