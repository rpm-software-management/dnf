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

"""Various utility functions, and a utility class."""

import os
import sys
import time
import exceptions

import dnf.yum
from cli import *
from dnf.yum import Errors
from dnf.yum import _
from dnf.yum.i18n import utf8_width, exception2msg
from dnf.yum import logginglevels
from optparse import OptionGroup

import dnf.yum.plugins as plugins
from urlgrabber.progress import format_number

try:
    _USER_HZ = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
except (AttributeError, KeyError):
    # Huh, non-Unix platform? Or just really old?
    _USER_HZ = 100

def suppress_keyboard_interrupt_message():
    """Change settings so that nothing will be printed to the
    terminal after an uncaught :class:`exceptions.KeyboardInterrupt`.
    """
    old_excepthook = sys.excepthook

    def new_hook(type, value, traceback):
        if type != exceptions.KeyboardInterrupt:
            old_excepthook(type, value, traceback)
        else:
            pass

    sys.excepthook = new_hook

def jiffies_to_seconds(jiffies):
    """Convert a number of jiffies to seconds. How many jiffies are in a second
    is system-dependent, e.g. 100 jiffies = 1 second is common.

    :param jiffies: a number of jiffies
    :return: the equivalent number of seconds
    """
    return int(jiffies) / _USER_HZ

def seconds_to_ui_time(seconds):
    """Return a human-readable string representation of the length of
    a time interval given in seconds.

    :param seconds: the length of the time interval in seconds
    :return: a human-readable string representation of the length of
    the time interval
    """
    if seconds >= 60 * 60 * 24:
        return "%d day(s) %d:%02d:%02d" % (seconds / (60 * 60 * 24),
                                           (seconds / (60 * 60)) % 24,
                                           (seconds / 60) % 60,
                                           seconds % 60)
    if seconds >= 60 * 60:
        return "%d:%02d:%02d" % (seconds / (60 * 60), (seconds / 60) % 60,
                                 (seconds % 60))
    return "%02d:%02d" % ((seconds / 60), seconds % 60)

def get_process_info(pid):
    """Return information about a process taken from
    /proc/*pid*/status, /proc/stat/, and /proc/*pid*/stat.

    :param pid: the process id number
    :return: a dictionary containing information about the process
    """
    if not pid:
        return

    try:
        pid = int(pid)
    except ValueError, e:
        return
        
    # Maybe true if /proc isn't mounted, or not Linux ... or something.
    if (not os.path.exists("/proc/%d/status" % pid) or
        not os.path.exists("/proc/stat") or
        not os.path.exists("/proc/%d/stat" % pid)):
        return

    ps = {}
    for line in open("/proc/%d/status" % pid):
        if line[-1] != '\n':
            continue
        data = line[:-1].split(':\t', 1)
        if len(data) < 2:
            continue
        if data[1].endswith(' kB'):
            data[1] = data[1][:-3]
        ps[data[0].strip().lower()] = data[1].strip()
    if 'vmrss' not in ps:
        return
    if 'vmsize' not in ps:
        return
    boot_time = None
    for line in open("/proc/stat"):
        if line.startswith("btime "):
            boot_time = int(line[len("btime "):-1])
            break
    if boot_time is None:
        return
    ps_stat = open("/proc/%d/stat" % pid).read().split()
    ps['utime'] = jiffies_to_seconds(ps_stat[13])
    ps['stime'] = jiffies_to_seconds(ps_stat[14])
    ps['cutime'] = jiffies_to_seconds(ps_stat[15])
    ps['cstime'] = jiffies_to_seconds(ps_stat[16])
    ps['start_time'] = boot_time + jiffies_to_seconds(ps_stat[21])
    ps['state'] = {'R' : _('Running'),
                   'S' : _('Sleeping'),
                   'D' : _('Uninterruptible'),
                   'Z' : _('Zombie'),
                   'T' : _('Traced/Stopped')
                   }.get(ps_stat[2], _('Unknown'))
                   
    return ps

def show_lock_owner(pid, logger):
    """Output information about another process that is holding the
    yum lock.

    :param pid: the process id number of the process holding the yum
       lock
    :param logger: the logger to output the information to
    :return: a dictionary containing information about the process.
       This is the same as the dictionary returned by
       :func:`get_process_info`.
    """
    ps = get_process_info(pid)
    if not ps:
        return None

    # This yumBackend isn't very friendly, so...
    if ps['name'] == 'yumBackend.py':
        nmsg = _("  The other application is: PackageKit")
    else:
        nmsg = _("  The other application is: %s") % ps['name']

    logger.critical("%s", nmsg)
    logger.critical(_("    Memory : %5s RSS (%5sB VSZ)") %
                    (format_number(int(ps['vmrss']) * 1024),
                     format_number(int(ps['vmsize']) * 1024)))
    
    ago = seconds_to_ui_time(int(time.time()) - ps['start_time'])
    logger.critical(_("    Started: %s - %s ago") %
                    (time.ctime(ps['start_time']), ago))
    logger.critical(_("    State  : %s, pid: %d") % (ps['state'], pid))

    return ps


class YumUtilBase(YumBaseCli):
    """A class to extend the yum cli for utilities."""
    
    def __init__(self,name,ver,usage):
        YumBaseCli.__init__(self)
        self._parser = YumOptionParser(base=self,utils=True,usage=usage)
        self._usage = usage
        self._utilName = name
        self._utilVer = ver
        self._option_group = OptionGroup(self._parser, "%s options" % self._utilName,"")
        self._parser.add_option_group(self._option_group)
        suppress_keyboard_interrupt_message()
        logger = logging.getLogger("yum.util")
        verbose_logger = logging.getLogger("yum.verbose.util")
        # Add yum-utils version to history records.
        if hasattr(self, 'run_with_package_names'):
            self.run_with_package_names.add("yum-utils")

    def exUserCancel(self):
        """Output a message stating that the operation was cancelled
        by the user.

        :return: the exit code
        """
        self.logger.critical(_('\n\nExiting on user cancel'))
        if self.unlock(): return 200
        return 1

    def exIOError(self, e):
        """Output a message stating that the program is exiting due to
        an IO exception.

        :param e: the IO exception
        :return: the exit code
        """
        if e.errno == 32:
            self.logger.critical(_('\n\nExiting on Broken Pipe'))
        else:
            self.logger.critical(_('\n\n%s') % exception2msg(e))
        if self.unlock(): return 200
        return 1

    def exPluginExit(self, e):
        """Called when a plugin raises
           :class:`dnf.yum.plugins.PluginYumExit`.  Log the plugin's exit
           message if one was supplied.

        :param e: the exception
        :return: the exit code
        """ # ' xemacs hack
        exitmsg = exception2msg(e)
        if exitmsg:
            self.logger.warn('\n\n%s', exitmsg)
        if self.unlock(): return 200
        return 1

    def exFatal(self, e):
        """Output a message stating that a fatal error has occurred.

        :param e: the exception
        :return: the exit code
        """
        self.logger.critical('\n\n%s', exception2msg(e))
        if self.unlock(): return 200
        return 1
        
    def unlock(self):
        """Release the yum lock.

        :return: the exit code
        """
        try:
            self.closeRpmDB()
            self.doUnlock()
        except Errors.LockError, e:
            return 200
        return 0
        
        
    def getOptionParser(self):
        """Return the :class:`cli.YumOptionParser` for this object.

        :return: the :class:`cli.YumOptionParser` for this object
        """
        return self._parser        

    def getOptionGroup(self):
        """Return an option group to add non inherited options.

        :return: a :class:`optparse.OptionGroup` for adding options
           that are not inherited from :class:`YumBaseCli`.
        """
        return self._option_group    
    
    def waitForLock(self):
        """Establish the yum lock.  If another process is already
        holding the yum lock, by default this method will keep trying
        to establish the lock until it is successful.  However, if
        :attr:`self.conf.exit_on_lock` is set to True, it will
        raise a :class:`Errors.YumBaseError`.
        """
        lockerr = ""
        while True:
            try:
                self.doLock()
            except Errors.LockError, e:
                if exception2msg(e) != lockerr:
                    lockerr = exception2msg(e)
                    self.logger.critical(lockerr)
                if not self.conf.exit_on_lock:
                    self.logger.critical("Another app is currently holding the yum lock; waiting for it to exit...")  
                    show_lock_owner(e.pid, self.logger)
                    time.sleep(2)
                else:
                    raise Errors.YumBaseError, _("Another app is currently holding the yum lock; exiting as configured by exit_on_lock")
            else:
                break
        
    def _printUtilVersion(self):
        print "%s - %s (yum - %s)" % (self._utilName,self._utilVer,dnf.yum.__version__)
        
    def doUtilConfigSetup(self,args = sys.argv[1:],pluginsTypes=(plugins.TYPE_CORE,)):
        """Parse command line options, and perform configuration.

        :param args: list of arguments to use for configuration
        :param pluginsTypes: a sequence specifying the types of
           plugins to load
        :return: a dictionary containing the values of command line options
        """
        # Parse only command line options that affect basic yum setup
        opts = self._parser.firstParse(args)

        # go through all the setopts and set the global ones
        self._parseSetOpts(opts.setopts)

        if self.main_setopts:
            for opt in self.main_setopts.items:
                setattr(opts, opt, getattr(self.main_setopts, opt))

        # Just print out the version if that's what the user wanted
        if opts.version:
            self._printUtilVersion()
            sys.exit(0)
        # get the install root to use
        root = self._parser.getRoot(opts)
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
            pc.plugin_types = pluginsTypes
            pc.optparser = self._parser
            pc.debuglevel = opts.debuglevel
            pc.errorlevel = opts.errorlevel
            if hasattr(opts, "disableplugins"):
                pc.disabled_plugins =self._parser._splitArg(opts.disableplugins)
            if hasattr(opts, "enableplugins"):
                pc.enabled_plugins = self._parser._splitArg(opts.enableplugins)
            if hasattr(opts, "releasever"):
                pc.releasever = opts.releasever
            self.conf

            # now set  all the non-first-start opts from main from our setopts
            if self.main_setopts:
                for opt in self.main_setopts.items:
                    setattr(self.conf, opt, getattr(self.main_setopts, opt))

        except Errors.ConfigError, e:
            self.logger.critical(_('Config Error: %s'), exception2msg(e))
            sys.exit(1)
        except ValueError, e:
            self.logger.critical(_('Options Error: %s'), exception2msg(e))
            sys.exit(1)
        except plugins.PluginYumExit, e:
            self.logger.critical(_('PluginExit Error: %s'), exception2msg(e))
            sys.exit(1)
        except Errors.YumBaseError, e:
            self.logger.critical(_('Yum Error: %s'), exception2msg(e))
            sys.exit(1)
            
        # update usage in case plugins have added commands
        self._parser.set_usage(self._usage)
        
        # Now parse the command line for real and 
        # apply some of the options to self.conf
        (opts, self.cmds) = self._parser.setupYumConfig()
        if self.cmds:
            self.basecmd = self.cmds[0] # our base command
        else:
            self.basecmd = None
        self.extcmds = self.cmds[1:] # out extended arguments/commands

        return opts

    def doUtilYumSetup(self):
        """Do a default setup for all the normal or necessary yum components;
           this method is mostly just a used for testing.
        """
        # FIXME - we need another way to do this, I think.
        try:
            self.waitForLock()
            self._getTs()
            self._getRpmDB()
            self._getRepos(doSetup = True)
            self._getSacks()
        except Errors.YumBaseError, msg:
            self.logger.critical(exception2msg(msg))
            sys.exit(1)

    def doUtilBuildTransaction(self, unfinished_transactions_check=True):
        """Build the transaction.

        :param unfinished_transactions_check: whether to check if an
           unfinished transaction has been saved
        """
        try:
            (result, resultmsgs) = self.buildTransaction(unfinished_transactions_check = unfinished_transactions_check)
        except plugins.PluginYumExit, e:
            return self.exPluginExit(e)
        except Errors.YumBaseError, e:
            result = 1
            resultmsgs = [exception2msg(e)]
        except KeyboardInterrupt:
            return self.exUserCancel()
        except IOError, e:
            return self.exIOError(e)
       
        # Act on the depsolve result
        if result == 0:
            # Normal exit
            if self.unlock(): return 200
            return 0
        elif result == 1:
            # Fatal error
            for msg in resultmsgs:
                prefix = _('Error: %s')
                prefix2nd = (' ' * (utf8_width(prefix) - 2))
                self.logger.critical(prefix, msg.replace('\n', '\n' + prefix2nd))
            if not self.conf.skip_broken:
                self.verbose_logger.info(_(" You could try using --skip-broken to work around the problem"))
            if not self._rpmdb_warn_checks(out=self.verbose_logger.info, warn=False):
                self.verbose_logger.info(_(" You could try running: rpm -Va --nofiles --nodigest"))
            if self.unlock(): return 200
            return 1
        elif result == 2:
            # Continue on
            pass
        else:
            self.logger.critical(_('Unknown Error(s): Exit Code: %d:'), result)
            for msg in resultmsgs:
                self.logger.critical(msg)
            if self.unlock(): return 200
            return 3

        self.verbose_logger.log(logginglevels.INFO_2, _('\nDependencies Resolved'))
        
    def doUtilTransaction(self):
        """Perform the transaction."""

        try:
            return_code = self.doTransaction()
        except plugins.PluginYumExit, e:
            return self.exPluginExit(e)
        except Errors.YumBaseError, e:
            return self.exFatal(e)
        except KeyboardInterrupt:
            return self.exUserCancel()
        except IOError, e:
            return self.exIOError(e,)

        self.verbose_logger.log(logginglevels.INFO_2, _('Complete!'))
        if self.unlock(): return 200
        return return_code
        
def main():
    name = 'testutil'
    ver  = '0.1'
    usage = 'testutil [options] [args]'
    util = YumUtilBase(name,ver,usage)
    parser = util.getOptionParser() 
    parser.add_option("", "--myoption", dest="myoption",
                    action="store_true", default=False, 
                    help="This is an util option")
    util.logger.info("Setup Yum Config")
    opts = util.doUtilConfigSetup()
    util.logger.info("Setup Yum")
    util.doUtilYumSetup()
    print "Command line args: %s" % " ".join(util.cmds)
    print "Command line options :"
    print opts
    
    util.logger.info("%s Completed" % name)
if __name__ == '__main__':
    main()

    
