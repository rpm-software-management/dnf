# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf

from .common import TestCase


class DnfPackageApiTest(TestCase):
    def setUp(self):
        self.base = dnf.Base(dnf.conf.Conf())
        self.package = self._get_pkg()

    def tearDown(self):
        self.base.close()

    def test_arch(self):
        # Package.arch
        self.assertHasAttr(self.package, "arch")
        self.assertHasType(self.package.arch, str)

    def test_baseurl(self):
        # Package.baseurl
        self.assertHasAttr(self.package, "baseurl")
        # The value is missing here so the type is type(None) but it should be str
        # self.assertHasType(self.package.baseurl, str)
        self.package.baseurl

    def test_buildtime(self):
        # Package.buildtime
        self.assertHasAttr(self.package, "buildtime")
        self.assertHasType(self.package.buildtime, int)

    def test_chksum(self):
        # Package.chksum()
        self.assertHasAttr(self.package, "chksum")
        # The value is missing here so the type is type(None) but it should be str
        # self.assertHasType(self.package.chksum, str)
        self.package.chksum

    def test_conflicts(self):
        # Package.conflicts()
        self.assertHasAttr(self.package, "conflicts")
        self.assertHasType(self.package.conflicts, list)

    def test_debug_name(self):
        # Package.debug_name
        self.assertHasAttr(self.package, "debug_name")
        self.assertHasType(self.package.debug_name, str)

    def test_description(self):
        # Package.description
        self.assertHasAttr(self.package, "description")
        self.assertHasType(self.package.description, str)

    def test_downloadsize(self):
        # Package.downloadsize
        self.assertHasAttr(self.package, "downloadsize")
        self.assertHasType(self.package.downloadsize, int)

    def test_epoch(self):
        # Package.epoch
        self.assertHasAttr(self.package, "epoch")
        self.assertHasType(self.package.epoch, int)

    def test_enhances(self):
        # Package.enhances
        self.assertHasAttr(self.package, "enhances")
        self.assertHasType(self.package.enhances, list)

    def test_evr(self):
        # Package.evr
        self.assertHasAttr(self.package, "evr")
        self.assertHasType(self.package.evr, str)

    def test_files(self):
        # Package.files
        self.assertHasAttr(self.package, "files")
        self.assertHasType(self.package.files, list)

    def test_group(self):
        # Package.group
        self.assertHasAttr(self.package, "group")
        self.assertHasType(self.package.group, str)

    def test_hdr_chksum(self):
        # Package.hdr_chksum
        self.assertHasAttr(self.package, "hdr_chksum")
        # The value is missing here so the type is type(None) but it should be str
        # self.assertHasType(self.package.hdr_chksum, str)
        self.package.hdr_chksum

    def test_hdr_end(self):
        # Package.hdr_end
        self.assertHasAttr(self.package, "hdr_end")
        self.assertHasType(self.package.hdr_end, int)

    def test_changelogs(self):
        # Package.changelogs
        self.assertHasAttr(self.package, "changelogs")
        self.assertHasType(self.package.changelogs, list)

    def test_installed(self):
        # Package.installed
        self.assertHasAttr(self.package, "installed")
        self.assertHasType(self.package.installed, bool)

    def test_installtime(self):
        # Package.installtime
        self.assertHasAttr(self.package, "installtime")
        self.assertHasType(self.package.installtime, int)

    def test_installsize(self):
        # Package.installsize
        self.assertHasAttr(self.package, "installsize")
        self.assertHasType(self.package.installsize, int)

    def test_license(self):
        # Package.license
        self.assertHasAttr(self.package, "license")
        self.assertHasType(self.package.license, str)

    def test_medianr(self):
        # Package.medianr
        self.assertHasAttr(self.package, "medianr")
        self.assertHasType(self.package.medianr, int)

    def test_name(self):
        # Package.name
        self.assertHasAttr(self.package, "name")
        self.assertHasType(self.package.name, str)

    def test_obsoletes(self):
        # Package.obsoletes
        self.assertHasAttr(self.package, "obsoletes")
        self.assertHasType(self.package.obsoletes, list)

    def test_provides(self):
        # Package.provides
        self.assertHasAttr(self.package, "provides")
        self.assertHasType(self.package.provides, list)

    def test_recommends(self):
        # Package.recommends
        self.assertHasAttr(self.package, "recommends")
        self.assertHasType(self.package.recommends, list)

    def test_release(self):
        # Package.release
        self.assertHasAttr(self.package, "release")
        self.assertHasType(self.package.release, str)

    def test_reponame(self):
        # Package.reponame
        self.assertHasAttr(self.package, "reponame")
        self.assertHasType(self.package.reponame, str)

    def test_requires(self):
        # Package.requires
        self.assertHasAttr(self.package, "requires")
        self.assertHasType(self.package.requires, list)

    def test_requires_pre(self):
        # Package.requires_pre
        self.assertHasAttr(self.package, "requires_pre")
        self.assertHasType(self.package.requires_pre, list)

    def test_regular_requires(self):
        # Package.regular_requires
        self.assertHasAttr(self.package, "regular_requires")
        self.assertHasType(self.package.regular_requires, list)

    def test_prereq_ignoreinst(self):
        # Package.prereq_ignoreinst
        self.assertHasAttr(self.package, "prereq_ignoreinst")
        self.assertHasType(self.package.prereq_ignoreinst, list)

    def test_rpmdbid(self):
        # Package.rpmdbid
        self.assertHasAttr(self.package, "rpmdbid")
        self.assertHasType(self.package.rpmdbid, int)

    def test_source_debug_name(self):
        # Package.source_debug_name
        self.assertHasAttr(self.package, "source_debug_name")
        self.assertHasType(self.package.source_debug_name, str)

    def test_source_name(self):
        # Package.source_name
        self.assertHasAttr(self.package, "source_name")
        self.assertHasType(self.package.source_name, str)

    def test_debugsource_name(self):
        # Package.debugsource_name
        self.assertHasAttr(self.package, "debugsource_name")
        self.assertHasType(self.package.debugsource_name, str)

    def test_sourcerpm(self):
        # Package.sourcerpm
        self.assertHasAttr(self.package, "sourcerpm")
        self.assertHasType(self.package.sourcerpm, str)

    def test_suggests(self):
        # Package.suggests
        self.assertHasAttr(self.package, "suggests")
        self.assertHasType(self.package.suggests, list)

    def test_summary(self):
        # Package.summary
        self.assertHasAttr(self.package, "summary")
        self.assertHasType(self.package.summary, str)

    def test_supplements(self):
        # Package.supplements
        self.assertHasAttr(self.package, "supplements")
        self.assertHasType(self.package.supplements, list)

    def test_url(self):
        # Package.url
        self.assertHasAttr(self.package, "url")
        # The value is missing here so the type is type(None) but it should be str
        # self.assertHasType(self.package.url, str)
        self.package.url

    def test_version(self):
        # Package.version
        self.assertHasAttr(self.package, "version")
        self.assertHasType(self.package.version, str)

    def test_packager(self):
        # Package.packager
        self.assertHasAttr(self.package, "packager")
        # The value is missing here so the type is type(None) but it should be str
        # self.assertHasType(self.package.packager, str)
        self.package.packager

    def test_remote_location(self):
        # Package.remote_location
        self.assertHasAttr(self.package, "remote_location")
        # This fails due to a bug (filed RhBug:1873146)
        #self.package.remote_location(schemes='http')

    def test_debuginfo_suffix(self):
        # Package.DEBUGINFO_SUFFIX
        self.assertHasAttr(self.package, "DEBUGINFO_SUFFIX")
        self.assertHasType(self.package.DEBUGINFO_SUFFIX, str)

    def test_debugsource_suffix(self):
        # Package.DEBUGSOURCE_SUFFIX
        self.assertHasAttr(self.package, "DEBUGSOURCE_SUFFIX")
        self.assertHasType(self.package.DEBUGSOURCE_SUFFIX, str)

