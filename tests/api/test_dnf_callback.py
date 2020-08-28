# -*- coding: utf-8 -*-


from __future__ import absolute_import
from __future__ import unicode_literals

import dnf

from .common import TestCase


class DnfCallbackApiTest(TestCase):
    def test_pkg_downgrade(self):
        # dnf.callback.PKG_DOWNGRADE
        self.assertHasAttr(dnf.callback, "PKG_DOWNGRADE")
        self.assertHasType(dnf.callback.PKG_DOWNGRADE, int)

    def test_downgraded(self):
        # dnf.callback.PKG_DOWNGRADED
        self.assertHasAttr(dnf.callback, "PKG_DOWNGRADED")
        self.assertHasType(dnf.callback.PKG_DOWNGRADED, int)

    def test_pkg_install(self):
        # dnf.callback.PKG_INSTALL
        self.assertHasAttr(dnf.callback, "PKG_INSTALL")
        self.assertHasType(dnf.callback.PKG_INSTALL, int)

    def test_pkg_obsolete(self):
        # dnf.callback.PKG_OBSOLETE
        self.assertHasAttr(dnf.callback, "PKG_OBSOLETE")
        self.assertHasType(dnf.callback.PKG_OBSOLETE, int)

    def test_pkg_obsoleted(self):
        # dnf.callback.PKG_OBSOLETED
        self.assertHasAttr(dnf.callback, "PKG_OBSOLETED")
        self.assertHasType(dnf.callback.PKG_OBSOLETED, int)

    def test_pkg_reinstall(self):
        # dnf.callback.PKG_REINSTALL
        self.assertHasAttr(dnf.callback, "PKG_REINSTALL")
        self.assertHasType(dnf.callback.PKG_REINSTALL, int)

    def test_pkg_reinstalled(self):
        # dnf.callback.PKG_REINSTALLED
        self.assertHasAttr(dnf.callback, "PKG_REINSTALLED")
        self.assertHasType(dnf.callback.PKG_REINSTALLED, int)

    def test_pkg_remove(self):
        # dnf.callback.PKG_REMOVE
        self.assertHasAttr(dnf.callback, "PKG_REMOVE")
        self.assertHasType(dnf.callback.PKG_REMOVE, int)

    def test_pkg_upgrade(self):
        # dnf.callback.PKG_UPGRADE
        self.assertHasAttr(dnf.callback, "PKG_UPGRADE")
        self.assertHasType(dnf.callback.PKG_UPGRADE, int)

    def test_pkg_upgraded(self):
        # dnf.callback.PKG_UPGRADED
        self.assertHasAttr(dnf.callback, "PKG_UPGRADED")
        self.assertHasType(dnf.callback.PKG_UPGRADED, int)

    def test_pkg_cleanup(self):
        # dnf.callback.PKG_CLEANUP
        self.assertHasAttr(dnf.callback, "PKG_CLEANUP")
        self.assertHasType(dnf.callback.PKG_CLEANUP, int)

    def test_pkg_verify(self):
        # dnf.callback.PKG_VERIFY
        self.assertHasAttr(dnf.callback, "PKG_VERIFY")
        self.assertHasType(dnf.callback.PKG_VERIFY, int)

    def test_pkg_scriptlet(self):
        # dnf.callback.PKG_SCRIPTLET
        self.assertHasAttr(dnf.callback, "PKG_SCRIPTLET")
        self.assertHasType(dnf.callback.PKG_SCRIPTLET, int)

    def test_trans_preparation(self):
        # dnf.callback.TRANS_PREPARATION
        self.assertHasAttr(dnf.callback, "TRANS_PREPARATION")
        self.assertHasType(dnf.callback.TRANS_PREPARATION, int)

    def test_trans_post(self):
        # dnf.callback.TRANS_POST
        self.assertHasAttr(dnf.callback, "TRANS_POST")
        self.assertHasType(dnf.callback.TRANS_POST, int)

    def test_status_ok(self):
        # dnf.callback.STATUS_OK
        self.assertHasAttr(dnf.callback, "STATUS_OK")
        self.assertHasType(dnf.callback.STATUS_OK, object)

    def test_status_failed(self):
        # dnf.callback.STATUS_FAILED
        self.assertHasAttr(dnf.callback, "STATUS_FAILED")
        self.assertHasType(dnf.callback.STATUS_FAILED, int)

    def test_status_already_exists(self):
        # dnf.callback.STATUS_ALREADY_EXISTS
        self.assertHasAttr(dnf.callback, "STATUS_ALREADY_EXISTS")
        self.assertHasType(dnf.callback.STATUS_ALREADY_EXISTS, int)

    def test_status_mirror(self):
        # dnf.callback.STATUS_MIRROR
        self.assertHasAttr(dnf.callback, "STATUS_MIRROR")
        self.assertHasType(dnf.callback.STATUS_MIRROR, int)

    def test_status_drpm(self):
        # dnf.callback.STATUS_DRPM
        self.assertHasAttr(dnf.callback, "STATUS_DRPM")
        self.assertHasType(dnf.callback.STATUS_DRPM, int)

    def test_payload(self):
        # dnf.callback.Payload
        self.assertHasAttr(dnf.callback, "Payload")
        self.assertHasType(dnf.callback.Payload, object)

    def test_payload_init(self):
        # dnf.callback.Payload.__init__
        download_progress = dnf.callback.DownloadProgress()
        _ = dnf.callback.Payload(progress=download_progress)

    def test_payload_str(self):
        # dnf.callback.Payload.__str__
        download_progress = dnf.callback.DownloadProgress()
        payload = dnf.callback.Payload(progress=download_progress)
        payload.__str__()

    def test_payload_download_size(self):
        # dnf.callback.Payload.download_size
        download_progress = dnf.callback.DownloadProgress()
        payload = dnf.callback.Payload(progress=download_progress)
        self.assertHasAttr(payload, "download_size")
        self.assertHasType(payload.download_size, object)

    def test_download_progress(self):
        # dnf.callback.DownloadProgress
        self.assertHasAttr(dnf.callback, "DownloadProgress")
        self.assertHasType(dnf.callback.DownloadProgress, object)

    def test_download_progress_end(self):
        # dnf.callback.DownloadProgress.end
        download_progress = dnf.callback.DownloadProgress()
        payload = dnf.callback.Payload(progress=download_progress)
        download_progress.end(payload=payload, status=dnf.callback.STATUS_OK, msg="err_msg")

    def test_download_progress_progress(self):
        # dnf.callback.DownloadProgress.progress
        download_progress = dnf.callback.DownloadProgress()
        payload = dnf.callback.Payload(progress=download_progress)
        download_progress.progress(payload=payload, done=0)

    def test_download_progress_start(self):
        # dnf.callback.DownloadProgress.start
        download_progress = dnf.callback.DownloadProgress()
        download_progress.start(total_files=1, total_size=1, total_drpms=0)

    def test_TransactionProgress(self):
        # dnf.callback.TransactionProgress
        self.assertHasAttr(dnf.callback, "TransactionProgress")
        self.assertHasType(dnf.callback.TransactionProgress, object)
