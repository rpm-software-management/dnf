==================================
 Common Provisions of the DNF API
==================================

.. _logging_label:

---------
 Logging
---------

DNF uses the standard `Python logging module <http://docs.python.org/3.3/library/logging.html>`_ to do its logging. Three standard loggers are provided:

* ``dnf``, used by the core and CLI components of DNF. Messages logged via this logger can end up written to the stdout (console) the DNF process is attached too. For this reason messages logged on the ``INFO`` level or above should be marked for localization (if the extension uses it).
* ``dnf.plugin`` should be used by plugins for debugging and similar messages that are generally not written to the standard output streams but logged into the DNF logfile.
* ``dnf.rpm`` is a logger used by RPM transaction callbacks. Plugins and extensions should not manipulate this logger.

Extensions and plugins can add or remove logging handlers of these loggers at their own discretion.