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

"""Various utility functions, and a utility class."""

import os
import sys
import time

import dnf.yum
from cli import *
from dnf.yum.i18n import utf8_width, exception2msg, _
from optparse import OptionGroup

import dnf.yum.plugins as plugins
from dnf.cli.output import YumOutput
format_number = YumOutput.format_number

try:
    _USER_HZ = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
except (AttributeError, KeyError):
    # Huh, non-Unix platform? Or just really old?
    _USER_HZ = 100

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
    msg = _('  The application with PID %d is: %s')
    if ps['name'] == 'yumBackend.py':
        nmsg = msg % (pid, 'PackageKit')
    else:
        nmsg = msg % (pid, ps['name'])

    logger.critical("%s", nmsg)
    logger.critical(_("    Memory : %5s RSS (%5sB VSZ)") %
                    (format_number(int(ps['vmrss']) * 1024),
                     format_number(int(ps['vmsize']) * 1024)))

    ago = seconds_to_ui_time(int(time.time()) - ps['start_time'])
    logger.critical(_("    Started: %s - %s ago") %
                    (time.ctime(ps['start_time']), ago))
    logger.critical(_("    State  : %s") % ps['state'])

    return ps
