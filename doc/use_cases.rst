..
  Copyright (C) 2015  Red Hat, Inc.

  This copyrighted material is made available to anyone wishing to use,
  modify, copy, or redistribute it subject to the terms and conditions of
  the GNU General Public License v.2, or (at your option) any later version.
  This program is distributed in the hope that it will be useful, but WITHOUT
  ANY WARRANTY expressed or implied, including the implied warranties of
  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General
  Public License for more details.  You should have received a copy of the
  GNU General Public License along with this program; if not, see
  <https://www.gnu.org/licenses/>.  Any Red Hat trademarks that are
  incorporated in the source code or documentation are not subject to the GNU
  General Public License and may only be used or replicated with the express
  permission of Red Hat, Inc.

###############
 DNF Use Cases
###############

.. contents::

==============
 Introduction
==============

Every feature present in DNF should be based on a reasonable use case. All the
supported use cases are supposed to be enumerated in this document.

In case you use DNF to achieve a goal which is not documented here, either you
found an error in the documentation or you misuse DNF. In either case we would
appreciate if you share the case with us so we can help you to use DNF in the
correct way or add the case to the list. You can only benefit from such a
report because then you can be sure that the behavior that you expect will not
change without prior notice in the :doc:`release_notes` and that the behavior
will be covered by our test suite.

.. IMPORTANT::

  Please consult every usage of DNF with our reference documentation to be sure
  what are you doing. The examples mentioned here are supposed to be as simple
  as possible and may ignore some minor corner cases.

.. WARNING::

  The list is not complete yet - the use cases are being added incrementally
  these days.

=====================
 General assumptions
=====================

The user in question must have the appropriate permissions.

.. _install_use_case-label:

========================================================================================
 Ensure that my system contains given mix of features (packages/files/providers/groups)
========================================================================================

A system administrator has a list of features that has to be present in an
operating system. The features must be provided by RPM packages in system
repositories that must be accessible.

A feature may be for example a concrete version of a package
(``hawkey-0.5.3-1.fc21.i686``), a pathname of a binary RPM file
(``/var/lib/mock/fedora-21-i386/result/hawkey-0.5.3-2.20150116gitd002c90.fc21.i686.rpm``),
an URL of a binary RPM file
(``http://jenkins.cloud.fedoraproject.org/job/DNF/lastSuccessfulBuild/artifact/fedora-21-i386-build/hawkey-0.5.3-99.649.20150116gitd002c90233fc96893806836a258f14a50ee0cf47.fc21.i686.rpm``),
a configuration file (``/etc/yum.repos.d/fedora-rawhide.repo``), a language
interpreter (``ruby(runtime_executable)``), an extension (``python3-dnf``), a
support for building modules for the current running kernel
(``kernel-devel-uname-r = $(uname -r)``), an executable (``*/binaryname``) or a
collection of packages specified by any available identifier (``kde-desktop``).

The most recent packages that provide the missing features and suit
installation (that are not obsoleted and do not conflict with each other or
with the other installed packages) are installed if the given feature is not
present already. If any of the packages cannot be installed, the operation
fails.

-----
 CLI
-----

::

    SPECS="hawkey-0.5.3-1.fc21.i686 @kde-desktop"  # Set the features here.

    dnf install $SPECS

-----------------
 Plugins/CLI API
-----------------

.. include:: examples/install_plugin.py
   :code: python
   :start-line: 16

If it makes any sense, the plugin can do the operation in appropriate hooks
instead of registering a new command that needs to be called from the command
line.

---------------
 Extension API
---------------

.. include:: examples/install_extension.py
   :code: python
   :start-line: 16

=========================================================================
Get a list of available packages filtered by their relation to the system
=========================================================================

A system user wants to obtain a list of available RPM packages for their
consecutive automatic processing or for informative purpose only.
The list of RPM packages is filtered by requested relation to the system
or user provided <package-name-specs>. The obtained list of packages
is based on available data supplied by accessible system repositories.

A relation to the system might be for example one of the following:

installed - packages already installed on the system

available - packages available in any accessible repository

extras - packages installed on the system not available in any known
repository

obsoletes - installed packages that are obsoleted by packages in any
accessible repository

recent - packages recently added into accessible repositories

upgrades - available packages upgrading some installed packages

-----
CLI
-----

::

    dnf list *dnf*
    dnf list installed *debuginfo
    dnf list available gtk*devel
    dnf list extras
    dnf list obsoletes
    dnf list recent
    dnf list upgrades

-----------------
Plugins/CLI API
-----------------

.. include:: examples/list_obsoletes_plugin.py
   :code: python
   :start-line: 16

---------------
Extension API
---------------

.. include:: examples/list_extras_extension.py
   :code: python
   :start-line: 16
