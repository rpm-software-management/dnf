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

def setDebugLevel(level):
    converted_level = logLevelFromDebugLevel(level)
    logging.getLogger("yum.verbose").setLevel(converted_level)
    
def setErrorLevel(level):
    converted_level = logLevelFromErrorLevel(level)
    logging.getLogger("yum").setLevel(converted_level)

def doLoggingSetup(debuglevel, errorlevel):
    """
    Configure the python logger.
    
    errorlevel is optional. If provided, it will override the logging level
    provided in the logging config file for error messages.
    debuglevel is optional. If provided, it will override the logging level
    provided in the logging config file for debug messages.
    """

    logging.basicConfig()

    plainformatter = logging.Formatter("%(message)s")
        
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
    filelogger.setLevel(logging.INFO)
    filelogger.propagate = False

    log_dev = '/dev/log'
    syslog = None
    if os.path.exists(log_dev):
        try:
            syslog = logging.handlers.SysLogHandler(log_dev)
            syslog.setFormatter(plainformatter)
            filelogger.addHandler(syslog)
        except socket.error:
            if syslog is not None:
                syslog.close()

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
            filelogger = logging.getLogger("yum.filelogging")
            filehandler = logging.FileHandler(logfile)
            formatter = logging.Formatter("%(asctime)s %(message)s",
                "%b %d %H:%M:%S")
            filehandler.setFormatter(formatter)
            filelogger.addHandler(filehandler)
        #FIXME: XXX: A global exception catch? That seems unlikely.
        except Exception:
            logging.getLogger("yum").critical('Cannot open logfile %s', logfile)
