===================================
 ``Base``---The centerpiece of DNF
===================================

.. class:: dnf.Base

  Instances of :class:`dnf.Base` are the central point of functionality supplied by DNF. An application will typically create a single instance of this class which it will keep for the runtime needed to accomplish its packaging tasks. Plugins are managed by DNF and get a reference to :class:`dnf.Base` object when they run.

  .. attribute:: comps

    Is ``None`` by default. Explicit load via :meth:`read_comps`  initializes this attribute to a :class:`dnf.comps.Comps` instance.

  .. attribute:: conf

    An instance of :class:`dnf.conf.Conf`, concentrates all the different configuration options. :meth:`__init__` initializes this to usable defaults.

  .. attribute:: repos

    A :class:`dnf.repodict.RepoDict` instance, this member object contains all the repositories available.

  .. attribute:: transaction

    A resolved transaction object, a :class:`dnf.transaction.Transaction` instance, or ``None`` if no transaction has been prepared yet.

  .. method:: __init__()

    Produce an instance with a reasonable default configuration. The constructor takes no arguments.

  .. method:: fill_sack([load_system_repo=True, load_available_repos=True])

    Setup the package sack. If `load_system_repo` is ``True``, load information about packages in the local RPMDB into the sack. Else no package is considered installed during dependency solving. If `load_available_repos` is ``True``, load information about packages from the available repositories into the sack.

    This operation can take a long time. Adding repositories or changing repositories' configuration does not affect the information within the sack until :meth:`activate_sack` has been called.

  .. method:: do_transaction([display])

    Perform the resolved transaction. Use the optional `display` object to report the progress.

  .. method:: download_packages(pkglist)

    Download packages in `pkglist` from remote repositories. Packages from local repositories or from the command line are not downloaded.

  .. method:: install(pkg_spec)

    Mark packages matching `pkg_spec` for installation. `pkg_spec` can be any package specification recognized by :class:`dnf.queries.Subject`. Raises :exc:`dnf.exceptions.PackageNotFoundError` if the spec could not be matched against a known package. Return the number of packages that the operation has marked for installation.

  .. method:: read_comps()

    Read comps data from all the enabled repositories and initialize the :attr:`comps` object.

  .. method:: resolve()

    Resolve the marked requirements and store the resulting :class:`dnf.transaction.Transaction` into :attr:`transaction`. Raise :exc:`dnf.exceptions.DepsolveError` on a depsolving error. Return ``True`` iff the resolved transaction is non-empty.

    The exact operation of the solver depends on the :attr:`dnf.conf.Conf.best` setting.

  .. method:: select_group(group, pkg_types=None)

    Mark packages in the group for installation. Return the number of packages that the operation has marked for installation. `pkg_types` is a sequence of strings determining the kinds of packages to be installed, where the respective groups can be selected by adding ``"mandatory"``, ``"default"`` or ``"optional"`` to it. If `pkg_types` is ``None``, it defaults to ``("mandatory", "default")``.