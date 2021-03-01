# logging.py
# DNF Logging Subsystem.
#
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
#

from __future__ import absolute_import
from __future__ import unicode_literals
import dnf.exceptions
import dnf.const
import dnf.lock
import dnf.util
import libdnf.repo
import logging
import logging.handlers
import os
import sys
import time
import warnings
import gzip

# :api loggers are: 'dnf', 'dnf.plugin', 'dnf.rpm'

SUPERCRITICAL = 100 # do not use this for logging
CRITICAL = logging.CRITICAL
ERROR = logging.ERROR
WARNING = logging.WARNING
INFO = logging.INFO
DEBUG = logging.DEBUG
DDEBUG = 8  # used by anaconda (pyanaconda/payload/dnfpayload.py)
SUBDEBUG = 6
TRACE = 4
ALL = 2

def only_once(func):
    """Method decorator turning the method into noop on second or later calls."""
    def noop(*_args, **_kwargs):
        pass
    def swan_song(self, *args, **kwargs):
        func(self, *args, **kwargs)
        setattr(self, func.__name__, noop)
    return swan_song

class _MaxLevelFilter(object):
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
    7 : DDEBUG,
    8 : SUBDEBUG,
    9 : TRACE,
    10: ALL,   # more verbous librepo and hawkey
    }

def _cfg_verbose_val2level(cfg_errval):
    assert 0 <= cfg_errval <= 10
    return _VERBOSE_VAL_MAPPING.get(cfg_errval, TRACE)


# Both the DNF default and the verbose default are WARNING. Note that ERROR has
# no specific level.
_ERR_VAL_MAPPING = {
    0: SUPERCRITICAL,
    1: logging.CRITICAL,
    2: logging.ERROR
    }

def _cfg_err_val2level(cfg_errval):
    assert 0 <= cfg_errval <= 10
    return _ERR_VAL_MAPPING.get(cfg_errval, logging.WARNING)


def compression_namer(name):
    return name + ".gz"


CHUNK_SIZE = 128 * 1024 # 128 KB


def compression_rotator(source, dest):
    with open(source, "rb") as sf:
        with gzip.open(dest, 'wb') as wf:
            while True:
                data = sf.read(CHUNK_SIZE)
                if not data:
                    break
                wf.write(data)
    os.remove(source)


class MultiprocessRotatingFileHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, encoding=None, delay=False):
        super(MultiprocessRotatingFileHandler, self).__init__(
            filename, mode, maxBytes, backupCount, encoding, delay)
        self.rotate_lock = dnf.lock.build_log_lock("/var/log/", True)

    def emit(self, record):
        while True:
            try:
                if self.shouldRollover(record):
                    with self.rotate_lock:
                        # Do rollover while preserving the mode of the new log file
                        mode = os.stat(self.baseFilename).st_mode
                        self.doRollover()
                        os.chmod(self.baseFilename, mode)
                logging.FileHandler.emit(self, record)
                return
            except (dnf.exceptions.ProcessLockError, dnf.exceptions.ThreadLockError):
                time.sleep(0.01)
            except Exception:
                self.handleError(record)
                return


def _create_filehandler(logfile, log_size, log_rotate, log_compress):
    if not os.path.exists(logfile):
        dnf.util.ensure_dir(os.path.dirname(logfile))
        dnf.util.touch(logfile)
    handler = MultiprocessRotatingFileHandler(logfile, maxBytes=log_size, backupCount=log_rotate)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s",
                                  "%Y-%m-%dT%H:%M:%S%z")
    formatter.converter = time.localtime
    handler.setFormatter(formatter)
    if log_compress:
        handler.rotator = compression_rotator
        handler.namer = compression_namer
    return handler

def _paint_mark(logger):
    logger.log(INFO, dnf.const.LOG_MARKER)


class Logging(object):
    def __init__(self):
        self.stdout_handler = self.stderr_handler = None
        logging.addLevelName(DDEBUG, "DDEBUG")
        logging.addLevelName(SUBDEBUG, "SUBDEBUG")
        logging.addLevelName(TRACE, "TRACE")
        logging.addLevelName(ALL, "ALL")
        logging.captureWarnings(True)
        logging.raiseExceptions = False

    @only_once
    def _presetup(self):
        logger_dnf = logging.getLogger("dnf")
        logger_dnf.setLevel(TRACE)

        # setup stdout
        stdout = logging.StreamHandler(sys.stdout)
        stdout.setLevel(INFO)
        stdout.addFilter(_MaxLevelFilter(logging.WARNING))
        logger_dnf.addHandler(stdout)
        self.stdout_handler = stdout

        # setup stderr
        stderr = logging.StreamHandler(sys.stderr)
        stderr.setLevel(WARNING)
        logger_dnf.addHandler(stderr)
        self.stderr_handler = stderr

    @only_once
    def _setup_file_loggers(self, logfile_level, logdir, log_size, log_rotate, log_compress):
        logger_dnf = logging.getLogger("dnf")
        logger_dnf.setLevel(TRACE)

        # setup file logger
        logfile = os.path.join(logdir, dnf.const.LOG)
        handler = _create_filehandler(logfile, log_size, log_rotate, log_compress)
        handler.setLevel(logfile_level)
        logger_dnf.addHandler(handler)

        # setup Python warnings
        logger_warnings = logging.getLogger("py.warnings")
        logger_warnings.addHandler(handler)

        logger_librepo = logging.getLogger("librepo")
        logger_librepo.setLevel(TRACE)
        logfile = os.path.join(logdir, dnf.const.LOG_LIBREPO)
        handler = _create_filehandler(logfile, log_size, log_rotate, log_compress)
        logger_librepo.addHandler(handler)
        libdnf.repo.LibrepoLog.addHandler(logfile, logfile_level <= ALL)

        # setup RPM callbacks logger
        logger_rpm = logging.getLogger("dnf.rpm")
        logger_rpm.propagate = False
        logger_rpm.setLevel(SUBDEBUG)
        logfile = os.path.join(logdir, dnf.const.LOG_RPM)
        handler = _create_filehandler(logfile, log_size, log_rotate, log_compress)
        logger_rpm.addHandler(handler)

    @only_once
    def _setup(self, verbose_level, error_level, logfile_level, logdir, log_size, log_rotate, log_compress):
        self._presetup()

        self._setup_file_loggers(logfile_level, logdir, log_size, log_rotate, log_compress)

        logger_warnings = logging.getLogger("py.warnings")
        logger_warnings.addHandler(self.stderr_handler)

        # setup RPM callbacks logger
        logger_rpm = logging.getLogger("dnf.rpm")
        logger_rpm.addHandler(self.stdout_handler)
        logger_rpm.addHandler(self.stderr_handler)

        logger_dnf = logging.getLogger("dnf")
        # temporarily turn off stdout/stderr handlers:
        self.stdout_handler.setLevel(WARNING)
        self.stderr_handler.setLevel(WARNING)
        _paint_mark(logger_dnf)
        _paint_mark(logger_rpm)
        # bring std handlers to the preferred level
        self.stdout_handler.setLevel(verbose_level)
        self.stderr_handler.setLevel(error_level)

    def _setup_from_dnf_conf(self, conf, file_loggers_only=False):
        verbose_level_r = _cfg_verbose_val2level(conf.debuglevel)
        error_level_r = _cfg_err_val2level(conf.errorlevel)
        logfile_level_r = _cfg_verbose_val2level(conf.logfilelevel)
        logdir = conf.logdir
        log_size = conf.log_size
        log_rotate = conf.log_rotate
        log_compress = conf.log_compress
        if file_loggers_only:
            return self._setup_file_loggers(logfile_level_r, logdir, log_size, log_rotate, log_compress)
        else:
            return self._setup(
                verbose_level_r, error_level_r, logfile_level_r, logdir, log_size, log_rotate, log_compress)


class Timer(object):
    def __init__(self, what):
        self.what = what
        self.start = time.time()

    def __call__(self):
        diff = time.time() - self.start
        msg = 'timer: %s: %d ms' % (self.what, diff * 1000)
        logging.getLogger("dnf").log(DDEBUG, msg)


_LIBDNF_TO_DNF_LOGLEVEL_MAPPING = {
    libdnf.utils.Logger.Level_CRITICAL: CRITICAL,
    libdnf.utils.Logger.Level_ERROR: ERROR,
    libdnf.utils.Logger.Level_WARNING: WARNING,
    libdnf.utils.Logger.Level_NOTICE: INFO,
    libdnf.utils.Logger.Level_INFO: INFO,
    libdnf.utils.Logger.Level_DEBUG: DEBUG,
    libdnf.utils.Logger.Level_TRACE: TRACE
}


class LibdnfLoggerCB(libdnf.utils.Logger):
    def __init__(self):
        super(LibdnfLoggerCB, self).__init__()
        self._dnf_logger = logging.getLogger("dnf")
        self._librepo_logger = logging.getLogger("librepo")

    def write(self, source, *args):
        """Log message.

        source -- integer, defines origin (libdnf, librepo, ...) of message, 0 - unknown
        """
        if len(args) == 2:
            level, message = args
        elif len(args) == 4:
            time, pid, level, message = args
        if source == libdnf.utils.Logger.LOG_SOURCE_LIBREPO:
            self._librepo_logger.log(_LIBDNF_TO_DNF_LOGLEVEL_MAPPING[level], message)
        else:
            self._dnf_logger.log(_LIBDNF_TO_DNF_LOGLEVEL_MAPPING[level], message)


libdnfLoggerCB = LibdnfLoggerCB()
libdnf.utils.Log.setLogger(libdnfLoggerCB)
