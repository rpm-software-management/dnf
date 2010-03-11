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
# Copyright 2005 Duke University 
# Written by Seth Vidal

"""
Command line interface yum class and related.
"""

import os
import re
import sys
import time
import random
import logging
from optparse import OptionParser,OptionGroup
import rpm

from weakref import proxy as weakref

import output
import shell
import yum
import yum.Errors
import yum.logginglevels
import yum.misc
import yum.plugins
from rpmUtils.arch import isMultiLibArch
from yum import _
from yum.rpmtrans import RPMTransaction
import signal
import yumcommands

from yum.i18n import to_unicode, to_utf8

def sigquit(signum, frame):
    """ SIGQUIT handler for the yum cli. """
    print >> sys.stderr, "Quit signal sent - exiting immediately"
    sys.exit(1)

class CliError(yum.Errors.YumBaseError):

    """
    Command line interface related Exception.
    """

    def __init__(self, args=''):
        yum.Errors.YumBaseError.__init__(self)
        self.args = args

class YumBaseCli(yum.YumBase, output.YumOutput):
    """This is the base class for yum cli.
       Inherits from yum.YumBase and output.YumOutput """
       
    def __init__(self):
        # handle sigquit early on
        signal.signal(signal.SIGQUIT, sigquit)
        yum.YumBase.__init__(self)
        output.YumOutput.__init__(self)
        logging.basicConfig()
        self.logger = logging.getLogger("yum.cli")
        self.verbose_logger = logging.getLogger("yum.verbose.cli")
        self.yum_cli_commands = {}
        self.registerCommand(yumcommands.InstallCommand())
        self.registerCommand(yumcommands.UpdateCommand())
        self.registerCommand(yumcommands.InfoCommand())
        self.registerCommand(yumcommands.ListCommand())
        self.registerCommand(yumcommands.EraseCommand())
        self.registerCommand(yumcommands.GroupCommand())
        self.registerCommand(yumcommands.GroupListCommand())
        self.registerCommand(yumcommands.GroupInstallCommand())
        self.registerCommand(yumcommands.GroupRemoveCommand())
        self.registerCommand(yumcommands.GroupInfoCommand())
        self.registerCommand(yumcommands.MakeCacheCommand())
        self.registerCommand(yumcommands.CleanCommand())
        self.registerCommand(yumcommands.ProvidesCommand())
        self.registerCommand(yumcommands.CheckUpdateCommand())
        self.registerCommand(yumcommands.SearchCommand())
        self.registerCommand(yumcommands.UpgradeCommand())
        self.registerCommand(yumcommands.LocalInstallCommand())
        self.registerCommand(yumcommands.ResolveDepCommand())
        self.registerCommand(yumcommands.ShellCommand())
        self.registerCommand(yumcommands.DepListCommand())
        self.registerCommand(yumcommands.RepoListCommand())
        self.registerCommand(yumcommands.HelpCommand())
        self.registerCommand(yumcommands.ReInstallCommand())        
        self.registerCommand(yumcommands.DowngradeCommand())        
        self.registerCommand(yumcommands.VersionCommand())
        self.registerCommand(yumcommands.HistoryCommand())
        self.registerCommand(yumcommands.CheckRpmdbCommand())
        self.registerCommand(yumcommands.DistroSyncCommand())

    def registerCommand(self, command):
        for name in command.getNames():
            if name in self.yum_cli_commands:
                raise yum.Errors.ConfigError(_('Command "%s" already defined') % name)
            self.yum_cli_commands[name] = command
            
    def doRepoSetup(self, thisrepo=None, dosack=1):
        """grabs the repomd.xml for each enabled repository 
           and sets up the basics of the repository"""
        
        if self._repos and thisrepo is None:
            return self._repos
            
        if not thisrepo:
            self.verbose_logger.log(yum.logginglevels.INFO_2,
                _('Setting up repositories'))

        # Call parent class to do the bulk of work 
        # (this also ensures that reposetup plugin hook is called)
        if thisrepo:
            yum.YumBase._getRepos(self, thisrepo=thisrepo, doSetup=True)
        else:
            yum.YumBase._getRepos(self, thisrepo=thisrepo)

        if dosack: # so we can make the dirs and grab the repomd.xml but not import the md
            self.verbose_logger.log(yum.logginglevels.INFO_2,
                _('Reading repository metadata in from local files'))
            self._getSacks(thisrepo=thisrepo)
        
        return self._repos

    def _makeUsage(self):
        """
        Format an attractive usage string for yum, listing subcommand
        names and summary usages.
        """
        usage = 'yum [options] COMMAND\n\nList of Commands:\n\n'
        commands = yum.misc.unique(self.yum_cli_commands.values())
        commands.sort(key=lambda x: x.getNames()[0])
        for command in commands:
            # XXX Remove this when getSummary is common in plugins
            try:
                summary = command.getSummary()
                usage += "%-14s %s\n" % (command.getNames()[0], summary)
            except (AttributeError, NotImplementedError):
                usage += "%s\n" % command.getNames()[0]

        return usage

    def getOptionsConfig(self, args):
        """parses command line arguments, takes cli args:
        sets up self.conf and self.cmds as well as logger objects 
        in base instance"""
       
        self.optparser = YumOptionParser(base=self, usage=self._makeUsage())
        
        # Parse only command line options that affect basic yum setup
        opts = self.optparser.firstParse(args)

        # Just print out the version if that's what the user wanted
        if opts.version:
            print yum.__version__
            opts.quiet = True
            opts.verbose = False

        # get the install root to use
        root = self.optparser.getRoot(opts)

        if opts.quiet:
            opts.debuglevel = 0
        if opts.verbose:
            opts.debuglevel = opts.errorlevel = 6
       
        # Read up configuration options and initialise plugins
        try:
            pc = self.preconf
            pc.fn = opts.conffile
            pc.root = root
            pc.init_plugins = not opts.noplugins
            pc.plugin_types = (yum.plugins.TYPE_CORE,
                               yum.plugins.TYPE_INTERACTIVE)
            pc.optparser = self.optparser
            pc.debuglevel = opts.debuglevel
            pc.errorlevel = opts.errorlevel
            pc.disabled_plugins = self.optparser._splitArg(opts.disableplugins)
            pc.enabled_plugins  = self.optparser._splitArg(opts.enableplugins)
            pc.releasever = opts.releasever
            self.conf
                    
        except yum.Errors.ConfigError, e:
            self.logger.critical(_('Config Error: %s'), e)
            sys.exit(1)
        except ValueError, e:
            self.logger.critical(_('Options Error: %s'), e)
            sys.exit(1)

        # update usage in case plugins have added commands
        self.optparser.set_usage(self._makeUsage())
        
        self.plugins.run('args', args=args)
        # Now parse the command line for real and 
        # apply some of the options to self.conf
        (opts, self.cmds) = self.optparser.setupYumConfig(args=args)

        if opts.version:
            self.conf.cache = 1
            yum_progs = self.run_with_package_names
            done = False
            def sm_ui_time(x):
                return time.strftime("%Y-%m-%d %H:%M", time.gmtime(x))
            def sm_ui_date(x): # For changelogs, there is no time
                return time.strftime("%Y-%m-%d", time.gmtime(x))
            for pkg in sorted(self.rpmdb.returnPackages(patterns=yum_progs)):
                # We should only have 1 version of each...
                if done: print ""
                done = True
                if pkg.epoch == '0':
                    ver = '%s-%s.%s' % (pkg.version, pkg.release, pkg.arch)
                else:
                    ver = '%s:%s-%s.%s' % (pkg.epoch,
                                           pkg.version, pkg.release, pkg.arch)
                name = "%s%s%s" % (self.term.MODE['bold'], pkg.name,
                                   self.term.MODE['normal'])
                print _("  Installed: %s-%s at %s") %(name, ver,
                                                   sm_ui_time(pkg.installtime))
                print _("  Built    : %s at %s") % (pkg.packager,
                                                    sm_ui_time(pkg.buildtime))
                print _("  Committed: %s at %s") % (pkg.committer,
                                                    sm_ui_date(pkg.committime))
            sys.exit(0)

        if opts.sleeptime is not None:
            sleeptime = random.randrange(opts.sleeptime*60)
        else:
            sleeptime = 0
        
        # save our original args out
        self.args = args
        # save out as a nice command string
        self.cmdstring = 'yum '
        for arg in self.args:
            self.cmdstring += '%s ' % arg

        try:
            self.parseCommands() # before we return check over the base command + args
                                 # make sure they match/make sense
        except CliError:
            sys.exit(1)
    
        # run the sleep - if it's unchanged then it won't matter
        time.sleep(sleeptime)
        
    def parseCommands(self):
        """reads self.cmds and parses them out to make sure that the requested 
        base command + argument makes any sense at all""" 

        self.verbose_logger.debug('Yum Version: %s', yum.__version__)
        self.verbose_logger.log(yum.logginglevels.DEBUG_4,
                                'COMMAND: %s', self.cmdstring)
        self.verbose_logger.log(yum.logginglevels.DEBUG_4,
                                'Installroot: %s', self.conf.installroot)
        if len(self.conf.commands) == 0 and len(self.cmds) < 1:
            self.cmds = self.conf.commands
        else:
            self.conf.commands = self.cmds
        if len(self.cmds) < 1:
            self.logger.critical(_('You need to give some command'))
            self.usage()
            raise CliError
            
        self.basecmd = self.cmds[0] # our base command
        self.extcmds = self.cmds[1:] # out extended arguments/commands
        
        if len(self.extcmds) > 0:
            self.verbose_logger.log(yum.logginglevels.DEBUG_4,
                                    'Ext Commands:\n')
            for arg in self.extcmds:
                self.verbose_logger.log(yum.logginglevels.DEBUG_4, '   %s', arg)
        
        if self.basecmd not in self.yum_cli_commands:
            self.logger.critical(_('No such command: %s. Please use %s --help'),
                                  self.basecmd, sys.argv[0])
            raise CliError
    
        self.yum_cli_commands[self.basecmd].doCheck(self, self.basecmd, self.extcmds)

    def doShell(self):
        """do a shell-like interface for yum commands"""

        yumshell = shell.YumShell(base=self)
        if len(self.extcmds) == 0:
            yumshell.cmdloop()
        else:
            yumshell.script()
        return yumshell.result, yumshell.resultmsgs

    def errorSummary(self, errstring):
        """ parse the error string for 'interesting' errors which can
            be grouped, such as disk space issues """
        summary = ''
        # do disk space report first
        p = re.compile('needs (\d+)MB on the (\S+) filesystem')
        disk = {}
        for m in p.finditer(errstring):
            if not disk.has_key(m.group(2)):
                disk[m.group(2)] = int(m.group(1))
            if disk[m.group(2)] < int(m.group(1)):
                disk[m.group(2)] = int(m.group(1))
                
        if disk:
            summary += _('Disk Requirements:\n')
            for k in disk:
                summary += _('  At least %dMB more space needed on the %s filesystem.\n') % (disk[k], k)

        # TODO: simplify the dependency errors?

        # Fixup the summary
        summary = _('Error Summary\n-------------\n') + summary
              
        return summary


    def doCommands(self):
        """
        Calls the base command passes the extended commands/args out to be
        parsed (most notably package globs).
        
        Returns a numeric result code and an optional string
           - 0 = we're done, exit
           - 1 = we've errored, exit with error string
           - 2 = we've got work yet to do, onto the next stage
        """
        
        # at this point we know the args are valid - we don't know their meaning
        # but we know we're not being sent garbage
        
        # setup our transaction set if the command we're using needs it
        # compat with odd modules not subclassing YumCommand
        needTs = True
        needTsRemove = False
        cmd = self.yum_cli_commands[self.basecmd]
        if hasattr(cmd, 'needTs'):
            needTs = cmd.needTs(self, self.basecmd, self.extcmds)
        if not needTs and hasattr(cmd, 'needTsRemove'):
            needTsRemove = cmd.needTsRemove(self, self.basecmd, self.extcmds)
        
        if needTs or needTsRemove:
            try:
                self._getTs(needTsRemove)
            except yum.Errors.YumBaseError, e:
                return 1, [str(e)]

        return self.yum_cli_commands[self.basecmd].doCommand(self, self.basecmd, self.extcmds)

    def doTransaction(self):
        """takes care of package downloading, checking, user confirmation and actually
           RUNNING the transaction"""
    
        # just make sure there's not, well, nothing to do
        if len(self.tsInfo) == 0:
            self.verbose_logger.info(_('Trying to run the transaction but nothing to do. Exiting.'))
            return 1

        # NOTE: In theory we can skip this in -q -y mode, for a slight perf.
        #       gain. But it's probably doom to have a different code path.
        lsts = self.listTransaction()
        if self.verbose_logger.isEnabledFor(yum.logginglevels.INFO_1):
            self.verbose_logger.log(yum.logginglevels.INFO_1, lsts)
        elif not self.conf.assumeyes:
            #  If we are in quiet, and assumeyes isn't on we want to output
            # at least the transaction list anyway.
            self.logger.warn(lsts)
        
        # Check which packages have to be downloaded
        downloadpkgs = []
        stuff_to_download = False
        install_only = True
        for txmbr in self.tsInfo.getMembers():
            if txmbr.ts_state not in ('i', 'u'):
                install_only = False
            else:
                stuff_to_download = True
                po = txmbr.po
                if po:
                    downloadpkgs.append(po)

        # Close the connection to the rpmdb so that rpm doesn't hold the SIGINT
        # handler during the downloads. self.ts is reinitialised later in this
        # function anyway (initActionTs). 
        self.ts.close()

        # Report the total download size to the user, so he/she can base
        # the answer on this info
        if stuff_to_download:
            self.reportDownloadSize(downloadpkgs, install_only)
        
        # confirm with user
        if self._promptWanted():
            if not self.userconfirm():
                self.verbose_logger.info(_('Exiting on user Command'))
                return 1

        self.verbose_logger.log(yum.logginglevels.INFO_2,
            _('Downloading Packages:'))
        problems = self.downloadPkgs(downloadpkgs, callback_total=self.download_callback_total_cb) 

        if len(problems) > 0:
            errstring = ''
            errstring += _('Error Downloading Packages:\n')
            for key in problems:
                errors = yum.misc.unique(problems[key])
                for error in errors:
                    errstring += '  %s: %s\n' % (key, error)
            raise yum.Errors.YumBaseError, errstring

        # Check GPG signatures
        if self.gpgsigcheck(downloadpkgs) != 0:
            return 1
        
        if self.conf.rpm_check_debug:
            rcd_st = time.time()
            self.verbose_logger.log(yum.logginglevels.INFO_2, 
                 _('Running rpm_check_debug'))
            msgs = self._run_rpm_check_debug()
            if msgs:
                rpmlib_only = True
                for msg in msgs:
                    if msg.startswith('rpmlib('):
                        continue
                    rpmlib_only = False
                if rpmlib_only:
                    print _("ERROR You need to update rpm to handle:")
                else:
                    print _('ERROR with rpm_check_debug vs depsolve:')

                for msg in msgs:
                    print to_utf8(msg)

                if rpmlib_only:
                    return 1, [_('RPM needs to be updated')]
                return 1, [_('Please report this error in %s') % self.conf.bugtracker_url]

            self.verbose_logger.debug('rpm_check_debug time: %0.3f' % (time.time() - rcd_st))

        tt_st = time.time()            
        self.verbose_logger.log(yum.logginglevels.INFO_2,
            _('Running Transaction Test'))
        if not self.conf.diskspacecheck:
            self.tsInfo.probFilterFlags.append(rpm.RPMPROB_FILTER_DISKSPACE)
            
        
        testcb = RPMTransaction(self, test=True)
        
        self.initActionTs()
        # save our dsCallback out
        dscb = self.dsCallback
        self.dsCallback = None # dumb, dumb dumb dumb!
        self.populateTs(keepold=0) # sigh
        tserrors = self.ts.test(testcb)
        del testcb

        if len(tserrors) > 0:
            errstring = _('Transaction Check Error:\n')
            for descr in tserrors:
                errstring += '  %s\n' % to_unicode(descr)
            
            raise yum.Errors.YumBaseError, errstring + '\n' + \
                 self.errorSummary(errstring)
        self.verbose_logger.log(yum.logginglevels.INFO_2,
             _('Transaction Test Succeeded'))
        del self.ts
        
        self.verbose_logger.debug('Transaction Test time: %0.3f' % (time.time() - tt_st))
        
        # unset the sigquit handler
        signal.signal(signal.SIGQUIT, signal.SIG_DFL)
        
        ts_st = time.time()
        self.initActionTs() # make a new, blank ts to populate
        self.populateTs(keepold=0) # populate the ts
        self.ts.check() #required for ordering
        self.ts.order() # order

        # put back our depcheck callback
        self.dsCallback = dscb
        # setup our rpm ts callback
        cb = RPMTransaction(self,
                            display=output.YumCliRPMCallBack(weakref(self)))
        if self.conf.debuglevel < 2:
            cb.display.output = False

        self.verbose_logger.log(yum.logginglevels.INFO_2, _('Running Transaction'))
        resultobject = self.runTransaction(cb=cb)

        self.verbose_logger.debug('Transaction time: %0.3f' % (time.time() - ts_st))
        # close things
        self.verbose_logger.log(yum.logginglevels.INFO_1,
            self.postTransactionOutput())
        
        # put back the sigquit handler
        signal.signal(signal.SIGQUIT, sigquit)
        
        return resultobject.return_code
        
    def gpgsigcheck(self, pkgs):
        '''Perform GPG signature verification on the given packages, installing
        keys if possible

        Returns non-zero if execution should stop (user abort).
        Will raise YumBaseError if there's a problem
        '''
        for po in pkgs:
            result, errmsg = self.sigCheckPkg(po)

            if result == 0:
                # Verified ok, or verify not req'd
                continue            

            elif result == 1:
                if not sys.stdin.isatty() and not self.conf.assumeyes:
                    raise yum.Errors.YumBaseError, \
                            _('Refusing to automatically import keys when running ' \
                            'unattended.\nUse "-y" to override.')

                # the callback here expects to be able to take options which
                # userconfirm really doesn't... so fake it
                self.getKeyForPackage(po, lambda x, y, z: self.userconfirm())

            else:
                # Fatal error
                raise yum.Errors.YumBaseError, errmsg

        return 0

    def _maybeYouMeant(self, arg):
        """ If install argument doesn't match with case, tell the user. """
        matches = self.doPackageLists(patterns=[arg], ignore_case=True)
        matches = matches.installed + matches.available
        matches = set(map(lambda x: x.name, matches))
        if matches:
            msg = self.fmtKeyValFill(_('  * Maybe you meant: '),
                                     ", ".join(matches))
            self.verbose_logger.log(yum.logginglevels.INFO_2, msg)

    def _checkMaybeYouMeant(self, arg, always_output=True):
        """ If the update/remove argument doesn't match with case, or due
            to not being installed, tell the user. """
        # always_output is a wart due to update/remove not producing the
        # same output.
        matches = self.doPackageLists(patterns=[arg], ignore_case=False)
        if (matches.installed or (not matches.available and
                                  self.returnInstalledPackagesByDep(arg))):
            return # Found a match so ignore
        hibeg = self.term.MODE['bold']
        hiend = self.term.MODE['normal']
        if matches.available:
            self.verbose_logger.log(yum.logginglevels.INFO_2,
                _('Package(s) %s%s%s available, but not installed.'),
                                    hibeg, arg, hiend)
            return

        # No package name, so do the maybeYouMeant thing here too
        matches = self.doPackageLists(patterns=[arg], ignore_case=True)
        if not matches.installed and matches.available:
            self.verbose_logger.log(yum.logginglevels.INFO_2,
                _('Package(s) %s%s%s available, but not installed.'),
                                    hibeg, arg, hiend)
            return
        matches = set(map(lambda x: x.name, matches.installed))
        if always_output or matches:
            self.verbose_logger.log(yum.logginglevels.INFO_2,
                                    _('No package %s%s%s available.'),
                                    hibeg, arg, hiend)
        if matches:
            msg = self.fmtKeyValFill(_('  * Maybe you meant: '),
                                     ", ".join(matches))
            self.verbose_logger.log(yum.logginglevels.INFO_2, msg)

    def installPkgs(self, userlist):
        """Attempts to take the user specified list of packages/wildcards
           and install them, or if they are installed, update them to a newer
           version. If a complete version number if specified, attempt to 
           upgrade (or downgrade if they have been removed) them to the
           specified version"""
        # get the list of available packages
        # iterate over the user's list
        # add packages to Transaction holding class if they match.
        # if we've added any packages to the transaction then return 2 and a string
        # if we've hit a snag, return 1 and the failure explanation
        # if we've got nothing to do, return 0 and a 'nothing available to install' string
        
        oldcount = len(self.tsInfo)
        
        done = False
        for arg in userlist:
            if (arg.endswith('.rpm') and (yum.misc.re_remote_url(arg) or
                                          os.path.exists(arg))):
                self.localInstall(filelist=[arg])
                continue # it was something on disk and it ended in rpm 
                         # no matter what we don't go looking at repos
            try:
                self.install(pattern=arg)
            except yum.Errors.InstallError:
                self.verbose_logger.log(yum.logginglevels.INFO_2,
                                        _('No package %s%s%s available.'),
                                        self.term.MODE['bold'], arg,
                                        self.term.MODE['normal'])
                self._maybeYouMeant(arg)
            else:
                done = True
        if len(self.tsInfo) > oldcount:
            return 2, [_('Package(s) to install')]

        if not done:
            return 1, [_('Nothing to do')]
        return 0, [_('Nothing to do')]
        
    def updatePkgs(self, userlist, quiet=0):
        """take user commands and populate transaction wrapper with 
           packages to be updated"""
        
        # if there is no userlist, then do global update below
        # this is probably 90% of the calls
        # if there is a userlist then it's for updating pkgs, not obsoleting
        
        oldcount = len(self.tsInfo)
        if len(userlist) == 0: # simple case - do them all
            self.update()

        else:
            # go through the userlist - look for items that are local rpms. If we find them
            # pass them off to localInstall() and then move on
            localupdates = []
            for item in userlist:
                if (item.endswith('.rpm') and (yum.misc.re_remote_url(item) or
                                               os.path.exists(item))):
                    localupdates.append(item)
            
            if len(localupdates) > 0:
                self.localInstall(filelist=localupdates, updateonly=1)
                for item in localupdates:
                    userlist.remove(item)
                
            for arg in userlist:
                if not self.update(pattern=arg):
                    self._checkMaybeYouMeant(arg)

        if len(self.tsInfo) > oldcount:
            change = len(self.tsInfo) - oldcount
            msg = _('%d packages marked for Update') % change
            return 2, [msg]
        else:
            return 0, [_('No Packages marked for Update')]

    #  Note that we aren't in __init__ yet for a couple of reasons, but we 
    # probably will get there for 3.2.28.
    def distroSyncPkgs(self, userlist):
        """ This does either upgrade/downgrade, depending on if the latest
            installed version is older or newer. We allow "selection" but not
            local packages (use tmprepo, or something). """

        dupdates = []
        ipkgs = {}
        for pkg in sorted(self.rpmdb.returnPackages(patterns=userlist)):
            ipkgs[pkg.name] = pkg

        obsoletes = []
        if self.conf.obsoletes:
            obsoletes = self.up.getObsoletesTuples(newest=1)

        for (obsoleting, installed) in obsoletes:
            if installed[0] not in ipkgs:
                continue
            dupdates.extend(self.update(pkgtup=installed))
        for (obsoleting, installed) in obsoletes:
            if installed[0] not in ipkgs:
                continue
            del ipkgs[installed[0]]

        apkgs = {}
        for pkg in self.pkgSack.returnNewestByName():
            if pkg.name not in ipkgs:
                continue
            apkgs[pkg.name] = pkg

        for ipkgname in ipkgs:
            if ipkgname not in apkgs:
                continue

            ipkg = ipkgs[ipkgname]
            apkg = apkgs[ipkgname]
            if ipkg.verEQ(apkg):
                continue
            if self.allowedMultipleInstalls(apkg):
                found = False
                for napkg in self.rpmdb.searchNames([apkg.name]):
                    if napkg.verEQ(apkg):
                        found = True
                    elif napkg.verGT(apkg):
                        dupdates.extend(self.remove(po=napkg))
                if found:
                    continue
                dupdates.extend(self.install(pattern=apkg.name))
            elif ipkg.verLT(apkg):
                n,a,e,v,r = apkg.pkgtup
                dupdates.extend(self.update(name=n, epoch=e, ver=v, rel=r))
            else:
                n,a,e,v,r = apkg.pkgtup
                dupdates.extend(self.downgrade(name=n, epoch=e, ver=v, rel=r))

        if dupdates:
            msg = _('%d packages marked for Distribution Synchronization') % len(dupdates)
            return 2, [msg]
        else:
            return 0, [_('No Packages marked for Distribution Synchronization')]

    def erasePkgs(self, userlist):
        """take user commands and populate a transaction wrapper with packages
           to be erased/removed"""
        
        oldcount = len(self.tsInfo)
        
        for arg in userlist:
            if not self.remove(pattern=arg):
                self._checkMaybeYouMeant(arg, always_output=False)
        
        if len(self.tsInfo) > oldcount:
            change = len(self.tsInfo) - oldcount
            msg = _('%d packages marked for removal') % change
            return 2, [msg]
        else:
            return 0, [_('No Packages marked for removal')]
    
    def downgradePkgs(self, userlist):
        """Attempts to take the user specified list of packages/wildcards
           and downgrade them. If a complete version number if specified,
           attempt to downgrade them to the specified version"""

        oldcount = len(self.tsInfo)
        
        for arg in userlist:
            if (arg.endswith('.rpm') and (yum.misc.re_remote_url(arg) or
                                          os.path.exists(arg))):
                self.downgradeLocal(arg)
                continue # it was something on disk and it ended in rpm 
                         # no matter what we don't go looking at repos

            try:
                self.downgrade(pattern=arg)
            except yum.Errors.DowngradeError:
                self.verbose_logger.log(yum.logginglevels.INFO_2,
                                        _('No package %s%s%s available.'),
                                        self.term.MODE['bold'], arg,
                                        self.term.MODE['normal'])
                self._maybeYouMeant(arg)
        if len(self.tsInfo) > oldcount:
            return 2, [_('Package(s) to downgrade')]
        return 0, [_('Nothing to do')]
        
    def reinstallPkgs(self, userlist):
        """Attempts to take the user specified list of packages/wildcards
           and reinstall them. """

        oldcount = len(self.tsInfo)

        for arg in userlist:
            if (arg.endswith('.rpm') and (yum.misc.re_remote_url(arg) or
                                          os.path.exists(arg))):
                self.reinstallLocal(arg)
                continue # it was something on disk and it ended in rpm
                         # no matter what we don't go looking at repos

            try:
                self.reinstall(pattern=arg)
            except yum.Errors.ReinstallRemoveError:
                self._checkMaybeYouMeant(arg, always_output=False)
            except yum.Errors.ReinstallInstallError, e:
                ipkg = self.rpmdb.returnPackages(patterns=[arg])[0]
                xmsg = ''
                if 'from_repo' in ipkg.yumdb_info:
                    xmsg = ipkg.yumdb_info.from_repo
                    xmsg = _(' (from %s)') % xmsg
                self.verbose_logger.log(yum.logginglevels.INFO_2,
                                        _('Installed package %s%s%s%s not available.'),
                                        self.term.MODE['bold'], ipkg,
                                        self.term.MODE['normal'], xmsg)
            except yum.Errors.ReinstallError, e:
                assert False, "Shouldn't happen, but just in case"
                self.verbose_logger.log(yum.logginglevels.INFO_2, e)
        if len(self.tsInfo) > oldcount:
            return 2, [_('Package(s) to reinstall')]
        return 0, [_('Nothing to do')]

    def localInstall(self, filelist, updateonly=0):
        """handles installs/updates of rpms provided on the filesystem in a 
           local dir (ie: not from a repo)"""
           
        # read in each package into a YumLocalPackage Object
        # append it to self.localPackages
        # check if it can be installed or updated based on nevra versus rpmdb
        # don't import the repos until we absolutely need them for depsolving

        if len(filelist) == 0:
            return 0, [_('No Packages Provided')]

        installing = False
        for pkg in filelist:
            txmbrs = self.installLocal(pkg, updateonly=updateonly)
            if txmbrs:
                installing = True

        if installing:
            return 2, [_('Package(s) to install')]
        return 0, [_('Nothing to do')]

    def returnPkgLists(self, extcmds, installed_available=False):
        """Returns packages lists based on arguments on the cli.returns a 
           GenericHolder instance with the following lists defined:
           available = list of packageObjects
           installed = list of packageObjects
           updates = tuples of packageObjects (updating, installed)
           extras = list of packageObjects
           obsoletes = tuples of packageObjects (obsoleting, installed)
           recent = list of packageObjects

           installed_available = that the available package list is present
                                 as .hidden_available when doing any of:
                                 all/available/installed
           """
        
        special = ['available', 'installed', 'all', 'extras', 'updates', 'recent',
                   'obsoletes']
        
        pkgnarrow = 'all'
        done_hidden_available = False
        done_hidden_installed = False
        if len(extcmds) > 0:
            if installed_available and extcmds[0] == 'installed':
                done_hidden_available = True
                extcmds.pop(0)
            elif installed_available and extcmds[0] == 'available':
                done_hidden_installed = True
                extcmds.pop(0)
            elif extcmds[0] in special:
                pkgnarrow = extcmds.pop(0)
            
        ypl = self.doPackageLists(pkgnarrow=pkgnarrow, patterns=extcmds,
                                  ignore_case=True)
        if self.conf.showdupesfromrepos:
            ypl.available += ypl.reinstall_available

        if installed_available:
            ypl.hidden_available = ypl.available
            ypl.hidden_installed = ypl.installed
        if done_hidden_available:
            ypl.available = []
        if done_hidden_installed:
            ypl.installed = []
        return ypl

    def search(self, args):
        """cli wrapper method for module search function, searches simple
           text tags in a package object"""
        
        # call the yum module search function with lists of tags to search
        # and what to search for
        # display the list of matches
            
        searchlist = ['name', 'summary', 'description', 'url']
        dups = self.conf.showdupesfromrepos
        args = map(to_unicode, args)
        matching = self.searchGenerator(searchlist, args,
                                        showdups=dups, keys=True)
        
        okeys = set()
        akeys = set()
        for (po, keys, matched_value) in matching:
            if keys != okeys:
                if akeys:
                    print ""
                # Print them in the order they were passed
                used_keys = [arg for arg in args if arg in keys]
                print self.fmtSection(_('Matched: %s') % ", ".join(used_keys))
                okeys = keys
                akeys.update(keys)
            self.matchcallback(po, matched_value, args)

        for arg in args:
            if arg not in akeys:
                self.logger.warning(_('Warning: No matches found for: %s'), arg)

        if not akeys:
            return 0, [_('No Matches found')]
        return 0, matching

    def deplist(self, args):
        """cli wrapper method for findDeps method takes a list of packages and 
            returns a formatted deplist for that package"""

        pkgs = []
        for arg in args:
            if (arg.endswith('.rpm') and (yum.misc.re_remote_url(arg) or
                                          os.path.exists(arg))):
                thispkg = yum.packages.YumUrlPackage(self, self.ts, arg)
                pkgs.append(thispkg)
            else:                
                ematch, match, unmatch = self.pkgSack.matchPackageNames([arg])
                for po in ematch + match:
                    pkgs.append(po)
                
            results = self.findDeps(pkgs)
            self.depListOutput(results)

        return 0, []

    def provides(self, args):
        """use the provides methods in the rpmdb and pkgsack to produce a list 
           of items matching the provides strings. This is a cli wrapper to the 
           module"""
        
        old_sdup = self.conf.showdupesfromrepos
        # For output, as searchPackageProvides() is always in showdups mode
        self.conf.showdupesfromrepos = True
        cb = self.matchcallback_verbose
        matching = self.searchPackageProvides(args, callback=cb,
                                              callback_has_matchfor=True)
        self.conf.showdupesfromrepos = old_sdup
        
        if len(matching) == 0:
            for arg in args:
                if '*' in arg or (arg and arg[0] == '/'):
                    continue
                self.logger.warning(_('Warning: 3.0.x versions of yum would erroneously match against filenames.\n You can use "%s*/%s%s" and/or "%s*bin/%s%s" to get that behaviour'),
                                    self.term.MODE['bold'], arg,
                                    self.term.MODE['normal'],
                                    self.term.MODE['bold'], arg,
                                    self.term.MODE['normal'])
            return 0, ['No Matches found']
        
        return 0, []
    
    def resolveDepCli(self, args):
        """returns a package (one per user arg) that provide the supplied arg"""
        
        for arg in args:
            try:
                pkg = self.returnPackageByDep(arg)
            except yum.Errors.YumBaseError:
                self.logger.critical(_('No Package Found for %s'), arg)
            else:
                msg = '%s:%s-%s-%s.%s' % (pkg.epoch, pkg.name, pkg.version, pkg.release, pkg.arch)
                self.verbose_logger.info(msg)

        return 0, []
    
    def cleanCli(self, userlist):
        hdrcode = pkgcode = xmlcode = dbcode = expccode = 0
        pkgresults = hdrresults = xmlresults = dbresults = expcresults = []
        if 'all' in userlist:
            self.verbose_logger.log(yum.logginglevels.INFO_2,
                _('Cleaning up Everything'))
            pkgcode, pkgresults = self.cleanPackages()
            hdrcode, hdrresults = self.cleanHeaders()
            xmlcode, xmlresults = self.cleanMetadata()
            dbcode, dbresults = self.cleanSqlite()
            rpmcode, rpmresults = self.cleanRpmDB()
            self.plugins.run('clean')
            
            code = hdrcode + pkgcode + xmlcode + dbcode + rpmcode
            results = (hdrresults + pkgresults + xmlresults + dbresults +
                       rpmresults)
            for msg in results:
                self.logger.debug(msg)
            return code, []
            
        if 'headers' in userlist:
            self.logger.debug(_('Cleaning up Headers'))
            hdrcode, hdrresults = self.cleanHeaders()
        if 'packages' in userlist:
            self.logger.debug(_('Cleaning up Packages'))
            pkgcode, pkgresults = self.cleanPackages()
        if 'metadata' in userlist:
            self.logger.debug(_('Cleaning up xml metadata'))
            xmlcode, xmlresults = self.cleanMetadata()
        if 'dbcache' in userlist or 'metadata' in userlist:
            self.logger.debug(_('Cleaning up database cache'))
            dbcode, dbresults =  self.cleanSqlite()
        if 'expire-cache' in userlist or 'metadata' in userlist:
            self.logger.debug(_('Cleaning up expire-cache metadata'))
            expccode, expcresults = self.cleanExpireCache()
        if 'rpmdb' in userlist:
            self.logger.debug(_('Cleaning up cached rpmdb data'))
            expccode, expcresults = self.cleanRpmDB()
        if 'plugins' in userlist:
            self.logger.debug(_('Cleaning up plugins'))
            self.plugins.run('clean')

        code = hdrcode + pkgcode + xmlcode + dbcode + expccode
        results = hdrresults + pkgresults + xmlresults + dbresults + expcresults
        for msg in results:
            self.verbose_logger.log(yum.logginglevels.INFO_2, msg)
        return code, []

    def returnGroupLists(self, userlist):

        uservisible=1
            
        if len(userlist) > 0:
            if userlist[0] == 'hidden':
                uservisible=0
                userlist.pop(0)
        if not userlist:
            userlist = None # Match everything...

        installed, available = self.doGroupLists(uservisible=uservisible,
                                                 patterns=userlist)
        
        if len(installed) > 0:
            self.verbose_logger.log(yum.logginglevels.INFO_2,
                _('Installed Groups:'))
            for group in installed:
                if self.verbose_logger.isEnabledFor(yum.logginglevels.DEBUG_3):
                    self.verbose_logger.log(yum.logginglevels.INFO_2,
                                            '   %s (%s)', group.ui_name,
                                            group.groupid)
                else:
                    self.verbose_logger.log(yum.logginglevels.INFO_2,
                                            '   %s', group.ui_name)
        
        if len(available) > 0:
            self.verbose_logger.log(yum.logginglevels.INFO_2,
                _('Available Groups:'))
            for group in available:
                if self.verbose_logger.isEnabledFor(yum.logginglevels.DEBUG_3):
                    self.verbose_logger.log(yum.logginglevels.INFO_2,
                                            '   %s (%s)', group.ui_name,
                                            group.groupid)
                else:
                    self.verbose_logger.log(yum.logginglevels.INFO_2,
                                            '   %s', group.ui_name)

        return 0, [_('Done')]
    
    def returnGroupInfo(self, userlist):
        """returns complete information on a list of groups"""
        for strng in userlist:
            group_matched = False
            for group in self.comps.return_groups(strng):
                self.displayPkgsInGroups(group)
                group_matched = True

            if not group_matched:
                self.logger.error(_('Warning: Group %s does not exist.'), strng)
        
        return 0, []
        
    def installGroups(self, grouplist):
        """for each group requested do 'selectGroup' on them."""
        
        pkgs_used = []
        
        for group_string in grouplist:
            group_matched = False
            for group in self.comps.return_groups(group_string):
                group_matched = True

            
                try:
                    txmbrs = self.selectGroup(group.groupid)
                except yum.Errors.GroupsError:
                    self.logger.critical(_('Warning: Group %s does not exist.'), group_string)
                    continue
                else:
                    pkgs_used.extend(txmbrs)

            if not group_matched:
                self.logger.error(_('Warning: Group %s does not exist.'), group_string)
                continue
            
        if not pkgs_used:
            return 0, [_('No packages in any requested group available to install or update')]
        else:
            return 2, [_('%d Package(s) to Install') % len(pkgs_used)]

    def removeGroups(self, grouplist):
        """Remove only packages of the named group(s). Do not recurse."""

        pkgs_used = []
        for group_string in grouplist:
            try:
                txmbrs = self.groupRemove(group_string)
            except yum.Errors.GroupsError:
                self.logger.critical(_('No group named %s exists'), group_string)
                continue
            else:
                pkgs_used.extend(txmbrs)
                
        if not pkgs_used:
            return 0, [_('No packages to remove from groups')]
        else:
            return 2, [_('%d Package(s) to remove') % len(pkgs_used)]



    def _promptWanted(self):
        # shortcut for the always-off/always-on options
        if self.conf.assumeyes:
            return False
        if self.conf.alwaysprompt:
            return True
        
        # prompt if:
        #  package was added to fill a dependency
        #  package is being removed
        #  package wasn't explictly given on the command line
        for txmbr in self.tsInfo.getMembers():
            if txmbr.isDep or \
                   txmbr.ts_state == 'e' or \
                   txmbr.name not in self.extcmds:
                return True
        
        # otherwise, don't prompt        
        return False

    def usage(self):
        ''' Print out command line usage '''
        sys.stdout.write(self.optparser.format_help())

    def shellUsage(self):
        ''' Print out the shell usage '''
        sys.stdout.write(self.optparser.get_usage())
    
    def _installable(self, pkg, ematch=False):

        """check if the package is reasonably installable, true/false"""
        
        exactarchlist = self.conf.exactarchlist        
        # we look through each returned possibility and rule out the
        # ones that we obviously can't use
        
        if self.rpmdb.contains(po=pkg):
            self.verbose_logger.log(yum.logginglevels.DEBUG_3,
                _('Package %s is already installed, skipping'), pkg)
            return False
        
        # everything installed that matches the name
        installedByKey = self.rpmdb.searchNevra(name=pkg.name)
        comparable = []
        for instpo in installedByKey:
            if isMultiLibArch(instpo.arch) == isMultiLibArch(pkg.arch):
                comparable.append(instpo)
            else:
                self.verbose_logger.log(yum.logginglevels.DEBUG_3,
                    _('Discarding non-comparable pkg %s.%s'), instpo.name, instpo.arch)
                continue
                
        # go through each package 
        if len(comparable) > 0:
            for instpo in comparable:
                if pkg.verGT(instpo): # we're newer - this is an update, pass to them
                    if instpo.name in exactarchlist:
                        if pkg.arch == instpo.arch:
                            return True
                    else:
                        return True
                        
                elif pkg.verEQ(instpo): # same, ignore
                    return False
                    
                elif pkg.verLT(instpo): # lesser, check if the pkgtup is an exactmatch
                                   # if so then add it to be installed
                                   # if it can be multiply installed
                                   # this is where we could handle setting 
                                   # it to be an 'oldpackage' revert.
                                   
                    if ematch and self.allowedMultipleInstalls(pkg):
                        return True
                        
        else: # we've not got any installed that match n or n+a
            self.verbose_logger.log(yum.logginglevels.DEBUG_1, _('No other %s installed, adding to list for potential install'), pkg.name)
            return True
        
        return False

class YumOptionParser(OptionParser):
    '''Subclass that makes some minor tweaks to make OptionParser do things the
    "yum way".
    '''

    def __init__(self,base, **kwargs):
        # check if this is called with a utils=True/False parameter
        if 'utils' in kwargs:
            self._utils = kwargs['utils']
            del kwargs['utils'] 
        else:
            self._utils = False
        OptionParser.__init__(self, **kwargs)
        self.logger = logging.getLogger("yum.cli")
        self.base = base
        self.plugin_option_group = OptionGroup(self, _("Plugin Options"))
        self.add_option_group(self.plugin_option_group)

        self._addYumBasicOptions()

    def error(self, msg):
        '''This method is overridden so that error output goes to logger. '''
        self.print_usage()
        self.logger.critical(_("Command line error: %s"), msg)
        sys.exit(1)

    def firstParse(self,args):
        # Parse only command line options that affect basic yum setup
        try:
            args = _filtercmdline(
                        ('--noplugins','--version','-q', '-v', "--quiet", "--verbose"), 
                        ('-c', '-d', '-e', '--installroot',
                         '--disableplugin', '--enableplugin', '--releasever'), 
                        args)
        except ValueError, arg:
            self.base.usage()
            print >> sys.stderr, (_("\n\n%s: %s option requires an argument") %
                                  ('Command line error', arg))
            sys.exit(1)
        return self.parse_args(args=args)[0]

    @staticmethod
    def _splitArg(seq):
        """ Split all strings in seq, at "," and whitespace.
            Returns a new list. """
        ret = []
        for arg in seq:
            ret.extend(arg.replace(",", " ").split())
        return ret
        
    def setupYumConfig(self, args=None):
        # Now parse the command line for real
        if not args:
            (opts, cmds) = self.parse_args()
        else:
            (opts, cmds) = self.parse_args(args=args)

        # Let the plugins know what happened on the command line
        self.base.plugins.setCmdLine(opts, cmds)

        try:
            # config file is parsed and moving us forward
            # set some things in it.
                
            # Handle remaining options
            if opts.assumeyes:
                self.base.conf.assumeyes =1

            #  Instead of going cache-only for a non-root user, try to use a
            # user writable cachedir. If that fails fall back to cache-only.
            if opts.cacheonly:
                self.base.conf.cache = 1
            elif not self.base.setCacheDir():
                self.base.conf.cache = 1

            if opts.obsoletes:
                self.base.conf.obsoletes = 1

            if opts.installroot:
                self.base.conf.installroot = opts.installroot
                
            if opts.skipbroken:
                self.base.conf.skip_broken = True

            if opts.showdupesfromrepos:
                self.base.conf.showdupesfromrepos = True

            if opts.color not in (None, 'auto', 'always', 'never',
                                  'tty', 'if-tty', 'yes', 'no', 'on', 'off'):
                raise ValueError, _("--color takes one of: auto, always, never")
            elif opts.color is None:
                if self.base.conf.color != 'auto':
                    self.base.term.reinit(color=self.base.conf.color)
            else:
                _remap = {'tty' : 'auto', 'if-tty' : 'auto',
                          '1' : 'always', 'true' : 'always',
                          'yes' : 'always', 'on' : 'always',
                          '0' : 'always', 'false' : 'always',
                          'no' : 'never', 'off' : 'never'}
                opts.color = _remap.get(opts.color, opts.color)
                if opts.color != 'auto':
                    self.base.term.reinit(color=opts.color)

            if opts.disableexcludes:
                disable_excludes = self._splitArg(opts.disableexcludes)
            else:
                disable_excludes = []
            self.base.conf.disable_excludes = disable_excludes

            for exclude in self._splitArg(opts.exclude):
                try:
                    excludelist = self.base.conf.exclude
                    excludelist.append(exclude)
                    self.base.conf.exclude = excludelist
                except yum.Errors.ConfigError, e:
                    self.logger.critical(e)
                    self.base.usage()
                    sys.exit(1)

            if opts.rpmverbosity is not None:
                self.base.conf.rpmverbosity = opts.rpmverbosity

            # setup the progress bars/callbacks
            self.base.setupProgressCallbacks()
            # setup the callbacks to import gpg pubkeys and confirm them
            self.base.setupKeyImportCallbacks()
                    
            # Process repo enables and disables in order
            for opt, repoexp in opts.repos:
                try:
                    if opt == '--enablerepo':
                        self.base.repos.enableRepo(repoexp)
                    elif opt == '--disablerepo':
                        self.base.repos.disableRepo(repoexp)
                except yum.Errors.ConfigError, e:
                    self.logger.critical(e)
                    self.base.usage()
                    sys.exit(1)

            # make sure the added repos are setup.        
            if len(opts.repos) > 0:
                self.base._getRepos(doSetup=True)

            # Disable all gpg key checking, if requested.
            if opts.nogpgcheck:
                self.base.conf.gpgcheck      = False
                self.base.conf.repo_gpgcheck = False
                for repo in self.base.repos.listEnabled():
                    repo.gpgcheck      = False
                    repo.repo_gpgcheck = False
                            
        except ValueError, e:
            self.logger.critical(_('Options Error: %s'), e)
            self.base.usage()
            sys.exit(1)
         
        return opts, cmds

    def getRoot(self,opts):
        # If the conf file is inside the  installroot - use that.
        # otherwise look for it in the normal root
        if opts.installroot:
            if os.access(opts.installroot+'/'+opts.conffile, os.R_OK):
                opts.conffile = opts.installroot+'/'+opts.conffile
            elif opts.conffile == '/etc/yum/yum.conf':
                # check if /installroot/etc/yum.conf exists.
                if os.access(opts.installroot+'/etc/yum.conf', os.R_OK):
                    opts.conffile = opts.installroot+'/etc/yum.conf'         
            root=opts.installroot
        else:
            root = '/'
        return root

    def _wrapOptParseUsage(self, opt, value, parser, *args, **kwargs):
        self.base.usage()
        self.exit()

    def _addYumBasicOptions(self):
        def repo_optcb(optobj, opt, value, parser):
            '''Callback for the enablerepo and disablerepo option. 
            
            Combines the values given for these options while preserving order
            from command line.
            '''
            dest = eval('parser.values.%s' % optobj.dest)
            dest.append((opt, value))

        if self._utils:
            group = OptionGroup(self, "Yum Base Options")
            self.add_option_group(group)
        else:
            group = self
    
        # Note that we can't use the default action="help" because of the
        # fact that print_help() unconditionally does .encode() ... which is
        # bad on unicode input.
        group.conflict_handler = "resolve"
        group.add_option("-h", "--help", action="callback",
                        callback=self._wrapOptParseUsage, 
                help=_("show this help message and exit"))
        group.conflict_handler = "error"

        group.add_option("-t", "--tolerant", action="store_true",
                help=_("be tolerant of errors"))
        group.add_option("-C", "--cacheonly", dest="cacheonly",
                action="store_true",
                help=_("run entirely from system cache, don't update cache"))
        group.add_option("-c", "--config", dest="conffile",
                default='/etc/yum/yum.conf',
                help=_("config file location"), metavar='[config file]')
        group.add_option("-R", "--randomwait", dest="sleeptime", type='int',
                default=None,
                help=_("maximum command wait time"), metavar='[minutes]')
        group.add_option("-d", "--debuglevel", dest="debuglevel", default=None,
                help=_("debugging output level"), type='int',
                metavar='[debug level]')
        group.add_option("--showduplicates", dest="showdupesfromrepos",
                        action="store_true",
                help=_("show duplicates, in repos, in list/search commands"))
        group.add_option("-e", "--errorlevel", dest="errorlevel", default=None,
                help=_("error output level"), type='int',
                metavar='[error level]')
        group.add_option("", "--rpmverbosity", default=None,
                help=_("debugging output level for rpm"),
                metavar='[debug level name]')
        group.add_option("-q", "--quiet", dest="quiet", action="store_true",
                        help=_("quiet operation"))
        group.add_option("-v", "--verbose", dest="verbose", action="store_true",
                        help=_("verbose operation"))
        group.add_option("-y", "--assumeyes", dest="assumeyes",
                action="store_true", help=_("answer yes for all questions"))
        group.add_option("--version", action="store_true", 
                help=_("show Yum version and exit"))
        group.add_option("--installroot", help=_("set install root"), 
                metavar='[path]')
        group.add_option("--enablerepo", action='callback',
                type='string', callback=repo_optcb, dest='repos', default=[],
                help=_("enable one or more repositories (wildcards allowed)"),
                metavar='[repo]')
        group.add_option("--disablerepo", action='callback',
                type='string', callback=repo_optcb, dest='repos', default=[],
                help=_("disable one or more repositories (wildcards allowed)"),
                metavar='[repo]')
        group.add_option("-x", "--exclude", default=[], action="append",
                help=_("exclude package(s) by name or glob"), metavar='[package]')
        group.add_option("", "--disableexcludes", default=[], action="append",
                help=_("disable exclude from main, for a repo or for everything"),
                        metavar='[repo]')
        group.add_option("--obsoletes", action="store_true", 
                help=_("enable obsoletes processing during updates"))
        group.add_option("--noplugins", action="store_true", 
                help=_("disable Yum plugins"))
        group.add_option("--nogpgcheck", action="store_true",
                help=_("disable gpg signature checking"))
        group.add_option("", "--disableplugin", dest="disableplugins", default=[], 
                action="append", help=_("disable plugins by name"),
                metavar='[plugin]')
        group.add_option("", "--enableplugin", dest="enableplugins", default=[], 
                action="append", help=_("enable plugins by name"),
                metavar='[plugin]')
        group.add_option("--skip-broken", action="store_true", dest="skipbroken",
                help=_("skip packages with depsolving problems"))
        group.add_option("", "--color", dest="color", default=None, 
                help=_("control whether color is used"))
        group.add_option("", "--releasever", dest="releasever", default=None, 
                help=_("set value of $releasever in yum config and repo files"))


        
def _filtercmdline(novalopts, valopts, args):
    '''Keep only specific options from the command line argument list

    This function allows us to peek at specific command line options when using
    the optparse module. This is useful when some options affect what other
    options should be available.

    @param novalopts: A sequence of options to keep that don't take an argument.
    @param valopts: A sequence of options to keep that take a single argument.
    @param args: The command line arguments to parse (as per sys.argv[:1]
    @return: A list of strings containing the filtered version of args.

    Will raise ValueError if there was a problem parsing the command line.
    '''
    out = []
    args = list(args)       # Make a copy because this func is destructive

    while len(args) > 0:
        a = args.pop(0)
        if '=' in a:
            opt, _ = a.split('=', 1)
            if opt in valopts:
                out.append(a)

        elif a in novalopts:
            out.append(a)

        elif a in valopts:
            if len(args) < 1:
                raise ValueError, a
            next = args.pop(0)
            if next[0] == '-':
                raise ValueError, a

            out.extend([a, next])
       
        else:
            # Check for single letter options that take a value, where the
            # value is right up against the option
            for opt in valopts:
                if len(opt) == 2 and a.startswith(opt):
                    out.append(a)

    return out

