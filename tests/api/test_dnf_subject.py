# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf

from .common import TestCase


class DnfSubjectApiTest(TestCase):
    def setUp(self):
        self.subject = dnf.subject.Subject("")

    def test_subject(self):
        # dnf.subject.Subject
        self.assertHasAttr(dnf.subject, "Subject")
        self.assertHasType(dnf.subject.Subject, object)

    def test_init(self):
        # Subject.__init__
        _ = dnf.subject.Subject("")

    def test_get_best_query(self):
        # Subject.get_best_query
        self.assertHasAttr(self.subject, "get_best_query")
        b = dnf.Base(dnf.conf.Conf())
        b.fill_sack(False, False)
        self.assertHasType(
            self.subject.get_best_query(
                sack=b.sack,
                with_nevra=False,
                with_provides=False,
                with_filenames=False,
                forms=None
            ), dnf.query.Query)

    def test_get_best_selector(self):
        # Subject.get_best_selector
        self.assertHasAttr(self.subject, "get_best_selector")
        b = dnf.Base(dnf.conf.Conf())
        b.fill_sack(False, False)
        self.assertHasType(
            self.subject.get_best_selector(
                sack=b.sack,
                forms=None,
                obsoletes=False,
                reponame=None
            ), dnf.selector.Selector)

    def test_get_nevra_possibilities(self):
        # Subject.get_nevra_possibilities
        self.assertHasAttr(self.subject, "get_nevra_possibilities")
        self.assertHasType(self.subject.get_nevra_possibilities(forms=None), list)
