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

    `msg` is a an optional string error message further explaining the `status`.

  .. method:: progress(payload, done)

    Report ongoing progress on the given `payload`. `done` is the number of bytes already downloaded from `payload`.

  .. method:: start(total_files, total_size)

    Report start of a download batch. `total_files` is the total number of payloads in the batch. `total_size` is the total number of bytes to be downloaded.
