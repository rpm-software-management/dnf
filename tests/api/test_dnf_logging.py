# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf

import logging
from .common import TestCase


class DnfLoggingApiTest(TestCase):
    def test_levels(self):
        self.assertHasAttr(dnf.logging, "SUPERCRITICAL")
        self.assertHasType(dnf.logging.SUPERCRITICAL, int)

        self.assertHasAttr(dnf.logging, "CRITICAL")
        self.assertHasType(dnf.logging.CRITICAL, int)

        self.assertHasAttr(dnf.logging, "ERROR")
        self.assertHasType(dnf.logging.ERROR, int)

        self.assertHasAttr(dnf.logging, "WARNING")
        self.assertHasType(dnf.logging.WARNING, int)

        self.assertHasAttr(dnf.logging, "INFO")
        self.assertHasType(dnf.logging.INFO, int)

        self.assertHasAttr(dnf.logging, "DEBUG")
        self.assertHasType(dnf.logging.DEBUG, int)

        self.assertHasAttr(dnf.logging, "DDEBUG")
        self.assertHasType(dnf.logging.DDEBUG, int)

        self.assertHasAttr(dnf.logging, "SUBDEBUG")
        self.assertHasType(dnf.logging.SUBDEBUG, int)

        self.assertHasAttr(dnf.logging, "TRACE")
        self.assertHasType(dnf.logging.TRACE, int)

        self.assertHasAttr(dnf.logging, "ALL")
        self.assertHasType(dnf.logging.ALL, int)

    def test_logging_level_names(self):
        # Level names added in dnf logging initialization
        self.assertTrue(logging.getLevelName(dnf.logging.DDEBUG) == "DDEBUG")
        self.assertTrue(logging.getLevelName(dnf.logging.SUBDEBUG) == "SUBDEBUG")
        self.assertTrue(logging.getLevelName(dnf.logging.TRACE) == "TRACE")

    def test_dnf_logger(self):
        # This doesn't really test much since python allows getting any logger,
        # at least check if it has handlers (setup in dnf).
        logger = logging.getLogger('dnf')
        self.assertTrue(len(logger.handlers) > 0)

    def test_dnf_rpm_logger(self):
        # This doesn't really test dnf api since python allows getting any logger,
        # but at least check that the messages are somehow taken care of.
        logger = logging.getLogger('dnf.rpm')
        self.assertTrue(len(logger.handlers) > 0 or logger.propagate)

    def test_dnf_plugin_logger(self):
        # This doesn't really test dnf api since python allows getting any logger,
        # but at least check that the messages are somehow taken care of.
        logger = logging.getLogger('dnf.plugin')
        self.assertTrue(len(logger.handlers) > 0 or logger.propagate)
