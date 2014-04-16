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
from __future__ import unicode_literals
import dnf.exceptions
import dnf.const
import dnf.util
import logging
import os
import sys
import warnings

# :api loggers are: 'dnf', 'dnf.plugin', 'dnf.rpm'

SUPERCRITICAL = 100 # do not use this for logging
CRITICAL      = logging.CRITICAL
ERROR         = logging.ERROR
WARNING       = logging.WARNING
INFO          = logging.INFO
DEBUG         = logging.DEBUG
SUBDEBUG      = 6

def only_once(fn):
    """Method decorator turning the method into noop on second or later calls."""
    def noop(*args, **kwargs):
        pass
    def swan_song(self, *args, **kwargs):
        fn(self, *args, **kwargs)
        setattr(self, fn.__name__, noop)
    return swan_song

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
        dnf.util.ensure_dir(os.path.dirname(logfile))
        dnf.util.touch(logfile)
        # By default, make logfiles readable by the user (so the reporting ABRT
        # user can attach root logfiles).
        os.chmod(logfile, 0o644)
    handler = logging.FileHandler(logfile)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                                  "%b %d %H:%M:%S")
    handler.setFormatter(formatter)
    return handler

def _paint_mark(logger):
    logger.log(INFO, dnf.const.LOG_MARKER)

def depr(msg):
    warnings.warn(msg, dnf.exceptions.DeprecationWarning, 2)

class Logging(object):
    def __init__(self):
        self.stdout_handler = self.stderr_handler = None

    @only_once
    def presetup(self):
        logging.addLevelName(SUBDEBUG, "SUBDEBUG")
        logger_dnf = logging.getLogger("dnf")
        logger_dnf.setLevel(SUBDEBUG)

        # setup stdout
        stdout = logging.StreamHandler(sys.stdout)
        stdout.setLevel(INFO)
        stdout.addFilter(MaxLevelFilter(logging.WARNING))
        logger_dnf.addHandler(stdout)
        self.stdout_handler = stdout

        # setup stderr
        stderr = logging.StreamHandler(sys.stderr)
        stderr.setLevel(WARNING)
        logger_dnf.addHandler(stderr)
        self.stderr_handler = stderr

    @only_once
    def setup(self, verbose_level, error_level, logdir):
        self.presetup()
        logger_dnf = logging.getLogger("dnf")

        # setup file logger
        logfile = os.path.join(logdir, dnf.const.LOG)
        handler = _create_filehandler(logfile)
        logger_dnf.addHandler(handler)
        # temporarily turn off stdout/stderr handlers:
        self.stdout_handler.setLevel(SUPERCRITICAL)
        self.stderr_handler.setLevel(SUPERCRITICAL)
        # put the marker in the file now:
        _paint_mark(logger_dnf)
        # bring std handlers to the preferred level
        self.stdout_handler.setLevel(verbose_level)
        self.stderr_handler.setLevel(error_level)

        # setup Python warnings
        logging.captureWarnings(True)
        logger_warnings = logging.getLogger("py.warnings")
        logger_warnings.addHandler(self.stderr_handler)
        logger_warnings.addHandler(handler)

        # setup RPM callbacks logger
        logger_rpm = logging.getLogger("dnf.rpm")
        logger_rpm.propagate = False
        logger_rpm.setLevel(SUBDEBUG)
        logfile = os.path.join(logdir, dnf.const.LOG_RPM)
        handler = _create_filehandler(logfile)
        logger_rpm.addHandler(handler)
        _paint_mark(logger_rpm)

    def setup_from_dnf_conf(self, conf):
        verbose_level_r = _cfg_verbose_val2level(conf.debuglevel)
        error_level_r = _cfg_err_val2level(conf.errorlevel)
        logdir = conf.logdir
        return self.setup(verbose_level_r, error_level_r, logdir)
