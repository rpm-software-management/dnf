============
 Exceptions
============

.. exception:: dnf.exceptions.Error

.. exception:: dnf.exceptions.DeprecationWarning

  Used to emit deprecation warnings using Python's :func:`warnings.warning` function.

.. exception:: dnf.exceptions.DepsolveError

.. exception:: dnf.exceptions.DownloadError

.. exception:: dnf.exceptions.MarkingError

.. exception:: dnf.exceptions.PackageNotFoundError

  Inherits from :exc:`.MarkingError`.

  .. warning::
    As of dnf-0.4.9 this exception is deprecated and will be dropped as early as dnf-0.4.12 (also see :ref:`deprecating-label`).

.. exception:: dnf.exceptions.RepoError
