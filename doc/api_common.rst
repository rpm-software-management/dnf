..
  Copyright (C) 2014-2018 Red Hat, Inc.

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