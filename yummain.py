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


import os
import sys
import locale

import callback
import yum
import rpmUtils.transaction
import rpmUtils.updates
import yum.yumcomps
import yum.Errors
import cli
import output

from i18n import _

__version__='2.1.0'


def main(args):
    """This does all the real work"""

    locale.setlocale(locale.LC_ALL, '')
    
    if len(args) < 1:
        cli.usage()

    # this will be our holder object, things will be pushed in here and passed around 
    # think of this like a global
    base = yum.YumBase()
    cli.base = base # push it into the cli namespace for future use
    
    # parse our cli args, read in the config file and setup the logs
    cli.getOptionsConfig(args, base)
    
    if len(base.conf.getConfigOption('commands')) == 0 and len(base.cmds) < 1:
        base.cmds = base.conf.getConfigOption('commands')
    else:
        base.conf.setConfigOption('commands', base.cmds)
        
    if len (base.cmds) < 1:
        base.errorlog(0, _('Options Error: no commands found'))
        cli.usage()

    if base.cmds[0] not in ('update', 'install','info', 'list', 'erase',\
                       'grouplist','groupupdate','groupinstall','clean', \
                       'remove', 'provides', 'check-update', 'search'):
        cli.usage()
    process = base.cmds[0]
    
    # ok at this point lets check the lock/set the lock if we can
    if base.conf.getConfigOption('uid') == 0:
        mypid = str(os.getpid())
        try:
            yum.doLock('/var/run/yum.pid', mypid)
        except Errors.LockError, e:
            print _('%s') % e.msg
            sys.exit(200)
            
    # set our caching mode correctly
    if base.conf.getConfigOption('uid') != 0:
        base.conf.setConfigOption('cache', 1)
    if process == 'clean':
        base.conf.setConfigOption('cache', 1)

    # get our transaction set together that we'll use all over the place
    base.read_ts = rpmUtils.transaction.initReadOnlyTransaction()
    
    # create structs for local rpmdb
    base.rpmdb = rpmUtils.RpmDBHolder()
    base.rpmdb.addDB(base.read_ts)
    base.log(2, '#pkgs in db = %s' % len(base.rpmdb.getPkgList()))

    
    if process in ['groupupdate', 'groupinstall', 'grouplist', 'groupremove']:
        base.grpInfo = yum.yumcomps.Groups_Info(base.rpmdb.getPkgList(),
                                 base.conf.getConfigOption('overwrite_groups'))
                                 
        for repo in base.repos.listGroupsEnabled():
            groupfile = repo.getGroups(base.conf.getConfigOption('cache'))
            if groupfile:
                base.log(4, 'Group File found for %s' % repo)
                base.log(4, 'Adding Groups from %s' % repo)
                base.grpInfo.add(groupfile)

        if base.grpInfo.compscount > 0:
            base.grpInfo.compileGroups()
        else:
            base.errorlog(0, _('No groups provided or accessible on any repository.'))
            base.errorlog(1, _('Exiting.'))
            sys.exit(1)

    base.repos.populateSack(callback=output.simpleProgressBar)
    base.pkgSack = base.repos.pkgSack
    base.log(2, '#pkgs in repos = %s' % len(base.pkgSack))

   
    base.log(2, _('Finding updated packages'))
    base.up = rpmUtils.updates.Updates(base.rpmdb.getPkgList(), base.pkgSack.simplePkgList())
    base.up.exactarch = base.conf.getConfigOption('exactarch')
    base.up.doUpdates()
    base.up.condenseUpdates()
    base.log(2, '# of updates = %s' % len(base.up.getUpdatesList()))

    base.log(2, '# of avail pkgs = %s' % len(base.up.getOthersList()))
    
    base.tsInfo = rpmUtils.transaction.TransactionData()
    for pkgtup in base.up.getUpdatesList():
        base.tsInfo.add(pkgtup, 'u', 'user')
        
    print base.tsInfo.display()
    # build up a list of pkgobj from the pkgsack to go with each item in a:
    # i or u mode in the tsInfo
    base.updatespkgs = []
    for (pkgtup, mode) in base.tsInfo.data['packages']:
        if mode in ['u', 'i']:
            (n, a, e, v, r) = pkgtup
            pkgs = base.pkgSack.searchNevra(name=n, arch=a, epoch=e, ver=v, rel=r)
            for pkg in pkgs:
               print pkg.returnSimple('relativepath')
 
"""
    if len(tsInfo.NAkeys()) < 1:
        log(2, _('No actions to take'))
        sys.exit(0)
        
    
    if process not in ('erase', 'remove'):
        # put available pkgs in tsInfonevral in state 'a'
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
            sys.exit(1)
    
    # Test run for file conflicts and diskspace check, etc.
    tstest = clientStuff.create_final_ts(tsInfo)
    log(2, _('Running test transaction:'))
    clientStuff.tsTest(tstest)
    tstest.closeDB()
    del tstest
    log(2, _('Test transaction complete, Success!'))
    
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
            sys.exit(1)
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
    sys.exit(0)
"""

    
if __name__ == "__main__":
        main(sys.argv[1:])
