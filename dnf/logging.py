# logging.py
# DNF Logging Subsystem.
#
# Copyright (C) 2013  Red Hat, Inc.
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
#

from __future__ import absolute_import
import dnf.const
import dnf.util
import logging
import os
import sys

SUPERCRITICAL = 100 # do not use this for logging
CRITICAL      = logging.CRITICAL
ERROR         = logging.ERROR
WARNING       = logging.WARNING
INFO          = logging.INFO
DEBUG         = logging.DEBUG
SUBDEBUG      = 6

class MaxLevelFilter(object):
    def __init__(self, max_level):
        self.max_level = max_level

    def filter(self, record):
        if record.levelno >= self.max_level:
            return 0
        return 1

_VERBOSE_VAL_MAPPING = {
    0 : SUPERCRITICAL,
    1 : logging.INFO,
    2 : logging.INFO, # the default
    3 : logging.DEBUG,
    4 : logging.DEBUG,
    5 : logging.DEBUG,
    6 : logging.DEBUG, # verbose value
    }

def _cfg_verbose_val2level(cfg_errval):
    assert(0 <= cfg_errval <= 10)
    return _VERBOSE_VAL_MAPPING.get(cfg_errval, SUBDEBUG)

# Both the DNF default and the verbose default are WARNING. Note that ERROR has
# no specific level.
_ERR_VAL_MAPPING = {
    0 : SUPERCRITICAL,
    1 : logging.CRITICAL
    }

def _cfg_err_val2level(cfg_errval):
    assert(0 <= cfg_errval <= 10)
    return _ERR_VAL_MAPPING.get(cfg_errval, logging.WARNING)

def _create_filehandler(logfile):
    if not os.path.exists(logfile):
        dnf.util.touch(logfile)
        # By default, make logfiles readable by the user (so the reporting ABRT
        # user can attach root logfiles).
        os.chmod(logfile, 0644)
    handler = logging.FileHandler(logfile)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                                  "%b %d %H:%M:%S")
    handler.setFormatter(formatter)
    return handler

def setup(verbose_level, error_level, logdir):
    logging.addLevelName(SUBDEBUG, "SUBDEBUG")
    logger_dnf = logging.getLogger("dnf")
    logger_dnf.setLevel(SUBDEBUG)

    # setup stdout
    stdout = logging.StreamHandler(sys.stdout)
    stdout.setLevel(verbose_level)
    stdout.addFilter(MaxLevelFilter(logging.WARNING))
    logger_dnf.addHandler(stdout)

    # setup stderr
    stderr = logging.StreamHandler(sys.stderr)
    stderr.setLevel(error_level)
    logger_dnf.addHandler(stderr)

    # setup file logger
    logfile = os.path.join(logdir, dnf.const.LOG)
    handler = _create_filehandler(logfile)
    logger_dnf.addHandler(handler)

    # setup RPM callbacks logger
    logger_rpm = logging.getLogger("dnf.rpm")
    logger_rpm.propagate = False
    logger_rpm.setLevel(SUBDEBUG)
    logfile = os.path.join(logdir, dnf.const.LOG_RPM)
    handler = _create_filehandler(logfile)
    logger_rpm.addHandler(handler)

def setup_from_dnf_levels(verbose_level, error_level, logdir):
    verbose_level_r = _cfg_verbose_val2level(verbose_level)
    error_level_r = _cfg_err_val2level(error_level)
    return setup(verbose_level_r, error_level_r, logdir)
