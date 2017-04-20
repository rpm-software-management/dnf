..
  Copyright (C) 2014-2015  Red Hat, Inc.

  This copyrighted material is made available to anyone wishing to use,
  modify, copy, or redistribute it subject to the terms and conditions of
  the GNU General Public License v.2, or (at your option) any later version.
  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY expressed or implied, including the implied warranties of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
  Public License for more details.  You should have received a copy of the
  GNU General Public License along with this program; if not, write to the
  Free Software Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA
  02110-1301, USA.  Any Red Hat trademarks that are incorporated in the
  source code or documentation are not subject to the GNU General Public
  License and may only be used or replicated with the express permission of
  Red Hat, Inc.

===================================
 Progress Reporting with Callbacks
===================================

.. module:: dnf.callback

.. class:: Payload

  Represents one item (file) from the download batch.

  .. method:: __str__

    Provide concise, human-readable representation of this Payload.

  .. method:: download_size

    Total size of this Payload when transferred (e.g. over network).

.. class:: DownloadProgress

  Base class providing callbacks to receive information about an ongoing download.

  .. method:: end(payload, status, msg)

    Report finished download of a `payload`, :class:`.Payload` instance. `status` is a constant with the following meaning:

    ====================== =======================================================
    `status` value         meaning
    ====================== =======================================================
    STATUS_OK              Download finished successfully.
    STATUS_DRPM            DRPM rebuilt successfully.
    STATUS_ALREADY_EXISTS  Download skipped because the local file already exists.
    STATUS_MIRROR          Download failed on the current mirror, will try to use
                           next mirror in the list.
    STATUS_FAILED          Download failed because of another error.
    ====================== =======================================================

    `msg` is an optional string error message further explaining the `status`.

  .. method:: progress(payload, done)

    Report ongoing progress on the given `payload`. `done` is the number of bytes already downloaded from `payload`.

  .. method:: start(total_files, total_size, total_drpms=0)

    Report start of a download batch. `total_files` is the total number of payloads in the batch.
    `total_size` is the total number of bytes to be downloaded. `total_drpms` is the total number
    of drpms payloads in the batch.

.. class:: TransactionProgress

  Base class providing callbacks to receive information about an ongoing transaction.

  .. method:: error(message)

    Report an error that occurred during the transaction. `message` is a string which describes the error.

  .. method:: progress(package, action, ti_done, ti_total, ts_done, ts_total)

    Report ongoing progress on the given transaction item. `package` is the :class:`dnf.package.Package` being processed and `action` is a constant with the following meaning:

    ================== ================================================================================= ===========
    `action` value     meaning                                                                           Appearance*
    ================== ================================================================================= ===========
    PKG_CLEANUP        `package` cleanup is being performed.                                             3
    PKG_DOWNGRADE      `package` is being downgraded.                                                    2
    PKG_INSTALL        `package` is being installed.                                                     2
    PKG_OBSOLETE       `package` is being obsoleted.                                                     2
    PKG_REINSTALL      `package` is being reinstalled.                                                   2
    PKG_REMOVE         `package` is being removed.                                                       2
    PKG_UPGRADE        `package` is being upgraded.                                                      2
    PKG_VERIFY         `package` is being verified.                                                      5
    PKG_SCRIPTLET      `package` scriplet is being performed.                                            Anytime
    TRANS_PREPARATION  `transaction` is being prepared.                                                  1
    TRANS_POST         The post-trans phase started. In this case, all the other arguments are ``None``. 4
    ================== ================================================================================= ===========

  \*\ This is order in which state of transaction which callback action can appear. Only PKG_SCRIPTLET
  can appear anytime during transaction even before transaction starts.

  `ti_done` is the number of processed bytes of the transaction item, `ti_total` is the total number of bytes of the transaction item, `ts_done` is the number of actions processed in the whole transaction and `ts_total` is the total number of actions in the whole transaction.
