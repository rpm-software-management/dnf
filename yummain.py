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
import sys
import rpm
import string
import getopt

def main():
    """This does all the real work"""
    #parse commandline options here - leave the user instructions (cmds) 
    #until after the startup stuff is done

    import clientStuff
    import nevral
    import pkgaction
    import callback
    from logger import Logger
    from config import yumconf

    ##############################################################
    #who are we:
    uid=os.geteuid()

    args = sys.argv[1:]
    if len(args) < 1:
        usage()
    try:
        gopts,cmds = getopt.getopt(args, 'c:he:d:y',['help'])
    except getopt.error, e:
        errorlog(0,"Options Error: %s" % e)
        sys.exit(1)
    # our default config file location
    yumconffile="/etc/yum.conf"
    for o,a in gopts:
        if o =='-d':
            log.threshold=int(a)
            conf.debuglevel=int(a)
        if o =='-e':
            errorlog.threshold=int(a)
            conf.errorlevel=int(a)
        if o =='-y':
            conf.assumeyes=1
        if o =='-c':
            yumconffile=a
        if o in ('-h', '--help'):
            usage()
    if cmds[0] not in ('update','upgrade','install','list','erase','grouplist','groupupdate','groupinstall','clean','remove'):
        usage()
    process=cmds[0]

    conf=yumconf(configfile=yumconffile)
    
    #setup log classes
    #used for the syslog-style log
    #syslog-style log
    logfile=open(conf.logfile,"a")
    filelog=Logger(threshold=10, file_object=logfile,preprefix=clientStuff.printtime())
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

    #make remote nevral class
    HeaderInfo = nevral.nevral()
    
    #get the package info file
    clientStuff.get_package_info_from_servers(conf, HeaderInfo)
    
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
    clientStuff.download_headers(HeaderInfo, nulist)
    log(2,"Finding obsoleted packages")
    obsdict=clientStuff.returnObsoletes(HeaderInfo,rpmDBInfo,nulist)
    obslist=obsdict.keys()
    
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

    clientStuff.take_action(cmds,nulist,uplist,newlist,obslist,tsInfo,HeaderInfo,rpmDBInfo,obsdict)
    
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
    #(i, u, e, ed, ud,iu(installing, but marking as 'u' in the actual ts, just in case)) confirm w/the user
    
    (i_list,u_list,e_list,ud_list,ed_list)=clientStuff.actionslists(tsInfo)
    
    clientStuff.printactions(i_list,u_list,e_list,ud_list,ed_list)
    if conf.assumeyes==0:
        if clientStuff.userconfirm():
            errorlog(1,"Exiting on user command.")
            sys.exit(1)
    
    if uid==0:
        dbfin = clientStuff.openrpmdb(1,'/')
    else:
        dbfin = clientStuff.openrpmdb(0,'/')
    
    tsfin = clientStuff.create_final_ts(tsInfo,dbfin)

    if uid == 0:
        #sigh - the magical "order" command - nice of this not to really be documented anywhere.
        tsfin.order()
        errors = tsfin.run(0, 0, callback.install_callback, '')
        if errors:
            errorlog(0,"Errors installing:")
            for error in errors:
                errorlog(0,error)
            sys.exit(1)
        
        del dbfin
        del tsfin
        
        #Check to see if we've got a new kernel and put it in the right place in grub/lilo
        pkgaction.kernelupdate(tsInfo)
        
        #log what we did and also print it out
        clientStuff.filelogactions(i_list,u_list,e_list,ud_list,ed_list)
        clientStuff.shortlogactions(i_list,u_list,e_list,ud_list,ed_list)
        
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
          -e [error level] - set the error logging level
          -d [debug level] - set the debugging level
          -y answer yes to all questions
          -h, --help this screen
    """
    sys.exit(1)
    
if __name__ == "__main__":
    main()

