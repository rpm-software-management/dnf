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

===========
Transaction
===========

.. module:: dnf.db.group


.. class:: RPMTransaction

  Instances of this class describe a resolved transaction set. The transaction object can be iterated for the contained :class:`items <.TransactionItem>`.

  The packaging requests from the contained items are later passed to the core package manager (RPM) as they are without further dependency resolving. If the set is not fit for an actual transaction (e.g. introduces conflicts, has inconsistent dependencies) RPM then by default refuses to proceed.

  .. attribute:: install_set

    Read-only property which contains set of :class:`Packages <.package.Package>` to be installed.

  .. attribute:: remove_set

    Read-only property which contains set of :class:`Packages <.package.Package>` to be removed.
