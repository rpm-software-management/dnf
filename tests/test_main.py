# -*- coding: utf-8 -*-

# Copyright (C) 2014-2018 Red Hat, Inc.
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

"""Tests of the CLI entry point."""

from __future__ import unicode_literals

import dnf.cli.main
import dnf.logging
import dnf.pycomp

import tests.support


class MainTest(tests.support.TestCase):
    """Tests the ``dnf.cli.main`` module."""

    def test_ex_IOError_logs_traceback(self):
        """Test whether the traceback is logged if an error is raised."""

        lvl = dnf.logging.SUBDEBUG
        out = dnf.pycomp.StringIO()

        with tests.support.wiretap_logs('dnf', lvl, out):
            try:
                raise OSError('test_ex_IOError_logs_traceback')
            except OSError as e:
                dnf.cli.main.ex_IOError(e)
        self.assertTracebackIn('OSError: test_ex_IOError_logs_traceback\n',
                               out.getvalue())
