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

"""
Entrance point for the yum command line interface.
"""

import os
import os.path
import sys
import logging
import time

from yum import Errors
from yum import plugins
from yum import logginglevels
from yum import _
from yum.i18n import to_unicode
import yum.misc
import cli


def main(args):
    """This does all the real work"""

    yum.misc.setup_locale(override_time=True)

    def exUserCancel():
        logger.critical(_('\n\nExiting on user cancel'))
        if unlock(): return 200
        return 1

    def exIOError(e):
        if e.errno == 32:
            logger.critical(_('\n\nExiting on Broken Pipe'))
        if unlock(): return 200
        return 1

    def exPluginExit(e):
        '''Called when a plugin raises PluginYumExit.

        Log the plugin's exit message if one was supplied.
        ''' # ' xemacs hack
        exitmsg = str(e)
        if exitmsg:
            logger.warn('\n\n%s', exitmsg)
        if unlock(): return 200
        return 1

    def exFatal(e):
        logger.critical('\n\n%s', to_unicode(e))
        if unlock(): return 200
        return 1

    def unlock():
        try:
            base.closeRpmDB()
            base.doUnlock()
        except Errors.LockError, e:
            return 200
        return 0

    def jiffies_to_seconds(jiffies):
        Hertz = 100 # FIXME: Hack, need to get this, AT_CLKTCK elf note *sigh*
        return int(jiffies) / Hertz
    def seconds_to_ui_time(seconds):
        if seconds >= 60 * 60 * 24:
            return "%d day(s) %d:%02d:%02d" % (seconds / (60 * 60 * 24),
                                               (seconds / (60 * 60)) % 24,
                                               (seconds / 60) % 60,
                                               seconds % 60)
        if seconds >= 60 * 60:
            return "%d:%02d:%02d" % (seconds / (60 * 60), (seconds / 60) % 60,
                                     (seconds % 60))
        return "%02d:%02d" % ((seconds / 60), seconds % 60)
    def show_lock_owner(pid):
        if not pid:
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
                       'D' : _('Uninteruptable'),
                       'Z' : _('Zombie'),
                       'T' : _('Traced/Stopped')
                       }.get(ps_stat[2], _('Unknown'))

        # This yumBackend isn't very friendly, so...
        if ps['name'] == 'yumBackend.py':
            nmsg = _("  The other application is: PackageKit")
        else:
            nmsg = _("  The other application is: %s") % ps['name']

        logger.critical("%s", nmsg)
        logger.critical(_("    Memory : %5s RSS (%5sB VSZ)") %
                        (base.format_number(int(ps['vmrss']) * 1024),
                         base.format_number(int(ps['vmsize']) * 1024)))
        ago = seconds_to_ui_time(int(time.time()) - ps['start_time'])
        logger.critical(_("    Started: %s - %s ago") %
                        (time.ctime(ps['start_time']), ago))
        logger.critical(_("    State  : %s, pid: %d") % (ps['state'], pid))

    logger = logging.getLogger("yum.main")
    verbose_logger = logging.getLogger("yum.verbose.main")

    # our core object for the cli
    base = cli.YumBaseCli()

    # do our cli parsing and config file setup
    # also sanity check the things being passed on the cli
    try:
        base.getOptionsConfig(args)
    except plugins.PluginYumExit, e:
        return exPluginExit(e)
    except Errors.YumBaseError, e:
        return exFatal(e)

    lockerr = ""
    while True:
        try:
            base.doLock()
        except Errors.LockError, e:
            if "%s" %(e.msg,) != lockerr:
                lockerr = "%s" %(e.msg,)
                logger.critical(lockerr)
            logger.critical(_("Another app is currently holding the yum lock; waiting for it to exit..."))
            show_lock_owner(e.pid)
            time.sleep(2)
        else:
            break

    try:
        result, resultmsgs = base.doCommands()
    except plugins.PluginYumExit, e:
        return exPluginExit(e)
    except Errors.YumBaseError, e:
        result = 1
        resultmsgs = [unicode(e)]
    except KeyboardInterrupt:
        return exUserCancel()
    except IOError, e:
        return exIOError(e)

    # Act on the command/shell result
    if result == 0:
        # Normal exit 
        for msg in resultmsgs:
            verbose_logger.log(logginglevels.INFO_2, '%s', msg)
        if unlock(): return 200
        return 0
    elif result == 1:
        # Fatal error
        for msg in resultmsgs:
            logger.critical(_('Error: %s'), msg)
        if unlock(): return 200
        return 1
    elif result == 2:
        # Continue on
        pass
    elif result == 100:
        if unlock(): return 200
        return 100
    else:
        logger.critical(_('Unknown Error(s): Exit Code: %d:'), result)
        for msg in resultmsgs:
            logger.critical(msg)
        if unlock(): return 200
        return 3
            
    # Depsolve stage
    verbose_logger.log(logginglevels.INFO_2, _('Resolving Dependencies'))

    try:
        (result, resultmsgs) = base.buildTransaction() 
    except plugins.PluginYumExit, e:
        return exPluginExit(e)
    except Errors.YumBaseError, e:
        result = 1
        resultmsgs = [unicode(e)]
    except KeyboardInterrupt:
        return exUserCancel()
    except IOError, e:
        return exIOError(e)
   
    # Act on the depsolve result
    if result == 0:
        # Normal exit
        if unlock(): return 200
        return 0
    elif result == 1:
        # Fatal error
        for msg in resultmsgs:
            logger.critical(_('Error: %s'), msg)
        if not base.conf.skip_broken:
            verbose_logger.info(_(" You could try using --skip-broken to work around the problem"))
        verbose_logger.info(_(" You could try running: package-cleanup --problems\n"
                              "                        package-cleanup --dupes\n"
                              "                        rpm -Va --nofiles --nodigest"))
        base.yumUtilsMsg(verbose_logger.info, "package-cleanup")
        if unlock(): return 200
        return 1
    elif result == 2:
        # Continue on
        pass
    else:
        logger.critical(_('Unknown Error(s): Exit Code: %d:'), result)
        for msg in resultmsgs:
            logger.critical(msg)
        if unlock(): return 200
        return 3

    verbose_logger.log(logginglevels.INFO_2, _('\nDependencies Resolved'))

    # Run the transaction
    try:
        return_code = base.doTransaction()
    except plugins.PluginYumExit, e:
        return exPluginExit(e)
    except Errors.YumBaseError, e:
        return exFatal(e)
    except KeyboardInterrupt:
        return exUserCancel()
    except IOError, e:
        return exIOError(e)

    verbose_logger.log(logginglevels.INFO_2, _('Complete!'))
    if unlock(): return 200
    return return_code

def hotshot(func, *args, **kwargs):
    import hotshot.stats
    fn = os.path.expanduser("~/yum.prof")
    prof = hotshot.Profile(fn)
    rc = prof.runcall(func, *args, **kwargs)
    prof.close()
    print_stats(hotshot.stats.load(fn))
    return rc

def cprof(func, *args, **kwargs):
    import cProfile, pstats
    fn = os.path.expanduser("~/yum.prof")
    prof = cProfile.Profile()
    rc = prof.runcall(func, *args, **kwargs)
    prof.dump_stats(fn)
    print_stats(pstats.Stats(fn))
    return rc

def print_stats(stats):
    stats.strip_dirs()
    stats.sort_stats('time', 'calls')
    stats.print_stats(20)
    stats.sort_stats('cumulative')
    stats.print_stats(40)

def user_main(args, exit_code=False):
    """ This calls one of the multiple main() functions based on env. vars """
    errcode = None
    if 'YUM_PROF' in os.environ:
        if os.environ['YUM_PROF'] == 'cprof':
            errcode = cprof(main, args)
        if os.environ['YUM_PROF'] == 'hotshot':
            errcode = hotshot(main, args)
    if errcode is None:
        errcode = main(args)
    if exit_code:
        sys.exit(errcode)
    return errcode

if __name__ == "__main__":
    try:
        user_main(sys.argv[1:], exit_code=True)
    except KeyboardInterrupt, e:
        print >> sys.stderr, _("\n\nExiting on user cancel.")
        sys.exit(1)
