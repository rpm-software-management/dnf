# Copyright (C) 2013-2016 Red Hat, Inc.
#
# This copyrighted material is made available to anyone wishing to use,
# modify, copy, or redistribute it subject to the terms and conditions of
# the GNU General Public License v.2, or (at your option) any later version.
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY expressed or implied, including the implied warranties of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
# Public License for more details.  You should have received a copy of the
# GNU General Public License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
# 02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
# source code or documentation are not subject to the GNU General Public
# License and may only be used or replicated with the express permission of
# Red Hat, Inc.

from __future__ import unicode_literals
from dnf.pycomp import long

def format_number(number, SI=0, space=' '):
    """Return a human-readable metric-like string representation
    of a number.

    :param number: the number to be converted to a human-readable form
    :param SI: If is 0, this function will use the convention
       that 1 kilobyte = 1024 bytes, otherwise, the convention
       that 1 kilobyte = 1000 bytes will be used
    :param space: string that will be placed between the number
       and the SI prefix
    :return: a human-readable metric-like string representation of
       *number*
    """

    # copied from from urlgrabber.progress
    symbols = [ ' ', # (none)
                'k', # kilo
                'M', # mega
                'G', # giga
                'T', # tera
                'P', # peta
                'E', # exa
                'Z', # zetta
                'Y'] # yotta

    if SI: step = 1000.0
    else: step = 1024.0

    thresh = 999
    depth = 0
    max_depth = len(symbols) - 1

    if number is None:
        number = 0.0

    # we want numbers between 0 and thresh, but don't exceed the length
    # of our list.  In that event, the formatting will be screwed up,
    # but it'll still show the right number.
    while number > thresh and depth < max_depth:
        depth  = depth + 1
        number = number / step

    if isinstance(number, int) or isinstance(number, long):
        format = '%i%s%s'
    elif number < 9.95:
        # must use 9.95 for proper sizing.  For example, 9.99 will be
        # rounded to 10.0 with the .1f format string (which is too long)
        format = '%.1f%s%s'
    else:
        format = '%.0f%s%s'

    return(format % (float(number or 0), space, symbols[depth]))

def format_time(seconds, use_hours=0):
    """Return a human-readable string representation of a number
    of seconds.  The string will show seconds, minutes, and
    optionally hours.

    :param seconds: the number of seconds to convert to a
       human-readable form
    :param use_hours: If use_hours is 0, the representation will
       be in minutes and seconds. Otherwise, it will be in hours,
       minutes, and seconds
    :return: a human-readable string representation of *seconds*
    """

    # copied from from urlgrabber.progress
    if seconds is None or seconds < 0:
        if use_hours: return '--:--:--'
        else:         return '--:--'
    elif seconds == float('inf'):
        return 'Infinite'
    else:
        seconds = int(seconds)
        minutes = seconds // 60
        seconds = seconds % 60
        if use_hours:
            hours = minutes // 60
            minutes = minutes % 60
            return '%02i:%02i:%02i' % (hours, minutes, seconds)
        else:
            return '%02i:%02i' % (minutes, seconds)

def indent_block(s):
    return '\n'.join('  ' + s for s in s.splitlines())
