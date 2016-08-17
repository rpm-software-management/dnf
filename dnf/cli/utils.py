# Copyright (C) 2016  Red Hat, Inc.
#
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

from __future__ import absolute_import
from __future__ import unicode_literals
from dnf.cli.format import format_number
from dnf.i18n import _
import dnf.util
import logging
import os
import time

_USER_HZ = os.sysconf(os.sysconf_names['SC_CLK_TCK'])
logger = logging.getLogger('dnf')

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
        return "%d day(s) %d:%02d:%02d" % (seconds // (60 * 60 * 24),
                                           (seconds // (60 * 60)) % 24,
                                           (seconds // 60) % 60,
                                           seconds % 60)
    if seconds >= 60 * 60:
        return "%d:%02d:%02d" % (seconds // (60 * 60), (seconds // 60) % 60,
                                 (seconds % 60))
    return "%02d:%02d" % ((seconds // 60), seconds % 60)


def get_process_info(pid):
    """Return info dict about a process."""

    pid = int(pid)

    # Maybe true if /proc isn't mounted, or not Linux ... or something.
    if (not os.path.exists("/proc/%d/status" % pid) or
        not os.path.exists("/proc/stat") or
        not os.path.exists("/proc/%d/stat" % pid)):
        return

    ps = {}
    with open("/proc/%d/status" % pid) as status_file:
        for line in status_file:
            if line[-1] != '\n':
                continue
            data = line[:-1].split(':\t', 1)
            if len(data) < 2:
                continue
            data[1] = dnf.util.rtrim(data[1], ' kB')
            ps[data[0].strip().lower()] = data[1].strip()
    if 'vmrss' not in ps:
        return
    if 'vmsize' not in ps:
        return

    boot_time = None
    with open("/proc/stat") as stat_file:
        for line in stat_file:
            if line.startswith("btime "):
                boot_time = int(line[len("btime "):-1])
                break
    if boot_time is None:
        return

    with open('/proc/%d/stat' % pid) as stat_file:
        ps_stat = stat_file.read().split()
        ps['start_time'] = boot_time + jiffies_to_seconds(ps_stat[21])
        ps['state'] = {'R' : _('Running'),
                       'S' : _('Sleeping'),
                       'D' : _('Uninterruptible'),
                       'Z' : _('Zombie'),
                       'T' : _('Traced/Stopped')
                       }.get(ps_stat[2], _('Unknown'))

    return ps


def show_lock_owner(pid):
    """Output information about process holding a lock."""

    ps = get_process_info(pid)
    if not ps:
        msg = _('Unable to find information about the locking process (PID %d)')
        logger.critical(msg, pid)
        return

    msg = _('  The application with PID %d is: %s') % (pid, ps['name'])

    logger.critical("%s", msg)
    logger.critical(_("    Memory : %5s RSS (%5sB VSZ)"),
                    format_number(int(ps['vmrss']) * 1024),
                    format_number(int(ps['vmsize']) * 1024))

    ago = seconds_to_ui_time(int(time.time()) - ps['start_time'])
    logger.critical(_('    Started: %s - %s ago'),
                    dnf.util.normalize_time(ps['start_time']), ago)
    logger.critical(_('    State  : %s'), ps['state'])

    return
