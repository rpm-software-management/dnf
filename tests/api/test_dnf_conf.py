# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf

from .common import TestCase


class DnfConfTest(TestCase):
    def setUp(self):
        self.base = dnf.Base()
        self.conf = self.base.conf

    def tearDown(self):
        self.base.close()

    def test_priorities(self):
        self.assertHasAttr(dnf.conf.config, "PRIO_EMPTY")
        self.assertHasType(dnf.conf.config.PRIO_EMPTY, int)

        self.assertHasAttr(dnf.conf.config, "PRIO_DEFAULT")
        self.assertHasType(dnf.conf.config.PRIO_DEFAULT, int)

        self.assertHasAttr(dnf.conf.config, "PRIO_MAINCONFIG")
        self.assertHasType(dnf.conf.config.PRIO_MAINCONFIG, int)

        self.assertHasAttr(dnf.conf.config, "PRIO_AUTOMATICCONFIG")
        self.assertHasType(dnf.conf.config.PRIO_AUTOMATICCONFIG, int)

        self.assertHasAttr(dnf.conf.config, "PRIO_REPOCONFIG")
        self.assertHasType(dnf.conf.config.PRIO_REPOCONFIG, int)

        self.assertHasAttr(dnf.conf.config, "PRIO_PLUGINDEFAULT")
        self.assertHasType(dnf.conf.config.PRIO_PLUGINDEFAULT, int)

        self.assertHasAttr(dnf.conf.config, "PRIO_PLUGINCONFIG")
        self.assertHasType(dnf.conf.config.PRIO_PLUGINCONFIG, int)

        self.assertHasAttr(dnf.conf.config, "PRIO_COMMANDLINE")
        self.assertHasType(dnf.conf.config.PRIO_COMMANDLINE, int)

        self.assertHasAttr(dnf.conf.config, "PRIO_RUNTIME")
        self.assertHasType(dnf.conf.config.PRIO_RUNTIME, int)

    def test_get_reposdir(self):
        # Conf.get_reposiir
        self.assertHasAttr(self.conf, "get_reposdir")
        self.assertHasType(self.conf.get_reposdir, str)

    def test_substitutions(self):
        # Conf.substitutions
        self.assertHasAttr(self.conf, "substitutions")
        self.assertHasType(self.conf.substitutions, dnf.conf.substitutions.Substitutions)

    def test_tempfiles(self):
        # Conf.tempfiles
        self.assertHasAttr(self.conf, "tempfiles")
        self.assertHasType(self.conf.tempfiles, list)

    def test_exclude_pkgs(self):
        # Conf.exclude_pkgs
        self.assertHasAttr(self.conf, "exclude_pkgs")
        self.conf.exclude_pkgs(pkgs=["package_a", "package_b"])

    def test_prepend_installroot(self):
        # Conf.prepend_installroot
        self.assertHasAttr(self.conf, "prepend_installroot")
        self.conf.prepend_installroot(optname="logdir")

    def test_read(self):
        # Conf.read
        self.assertHasAttr(self.conf, "read")
        self.conf.read(filename=None, priority=dnf.conf.config.PRIO_DEFAULT)

    def test_dump(self):
        # Conf.dump
        self.assertHasAttr(self.conf, "dump")
        self.assertHasType(self.conf.dump(), str)

    def test_releasever(self):
        # Conf.releasever
        self.assertHasAttr(self.conf, "releasever")
        self.conf.releasever = "test setter"
        self.assertHasType(self.conf.releasever, str)

    def test_arch(self):
        # Conf.arch
        self.assertHasAttr(self.conf, "arch")
        self.conf.arch = "aarch64"
        self.assertHasType(self.conf.arch, str)

    def test_basearch(self):
        # Conf.basearch
        self.assertHasAttr(self.conf, "basearch")
        self.conf.basearch = "aarch64"
        self.assertHasType(self.conf.basearch, str)

    def test_write_raw_configfile(self):
        # Conf.write_raw_configfile
        self.assertHasAttr(self.conf, "write_raw_configfile")
        s = dnf.conf.substitutions.Substitutions()
        self.conf.write_raw_configfile(filename="file.conf", section_id='main', substitutions=s, modify={})


class DnfSubstitutionsTest(TestCase):
    def test_update_from_etc(self):
        # Substitutions.update_from_etc
        substitutions = dnf.conf.substitutions.Substitutions()
        self.assertHasAttr(substitutions, "update_from_etc")
        substitutions.update_from_etc(installroot="path", varsdir=("/etc/path/", "/etc/path2"))
