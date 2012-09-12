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
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
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
from optparse import OptionParser,OptionGroup,SUPPRESS_HELP
import rpm

from weakref import proxy as weakref

import output
import shell
import dnf.yum
import dnf.yum.Errors
import dnf.yum.logginglevels
import dnf.yum.misc
from dnf.yum.parser import varReplace
import dnf.yum.plugins
from dnf.rpmUtils.arch import isMultiLibArch
from dnf.yum import _, P_
from dnf.yum.rpmtrans import RPMTransaction
import signal
import yumcommands
import dnf.queries
import dnf.const

from dnf.yum.i18n import to_unicode, to_utf8, exception2msg

#  This is for yum-utils/yumdownloader in RHEL-5, where it isn't importing this
# directly but did do "from cli import *", and we did have this in 3.2.22. I
# just _love_ how python re-exports these by default.
# pylint: disable-msg=W0611
from dnf.yum.packages import parsePackages
# pylint: enable-msg=W0611

def sigquit(signum, frame):
    """SIGQUIT handler for the yum cli.  This function will print an
    error message and exit the program.

    :param signum: unused
    :param frame: unused
    """
    print >> sys.stderr, "Quit signal sent - exiting immediately"
    sys.exit(1)

class CliError(dnf.yum.Errors.YumBaseError):
    """Command line interface related Exception."""

    def __init__(self, args=''):
        dnf.yum.Errors.YumBaseError.__init__(self)
        self.args = args

class YumBaseCli(dnf.yum.YumBase, output.YumOutput):
    """This is the base class for yum cli."""

    def __init__(self):
        # handle sigquit early on
        signal.signal(signal.SIGQUIT, sigquit)
        dnf.yum.YumBase.__init__(self)
        output.YumOutput.__init__(self)
        logging.basicConfig()
        self.logger = logging.getLogger("yum.cli")
        self.verbose_logger = logging.getLogger("yum.verbose.cli")
        self.yum_cli_commands = {}
        self.use_txmbr_in_callback = True
        # :hawkey -- commented out are not yet supported in dnf
        self.registerCommand(yumcommands.InstallCommand())
        self.registerCommand(yumcommands.UpdateCommand())
        self.registerCommand(yumcommands.InfoCommand())
        self.registerCommand(yumcommands.ListCommand())
        self.registerCommand(yumcommands.EraseCommand())
        # self.registerCommand(yumcommands.GroupsCommand())
        self.registerCommand(yumcommands.MakeCacheCommand())
        # self.registerCommand(yumcommands.CleanCommand())
        self.registerCommand(yumcommands.ProvidesCommand())
        # self.registerCommand(yumcommands.CheckUpdateCommand())
        # self.registerCommand(yumcommands.SearchCommand())
        # self.registerCommand(yumcommands.UpgradeCommand())
        # self.registerCommand(yumcommands.ResolveDepCommand())
        # self.registerCommand(yumcommands.ShellCommand())
        # self.registerCommand(yumcommands.DepListCommand())
        self.registerCommand(yumcommands.RepoListCommand())
        self.registerCommand(yumcommands.HelpCommand())
        # self.registerCommand(yumcommands.ReInstallCommand())
        self.registerCommand(yumcommands.DowngradeCommand())
        # self.registerCommand(yumcommands.VersionCommand())
        self.registerCommand(yumcommands.HistoryCommand())
        # self.registerCommand(yumcommands.CheckRpmdbCommand())
        # self.registerCommand(yumcommands.DistroSyncCommand())
        # self.registerCommand(yumcommands.LoadTransactionCommand())

    def registerCommand(self, command):
        """Register a :class:`yumcommands.YumCommand` so that it can be called by
        any of the names returned by its
        :func:`yumcommands.YumCommand.getNames` method.

        :param command: the :class:`yumcommands.YumCommand` to register
        """
        for name in command.getNames():
            if name in self.yum_cli_commands:
                raise dnf.yum.Errors.ConfigError(_('Command "%s" already defined') % name)
            self.yum_cli_commands[name] = command

    def doRepoSetup(self, thisrepo=None, dosack=1):
        """Grab the repomd.xml for each enabled and set up the basics
        of the repository.

        :param thisrepo: the repository to set up
        :param dosack: whether to get the repo sack
        """
        if self._repos and thisrepo is None:
            return self._repos

        if not thisrepo:
            self.verbose_logger.log(dnf.yum.logginglevels.INFO_2,
                _('Setting up repositories'))

        # Call parent class to do the bulk of work
        # (this also ensures that reposetup plugin hook is called)
        if thisrepo:
            dnf.yum.YumBase._getRepos(self, thisrepo=thisrepo, doSetup=True)
        else:
            dnf.yum.YumBase._getRepos(self, thisrepo=thisrepo)

        if dosack: # so we can make the dirs and grab the repomd.xml but not import the md
            self.verbose_logger.log(dnf.yum.logginglevels.INFO_2,
                _('Reading repository metadata in from local files'))
            self._getSacks(thisrepo=thisrepo)

        return self._repos

    def _makeUsage(self):
        """
        Format an attractive usage string for yum, listing subcommand
        names and summary usages.
        """
        name = dnf.const.PROGRAM_NAME
        usage = '%s [options] COMMAND\n\nList of Commands:\n\n' % name
        commands = dnf.yum.misc.unique([x for x in self.yum_cli_commands.values()
                                    if not (hasattr(x, 'hidden') and x.hidden)])
        commands.sort(key=lambda x: x.getNames()[0])
        for command in commands:
            # XXX Remove this when getSummary is common in plugins
            try:
                summary = command.getSummary()
                usage += "%-14s %s\n" % (command.getNames()[0], summary)
            except (AttributeError, NotImplementedError):
                usage += "%s\n" % command.getNames()[0]

        return usage

    def _parseSetOpts(self, setopts):
        """parse the setopts list handed to us and saves the results as
           repo_setopts and main_setopts in the yumbase object"""

        repoopts = {}
        mainopts = dnf.yum.misc.GenericHolder()
        mainopts.items = []

        bad_setopt_tm = []
        bad_setopt_ne = []

        for item in setopts:
            vals = item.split('=')
            if len(vals) > 2:
                bad_setopt_tm.append(item)
                continue
            if len(vals) < 2:
                bad_setopt_ne.append(item)
                continue
            k,v = vals
            period = k.find('.')
            if period != -1:
                repo = k[:period]
                k = k[period+1:]
                if repo not in repoopts:
                    repoopts[repo] = dnf.yum.misc.GenericHolder()
                    repoopts[repo].items = []
                setattr(repoopts[repo], k, v)
                repoopts[repo].items.append(k)
            else:
                setattr(mainopts, k, v)
                mainopts.items.append(k)

        self.main_setopts = mainopts
        self.repo_setopts = repoopts

        return bad_setopt_tm, bad_setopt_ne

    def getOptionsConfig(self, args):
        """Parse command line arguments, and set up :attr:`self.conf` and
        :attr:`self.cmds`, as well as logger objects in base instance.

        :param args: a list of command line arguments
        """
        self.optparser = YumOptionParser(base=self, usage=self._makeUsage())

        # Parse only command line options that affect basic yum setup
        opts = self.optparser.firstParse(args)

        # Just print out the version if that's what the user wanted
        if opts.version:
            print dnf.const.VERSION
            opts.quiet = True
            opts.verbose = False

        # go through all the setopts and set the global ones
        bad_setopt_tm, bad_setopt_ne = self._parseSetOpts(opts.setopts)

        if self.main_setopts:
            for opt in self.main_setopts.items:
                setattr(opts, opt, getattr(self.main_setopts, opt))

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
            pc.plugin_types = (dnf.yum.plugins.TYPE_CORE,
                               dnf.yum.plugins.TYPE_INTERACTIVE)
            pc.optparser = self.optparser
            pc.debuglevel = opts.debuglevel
            pc.errorlevel = opts.errorlevel
            pc.disabled_plugins = self.optparser._splitArg(opts.disableplugins)
            pc.enabled_plugins  = self.optparser._splitArg(opts.enableplugins)
            pc.releasever = opts.releasever
            self.conf

            for item in  bad_setopt_tm:
                msg = "Setopt argument has multiple values: %s"
                self.logger.warning(msg % item)
            for item in  bad_setopt_ne:
                msg = "Setopt argument has no value: %s"
                self.logger.warning(msg % item)
            # now set  all the non-first-start opts from main from our setopts
            if self.main_setopts:
                for opt in self.main_setopts.items:
                    if not hasattr(self.conf, opt):
                        msg ="Main config did not have a %s attr. before setopt"
                        self.logger.warning(msg % opt)
                    setattr(self.conf, opt, getattr(self.main_setopts, opt))

        except dnf.yum.Errors.ConfigError, e:
            self.logger.critical(_('Config Error: %s'), e)
            sys.exit(1)
        except IOError, e:
            e = '%s: %s' % (to_unicode(e.args[1]), repr(e.filename))
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
            opts.quiet = True
            opts.verbose = False

        #  Check that firstParse didn't miss anything, and warn the user if it
        # did ... because this is really magic, and unexpected.
        if opts.quiet:
            opts.debuglevel = 0
        if opts.verbose:
            opts.debuglevel = opts.errorlevel = 6
        if opts.debuglevel != pc.debuglevel or opts.errorlevel != pc.errorlevel:
            self.logger.warning("Ignored option -q, -v, -d or -e (probably due to merging: -yq != -y -q)")
        #  getRoot() changes it, but then setupYumConfig() changes it back. So
        # don't test for this, if we are using --installroot.
        if root == '/' and opts.conffile != pc.fn:
            self.logger.warning("Ignored option -c (probably due to merging -yc != -y -c)")

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
        self.cmdstring = dnf.const.PROGRAM_NAME + ' '
        for arg in self.args:
            self.cmdstring += '%s ' % arg

        # configuration has been collected, accumulate it into sensible form
        self.cache_c.prefix = self.conf.cachedir
        self.cache_c.suffix = varReplace(dnf.const.CACHEDIR_SUFFIX,
                                         self.conf.yumvar)
        del self.conf.cachedir # ensure access to the value is done via cache_c

        try:
            self.parseCommands() # before we return check over the base command + args
                                 # make sure they match/make sense
        except CliError:
            sys.exit(1)

        # run the sleep - if it's unchanged then it won't matter
        time.sleep(sleeptime)

    def parseCommands(self):
        """Read :attr:`self.cmds` and parse them out to make sure that
        the requested base command and argument makes any sense at
        all.  This function will also set :attr:`self.basecmd` and
        :attr:`self.extcmds`.
        """
        self.verbose_logger.debug('dnf version: %s', dnf.const.VERSION)
        self.verbose_logger.log(dnf.yum.logginglevels.DEBUG_4,
                                'COMMAND: %s', self.cmdstring)
        self.verbose_logger.log(dnf.yum.logginglevels.DEBUG_4,
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
            self.verbose_logger.log(dnf.yum.logginglevels.DEBUG_4,
                                    'Ext Commands:\n')
            for arg in self.extcmds:
                self.verbose_logger.log(dnf.yum.logginglevels.DEBUG_4, '   %s', arg)

        if self.basecmd not in self.yum_cli_commands:
            self.logger.critical(_('No such command: %s. Please use %s --help'),
                                  self.basecmd, sys.argv[0])
            raise CliError

        self.yum_cli_commands[self.basecmd].doCheck(self, self.basecmd, self.extcmds)

    def _shell_history_write(self):
        if not hasattr(self, '_shell_history_cmds'):
            return
        if not self._shell_history_cmds:
            return

        data = self._shell_history_cmds
        # Turn: [["a", "b"], ["c", "d"]] => "a b\nc d\n"
        data = [" ".join(cmds) for cmds in data]
        data.append('')
        data = "\n".join(data)
        self.history.write_addon_data('shell-cmds', data)

    def doShell(self):
        """Run a shell-like interface for yum commands.

        :return: a tuple containing the shell result number, and the
           shell result messages
        """

        yumshell = shell.YumShell(base=self)

        # We share this array...
        self._shell_history_cmds = yumshell._shell_history_cmds

        if len(self.extcmds) == 0:
            yumshell.cmdloop()
        else:
            yumshell.script()

        del self._shell_history_cmds

        return yumshell.result, yumshell.resultmsgs

    def errorSummary(self, errstring):
        """Parse the error string for 'interesting' errors which can
        be grouped, such as disk space issues.

        :param errstring: the error string
        :return: a string containing a summary of the errors
        """
        summary = ''
        # do disk space report first
        p = re.compile('needs (\d+)MB on the (\S+) filesystem')
        disk = {}
        for m in p.finditer(errstring):
            if m.group(2) not in disk:
                disk[m.group(2)] = int(m.group(1))
            if disk[m.group(2)] < int(m.group(1)):
                disk[m.group(2)] = int(m.group(1))

        if disk:
            summary += _('Disk Requirements:\n')
            for k in disk:
                summary += P_('  At least %dMB more space needed on the %s filesystem.\n', '  At least %dMB more space needed on the %s filesystem.\n', disk[k]) % (disk[k], k)

        # TODO: simplify the dependency errors?

        # Fixup the summary
        summary = _('Error Summary\n-------------\n') + summary

        return summary


    def doCommands(self):
        """Call the base command, and pass it the extended commands or
           arguments.

        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        return self.yum_cli_commands[self.basecmd].doCommand(self, self.basecmd, self.extcmds)

    def doTransaction(self):
        """Take care of package downloading, checking, user
        confirmation and actually running the transaction.

        :return: a numeric return code, and optionally a list of
           errors.  A negative return code indicates that errors
           occurred in the pre-transaction checks
        """
        # just make sure there's not, well, nothing to do
        if len(self.tsInfo) == 0:
            self.verbose_logger.info(_('Trying to run the transaction but nothing to do. Exiting.'))
            return -1

        # NOTE: In theory we can skip this in -q -y mode, for a slight perf.
        #       gain. But it's probably doom to have a different code path.
        lsts = self.listTransaction()
        if self.verbose_logger.isEnabledFor(dnf.yum.logginglevels.INFO_1):
            self.verbose_logger.log(dnf.yum.logginglevels.INFO_1, lsts)
        elif self.conf.assumeno or not self.conf.assumeyes:
            #  If we are in quiet, and assumeyes isn't on we want to output
            # at least the transaction list anyway.
            self.logger.warn(lsts)

        # Check which packages have to be downloaded
        downloadpkgs = []
        rmpkgs = []
        stuff_to_download = False
        install_only = True
        for txmbr in self.tsInfo.getMembers():
            if txmbr.ts_state not in ('i', 'u'):
                install_only = False
                po = txmbr.po
                if po:
                    rmpkgs.append(po)
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
        if not stuff_to_download:
            self.reportRemoveSize(rmpkgs)
        else:
            self.reportDownloadSize(downloadpkgs, install_only)

        # confirm with user
        if self._promptWanted():
            if self.conf.assumeno or not self.userconfirm():
                self.verbose_logger.info(_('Exiting on user Command'))
                return -1

        self.verbose_logger.log(dnf.yum.logginglevels.INFO_2,
            _('Downloading Packages:'))
        problems = self.downloadPkgs(downloadpkgs, callback_total=self.download_callback_total_cb)

        if len(problems) > 0:
            errstring = ''
            errstring += _('Error Downloading Packages:\n')
            for key in problems:
                errors = dnf.yum.misc.unique(problems[key])
                for error in errors:
                    errstring += '  %s: %s\n' % (key, error)
            raise dnf.yum.Errors.YumBaseError, errstring

        # Check GPG signatures
        if self.gpgsigcheck(downloadpkgs) != 0:
            return -1

        self.initActionTs()
        # save our dsCallback out
        dscb = self.dsCallback
        self.dsCallback = None # dumb, dumb dumb dumb!
        self.populateTs(keepold=0) # sigh

        rcd_st = time.time()
        self.verbose_logger.log(dnf.yum.logginglevels.INFO_2,
             _('Running Transaction Check'))
        msgs = self._run_rpm_check()
        if msgs:
            rpmlib_only = True
            for msg in msgs:
                if msg.startswith('rpmlib('):
                    continue
                rpmlib_only = False
            if rpmlib_only:
                print _("ERROR You need to update rpm to handle:")
            else:
                print _('ERROR with transaction check vs depsolve:')

            for msg in msgs:
                print to_utf8(msg)

            if rpmlib_only:
                return 1, [_('RPM needs to be updated')]
            return 1, [_('Please report this error in %s') % self.conf.bugtracker_url]

        self.verbose_logger.debug('Transaction Check time: %0.3f' % (time.time() - rcd_st))

        tt_st = time.time()
        self.verbose_logger.log(dnf.yum.logginglevels.INFO_2,
            _('Running Transaction Test'))
        if not self.conf.diskspacecheck:
            self.tsInfo.probFilterFlags.append(rpm.RPMPROB_FILTER_DISKSPACE)

        self.ts.order() # order the transaction
        self.ts.clean() # release memory not needed beyond this point

        testcb = RPMTransaction(self, test=True)
        tserrors = self.ts.test(testcb)
        del testcb

        if len(tserrors) > 0:
            errstring = _('Transaction Check Error:\n')
            for descr in tserrors:
                errstring += '  %s\n' % to_unicode(descr)

            raise dnf.yum.Errors.YumBaseError, errstring + '\n' + \
                 self.errorSummary(errstring)
        self.verbose_logger.log(dnf.yum.logginglevels.INFO_2,
             _('Transaction Test Succeeded'))

        self.verbose_logger.debug('Transaction Test time: %0.3f' % (time.time() - tt_st))

        # unset the sigquit handler
        signal.signal(signal.SIGQUIT, signal.SIG_DFL)

        ts_st = time.time()

        #  Reinstalls broke in: 7115478c527415cb3c8317456cdf50024de89a94 ...
        # I assume there's a "better" fix, but this fixes reinstalls and lets
        # other options continue as is (and they seem to work).
        have_reinstalls = False
        for txmbr in self.tsInfo.getMembers():
            if txmbr.reinstall:
                have_reinstalls = True
                break
        if have_reinstalls:
            self.initActionTs() # make a new, blank ts to populate
            self.populateTs(keepold=0) # populate the ts
            self.ts.check() #required for ordering
            self.ts.order() # order
            self.ts.clean() # release memory not needed beyond this point

        # put back our depcheck callback
        self.dsCallback = dscb
        # setup our rpm ts callback
        cb = RPMTransaction(self,
                            display=output.YumCliRPMCallBack(weakref(self)))
        if self.conf.debuglevel < 2:
            cb.display.output = False

        self.verbose_logger.log(dnf.yum.logginglevels.INFO_2, _('Running Transaction'))
        resultobject = self.runTransaction(cb=cb)

        self.verbose_logger.debug('Transaction time: %0.3f' % (time.time() - ts_st))
        # close things
        self.verbose_logger.log(dnf.yum.logginglevels.INFO_1,
            self.postTransactionOutput())

        # put back the sigquit handler
        signal.signal(signal.SIGQUIT, sigquit)

        return resultobject.return_code

    def gpgsigcheck(self, pkgs):
        """Perform GPG signature verification on the given packages,
        installing keys if possible.

        :param pkgs: a list of package objects to verify the GPG
           signatures of
        :return: non-zero if execution should stop due to an error
        :raises: Will raise :class:`YumBaseError` if there's a problem
        """
        for po in pkgs:
            result, errmsg = self.sigCheckPkg(po)

            if result == 0:
                # Verified ok, or verify not req'd
                continue

            elif result == 1:
                ay = self.conf.assumeyes and not self.conf.assumeno
                if not sys.stdin.isatty() and not ay:
                    raise dnf.yum.Errors.YumBaseError, \
                            _('Refusing to automatically import keys when running ' \
                            'unattended.\nUse "-y" to override.')

                # the callback here expects to be able to take options which
                # userconfirm really doesn't... so fake it
                self.getKeyForPackage(po, lambda x, y, z: self.userconfirm())

            else:
                # Fatal error
                raise dnf.yum.Errors.YumBaseError, errmsg

        return 0

    def _maybeYouMeant(self, arg):
        """ If install argument doesn't match with case, tell the user. """
        matches = self.doPackageLists(patterns=[arg], ignore_case=True)
        matches = matches.installed + matches.available
        matches = set(map(lambda x: x.name, matches))
        if matches:
            msg = self.fmtKeyValFill(_('  * Maybe you meant: '),
                                     ", ".join(matches))
            self.verbose_logger.log(dnf.yum.logginglevels.INFO_2, to_unicode(msg))

    def _checkMaybeYouMeant(self, arg, always_output=True, rpmdb_only=False):
        """ If the update/remove argument doesn't match with case, or due
            to not being installed, tell the user. """
        # always_output is a wart due to update/remove not producing the
        # same output.
        # if it is a grouppattern then none of this is going to make any sense
        # skip it.
        if not arg or arg[0] == '@':
            return

        pkgnarrow='all'
        if rpmdb_only:
            pkgnarrow='installed'

        matches = self.doPackageLists(pkgnarrow=pkgnarrow, patterns=[arg], ignore_case=False)
        if (matches.installed or (not matches.available and
                                  self.returnInstalledPackagesByDep(arg))):
            return # Found a match so ignore
        hibeg = self.term.MODE['bold']
        hiend = self.term.MODE['normal']
        if matches.available:
            self.verbose_logger.log(dnf.yum.logginglevels.INFO_2,
                _('Package(s) %s%s%s available, but not installed.'),
                                    hibeg, arg, hiend)
            return

        # No package name, so do the maybeYouMeant thing here too
        matches = self.doPackageLists(pkgnarrow=pkgnarrow, patterns=[arg], ignore_case=True)
        if not matches.installed and matches.available:
            self.verbose_logger.log(dnf.yum.logginglevels.INFO_2,
                _('Package(s) %s%s%s available, but not installed.'),
                                    hibeg, arg, hiend)
            return
        matches = set(map(lambda x: x.name, matches.installed))
        if always_output or matches:
            self.verbose_logger.log(dnf.yum.logginglevels.INFO_2,
                                    _('No package %s%s%s available.'),
                                    hibeg, arg, hiend)
        if matches:
            msg = self.fmtKeyValFill(_('  * Maybe you meant: '),
                                     ", ".join(matches))
            self.verbose_logger.log(dnf.yum.logginglevels.INFO_2, msg)

    def _install_upgraded_requires(self, txmbrs):
        """Go through the given txmbrs, and for any to be installed packages
        look for their installed deps. and try to upgrade them, if the
        configuration is set. Returning any new transaction members to be
        isntalled.

        :param txmbrs: a list of :class:`dnf.yum.transactioninfo.TransactionMember` objects
        :return: a list of :class:`dnf.yum.transactioninfo.TransactionMember` objects
        """

        return [] # :hawkey

        if not self.conf.upgrade_requirements_on_install:
            return []

        ret = []
        done = set()
        def _pkg2ups(pkg, reqpo=None):
            if pkg.name in done:
                return []
            if reqpo is None:
                reqpo = pkg

            done.add(pkg.name)

            uret = []
            for req in pkg.requires:
                for npkg in self.returnInstalledPackagesByDep(req):
                    if npkg.name in done:
                        continue
                    uret += self.update(name=npkg.name, requiringPo=reqpo)
                    uret += _pkg2ups(npkg, reqpo=reqpo)
            return uret

        for txmbr in txmbrs:
            for rtxmbr, T in txmbr.relatedto:
                ret += _pkg2ups(rtxmbr)
            ret += _pkg2ups(txmbr.po)

        return ret

    def installPkgs(self, userlist):
        """Attempt to take the user specified list of packages or
        wildcards and install them, or if they are installed, update
        them to a newer version. If a complete version number is
        specified, attempt to upgrade (or downgrade if they have been
        removed) them to the specified version.

        :param userlist: a list of names or wildcards specifying
           packages to install
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        # get the list of available packages
        # iterate over the user's list
        # add packages to Transaction holding class if they match.
        # if we've added any packages to the transaction then return 2 and a string
        # if we've hit a snag, return 1 and the failure explanation
        # if we've got nothing to do, return 0 and a 'nothing available to install' string

        oldcount = len(self.tsInfo)

        done = False
        for arg in userlist:
            if (arg.endswith('.rpm') and (dnf.yum.misc.re_remote_url(arg) or
                                          os.path.exists(arg))):
                txmbrs = self.install_local(arg)
                self._install_upgraded_requires(txmbrs)
                continue # it was something on disk and it ended in rpm
                         # no matter what we don't go looking at repos
            try:
                self.install(pattern=arg)
            except dnf.yum.Errors.InstallError:
                self.verbose_logger.log(dnf.yum.logginglevels.INFO_2,
                                        _('No package %s%s%s available.'),
                                        self.term.MODE['bold'], arg,
                                        self.term.MODE['normal'])
                self._maybeYouMeant(arg)
            else:
                done = True
                self._install_upgraded_requires([])
        if len(self.tsInfo) > oldcount:
            change = len(self.tsInfo) - oldcount
            return 2, [P_('%d package to install', '%d packages to install', change) % change]

        if not done:
            return 1, [_('Nothing to do')]
        return 0, [_('Nothing to do')]

    def updatePkgs(self, userlist, quiet=0, update_to=False):
        """Take user commands and populate transaction wrapper with
        packages to be updated.

        :param userlist: a list of names or wildcards specifying
           packages to update.  If *userlist* is an empty list, yum
           will perform a global update
        :param quiet: unused
        :param update_to: if *update_to* is True, the update will only
           be run if it will update the given package to the given
           version.  For example, if the package foo-1-2 is installed,
           updatePkgs(["foo-1-2], update_to=False) will work
           identically to updatePkgs(["foo"]), but
           updatePkgs(["foo-1-2"], update_to=True) will do nothing
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        # if there is no userlist, then do global update below
        # this is probably 90% of the calls
        # if there is a userlist then it's for updating pkgs, not obsoleting

        oldcount = len(self.tsInfo)
        if len(userlist) == 0: # simple case - do them all
            self.update()

        else:
            # go through the userlist - look for items that are local rpms. If we find them
            # pass them off to installLocal() and then move on
            for item in userlist:
                if (item.endswith('.rpm') and (dnf.yum.misc.re_remote_url(item) or
                                               os.path.exists(item))):
                    txmbrs = self.update_local(item)
                    self._install_upgraded_requires(txmbrs)
                    continue

                txmbrs = self.update(pattern=item, update_to=update_to)
                self._install_upgraded_requires(txmbrs)
                if not txmbrs:
                    self._checkMaybeYouMeant(item)

        if len(self.tsInfo) > oldcount:
            change = len(self.tsInfo) - oldcount
            return 2, [P_('%d package marked for Update', '%d packages marked for Update', change) % change]
        else:
            return 0, [_('No Packages marked for Update')]

    #  Note that we aren't in __init__ yet for a couple of reasons, but we
    # probably will get there for 3.2.28.
    def distroSyncPkgs(self, userlist):
        """Upgrade or downgrade packages to match the latest versions
        available in the enabled repositories.

        :param userlist: list of names or wildcards specifying
           packages to synchronize with the repositories.  If the
           first string in *userlist* is "full", packages will also be
           reinstalled if their checksums do not match the checksums
           in the repositories.  If *userlist* is an empty list or
           only contains "full", every installed package will be
           synchronized
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """

        level = 'diff'
        if userlist and userlist[0] in ('full', 'diff', 'different'):
            level = userlist[0]
            userlist = userlist[1:]
            if level == 'different':
                level = 'diff'

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
        pkgs = []
        if ipkgs:
            try:
                pkgs = self.pkgSack.returnNewestByName(patterns=ipkgs.keys())
            except dnf.yum.Errors.PackageSackError:
                pkgs = []

        for pkg in pkgs:
            if pkg.name not in ipkgs:
                continue
            apkgs[pkg.name] = pkg

        for ipkgname in ipkgs:
            if ipkgname not in apkgs:
                continue

            ipkg = ipkgs[ipkgname]
            apkg = apkgs[ipkgname]
            if ipkg.verEQ(apkg): # Latest installed == Latest avail.
                if level == 'diff':
                    continue

                # level == full: do reinstalls if checksum doesn't match.
                #                do removals, if older installed versions.
                for napkg in self.rpmdb.searchNames([ipkgname]):
                    if (not self.allowedMultipleInstalls(apkg) and
                        not napkg.verEQ(ipkg)):
                        dupdates.extend(self.remove(po=napkg))
                        continue

                    nayi = napkg.yumdb_info
                    found = False
                    for apkg in self.pkgSack.searchPkgTuple(napkg.pkgtup):
                        if ('checksum_type' in nayi and
                            'checksum_data' in nayi and
                            nayi.checksum_type == apkg.checksum_type and
                            nayi.checksum_data == apkg.pkgId):
                            found = True
                            break
                    if found:
                        continue
                    dupdates.extend(self.reinstall(pkgtup=napkg.pkgtup))
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
            return 2, [P_('%d package marked for Distribution Synchronization', '%d packages marked for Distribution Synchronization', len(dupdates)) % len(dupdates)]
        else:
            return 0, [_('No Packages marked for Distribution Synchronization')]

    def erasePkgs(self, userlist):
        """Take user commands and populate a transaction wrapper with
        packages to be erased.

        :param userlist: a list of names or wildcards specifying
           packages to erase
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """

        all_rms = []
        for arg in userlist:
            rms = self.remove(pattern=arg)
            if not rms:
                self._checkMaybeYouMeant(arg, always_output=False, rpmdb_only=True)
            all_rms.extend(rms)

        if all_rms:
            return 2, [P_('%d package marked for removal', '%d packages marked for removal', len(all_rms)) % len(all_rms)]
        else:
            return 0, [_('No Packages marked for removal')]

    def downgradePkgs(self, userlist):
        """Attempt to take the user specified list of packages or
        wildcards and downgrade them. If a complete version number if
        specified, attempt to downgrade them to the specified version

        :param userlist: a list of names or wildcards specifying
           packages to downgrade
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """

        oldcount = len(self.tsInfo)

        for arg in userlist:
            if (arg.endswith('.rpm') and (dnf.yum.misc.re_remote_url(arg) or
                                          os.path.exists(arg))):
                self.downgrade_local(arg)
                continue # it was something on disk and it ended in rpm
                         # no matter what we don't go looking at repos

            try:
                self.downgrade(pattern=arg)
            except dnf.yum.Errors.DowngradeError:
                self.verbose_logger.log(dnf.yum.logginglevels.INFO_2,
                                        _('No package %s%s%s available.'),
                                        self.term.MODE['bold'], arg,
                                        self.term.MODE['normal'])
                self._maybeYouMeant(arg)
        if len(self.tsInfo) > oldcount:
            change = len(self.tsInfo) - oldcount
            return 2, [P_('%d package to downgrade', '%d packages to downgrade', change) % change]
        return 0, [_('Nothing to do')]

    def reinstallPkgs(self, userlist):
        """Attempt to take the user specified list of packages or
        wildcards and reinstall them.

        :param userlist: a list of names or wildcards specifying
           packages to reinstall
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """

        oldcount = len(self.tsInfo)

        for arg in userlist:
            if (arg.endswith('.rpm') and (dnf.yum.misc.re_remote_url(arg) or
                                          os.path.exists(arg))):
                txmbrs = self.reinstallLocal(arg)
                self._install_upgraded_requires(txmbrs)
                continue # it was something on disk and it ended in rpm
                         # no matter what we don't go looking at repos

            try:
                txmbrs = self.reinstall(pattern=arg)
            except dnf.yum.Errors.ReinstallRemoveError:
                self._checkMaybeYouMeant(arg, always_output=False)
            except dnf.yum.Errors.ReinstallInstallError, e:
                for ipkg in e.failed_pkgs:
                    xmsg = ''
                    if 'from_repo' in ipkg.yumdb_info:
                        xmsg = ipkg.yumdb_info.from_repo
                        xmsg = _(' (from %s)') % xmsg
                    msg = _('Installed package %s%s%s%s not available.')
                    self.verbose_logger.log(dnf.yum.logginglevels.INFO_2, msg,
                                            self.term.MODE['bold'], ipkg,
                                            self.term.MODE['normal'], xmsg)
            except dnf.yum.Errors.ReinstallError, e:
                assert False, "Shouldn't happen, but just in case"
                self.verbose_logger.log(dnf.yum.logginglevels.INFO_2, e)
            else:
                self._install_upgraded_requires(txmbrs)

        if len(self.tsInfo) > oldcount:
            change = len(self.tsInfo) - oldcount
            return 2, [P_('%d package to reinstall', '%d packages to reinstall', change) % change]
        return 0, [_('Nothing to do')]

    def returnPkgLists(self, extcmds, installed_available=False):
        """Return a :class:`dnf.yum.misc.GenericHolder` object containing
        lists of package objects that match the given names or wildcards.

        :param extcmds: a list of names or wildcards specifying
           packages to list
        :param installed_available: whether the available package list
           is present as .hidden_available when doing all, available,
           or installed

        :return: a :class:`dnf.yum.misc.GenericHolder` instance with the
           following lists defined::

             available = list of packageObjects
             installed = list of packageObjects
             updates = tuples of packageObjects (updating, installed)
             extras = list of packageObjects
             obsoletes = tuples of packageObjects (obsoleting, installed)
             recent = list of packageObjects
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
        """Search for simple text tags in a package object. This is a
        cli wrapper method for the module search function.

        :param args: list of names or wildcards to search for.
           Normally this method will begin by searching the package
           names and summaries, and will only search urls and
           descriptions if that fails.  However, if the first string
           in *args* is "all", this method will always search
           everything
        :return: a tuple where the first item is an exit code, and
           the second item is a generator if the search is a
           successful, and a list of error messages otherwise

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """

        # call the yum module search function with lists of tags to search
        # and what to search for
        # display the list of matches

        searchlist = ['name', 'summary', 'description', 'url']
        dups = self.conf.showdupesfromrepos
        args = map(to_unicode, args)

        okeys = set()
        akeys = set() # All keys, used to see if nothing matched
        mkeys = set() # "Main" set of keys for N/S search (biggest term. hit).
        pos   = set()

        def _print_match_section(text):
            # Print them in the order they were passed
            used_keys = [arg for arg in args if arg in keys]
            print self.fmtSection(text % ", ".join(used_keys))

        #  First try just the name/summary fields, and if we get any hits
        # don't do the other stuff. Unless the user overrides via. "all".
        if len(args) > 1 and args[0] == 'all':
            args.pop(0)
        else:
            matching = self.searchGenerator(['name', 'summary'], args,
                                            showdups=dups, keys=True)
            for (po, keys, matched_value) in matching:
                if keys != okeys:
                    if akeys:
                        if len(mkeys) == len(args):
                            break
                        print ""
                    else:
                        mkeys = set(keys)
                    _print_match_section(_('N/S Matched: %s'))
                    okeys = keys
                pos.add(po)
                akeys.update(keys)
                self.matchcallback(po, matched_value, args)

        matching = self.searchGenerator(searchlist, args,
                                        showdups=dups, keys=True)

        okeys = set()

        #  If we got a hit with just name/summary then we only care about hits
        # with _more_ search terms. Thus. if we hit all our search terms. do
        # nothing.
        if len(mkeys) == len(args):
            print ""
            if len(args) == 1:
                msg = _('  Name and summary matches %sonly%s, use "search all" for everything.')
            else:
                msg = _('  Full name and summary matches %sonly%s, use "search all" for everything.')
            print msg % (self.term.MODE['bold'], self.term.MODE['normal'])
            matching = []

        for (po, keys, matched_value) in matching:
            #  Don't print matches for "a", "b", "c" on N+S+D when we already
            # matched that on just N+S.
            if len(keys) <= len(mkeys):
                continue
             #  Just print the highest level of full matches, when we did
             # minimal matches. Ie. "A", "B" match N+S, just print the
             # "A", "B", "C", "D" full match, and not the "B", "C", "D" matches.
            if mkeys and len(keys) < len(okeys):
                continue

            if keys != okeys:
                if akeys:
                    print ""
                _print_match_section(_('Matched: %s'))
                okeys = keys
                akeys.update(keys)
            self.matchcallback(po, matched_value, args)

        if mkeys and len(mkeys) != len(args):
            print ""
            print _('  Name and summary matches %smostly%s, use "search all" for everything.') % (self.term.MODE['bold'], self.term.MODE['normal'])

        for arg in args:
            if arg not in akeys:
                self.logger.warning(_('Warning: No matches found for: %s'), arg)

        if not akeys:
            return 0, [_('No Matches found')]
        return 0, matching

    def deplist(self, args):
        """Print out a formatted list of dependencies for a list of
        packages.  This is a cli wrapper method for
        :class:`dnf.yum.YumBase.findDeps`.

        :param args: a list of names or wildcards specifying packages
           that should have their dependenices printed
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        pkgs = []
        for arg in args:
            if (arg.endswith('.rpm') and (dnf.yum.misc.re_remote_url(arg) or
                                          os.path.exists(arg))):
                thispkg = dnf.yum.packages.YumUrlPackage(self, self.ts, arg)
                pkgs.append(thispkg)
            elif self.conf.showdupesfromrepos:
                pkgs.extend(self.pkgSack.returnPackages(patterns=[arg]))
            else:
                try:
                    pkgs.extend(self.pkgSack.returnNewestByName(patterns=[arg]))
                except dnf.yum.Errors.PackageSackError:
                    pass

        results = self.findDeps(pkgs)
        self.depListOutput(results)

        return 0, []

    def provides(self, args):
        """Print out a list of packages that provide the given file or
        feature.  This a cli wrapper to the provides methods in the
        rpmdb and pkgsack.

        :param args: the name of a file or feature to search for
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        old_sdup = self.conf.showdupesfromrepos
        # For output, as searchPackageProvides() is always in showdups mode
        self.conf.showdupesfromrepos = True
        cb = self.matchcallback_verbose
        matches = 0
        for pkg in dnf.queries.by_file(self.sack, args):
            self.matchcallback_verbose(pkg, [], args)
            matches += 1
        self.conf.showdupesfromrepos = old_sdup

        if not matches:
            return 0, ['No Matches found']
        return 0, [] # :hawkey

        matching = self.searchPackageProvides(args, callback=cb,
                                              callback_has_matchfor=True)
        if len(matching) == 0:
            #  Try to be a bit clever, for commands, and python modules.
            # Maybe want something so we can do perl/etc. too?
            paths = set(sys.path + os.environ['PATH'].split(':'))
            nargs = []
            for arg in args:
                if dnf.yum.misc.re_filename(arg) or dnf.yum.misc.re_glob(arg):
                    continue
                for path in paths:
                    if not path:
                        continue
                    nargs.append("%s/%s" % (path, arg))
            matching = self.searchPackageProvides(nargs, callback=cb,
                                                  callback_has_matchfor=True)
        self.conf.showdupesfromrepos = old_sdup

        if len(matching) == 0:
            return 0, ['No Matches found']

        return 0, []

    def resolveDepCli(self, args):
        """Print information about a package that provides the given
        dependency.  Only one package will be printed per dependency.

        :param args: a list of strings specifying dependencies to
           search for
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        for arg in args:
            try:
                ipkg = self.returnInstalledPackageByDep(arg)
            except dnf.yum.Errors.YumBaseError:
                ipkg = None
            else:
                self.verbose_logger.info("%s %s" % (ipkg.envra,
                                                    ipkg.ui_from_repo))
            try:
                pkg = self.returnPackageByDep(arg)
            except dnf.yum.Errors.YumBaseError:
                if not ipkg:
                    self.logger.critical(_('No Package Found for %s'), arg)
            else:
                if not pkg.verEQ(ipkg):
                    self.verbose_logger.info("%s %s" % (pkg.envra,
                                                        pkg.ui_from_repo))

        return 0, []

    def cleanCli(self, userlist):
        """Remove data from the yum cache directory.  What data is
        removed depends on the options supplied by the user.

        :param userlist: a list of options.  The following are valid
           options::

             expire-cache = Eliminate the local data saying when the
               metadata and mirror lists were downloaded for each
               repository.
             packages = Eliminate any cached packages
             headers = Eliminate the header files, which old versions
               of yum used for dependency resolution
             metadata = Eliminate all of the files which yum uses to
               determine the remote availability of packages
             dbcache = Eliminate the sqlite cache used for faster
               access to metadata
             rpmdb = Eliminate any cached datat from the local rpmdb
             plugins = Tell any enabled plugins to eliminate their
               cached data
             all = do all of the above
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        hdrcode = pkgcode = xmlcode = dbcode = expccode = 0
        pkgresults = hdrresults = xmlresults = dbresults = expcresults = []
        msg = self.fmtKeyValFill(_('Cleaning repos: '),
                        ' '.join([ x.id for x in self.repos.listEnabled()]))
        self.verbose_logger.log(dnf.yum.logginglevels.INFO_2, msg)
        if 'all' in userlist:
            self.verbose_logger.log(dnf.yum.logginglevels.INFO_2,
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
            self.verbose_logger.log(dnf.yum.logginglevels.INFO_2, msg)
        return code, []

    def returnGroupLists(self, userlist):
        """Print out a list of groups that match the given names or
        wildcards.

        :param extcmds: a list of names or wildcards specifying
           groups to list
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        uservisible=1

        if len(userlist) > 0:
            if userlist[0] == 'hidden':
                uservisible=0
                userlist.pop(0)
        if not userlist:
            userlist = None # Match everything...

        installed, available = self.doGroupLists(uservisible=uservisible,
                                                 patterns=userlist)

        if not installed and not available:
            self.logger.error(_('Warning: No groups match: %s'),
                              ", ".join(userlist))
            return 0, []

        def _out_grp(sect, group):
            if not done:
                self.verbose_logger.log(dnf.yum.logginglevels.INFO_2, sect)
            msg = '   %s' % group.ui_name
            if self.verbose_logger.isEnabledFor(dnf.yum.logginglevels.DEBUG_3):
                msg += ' (%s)' % group.groupid
            if group.langonly:
                msg += ' [%s]' % group.langonly
            self.verbose_logger.info('%s', msg)

        done = False
        for group in installed:
            if group.langonly: continue
            _out_grp(_('Installed Groups:'), group)
            done = True

        done = False
        for group in installed:
            if not group.langonly: continue
            _out_grp(_('Installed Language Groups:'), group)
            done = True

        done = False
        for group in available:
            if group.langonly: continue
            _out_grp(_('Available Groups:'), group)
            done = True

        done = False
        for group in available:
            if not group.langonly: continue
            _out_grp(_('Available Language Groups:'), group)
            done = True

        return 0, [_('Done')]

    def returnGroupSummary(self, userlist):
        """Print a summary of the groups that match the given names or
        wildcards.

        :param userlist: a list of names or wildcards specifying the
           groups to summarise. If *userlist* is an empty list, all
           installed and available packages will be summarised
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        uservisible=1

        if len(userlist) > 0:
            if userlist[0] == 'hidden':
                uservisible=0
                userlist.pop(0)
        if not userlist:
            userlist = None # Match everything...

        installed, available = self.doGroupLists(uservisible=uservisible,
                                                 patterns=userlist)

        def _out_grp(sect, num):
            if not num:
                return
            self.verbose_logger.log(dnf.yum.logginglevels.INFO_2, '%s %u', sect,num)
        done = 0
        for group in installed:
            if group.langonly: continue
            done += 1
        _out_grp(_('Installed Groups:'), done)

        done = 0
        for group in installed:
            if not group.langonly: continue
            done += 1
        _out_grp(_('Installed Language Groups:'), done)

        done = False
        for group in available:
            if group.langonly: continue
            done += 1
        _out_grp(_('Available Groups:'), done)

        done = False
        for group in available:
            if not group.langonly: continue
            done += 1
        _out_grp(_('Available Language Groups:'), done)

        return 0, [_('Done')]

    def returnGroupInfo(self, userlist):
        """Print complete information about the groups that match the
        given names or wildcards.

        :param userlist: a list of names or wildcards specifying the
           groups to print information about
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        for strng in userlist:
            group_matched = False
            for group in self.comps.return_groups(strng):
                self.displayPkgsInGroups(group)
                group_matched = True

            if not group_matched:
                self.logger.error(_('Warning: Group %s does not exist.'), strng)

        return 0, []

    def installGroups(self, grouplist):
        """Mark the packages in the given groups for installation.

        :param grouplist: a list of names or wildcards specifying
           groups to be installed
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        pkgs_used = []

        for group_string in grouplist:
            group_matched = False
            for group in self.comps.return_groups(group_string):
                group_matched = True


                try:
                    txmbrs = self.selectGroup(group.groupid)
                except dnf.yum.Errors.GroupsError:
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
            return 2, [P_('%d package to Install', '%d packages to Install', len(pkgs_used)) % len(pkgs_used)]

    def removeGroups(self, grouplist):
        """Mark the packages in the given groups for removal.

        :param grouplist: a list of names or wildcards specifying
           groups to be removed
        :return: (exit_code, [ errors ])

        exit_code is::

            0 = we're done, exit
            1 = we've errored, exit with error string
            2 = we've got work yet to do, onto the next stage
        """
        pkgs_used = []
        for group_string in grouplist:
            try:
                txmbrs = self.groupRemove(group_string)
            except dnf.yum.Errors.GroupsError:
                self.logger.critical(_('No group named %s exists'), group_string)
                continue
            else:
                pkgs_used.extend(txmbrs)

        if not pkgs_used:
            return 0, [_('No packages to remove from groups')]
        else:
            return 2, [P_('%d package to remove', '%d packages to remove', len(pkgs_used)) % len(pkgs_used)]



    def _promptWanted(self):
        # shortcut for the always-off/always-on options
        if self.conf.assumeyes and not self.conf.assumeno:
            return False
        if self.conf.alwaysprompt:
            return True

        # prompt if:
        #  package was added to fill a dependency
        #  package is being removed
        #  package wasn't explictly given on the command line
        for txmbr in self.tsInfo.getMembers():
            if txmbr.isDep or \
                   txmbr.name not in self.extcmds:
                return True

        # otherwise, don't prompt
        return False

    def usage(self):
        """Print out an explanation of command line usage."""
        sys.stdout.write(self.optparser.format_help())

    def shellUsage(self):
        """Print out an explanation of the shell usage."""
        sys.stdout.write(self.optparser.get_usage())

    def _installable(self, pkg, ematch=False):

        """check if the package is reasonably installable, true/false"""

        exactarchlist = self.conf.exactarchlist
        # we look through each returned possibility and rule out the
        # ones that we obviously can't use

        if self.rpmdb.contains(po=pkg):
            self.verbose_logger.log(dnf.yum.logginglevels.DEBUG_3,
                _('Package %s is already installed, skipping'), pkg)
            return False

        # everything installed that matches the name
        installedByKey = self.rpmdb.searchNevra(name=pkg.name)
        comparable = []
        for instpo in installedByKey:
            if isMultiLibArch(instpo.arch) == isMultiLibArch(pkg.arch):
                comparable.append(instpo)
            else:
                self.verbose_logger.log(dnf.yum.logginglevels.DEBUG_3,
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
            self.verbose_logger.log(dnf.yum.logginglevels.DEBUG_1, _('No other %s installed, adding to list for potential install'), pkg.name)
            return True

        return False

class YumOptionParser(OptionParser):
    """Subclass that makes some minor tweaks to make OptionParser do things the
    "yum way".
    """

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
        # self.plugin_option_group = OptionGroup(self, _("Plugin Options"))
        # self.add_option_group(self.plugin_option_group)

        self._addYumBasicOptions()

    def error(self, msg):
        """Output an error message, and exit the program.  This method
        is overridden so that error output goes to the logger.

        :param msg: the error message to output
        """
        self.print_usage()
        self.logger.critical(_("Command line error: %s"), msg)
        sys.exit(1)

    def firstParse(self,args):
        """Parse only command line options that affect basic yum
        setup.

        :param args: a list of command line options to parse
        :return: a dictionary containing the values of command line
           options
        """
        try:
            args = _filtercmdline(
                        ('--noplugins','--version','-q', '-v', "--quiet", "--verbose"),
                        ('-c', '--config', '-d', '--debuglevel',
                         '-e', '--errorlevel',
                         '--installroot',
                         '--disableplugin', '--enableplugin', '--releasever',
                         '--setopt'),
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
        """Parse command line options.

        :param args: the command line arguments entered by the user
        :return: (opts, cmds)  opts is a dictionary containing
           the values of command line options.  cmds is a list of the
           command line arguments that were not parsed as options.
           For example, if args is ["install", "foo", "--verbose"],
           cmds will be ["install", "foo"].
        """
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
                self.base.conf.assumeyes = 1
            if opts.assumeno:
                self.base.conf.assumeno  = 1

            #  Instead of going cache-only for a non-root user, try to use a
            # user writable cachedir. If that fails fall back to cache-only.
            if opts.cacheonly:
                self.base.conf.cache = 1

            if opts.obsoletes:
                self.base.conf.obsoletes = 1

            if opts.installroot:
                self._checkAbsInstallRoot(opts)
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
                except dnf.yum.Errors.ConfigError, e:
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
                except dnf.yum.Errors.ConfigError, e:
                    self.logger.critical(e)
                    self.base.usage()
                    sys.exit(1)

            # Disable all gpg key checking, if requested.
            if opts.nogpgcheck:
                #  Altering the normal configs. doesn't work too well, esp. with
                # regard to dynamically enabled repos.
                self.base._override_sigchecks = True
                for repo in self.base.repos.listEnabled():
                    repo._override_sigchecks = True

        except ValueError, e:
            self.logger.critical(_('Options Error: %s'), e)
            self.base.usage()
            sys.exit(1)

        return opts, cmds

    def _checkAbsInstallRoot(self, opts):
        if not opts.installroot:
            return
        if opts.installroot[0] == '/':
            return
        # We have a relative installroot ... haha
        self.logger.critical(_('--installroot must be an absolute path: %s'),
                             opts.installroot)
        sys.exit(1)

    def getRoot(self,opts):
        """Return the root location to use for the yum operation.
        This location can be changed by using the --installroot
        option.

        :param opts: a dictionary containing the values of the command
           line options
        :return: a string representing the root location
        """
        self._checkAbsInstallRoot(opts)
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

        group.add_option("-C", "--cacheonly", dest="cacheonly",
                action="store_true",
                help=_("run entirely from system cache, don't update cache"))
        group.add_option("-c", "--config", dest="conffile",
                default=dnf.const.CONF_FILENAME,
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
        group.add_option("--assumeno", dest="assumeno",
                action="store_true", help=_("answer no for all questions"))
        group.add_option("--version", action="store_true",
                help=_("show Yum version and exit"))
        group.add_option("--installroot", help=_("set install root"),
                metavar='[path]')
        group.add_option("--enablerepo", action='callback',
                type='string', callback=repo_optcb, dest='repos', default=[],
                # help=_("enable one or more repositories (wildcards allowed)"),
                help=SUPPRESS_HELP,
                metavar='[repo]')
        group.add_option("--disablerepo", action='callback',
                type='string', callback=repo_optcb, dest='repos', default=[],
                # help=_("disable one or more repositories (wildcards allowed)"),
                help=SUPPRESS_HELP,
                metavar='[repo]')
        group.add_option("-x", "--exclude", default=[], action="append",
                # help=_("exclude package(s) by name or glob"),
                help=SUPPRESS_HELP,
                metavar='[package]')
        group.add_option("", "--disableexcludes", default=[], action="append",
                # help=_("disable exclude from main, for a repo or for everything"),
                help=SUPPRESS_HELP,
                        metavar='[repo]')
        group.add_option("--obsoletes", action="store_true",
                # help=_("enable obsoletes processing during updates")
                help=SUPPRESS_HELP)
        group.add_option("--noplugins", action="store_true",
                # help=_("disable Yum plugins")
                help=SUPPRESS_HELP)
        group.add_option("--nogpgcheck", action="store_true",
                # help=_("disable gpg signature checking")
                help=SUPPRESS_HELP)
        group.add_option("", "--disableplugin", dest="disableplugins", default=[],
                action="append",
                # help=_("disable plugins by name"),
                help=SUPPRESS_HELP,
                metavar='[plugin]')
        group.add_option("", "--enableplugin", dest="enableplugins", default=[],
                action="append",
                # help=_("enable plugins by name"),
                help=SUPPRESS_HELP,
                metavar='[plugin]')
        group.add_option("--skip-broken", action="store_true", dest="skipbroken",
                # help=_("skip packages with depsolving problems")
                help=SUPPRESS_HELP)
        group.add_option("", "--color", dest="color", default=None,
                # help=_("control whether color is used")
                help=SUPPRESS_HELP)
        group.add_option("", "--releasever", dest="releasever", default=None,
                # help=_("set value of $releasever in yum config and repo files")
                help=SUPPRESS_HELP)
        group.add_option("", "--setopt", dest="setopts", default=[],
                action="append",
                # help=_("set arbitrary config and repo options")
                help=SUPPRESS_HELP)

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

        elif a == '--':
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

