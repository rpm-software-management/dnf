===========
Transaction
===========

.. class:: dnf.transaction.Transaction()

  Instances of this class describe a resolved transaction set. The members of the transaction are later passed to the core package manager (RPM) as they are without further dependency resolving. If the set is not fit for an actual transaction (e.g. introduces conflicts, has inconsistent dependencies) RPM then by default refuses to proceed.

  .. method:: add_downgrade(new, downgraded, obsoleted)

    Add a downgrade operation to the transaction. `new` is a :class:`~.package.Package` to downgrade to, `downgraded` is the installed :class:`~.package.Package` being downgraded, `obsoleted` is a list of installed :class:`Packages <.package.Package>` that are obsoleted by the `downgrade` (or ``None`` for no obsoletes).

  .. method:: add_erase(erased)

    Add an erase operation to the transaction. `erased` is a :class:`~.package.Package` to erase.

  .. method:: add_install(new, obsoleted, reason='unknown')

    Add an install operation to the transaction. `new` is a :class:`~.package.Package` to install, `obsoleted` is a list of installed :class:`Packages <.package.Package>` that are obsoleted by `new` (or ``None`` for no obsoletes). `reason`, if provided, must be either ``'dep'`` for a package installed as a dependnecy, ``'user'`` for a package installed per user's explicit request or ``'unknown'`` for cases where the package's origin can not be decided. This information is stored in the DNF package database and used for instance by the functionality that removes excess packages (see :ref:`clean_requirements_on_remove <clean_requirements_on_remove-label>`).

  .. method:: add_reinstall(new, reinstalled, obsoleted)

    Add a reinstall operation to the transaction. `new` is a :class:`~.package.Package` to reinstall over the installed `reinstalled`. `obsoleted` is a list of installed :class:`Packages <.package.Package>` that are obsoleted by `new`.

  .. method:: add_upgrade(upgrade, upgraded, obsoleted)

    Add an upgrade operation to the transaction. `upgrade` is a :class:`~.package.Package` to upgrade to, `upgraded` is the installed :class:`~.package.Package` to be upgraded, `obsoleted` is a list of installed :class:`Packages <.package.Package>` that are obsoleted by the `upgrade`.
