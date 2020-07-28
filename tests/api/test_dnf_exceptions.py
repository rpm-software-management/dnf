# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf.exceptions

from .common import TestCase


class DnfExceptionsApiTest(TestCase):

    def test_deprectation_warning(self):
        # dnf.exceptions.DeprecationWarning
        self.assertHasAttr(dnf.exceptions, "DeprecationWarning")
        self.assertHasType(dnf.exceptions.DeprecationWarning(), DeprecationWarning)

    def test_error(self):
        # dnf.exceptions.Error
        self.assertHasAttr(dnf.exceptions, "Error")
        ex = dnf.exceptions.Error(value=None)
        self.assertHasType(ex, Exception)

    def test_comps_error(self):
        # dnf.exceptions.CompsError
        self.assertHasAttr(dnf.exceptions, "CompsError")
        ex = dnf.exceptions.CompsError(value=None)
        self.assertHasType(ex, dnf.exceptions.Error)

    def test_depsolve_error(self):
        # dnf.exceptions.DepsolveError
        self.assertHasAttr(dnf.exceptions, "DepsolveError")
        ex = dnf.exceptions.DepsolveError(value=None)
        self.assertHasType(ex, dnf.exceptions.Error)

    def test_download_error(self):
        # dnf.exceptions.DownloadError
        self.assertHasAttr(dnf.exceptions, "DownloadError")
        ex = dnf.exceptions.DownloadError(errmap=None)
        self.assertHasType(ex, dnf.exceptions.Error)

    def test_marking_error(self):
        # dnf.exceptions.MarkinError
        self.assertHasAttr(dnf.exceptions, "MarkingError")
        ex = dnf.exceptions.MarkingError(value=None, pkg_spec=None)
        self.assertHasType(ex, dnf.exceptions.Error)

    def test_marking_errors(self):
        # dnf.exceptions.MarkinErrors
        self.assertHasAttr(dnf.exceptions, "MarkingErrors")
        ex = dnf.exceptions.MarkingErrors(
            no_match_group_specs=(),
            error_group_specs=(),
            no_match_pkg_specs=(),
            error_pkg_specs=(),
            module_depsolv_errors=()
        )
        self.assertHasType(ex, dnf.exceptions.Error)

    def test_repo_error(self):
        # dnf.exceptions.RepoError
        self.assertHasAttr(dnf.exceptions, "RepoError")
        ex = dnf.exceptions.RepoError()
        self.assertHasType(ex, dnf.exceptions.Error)
