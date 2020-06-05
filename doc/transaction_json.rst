..
  Copyright (C) 2020 Red Hat, Inc.

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

.. _transaction_json-label:

################################
 Stored Transaction JSON Format
################################

The stored transaction format is considered unstable and may change in an
incompatible way at any time. It will work if the same version of dnf is used
to store and replay (or between versions as long as it stays the same).

==================
 Top-level Object
==================

``version``
    Type: string

    The version of the stored transaction format, in the form ``MAJOR.MINOR``.

    ``MAJOR`` version denotes backwards incompatible changes (old dnf won't work with
    new transaction JSON).

    ``MINOR`` version denotes extending the format without breaking backwards
    compatibility (old dnf can work with new transaction JSON).

``rpms``
    Type: an array of :ref:`rpm <rpm-label>` objects

    A list of RPM packages in the transaction.

``groups``
    Type: an array of :ref:`group <group-label>` objects

    A list of groups in the transaction.

``environments``
    Type: an array of :ref:`group <environment-label>` objects

    A list of environment groups in the transaction.


.. _rpm-label:

==============
 `rpm` Object
==============

``action``
    Type: string

    Possible values: ``Downgrade, Downgraded, Install, Obsoleted, Reason Change, Reinstall, Reinstalled, Removed, Upgrade, Upgraded``

    The action performed on the package in the transaction.

``nevra``
    Type: string

    ``NEVRA`` (``name-epoch:version-release.arch``) of the package.

``reason``
    Type: string

    Possible values: ``dependency, clean, group, unknown, user, weak-dependency``

    The reason why the package was pulled into the transaction.

``repo_id``
    Type: string

    The id of the repository this package is coming from. Note repository ids are defined in the local respository configuration and may differ between systems.


.. _group-label:

================
 `group` Object
================

``action``
    Type: string

    Possible values: ``Install, Upgrade, Removed``

    The action performed on the group in the transaction.

``id``
    Type: string

    The id of the group.

``package_types``
    Type: string

    Possible values: ``conditional, default, mandatory, optional``

    The types of packages in the group that will be installed. Valid only for
    the ``Install`` action.

``packages``
    Type: an array of :ref:`group-package <group-package-label>` objects

    The packages belonging to the group in the transaction.


.. _environment-label:

======================
 `environment` Object
======================

``action``
    Type: string

    Possible values: ``Install, Upgrade, Removed``

    The action performed on the environment group in the transaction.

``id``
    Type: string

    The id of the environment group.

``package_types``
    Type: string

    Possible values: ``conditional, default, mandatory, optional``

    The types of packages in the environment group that will be installed.
    Valid only for the ``Install`` action.

``group``
    Type: an array of :ref:`environment-group <environment-group-label>` objects

    The groups belonging to the environment in the transaction.


.. _group-package-label:

========================
 `group-package` Object
========================

``installed``
    Type: boolean

    Whether the package is considered installed as part of the group.

``name``
    Type: string

    The name of the package.

``package_type``
    Type: string

    Possible values: ``conditional, default, mandatory, optional``

    The type of the package in the group.


.. _environment-group-label:

============================
 `environment-group` Object
============================

``group_type``
    Type: string

    Possible values: ``mandatory, optional``

    The type of the group in the environment.

``id``
    Type: string

    The id of the group.

``installed``
    Type: boolean

    Whether the group is considered installed as part of the environment.
