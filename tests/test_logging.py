# -*- coding: utf-8 -*-

# Copyright (C) 2013-2018  Red Hat, Inc.
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

import logging
import collections
import operator
import os
import tempfile

import dnf.const
import dnf.logging

import tests.support
from tests.support import mock


LogfileEntry = collections.namedtuple('LogfileEntry', ('date', 'time', 'message'))


def _split_logfile_entry(entry):
    record = entry.split(' ')
    datetime = record[0].split('T')
    # strip the trailing '\n' from the message:
    message = ' '.join(record[2:])[:-1]
    return LogfileEntry(date=datetime[0],
                        time=datetime[1], message=message)


def drop_all_handlers():
    for logger_name in ('dnf', 'dnf.rpm'):
        logger = logging.getLogger(logger_name)
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)


class TestLogging(tests.support.TestCase):
    """Tests the logging mechanisms in DNF.

    If it causes a problem in the future that loggers are singletons that don't
    get torn down between tests, look at logging.Manager internals.

    """

    def setUp(self):
        self.logdir = tempfile.mkdtemp(prefix="dnf-logtest-")
        self.log_size = 1024 * 1024
        self.log_rotate = 4
        self.logging = dnf.logging.Logging()

    def tearDown(self):
        drop_all_handlers()
        dnf.util.rm_rf(self.logdir)

    @staticmethod
    def _bench(logger):
        logger.debug(u"d")
        logger.info(u"i")
        logger.warning(u"w")
        logger.error(u"e")

    def test_level_conversion(self):
        self.assertRaises(AssertionError, dnf.logging._cfg_verbose_val2level, 11)
        self.assertEqual(dnf.logging._cfg_verbose_val2level(0),
                         dnf.logging.SUPERCRITICAL)
        self.assertEqual(dnf.logging._cfg_verbose_val2level(7),
                         dnf.logging.DDEBUG)

    def test_setup(self):
        logger = logging.getLogger("dnf")
        with tests.support.patch_std_streams() as (stdout, stderr):
            self.logging._setup(
                logging.INFO, logging.ERROR, self.logdir, self.log_size, self.log_rotate)
            self._bench(logger)
        self.assertEqual("i\n", stdout.getvalue())
        self.assertEqual("e\n", stderr.getvalue())

    def test_setup_verbose(self):
        logger = logging.getLogger("dnf")
        with tests.support.patch_std_streams() as (stdout, stderr):
            self.logging._setup(
                logging.DEBUG, logging.WARNING, self.logdir, self.log_size, self.log_rotate)
            self._bench(logger)
        self.assertEqual("d\ni\n", stdout.getvalue())
        self.assertEqual("w\ne\n", stderr.getvalue())

    @mock.patch('dnf.logging.Logging._setup')
    def test_setup_from_dnf_conf(self, setup_m):
        conf = mock.Mock(
            debuglevel=2, errorlevel=3, logdir=self.logdir,
            log_size=self.log_size, log_rotate=self.log_rotate)
        self.logging._setup_from_dnf_conf(conf)
        self.assertEqual(setup_m.call_args, mock.call(dnf.logging.INFO,
                                                      dnf.logging.WARNING,
                                                      self.logdir,
                                                      self.log_size,
                                                      self.log_rotate))
        conf = mock.Mock(
            debuglevel=6, errorlevel=6, logdir=self.logdir,
            log_size=self.log_size, log_rotate=self.log_rotate)
        self.logging._setup_from_dnf_conf(conf)
        self.assertEqual(setup_m.call_args, mock.call(dnf.logging.DEBUG,
                                                      dnf.logging.WARNING,
                                                      self.logdir,
                                                      self.log_size,
                                                      self.log_rotate))

    def test_file_logging(self):
        # log nothing to the console:
        self.logging._setup(
            dnf.logging.SUPERCRITICAL, dnf.logging.SUPERCRITICAL,
            self.logdir, self.log_size, self.log_rotate)
        logger = logging.getLogger("dnf")
        with tests.support.patch_std_streams() as (stdout, stderr):
            logger.info("i")
            logger.critical("c")
        self.assertEqual(stdout.getvalue(), '')
        self.assertEqual(stderr.getvalue(), '')
        # yet the file should contain both the entries:
        logfile = os.path.join(self.logdir, "dnf.log")
        self.assertFile(logfile)
        with open(logfile) as f:
            msgs = map(operator.attrgetter("message"),
                       map(_split_logfile_entry, f.readlines()))
        self.assertSequenceEqual(list(msgs), [dnf.const.LOG_MARKER, 'i', 'c'])

    def test_rpm_logging(self):
        # log everything to the console:
        self.logging._setup(
            dnf.logging.SUBDEBUG, dnf.logging.SUBDEBUG,
            self.logdir, self.log_size, self.log_rotate)
        logger = logging.getLogger("dnf.rpm")
        with tests.support.patch_std_streams() as (stdout, stderr):
            logger.info('rpm transaction happens.')
        # rpm logger never outputs to the console:
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")
        logfile = os.path.join(self.logdir, "dnf.rpm.log")
        self.assertFile(logfile)
        with open(logfile) as f:
            msgs = map(operator.attrgetter("message"),
                       map(_split_logfile_entry, f.readlines()))
        self.assertSequenceEqual(
            list(msgs),
            [dnf.const.LOG_MARKER, 'rpm transaction happens.']
        )

    def test_setup_only_once(self):
        logger = logging.getLogger("dnf")
        self.assertLength(logger.handlers, 0)
        self.logging._setup(
            dnf.logging.SUBDEBUG, dnf.logging.SUBDEBUG,
            self.logdir, self.log_size, self.log_rotate)
        cnt = len(logger.handlers)
        self.assertGreater(cnt, 0)
        self.logging._setup(
            dnf.logging.SUBDEBUG, dnf.logging.SUBDEBUG,
            self.logdir, self.log_size, self.log_rotate)
        # no new handlers
        self.assertEqual(cnt, len(logger.handlers))
