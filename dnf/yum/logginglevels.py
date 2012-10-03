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


"""
Custom logging levels for finer-grained logging using python's standard
logging module.
"""

import os
import socket
import sys
import logging
import logging.handlers
import dnf.const

INFO_1 = 19
INFO_2 = 18

DEBUG_1 = 9
DEBUG_2 = 8
DEBUG_3 = 7
DEBUG_4 = 6

logging.addLevelName(INFO_1, "INFO_1")
logging.addLevelName(INFO_2, "INFO_2")

logging.addLevelName(DEBUG_1, "DEBUG_1")
logging.addLevelName(DEBUG_2, "DEBUG_2")
logging.addLevelName(DEBUG_3, "DEBUG_3")
logging.addLevelName(DEBUG_4, "DEBUG_4")

# High level to effectively turn off logging.
# For compatability with the old logging system.
__NO_LOGGING = 100
logging.raiseExceptions = False

from logging.handlers import SysLogHandler as syslog_module

syslog = None

# Mostly borrowed from original yum-updated.py
_syslog_facility_map = { "KERN"   : syslog_module.LOG_KERN,
                         "USER"   : syslog_module.LOG_USER,
                         "MAIL"   : syslog_module.LOG_MAIL,
                         "DAEMON" : syslog_module.LOG_DAEMON,
                         "AUTH"   : syslog_module.LOG_AUTH,
                         "LPR"    : syslog_module.LOG_LPR,
                         "NEWS"   : syslog_module.LOG_NEWS,
                         "UUCP"   : syslog_module.LOG_UUCP,
                         "CRON"   : syslog_module.LOG_CRON,
                         "LOCAL0" : syslog_module.LOG_LOCAL0,
                         "LOCAL1" : syslog_module.LOG_LOCAL1,
                         "LOCAL2" : syslog_module.LOG_LOCAL2,
                         "LOCAL3" : syslog_module.LOG_LOCAL3,
                         "LOCAL4" : syslog_module.LOG_LOCAL4,
                         "LOCAL5" : syslog_module.LOG_LOCAL5,
                         "LOCAL6" : syslog_module.LOG_LOCAL6,
                         "LOCAL7" : syslog_module.LOG_LOCAL7,}
def syslogFacilityMap(facility):
    if type(facility) == int:
        return facility
    elif facility.upper() in _syslog_facility_map:
        return _syslog_facility_map[facility.upper()]
    elif (facility.upper().startswith("LOG_") and
          facility[4:].upper() in _syslog_facility_map):
        return _syslog_facility_map[facility[4:].upper()]
    return _syslog_facility_map["USER"]

def logLevelFromErrorLevel(error_level):
    """ Convert an old-style error logging level to the new style. """
    error_table = { -1 : __NO_LOGGING, 0 : logging.CRITICAL, 1 : logging.ERROR,
        2 : logging.WARNING}

    return __convertLevel(error_level, error_table)

def logLevelFromDebugLevel(debug_level):
    """ Convert an old-style debug logging level to the new style. """
    debug_table = {-1 : __NO_LOGGING, 0 : logging.INFO, 1 : INFO_1, 2 : INFO_2,
        3 : logging.DEBUG, 4 : DEBUG_1, 5 : DEBUG_2, 6 : DEBUG_3, 7 : DEBUG_4}

    return __convertLevel(debug_level, debug_table)

def __convertLevel(level, table):
    """ Convert yum logging levels using a lookup table. """
    # Look up level in the table.
    try:
        new_level = table[level]
    except KeyError:
        keys = table.keys()
        # We didn't find the level in the table, check if it's smaller
        # than the smallest level
        if level < keys[0]:
            new_level = table[keys[0]]
        # Nope. So it must be larger.
        else:
            new_level =  table[keys[-2]]

    return new_level

def doLoggingSetup(debuglevel, errorlevel,
                   syslog_ident=None, syslog_facility=None,
                   syslog_device='/dev/log'):
    """
    Configure the python logger.

    errorlevel is optional. If provided, it will override the logging level
    provided in the logging config file for error messages.
    debuglevel is optional. If provided, it will override the logging level
    provided in the logging config file for debug messages.
    """
    # set up the basic loggers, max them out for general (file) output
    plainformatter = logging.Formatter("%(message)s")

    console_stdout = logging.StreamHandler(sys.stdout)
    console_stdout.setFormatter(plainformatter)
    verbose = logging.getLogger("yum.verbose")
    verbose.setLevel(DEBUG_4)
    verbose.propagate = False
    verbose.addHandler(console_stdout)

    console_stderr = logging.StreamHandler(sys.stderr)
    console_stderr.setFormatter(plainformatter)
    logger = logging.getLogger("yum")
    logger.setLevel(DEBUG_4)
    logger.propagate = False
    logger.addHandler(console_stderr)

    filelogger = logging.getLogger("yum.filelogging")
    filelogger.setLevel(logging.INFO)
    filelogger.propagate = False

    # limit what goes into console according to user settings:
    console_stdout.setLevel(logLevelFromDebugLevel(debuglevel))
    console_stderr.setLevel(logLevelFromErrorLevel(errorlevel))

    global syslog
    if syslog_device:
        address = None
        if ":" in syslog_device:
            address = syslog_device.rsplit(":", 1)
            address = (address[0], int(address[1]))
        elif os.path.exists(syslog_device):
            address = syslog_device
        if address:
            try:
                facil = syslogFacilityMap(syslog_facility or "USER")
                syslog = logging.handlers.SysLogHandler(address, facil)
            except socket.error:
                if syslog is not None:
                    syslog.close()
            else:
                setLoggingApp(syslog_ident or "yum")
                filelogger.addHandler(syslog)

def setFileLogs(logdir, cleanup):
    try:
        if not os.path.exists(logdir):
            os.makedirs(logdir, mode=0755)
        mainhandler = _setFileLog(logging.getLogger("yum"),
                                  os.path.join(logdir, dnf.const.LOG), cleanup)
        _setFileLog(logging.getLogger("yum.filelogging"),
                    os.path.join(logdir, dnf.const.LOG_TRANSACTION), cleanup)
        # the main log file should end up knowing everything:
        logging.getLogger("yum.verbose").addHandler(mainhandler)
        logging.getLogger("yum.filelogging").addHandler(mainhandler)
    except IOError:
        logging.getLogger("yum").critical('Cannot open logfile %s', logfile)

def _setFileLog(logger, logfile, cleanup=None):
    # For installroot etc.
    if not os.path.exists(logfile):
        f = open(logfile, 'w')
        os.chmod(logfile, 0600) # making sure umask doesn't catch us up
        f.close()

    filehandler = logging.FileHandler(logfile)
    formatter = logging.Formatter("%(asctime)s %(message)s",
        "%b %d %H:%M:%S")
    filehandler.setFormatter(formatter)
    logger.addHandler(filehandler)
    if cleanup is not None:
        cleanup.append(lambda: logger.removeHandler(filehandler))
    return filehandler

def setLoggingApp(app):
    if syslog:
        syslogformatter = logging.Formatter(app + "[%(process)d]: %(message)s")
        syslog.setFormatter(syslogformatter)

def is_stdout_verbose(debuglevel):
    loglevel = logLevelFromDebugLevel(debuglevel)
    return loglevel <= logging.DEBUG
