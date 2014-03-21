# Copyright (C) 2012-2013  Red Hat, Inc.
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

from dnf.yum.config import Option, BaseConfig, YumConf
from dnf.conf import CliCache, GoalParameters
from tests.support import PycompTestCase
from tests.support import mock

import unittest

class OptionTest(unittest.TestCase):
    class Cfg(BaseConfig):
        a_setting = Option("roundabout")

    def test_delete(self):
        cfg = self.Cfg()
        self.assertEqual(cfg.a_setting, "roundabout")
        del cfg.a_setting
        try:
            cfg.a_setting
        except RuntimeError as e:
            pass
        else:
            self.fail("option should be deleted now.")

class CacheTest(PycompTestCase):
     @mock.patch('dnf.util.am_i_root', return_value=True)
     def test_root(self, unused_am_i_root):
         cache = CliCache('/var/lib/spinning', 'i286/20')
         self.assertEqual(cache.system_cachedir, '/var/lib/spinning/i286/20')
         self.assertEqual(cache.cachedir, '/var/lib/spinning/i286/20')

     @mock.patch('dnf.yum.misc.getCacheDir', return_value="/notmp/dnf-walr-yeAH")
     @mock.patch('dnf.util.am_i_root', return_value=False)
     def test_noroot(self, fn_root, fn_getcachedir):
         cache = CliCache('/var/lib/spinning', 'i286/20')
         self.assertEqual(fn_getcachedir.call_count, 0)
         self.assertEqual(cache.cachedir, '/notmp/dnf-walr-yeAH/i286/20')
         self.assertEqual(fn_getcachedir.call_count, 1)

         # the cachedirs are cached now, getCacheDir is not called again:
         self.assertEqual(cache.cachedir, '/notmp/dnf-walr-yeAH/i286/20')
         self.assertEqual(fn_getcachedir.call_count, 1)

class YumConfTest(PycompTestCase):
    def test_bugtracker(self):
        conf = YumConf()
        self.assertEqual(conf.bugtracker_url,
                         "https://bugzilla.redhat.com/enter_bug.cgi" +
                         "?product=Fedora&component=dnf")

    def test_overrides(self):
        conf = YumConf()
        self.assertFalse(conf.assumeyes)
        self.assertFalse(conf.assumeno)
        self.assertEqual(conf.color_list_installed_older, 'bold')

        override = {'assumeyes': True,
                    'color_list_installed_older': 'timid'}
        conf.override(override)
        self.assertTrue(conf.assumeyes)
        self.assertFalse(conf.assumeno) # no change
        self.assertEqual(conf.color_list_installed_older, 'timid')

    def test_prepend_installroot(self):
        conf = YumConf()
        conf.installroot = '/mnt/root'
        conf.prepend_installroot('persistdir')
        self.assertEqual(conf.persistdir, '/mnt/root/var/lib/dnf')

    def test_ranges(self):
        conf = YumConf()
        with self.assertRaises(ValueError):
            conf.debuglevel = 11

class GoalParametersTest(PycompTestCase):
    def test_default(self):
        gp = GoalParameters()
        self.assertFalse(gp.allow_uninstall)
