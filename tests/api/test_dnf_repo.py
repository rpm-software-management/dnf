# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf.conf
import dnf.repo

from .common import TestCase


class DnfRepoApiTest(TestCase):

    def test_init(self):
        # dnf.repo.Repo.__init__
        self.assertHasAttr(dnf.repo, "Repo")
        self.assertHasType(dnf.repo.Repo, object)
        repo = dnf.repo.Repo(name=None, parent_conf=None)

    def test_repo_id_invalid(self):
        # dnf.repo.repo_id_invalid
        self.assertHasAttr(dnf.repo, "repo_id_invalid")
        dnf.repo.repo_id_invalid(repo_id="repo-id")

    def test_metadata_fresh(self):
        # dnf.repo.Metadata.fresh
        self.assertHasAttr(dnf.repo, "Metadata")

        class MockRepo:
            def fresh(self):
                return True

        mock_repo = MockRepo()
        md = dnf.repo.Metadata(repo=mock_repo)
        self.assertEqual(md.fresh, True)

    def test_DEFAULT_SYNC(self):
        # dnf.repo.Repo.DEFAULT_SYNC
        self.assertHasAttr(dnf.repo.Repo, "DEFAULT_SYNC")
        self.assertHasType(dnf.repo.Repo.DEFAULT_SYNC, int)

    def test_metadata(self):
        # dnf.repo.Repo.metadata
        repo = dnf.repo.Repo()
        self.assertHasAttr(repo, "metadata")
        self.assertEqual(repo.metadata, None)

    def test_id(self):
        # dnf.repo.Repo.id
        repo = dnf.repo.Repo()
        self.assertHasAttr(repo, "id")
        self.assertEqual(repo.id, "")

    def test_repofile(self):
        # dnf.repo.Repo.
        repo = dnf.repo.Repo()
        self.assertEqual(repo.repofile, "")

    def test_pkgdir(self):
        # dnf.repo.Repo.pkgdir
        conf = dnf.conf.Conf()
        conf.cachedir = "/tmp/cache"
        repo = dnf.repo.Repo(name=None, parent_conf=conf)
        self.assertHasAttr(repo, "pkgdir")
        self.assertHasType(repo.pkgdir, str)

    def test_pkgdir_setter(self):
        # dnf.repo.Repo.pkgdir - setter
        repo = dnf.repo.Repo()
        repo.pkgdir = "dir"
        self.assertHasType(repo.pkgdir, str)
        self.assertEqual(repo.pkgdir, "dir")

    def test_disable(self):
        # dnf.repo.Repo.disable
        repo = dnf.repo.Repo()
        self.assertHasAttr(repo, "disable")
        repo.disable()

    def test_enable(self):
        # dnf.repo.Repo.enable
        repo = dnf.repo.Repo()
        self.assertHasAttr(repo, "enable")
        repo.enable()

    def test_add_metadata_type_to_download(self):
        # dnf.repo.Repo.add_metadata_type_to_download
        repo = dnf.repo.Repo()
        self.assertHasAttr(repo, "add_metadata_type_to_download")
        repo.add_metadata_type_to_download(metadata_type="primary")

    def test_remove_metadata_type_from_download(self):
        # dnf.repo.Repo.remove_metadata_type_from_download
        repo = dnf.repo.Repo()
        self.assertHasAttr(repo, "remove_metadata_type_from_download")
        repo.remove_metadata_type_from_download(metadata_type="primary")

    def test_get_metadata_path(self):
        # dnf.repo.Repo.get_metadata_path
        repo = dnf.repo.Repo()
        self.assertHasAttr(repo, "get_metadata_path")
        path = repo.get_metadata_path(metadata_type="primary")
        self.assertHasType(path, str)

    def test_get_metadata_content(self):
        # dnf.repo.Repo.get_metadata_content
        repo = dnf.repo.Repo()
        self.assertHasAttr(repo, "get_metadata_content")
        content = repo.get_metadata_content(metadata_type="primary")
        self.assertHasType(content, str)

    def test_load(self):
        # dnf.repo.Repo.load
        repo = dnf.repo.Repo()

        class MockRepo:
            def load(self):
                return True

        repo._repo = MockRepo()
        self.assertHasAttr(repo, "load")
        repo.load()

    def test_dump(self):
        # dnf.repo.Repo.dump - inherited from BaseConfig
        repo = dnf.repo.Repo()
        self.assertHasAttr(repo, "dump")
        content = repo.dump()
        self.assertHasType(content, str)

    def test_set_progress_bar(self):
        # dnf.repo.Repo.set_progress_bar
        repo = dnf.repo.Repo()
        self.assertHasAttr(repo, "set_progress_bar")
        repo.set_progress_bar(progress=None)

    def test_get_http_headers(self):
        # dnf.repo.Repo.get_http_headers
        repo = dnf.repo.Repo()
        self.assertHasAttr(repo, "get_http_headers")
        headers = repo.get_http_headers()
        self.assertHasType(headers, tuple)

    def test_set_http_headers(self):
        # dnf.repo.Repo.set_http_headers
        repo = dnf.repo.Repo()
        self.assertHasAttr(repo, "set_http_headers")
        headers = repo.set_http_headers(headers=[])
