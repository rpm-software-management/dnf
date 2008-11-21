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


"""
Custom logging levels for finer-grained logging using python's standard
logging module.
"""

import os
import socket
import sys
import logging
import logging.handlers
import time

# logging.info() == 20
INFO    = logging.INFO # Quiet
assert INFO == 20
INFO_1  = 19
INFO_2  = 18 # Normal
INFO_3  = 17 # Verbose

DEBUG   = logging.DEBUG
assert DEBUG == 10
DEBUG_1 = 9
DEBUG_2 = 8
DEBUG_3 = 7
DEBUG_4 = 6

logging.addLevelName(INFO_1, "INFO_1")
logging.addLevelName(INFO_2, "INFO_2")
logging.addLevelName(INFO_2, "INFO_3")

logging.addLevelName(DEBUG_1, "DEBUG_1")
logging.addLevelName(DEBUG_2, "DEBUG_2")
logging.addLevelName(DEBUG_3, "DEBUG_3")
logging.addLevelName(DEBUG_4, "DEBUG_4")

# High level to effectively turn off logging.
# For compatability with the old logging system.
__NO_LOGGING = 100
logging.raiseExceptions = False

import syslog as syslog_module

syslog = None

DEBUG_QUIET_LEVEL   = 0
DEBUG_NORMAL_LEVEL  = 2
DEBUG_VERBOSE_LEVEL = 3
DEBUG_DEBUG0_LEVEL  = 4
DEBUG_DEBUG1_LEVEL  = 5
DEBUG_DEBUG2_LEVEL  = 6
DEBUG_DEBUG3_LEVEL  = 7
DEBUG_DEBUG4_LEVEL  = 8
DEBUG_UPDATES_LEVEL = DEBUG_DEBUG3_LEVEL

DEBUG_MIN_LEVEL     = 0
DEBUG_MAX_LEVEL     = DEBUG_DEBUG4_LEVEL

ERROR_NORMAL_LEVEL  = 1
ERROR_VERBOSE_LEVEL = 2

ERROR_MIN_LEVEL     = 0
ERROR_MAX_LEVEL     = ERROR_VERBOSE_LEVEL

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
    return syslog.LOG_USER

def logLevelFromErrorLevel(error_level):
    """ Convert an old-style error logging level to the new style. """
    error_table = { -1 : __NO_LOGGING,
                    0 : logging.CRITICAL, 1 : logging.ERROR, 2 :logging.WARNING}
    
    return __convertLevel(error_level, error_table)

def logLevelFromDebugLevel(debug_level):
    """ Convert an old-style debug logging level to the new style. """
    debug_table = {-1 : __NO_LOGGING,
                   0 : INFO,  1 : INFO_1,  2 : INFO_2,  3 : INFO_3,
                   4 : DEBUG, 5 : DEBUG_1, 6 : DEBUG_2, 7 : DEBUG_3, 8 :DEBUG_4}

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

def setDebugLevel(level):
    converted_level = logLevelFromDebugLevel(level)
    logging.getLogger("yum.verbose").setLevel(converted_level)
    
def setErrorLevel(level):
    converted_level = logLevelFromErrorLevel(level)
    logging.getLogger("yum").setLevel(converted_level)

_added_handlers = False
def doLoggingSetup(debuglevel, errorlevel,
                   syslog_ident=None, syslog_facility=None):
    """
    Configure the python logger.
    
    errorlevel is optional. If provided, it will override the logging level
    provided in the logging config file for error messages.
    debuglevel is optional. If provided, it will override the logging level
    provided in the logging config file for debug messages.
    """
    global _added_handlers

    logging.basicConfig()

    if _added_handlers:
        if debuglevel is not None:
            setDebugLevel(debuglevel)
        if errorlevel is not None:  
            setErrorLevel(errorlevel)
        return

    plainformatter = logging.Formatter("%(message)s")
    syslogformatter = logging.Formatter("yum: %(message)s")
    
    console_stdout = logging.StreamHandler(sys.stdout)
    console_stdout.setFormatter(plainformatter)
    verbose = logging.getLogger("yum.verbose")
    verbose.propagate = False
    verbose.addHandler(console_stdout)
        
    console_stderr = logging.StreamHandler(sys.stderr)
    console_stderr.setFormatter(plainformatter)
    logger = logging.getLogger("yum")
    logger.propagate = False
    logger.addHandler(console_stderr)
   
    filelogger = logging.getLogger("yum.filelogging")
    filelogger.setLevel(INFO)
    filelogger.propagate = False

    log_dev = '/dev/log'
    global syslog
    if os.path.exists(log_dev):
        try:
            syslog = logging.handlers.SysLogHandler(log_dev)
            syslog.setFormatter(syslogformatter)
            filelogger.addHandler(syslog)
            if syslog_ident is not None or syslog_facility is not None:
                ident = syslog_ident    or ''
                facil = syslog_facility or 'LOG_USER'
                syslog_module.openlog(ident, 0, syslogFacilityMap(facil))
        except socket.error:
            if syslog is not None:
                syslog.close()
    _added_handlers = True

    if debuglevel is not None:
        setDebugLevel(debuglevel)
    if errorlevel is not None:  
        setErrorLevel(errorlevel)

def setFileLog(uid, logfile):
    # TODO: When python's logging config parser doesn't blow up
    # when the user is non-root, put this in the config file.
    # syslog-style log
    if uid == 0:
        try:
            # For installroot etc.
            logdir = os.path.dirname(logfile)
            if not os.path.exists(logdir):
                os.makedirs(logdir, mode=0755)

            filelogger = logging.getLogger("yum.filelogging")
            filehandler = logging.FileHandler(logfile)
            formatter = logging.Formatter("%(asctime)s %(message)s",
                "%b %d %H:%M:%S")
            filehandler.setFormatter(formatter)
            filelogger.addHandler(filehandler)
        except IOError:
            logging.getLogger("yum").critical('Cannot open logfile %s', logfile)

def setLoggingApp(app):
    if syslog:
        syslogformatter = logging.Formatter("yum(%s): "% (app,) + "%(message)s")
        syslog.setFormatter(syslogformatter)

class EasyLogger:
    """ Smaller to use logger for yum, wraps "logging.getLogger" module. """

    def __init__(self, name="main"):
        self.name   = name
        self.logger = logging.getLogger(name)

    def info(self, msg, *args):
        """ Log a message as info. Output even in quiet mode. """

        self.logger.info(msg % args)

    def info1(self, msg, *args):
        """ Log a message as log.INFO_1. Output in normal/verbose mode. """

        self.logger.log(INFO_1, msg % args)

    def info2(self, msg, *args):
        """ Log a message as log.INFO_2. Output in normal/verbose mode. """

        self.logger.log(INFO_2, msg % args)

    def info3(self, msg, *args):
        """ Log a message as log.INFO_3. Output in verbose mode. """

        self.logger.log(INFO_3, msg % args)

    def warn(self, msg, *args):
        """ Log a message as warning. """

        self.logger.warning(msg % args)

    # NOTE: Is "error" worthwhile, it's either warning, critical or an exception
    def error(self, msg, *args):
        """ Log a message as error. """

        self.logger.error(msg % args)

    def critical(self, msg, *args):
        """ Log a message as critical. """

        self.logger.critical(msg % args)

    def debug(self, msg, *args):
        """ Log a message as debug. """

        self.logger.debug(msg % args)

    def debug_tm(self, oldtm, msg, *args):
        """ Log a message as debug, with a timestamp delta. """

        now = time.time()
        out = msg % args
        self.debug("%s: time=%.4f" % (out, now - oldtm))

    def debug1(self, msg, *args):
        """ Log a message as log.DEBUG_1. """

        self.logger.log(DEBUG_1, msg % args)

    def debug2(self, msg, *args):
        """ Log a message as log.DEBUG_2. """

        self.logger.log(DEBUG_2, msg % args)

    def debug3(self, msg, *args):
        """ Log a message as log.DEBUG_3. """

        self.logger.log(DEBUG_3, msg % args)

    def debug4(self, msg, *args):
        """ Log a message as log.DEBUG_4. """

        self.logger.log(DEBUG_4, msg % args)

    def isEnabledFor(self, level):
        """ Wrap self.logger.isEnabledFor() """
        return self.logger.isEnabledFor(level)

    def verbose(self):
        """ Is this logger in "yum verbose" mode. """
        return self.isEnabledFor(INFO_3)
