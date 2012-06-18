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
