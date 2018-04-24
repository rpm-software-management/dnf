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

.. module:: dnf.transaction

.. class:: TransactionItem

  .. method:: installs()

    Return :class:`packages <dnf.package.Package>` that will get added onto the system by this transaction item.

  .. method:: removes()

    Return :class:`packages <dnf.package.Package>` that will get removed from the system by this transaction item.


.. class:: Transaction

  Instances of this class describe a resolved transaction set. The transaction object can be iterated for the contained :class:`items <.TransactionItem>`.

  The packaging requests from the contained items are later passed to the core package manager (RPM) as they are without further dependency resolving. If the set is not fit for an actual transaction (e.g. introduces conflicts, has inconsistent dependencies) RPM then by default refuses to proceed.

  .. attribute:: install_set

    Read-only property which contains set of :class:`Packages <.package.Package>` to be installed.

  .. attribute:: remove_set

    Read-only property which contains set of :class:`Packages <.package.Package>` to be removed.

  .. method:: add_downgrade(new, downgraded, obsoleted)

    Add a downgrade operation to the transaction. `new` is a :class:`~.package.Package` to downgrade to, `downgraded` is the installed :class:`~.package.Package` being downgraded, `obsoleted` is a list of installed :class:`Packages <.package.Package>` that are obsoleted by the `downgrade` (or ``None`` for no obsoletes).

  .. method:: add_erase(erased)

    Add an erase operation to the transaction. `erased` is a :class:`~.package.Package` to erase.

  .. method:: add_install(new, obsoleted, reason='unknown')

    Add an install operation to the transaction. `new` is a :class:`~.package.Package` to install, `obsoleted` is a list of installed :class:`Packages <.package.Package>` that are obsoleted by `new` (or ``None`` for no obsoletes). `reason`, if provided, must be either ``'dep'`` for a package installed as a dependency, ``'user'`` for a package installed per user's explicit request or ``'unknown'`` for cases where the package's origin can not be decided. This information is stored in the DNF package database and used for instance by the functionality that removes excess packages (see :ref:`clean_requirements_on_remove <clean_requirements_on_remove-label>`).

  .. method:: add_reinstall(new, reinstalled, obsoleted)

    Add a reinstall operation to the transaction. `new` is a :class:`~.package.Package` to reinstall over the installed `reinstalled`. `obsoleted` is a list of installed :class:`Packages <.package.Package>` that are obsoleted by `new`.

  .. method:: add_upgrade(upgrade, upgraded, obsoleted)

    Add an upgrade operation to the transaction. `upgrade` is a :class:`~.package.Package` to upgrade to, `upgraded` is the installed :class:`~.package.Package` to be upgraded, `obsoleted` is a list of installed :class:`Packages <.package.Package>` that are obsoleted by the `upgrade`.
