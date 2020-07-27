# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import os
import unittest


REPOS_DIR = os.path.join(os.path.dirname(__file__), "../repos/")
TOUR_4_4 = os.path.join(REPOS_DIR, "rpm/tour-4-4.noarch.rpm")
COMPS = os.path.join(REPOS_DIR, "main_comps.xml")


class TestCase(unittest.TestCase):

    def _get_pkg(self):
        self.base.fill_sack(load_system_repo=False, load_available_repos=False)
        self.base.add_remote_rpms(path_list=[TOUR_4_4], strict=True, progress=None)
        pkg = self.base.sack.query().filter(name="tour")[0]
        return pkg

    def _load_comps(self):
        self.base.read_comps()
        self.base.comps._add_from_xml_filename(COMPS)

    def assertHasAttr(self, obj, name):
        self.assertTrue(hasattr(obj, name))

    def assertHasType(self, obj, types):
        self.assertTrue(isinstance(obj, types))
