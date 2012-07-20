# Copyright (C) 2012  Red Hat, Inc.
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

import mock
import unittest
from dnf.yum.config import Option, BaseConfig
from dnf.conf import Cache

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

class CacheTest(unittest.TestCase):
     @mock.patch('dnf.util.am_i_root', return_value=True)
     def test_root(self, unused_am_i_root):
         cache = Cache()
         cache.prefix = '/var/lib/spinning'
         cache.suffix = 'i286/20'
         self.assertEqual(cache.cachedir, '/var/lib/spinning/i286/20')
         self.assertEqual(cache.fallback_cachedir, None)

     @mock.patch('dnf.yum.misc.getCacheDir', return_value="/notmp/dnf-walr-yeAH")
     def test_noroot(self, fn_getcachedir):
         cache = Cache()
         cache.prefix = '/var/lib/spinning'
         cache.suffix = 'i286/20'
         self.assertEqual(fn_getcachedir.call_count, 0)
         self.assertEqual(cache.cachedir, '/notmp/dnf-walr-yeAH/i286/20')
         self.assertEqual(fn_getcachedir.call_count, 1)
         self.assertEqual(cache.fallback_cachedir, '/var/lib/spinning/i286/20')

         # the cachedirs are cached now, getCacheDir is not called again:
         self.assertEqual(cache.cachedir, '/notmp/dnf-walr-yeAH/i286/20')
         self.assertEqual(fn_getcachedir.call_count, 1)
