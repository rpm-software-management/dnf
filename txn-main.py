#!/usr/bin/python -tt
# yum-transaction
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
# copyright 2003 Duke University


import os
import sys
import getopt
import clientStuff
import nevral
import pkgaction
import callback
import time
import random
import locale
import rpm
import rpmUtils
import yumcomps
import transactions

from logger import Logger
from config import yumconf
from i18n import _

__version__='2.1'

def getCommands(args):
    options = {}
    options['testmode'] = 0
    
    try:
        gopts, files = getopt.getopt(args, 'e:d:', ['test, version, installroot='])
    except getopt.error, e:
        print _('Options Error: %s') % e
        usage()

        for o,a in gopts:
            if o == '-d':
                options['debuglevel'] = int(a)
            elif o == '-e':
                options['errorlevel'] = int(a)
            elif o == '--installroot':
                if os.access(a, os.W_OK):
                    options['installroot'] = a
                else:
                    print _('Error: installroot %s cannot be accessed writable') % a
                    sys.exit(1)
            elif o == '--version':
                print __version__
                sys.exit()
            elif o == '--test':
                options['testmode']=1
                
    except ValueError, e:
        print _('Options Error: %s') % e
        usage()
        
    return (options, files)
    
def txnConfig(txnconfigfile, options):
    """take the config file and global options and setup logs, configs, etc"""
    
    # setup our errorlog object 
    errorlog=Logger(threshold=2, file_object=sys.stderr)
    
    if options.has_key('installroot'):
        if os.access(options['installroot'] + configfile, os.R_OK):
            txnconfigfile = options['installroot'] + configfile
    else:
        if not os.access(txnconfigfile, os.R_OK):
            errorlog(0, _('Cannot find any conf file.'))
            sys.exit(1)
    
    conf=yumconf(configfile=txnconfigfile)
    conf.yumversion = __version__

    # we'd like to have a log object now
    log=Logger(threshold=conf.debuglevel, file_object=sys.stdout)

    # syslog-style log
    logfile=open(conf.logfile,"a")
    filelog=Logger(threshold=10, file_object=logfile,preprefix=clientStuff.printtime())

    if options.has_key('debuglevel'):
        log.threshold=options['debuglevel']
        conf.debuglevel=options['debuglevel']
    if options.has_key('errorlevel'):
        errorlog.threshold=options['errorlevel']
        conf.errorlevel=options['errorlevel']
    if options.has_key('installroot'):
        conf.installroot=options['installroot']
    conf.assumeyes=1
    conf.tolerant=1

    return (log, errorlog, filelog, conf)
    

def main(args):
    """get all the files together, control the main set of transactions"""
    locale.setlocale(locale.LC_ALL, '')
    # take the yum xml file as an argument and --test, debug and error levels
    #script commands:
    (options, cmds) = getCommands(args)
    ytxnFileList = []
    for filename in cmds:
        if os.access(filename, os.R_OK):
            # it'd be nice to do this in a try except loop to rule out the files
            # that are no good - need a yumError class.
            ytxnfile = transactions.YumTransactionFile(filename)
            ytxnFileList.append(ytxnfile)
        else: 
            print _('Error reading %s, skipping') % filename
    
    print _('%d files used') % len(ytxnFileList)
    totaltxn = 0
    for ytxnfile in ytxnFileList:
        totaltxn = totaltxn + ytxnfile.transactionCount()
    print _('%d total transactions') % totaltxn
    
    for ytxnfile in ytxnFileList:
        for ytxn in ytxnfile.transactionList():
            print ytxn.name
            
            result = runTransaction(ytxn, options)
            if not result:
                print 'failed %s' % ytxn.name
            

def runTransaction(ytxn, options):
    """this should run any one transaction and return a result code"""
    
    # setup logs
    # setup config
    # push the logs into the other namespaces
    # push the ts "
    # push the conf "
    
    # create the lists of stuff we'll need
    # act like -y is always there

    (log, errorlog, filelog, conf) = txnConfig(ytxn.config, options)
    pkgaction.log = log
    clientStuff.log = log
    nevral.log = log
    rpmUtils.log = log

    pkgaction.errorlog = errorlog
    clientStuff.errorlog = errorlog
    nevral.errorlog = errorlog
    rpmUtils.errorlog = errorlog
    
    pkgaction.filelog = filelog
    clientStuff.filelog = filelog
    nevral.filelog = filelog
    rpmUtils.filelog = filelog
    
    # push the conf file into the other namespaces
    nevral.conf = conf
    clientStuff.conf = conf
    pkgaction.conf = conf
    callback.conf = conf
    rpmUtils.conf = conf
    
    # get our ts together that we'll use all over the place
    ts = rpmUtils.Rpm_Ts_Work()
    ts.sigChecking('none')
    clientStuff.ts = ts
    pkgaction.ts = ts
    nevral.ts = ts
    rpmUtils.ts = ts
    yumcomps.ts = ts
    
    # make remote nevral class
    HeaderInfo = nevral.nevral()
    
    # sorting the servers so that sort() will order them consistently
    # If you wanted to add scoring or somesuch thing for server preferences
    # or even getting rid of servers b/c of some criteria you could
    # replace serverlist.sort() with a function - all it has to do
    # is return an ordered list of serverids and have it stored in
    # serverlist
    serverlist = conf.servers
    serverlist.sort()

    # get the package info file
    clientStuff.get_package_info_from_servers(serverlist, HeaderInfo)
    
    # make local nevral class
    rpmDBInfo = nevral.nevral()
    clientStuff.rpmdbNevralLoad(rpmDBInfo)

    # create transaction set nevral class
    tsInfo = nevral.nevral()
    #################################################################################
    # generate all the lists we'll need to quickly iterate through the lists.
    #  uplist == list of updated packages
    #  newlist == list of uninstall/available NEW packages (ones we don't have at all)
    #  nulist == combination of the two
    #  obslist == packages obsoleting a package we have installed
    ################################################################################
    
    (pkgprocesses, groupprocesses) = ytxn.processes()
    #########
    ## This should go through the above and update the tsInfo nevral
    # - might want to consider what will need to happen and how to order processes
    #  - ie: cleans
    #        all group actions
    #        all pkg actions
    
    log(2, _('Finding updated packages'))
    (uplist, newlist, nulist) = clientStuff.getupdatedhdrlist(HeaderInfo, rpmDBInfo)

    if 'upgrade' in pkgprocesses:
        log(2, _('Finding obsoleted packages'))
        obsoleting, obsoleted = clientStuff.returnObsoletes(HeaderInfo, rpmDBInfo, nulist)
    else:
        obsoleting = {}
        obsoleted = {}

    if len(groupprocesses) > 0:
        servers_with_groups = clientStuff.get_groups_from_servers(serverlist)
        GroupInfo = yumcomps.Groups_Info(conf.overwrite_groups)
        if len(servers_with_groups) > 0:
            for serverid in servers_with_groups:
                log(4, 'Adding Group from %s' % serverid)
                GroupInfo.add(conf.localGroups(serverid))
        if GroupInfo.compscount > 0:
            GroupInfo.compileGroups()
            clientStuff.GroupInfo = GroupInfo
            pkgaction.GroupInfo = GroupInfo
        else:
            errorlog(0, 'No groups provided or accessible on any server.')
            errorlog(1, 'Exiting.')
            return 0

    
    log(3, 'nulist = %s' % len(nulist))
    log(3, 'uplist = %s' % len(uplist))
    log(3, 'newlist = %s' % len(newlist))
    log(3, 'obsoleting = %s' % len(obsoleting.keys()))
    log(3, 'obsoleted = %s' % len(obsoleted.keys()))

    
    ##################################################################
    # at this point we have all the prereq info we could ask for. we 
    # know whats in the rpmdb whats available, whats updated and what 
    # obsoletes. We should be able to do everything we want from here 
    # w/o getting anymore header info
    ##################################################################
    if len(groupprocesses) > 0:
        if 'install' in groupprocesses:
            cmds = ['groupinstall'] + ytxn.groupsInstall()
            clientStuff.take_action(cmds, nulist, uplist, newlist, obsoleting, tsInfo,\
                            HeaderInfo, rpmDBInfo, obsoleted)
        if 'update' in groupprocesses:
            cmds = ['groupupdate'] + ytxn.groupsUpdate()
            clientStuff.take_action(cmds, nulist, uplist, newlist, obsoleting, tsInfo,\
                            HeaderInfo, rpmDBInfo, obsoleted)
        if 'remove' in groupprocesses:
            cmds = ['groupremove'] + ytxn.groupsRemove()
            clientStuff.take_action(cmds, nulist, uplist, newlist, obsoleting, tsInfo,\
                            HeaderInfo, rpmDBInfo, obsoleted)
    
    if len(pkgprocesses) > 0:
        if 'install' in pkgprocesses:
            cmds = ['install'] + ytxn.pkgsInstall()
            clientStuff.take_action(cmds, nulist, uplist, newlist, obsoleting, tsInfo,\
                            HeaderInfo, rpmDBInfo, obsoleted)
        if 'update' in pkgprocesses:
            cmds = ['update'] + ytxn.pkgsUpdate()
            clientStuff.take_action(cmds, nulist, uplist, newlist, obsoleting, tsInfo,\
                            HeaderInfo, rpmDBInfo, obsoleted)
        if 'install' in pkgprocesses:
            cmds = ['upgrade'] + ytxn.pkgsUpgrade()
            clientStuff.take_action(cmds, nulist, uplist, newlist, obsoleting, tsInfo,\
                            HeaderInfo, rpmDBInfo, obsoleted)
        if 'remove' in pkgprocesses:
            cmds = ['remove'] + ytxn.pkgsRemove()
            clientStuff.take_action(cmds, nulist, uplist, newlist, obsoleting, tsInfo,\
                            HeaderInfo, rpmDBInfo, obsoleted)

    # back from taking actions - if we've not exited by this point then we have
    # an action that will install/erase/update something
    
    # at this point we should have a tsInfo nevral with all we need to complete our task.
    # if for some reason we've gotten all the way through this step with 
    # an empty tsInfo then exit and be confused :)
    if len(tsInfo.NAkeys()) < 1:
        log(2, _('No actions to take'))
        return 1
        
    
    for (name, arch) in nulist:
        if not tsInfo.exists(name, arch):
            ((e, v, r, a, l, i), s)=HeaderInfo._get_data(name, arch)
            log(6,'making available: %s' % name)
            tsInfo.add((name, e, v, r, arch, l, i), 'a')

    log(2, _('Resolving dependencies'))
    (errorcode, msgs) = tsInfo.resolvedeps(rpmDBInfo)
    if errorcode:
        for msg in msgs:
            print msg
        sys.exit(1)
    log(2, _('Dependencies resolved'))
    
    # prompt for use permission to do stuff in tsInfo - list all the actions 
    # (i, u, e, ed, ud,iu(installing, but marking as 'u' in the actual ts, just 
    # in case)) confirm w/the user
    
    (i_list, u_list, e_list, ud_list, ed_list)=clientStuff.actionslists(tsInfo)
    
    clientStuff.printactions(i_list, u_list, e_list, ud_list, ed_list, tsInfo)
    if conf.assumeyes==0:
        if clientStuff.userconfirm():
            errorlog(1, _('Exiting on user command.'))
            return 0

    
    # Test run for disk space checks
    # only run it if diskspacecheck = 1 and if there is anything being installed
    # or updated - erasures shouldn't need more disk space
    if conf.diskspacecheck:
        if len(i_list+u_list+ud_list) > 0:
            tstest = clientStuff.create_final_ts(tsInfo)
            log(2, _('Calculating available disk space - this could take a bit'))
            clientStuff.diskspacetest(tstest)
            tstest.closeDB()
            del tstest
    
    # FIXME the actual run should probably be elsewhere and this should be
    # inside a try, except set
    tsfin = clientStuff.create_final_ts(tsInfo)
    
    if conf.diskspacecheck == 0:
        tsfin.setProbFilter(rpm.RPMPROB_FILTER_DISKSPACE)

    if conf.uid == 0:
        # sigh - the magical "order" command - nice of this not to really be 
        # documented anywhere.
        tsfin.check()
        tsfin.order()
        cb = callback.RPMInstallCallback()
        errors = tsfin.run(cb.callback, '')
        if errors:
            errorlog(0, _('Errors installing:'))
            for error in errors:
                errorlog(0, error)
            return 0
        tsfin.closeDB()
        del tsfin
        
        # Check to see if we've got a new kernel and put it in the right place in grub/lilo
        pkgaction.kernelupdate(tsInfo)
        
        # log what we did and also print it out
        clientStuff.filelogactions(i_list, u_list, e_list, ud_list, ed_list, tsInfo)
        clientStuff.shortlogactions(i_list, u_list, e_list, ud_list, ed_list, tsInfo)
        
    else:
        errorlog(1, _('You\'re not root, we can\'t install things'))
        sys.exit(0)
        
    log(2, _('Transaction(s) Complete'))
    return 1


def usage():
    print _("""
    Usage:  yum [options] <update | upgrade | install | info | remove | list |
            clean | provides | check-update | groupinstall | groupupdate |
            grouplist >
                
         Options:
          -c [config file] - specify the config file to use
          -e [error level] - set the error logging level
          -d [debug level] - set the debugging level
          -y answer yes to all questions
          -t be tolerant about errors in package commands
          -R [time in minutes] - set the max amount of time to randonly run in.
          -C run from cache only - do not update the cache
          --installroot=[path] - set the install root (default '/')
          --version - output the version of yum
          -h, --help this screen
    """)
    sys.exit(1)
    
if __name__ == "__main__":
        main(sys.argv[1:])
