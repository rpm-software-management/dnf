import unittest
from dnf.yum.config import Option, BaseConfig

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
