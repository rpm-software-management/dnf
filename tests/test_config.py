# -*- coding: utf-8 -*-

# Copyright (C) 2012-2018 Red Hat, Inc.
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

from __future__ import unicode_literals

import argparse

import dnf.conf
import dnf.conf.read
import dnf.exceptions
from dnf.conf import Option, BaseConfig, Conf, RepoConf

import tests.support
from tests.support import mock


class OptionTest(tests.support.TestCase):

    class Cfg(BaseConfig):
        def __init__(self):
            super(OptionTest.Cfg, self).__init__()
            self._add_option('a_setting', Option("roundabout"))

    def test_option(self):
        cfg = self.Cfg()
        # default
        self.assertEqual(cfg.a_setting, "roundabout")
        # new value with high priority
        cfg.a_setting = "turn left"
        self.assertEqual(cfg.a_setting, "turn left")
        # new value with lower priority does nothing
        cfg._set_value('a_setting', "turn right", dnf.conf.PRIO_DEFAULT)
        self.assertEqual(cfg.a_setting, "turn left")


class CacheTest(tests.support.TestCase):

    @mock.patch('dnf.util.am_i_root', return_value=True)
    @mock.patch('dnf.const.SYSTEM_CACHEDIR', '/var/lib/spinning')
    def test_root(self, unused_am_i_root):
        conf = dnf.conf.Conf()
        self.assertEqual(conf.system_cachedir, '/var/lib/spinning')
        self.assertEqual(conf.cachedir, '/var/lib/spinning')

    @mock.patch('dnf.yum.misc.getCacheDir',
                return_value="/notmp/dnf-walr-yeAH")
    @mock.patch('dnf.util.am_i_root', return_value=False)
    @mock.patch('dnf.const.SYSTEM_CACHEDIR', '/var/lib/spinning')
    def test_noroot(self, fn_root, fn_getcachedir):
        self.assertEqual(fn_getcachedir.call_count, 0)
        conf = dnf.conf.Conf()
        self.assertEqual(conf.cachedir, '/notmp/dnf-walr-yeAH')
        self.assertEqual(fn_getcachedir.call_count, 1)


class ConfTest(tests.support.TestCase):

    def test_bugtracker(self):
        conf = Conf()
        self.assertEqual(conf.bugtracker_url,
                         "https://bugzilla.redhat.com/enter_bug.cgi" +
                         "?product=Fedora&component=dnf")

    def test_conf_from_file(self):
        conf = Conf()
        # defaults
        self.assertFalse(conf.gpgcheck)
        self.assertEqual(conf.installonly_limit, 3)
        self.assertTrue(conf.clean_requirements_on_remove)
        conf.config_file_path = '%s/etc/dnf/dnf.conf' % tests.support.dnf_toplevel()
        conf.read(priority=dnf.conf.PRIO_MAINCONFIG)
        self.assertTrue(conf.gpgcheck)
        self.assertEqual(conf.installonly_limit, 3)
        self.assertTrue(conf.clean_requirements_on_remove)

    def test_overrides(self):
        conf = Conf()
        self.assertFalse(conf.assumeyes)
        self.assertFalse(conf.assumeno)
        self.assertEqual(conf.color, 'auto')

        opts = argparse.Namespace(assumeyes=True, color='never')
        conf._configure_from_options(opts)
        self.assertTrue(conf.assumeyes)
        self.assertFalse(conf.assumeno)  # no change
        self.assertEqual(conf.color, 'never')

    def test_order_insensitive(self):
        conf = Conf()
        conf.config_file_path = '%s/etc/dnf/dnf.conf' % tests.support.dnf_toplevel()
        opts = argparse.Namespace(
            gpgcheck=False,
            main_setopts=argparse.Namespace(installonly_limit=5)
        )
        # read config
        conf.read(priority=dnf.conf.PRIO_MAINCONFIG)
        # update from commandline
        conf._configure_from_options(opts)
        self.assertFalse(conf.gpgcheck)
        self.assertEqual(conf.installonly_limit, 5)

        # and the other way round should have the same result
        # update from commandline
        conf._configure_from_options(opts)
        # read config
        conf.read(priority=dnf.conf.PRIO_MAINCONFIG)
        self.assertFalse(conf.gpgcheck)
        self.assertEqual(conf.installonly_limit, 5)

    def test_inheritance1(self):
        conf = Conf()
        repo = RepoConf(conf)

        # minrate is inherited from conf
        # default should be the same
        self.assertEqual(conf.minrate, 1000)
        self.assertEqual(repo.minrate, 1000)

        # after conf change, repoconf still should inherit its value
        conf.minrate = 2000
        self.assertEqual(conf.minrate, 2000)
        self.assertEqual(repo.minrate, 2000)

    def test_inheritance2(self):
        conf = Conf()

        # if repoconf reads value from config it no more inherits changes from conf
        conf.config_file_path = tests.support.resource_path('etc/repos.conf')
        with mock.patch('logging.Logger.warning'):
            reader = dnf.conf.read.RepoReader(conf, {})
            repo = list(reader)[0]

        self.assertEqual(conf.minrate, 1000)
        self.assertEqual(repo.minrate, 4096)

        # after global change
        conf.minrate = 2000
        self.assertEqual(conf.minrate, 2000)
        self.assertEqual(repo.minrate, 4096)

    def test_prepend_installroot(self):
        conf = Conf()
        conf.installroot = '/mnt/root'
        conf.prepend_installroot('persistdir')
        self.assertEqual(conf.persistdir, '/mnt/root/var/lib/dnf')

    def test_ranges(self):
        conf = Conf()
        with self.assertRaises(dnf.exceptions.ConfigError):
            conf.debuglevel = '11'
