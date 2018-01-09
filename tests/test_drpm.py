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

from __future__ import absolute_import
from __future__ import unicode_literals

import os
import shutil
import tempfile

import dnf.exceptions
from dnf.yum.misc import unlink_f
from dnf.util import Bunch

import tests.support
from tests import mock


PACKAGE = 'tour-5-1.noarch'


class Proggress_2(dnf.cli.progress.MultiFileProgressMeter):
    def start(self, total_files, total_size):
        self.total_files = total_files
        self.total_size = total_size

        # download state
        self.done_drpm = 0
        self.done_files = 0
        self.done_size = 0
        self.state = {}
        self.active = []

        # rate averaging
        self.last_time = 0
        self.last_size = 0
        self.rate = None


class Proggress_3(dnf.cli.progress.MultiFileProgressMeter):
    def start(self, total_files, total_size, total_drpms=0):
        self.total_files = total_files
        self.total_size = total_size
        self.total_drpm = total_drpms

        # download state
        self.done_drpm = 0
        self.done_files = 0
        self.done_size = 0
        self.state = {}
        self.active = []

        # rate averaging
        self.last_time = 0
        self.last_size = 0
        self.rate = None


class DrpmTest(tests.support.TestCase):
    def setUp(self):
        cachedir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, cachedir)
        self.base = tests.support.MockBase()
        self.base.conf.cachedir = tests.support.USER_RUNDIR

        # load the testing repo
        repo = self.base.add_test_dir_repo('drpm', self.base.conf)
        repo.deltarpm = True

        # find the newest 'tour' package available
        self.pkg = max(self.base.sack.query().available().filter(name='tour'))
        self.assertEqual(str(self.pkg), PACKAGE)

        # pretend it's remote and not cached
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(self.pkg.repo.__class__, '_local', False).start()
        self.pkg.localPkg = lambda: '/tmp/%s.rpm' % PACKAGE
        unlink_f(self.pkg.localPkg())

    def test_delta(self):
        # there should be a delta from 5-0 to 5-1
        self.assertTrue(self.pkg.get_delta_from_evr('5-0'))

    def download(self, errors=None, err={}):
        # utility function, calls Base.download_packages()
        # and returns the list of relative URLs it used.
        urls = []

        def dlp(targets, failfast):
            target, = targets
            self.assertEqual(target.__class__.__name__, 'PackageTarget')
            self.assertTrue(failfast)
            urls.append(target.relative_url)
            err = errors and errors.pop(0)
            if err:
                # PackageTarget.err is not writable
                targets[0] = Bunch(cbdata=target.cbdata, err=err)

        def lock_dir(_dir):
            return os.path.join(tests.support.USER_RUNDIR, dnf.const.PROGRAM_NAME)

        with mock.patch('librepo.download_packages', dlp),\
                mock.patch('dnf.lock._fit_lock_dir', lock_dir):
            try:
                self.base.download_packages([self.pkg])
            except dnf.exceptions.DownloadError as e:
                pass
        return urls

    def test_simple_download(self):
        self.assertEqual(self.download(), [PACKAGE + '.rpm'])

    def test_drpm_download(self):
        # the testing drpm is about 150% of the target..
        self.pkg.repo.deltarpm = 1
        dnf.drpm.APPLYDELTA = '/bin/true'

        self.base.conf.deltarpm_percentage = 50
        self.assertEqual(self.download(), ['tour-5-1.noarch.rpm'])

        self.base.conf.deltarpm_percentage = 200
        self.assertEqual(self.download(), ['drpms/tour-5-1.noarch.drpm'])

    def test_progress_start_2_args(self):
        p = Proggress_2()
        try:
            self.base.download_packages([self.pkg], progress=p)
        except dnf.exceptions.DownloadError as e:
            pass

    def test_progress_start_3_args(self):
        p = Proggress_3()
        try:
            self.base.download_packages([self.pkg], progress=p)
        except dnf.exceptions.DownloadError as e:
            pass
