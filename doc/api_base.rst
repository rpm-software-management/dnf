===================================
 ``Base``---The centerpiece of DNF
===================================

.. class:: dnf.Base

  Instances of :class:`dnf.Base` are the central point of functionality supplied by DNF. An application will typically create a single instance of this class which it will keep for the runtime needed to accomplish its packaging tasks. Plugins are managed by DNF and get a reference to :class:`dnf.Base` object when they run.

  :class:`.Base` instances are stateful objects holding references to various data sources and data sinks. To properly finalize and close off any handles the object may hold, client code should either call :meth:`.Base.close` when it has finished opertions with the instance, or use the instance as a context manager. After the object has left the context, or its :meth:`.Base.close` has been called explicitly, it must not be used.

  .. attribute:: comps

    Is ``None`` by default. Explicit load via :meth:`read_comps`  initializes this attribute to a :class:`dnf.comps.Comps` instance.

  .. attribute:: conf

    An instance of :class:`dnf.conf.Conf`, concentrates all the different configuration options. :meth:`__init__` initializes this to usable defaults.

  .. attribute:: repos

    A :class:`dnf.repodict.RepoDict` instance, this member object contains all the repositories available.

  .. attribute:: sack

    The :class:`Sack<dnf.sack.Sack>` that this :class:`Base<dnf.Base>` object is using. It needs to be explicitly initialized by :meth:`fill_sack`.

  .. attribute:: transaction

    A resolved transaction object, a :class:`dnf.transaction.Transaction` instance, or ``None`` if no transaction has been prepared yet.

  .. method:: __init__()

    Init an instance with a reasonable default configuration. The constructor takes no arguments.

  .. method:: add_remote_rpm(path)

    Add RPM file at `path` to the :attr:`sack` and return the respective :class:`dnf.package.Package` instance. Does the download to a temporary file if `path` is a remote URL. Raises :exc:`IOError` if there are problems obtaining or reading the file.

  .. method:: close()

    Close all external handles the object holds. This is called automatically via context manager mechanism if the instance is handled using the ``with`` statement.

  .. method:: fill_sack([load_system_repo=True, load_available_repos=True])

    Setup the package sack. If `load_system_repo` is ``True``, load information about packages in the local RPMDB into the sack. Else no package is considered installed during dependency solving. If `load_available_repos` is ``True``, load information about packages from the available repositories into the sack.

    This operation can take a long time. Adding repositories or changing repositories' configuration does not affect the information within the sack until :meth:`activate_sack` has been called.

  .. method:: do_transaction([display])

    Perform the resolved transaction. Use the optional `display` object to report the progress.

  .. method:: download_packages(pkglist, progress=None)

    Download packages in `pkglist` from remote repositories. Packages from local repositories or from the command line are not downloaded. `progress`, if given, should be a :class:`.DownloadProgress` and can be used by the caller to monitor the progress of the download. Raises :exc:`.DownloadError` if some packages failed to download.

  .. method:: group_install(group, pkg_types, exclude=None)

    Mark `group` (a :class:`dnf.comps.Group` instance) installed and mark the packages in the group for installation. Return the number of packages that the operation has marked for installation. `pkg_types` is a sequence of strings determining the kinds of packages to be installed, where the respective groups can be selected by including ``"mandatory"``, ``"default"`` or ``"optional"`` in it. If `exclude` is given, it has to be an iterable of package names: :meth:`.group_install` will then not mark the respective packages for installation whenever possible (but e.g. packages tagged *mandatory* will be marked for intallation no matter the value of `exlcude`)

  .. method:: group_remove(group)

    Mark `group` (a :class:`dnf.comps.Group` instance) not installed. All the packages marked as belonging to this group will be marked for removal. Return the number of packages marked for removal in this call.

  .. method:: read_all_repos()

    Read repository configuration from the main configuration file specified by :attr:`dnf.conf.Conf.config_file_path` and any ``.repo`` files under :attr:`dnf.conf.Conf.reposdir`. All the repositories found this way are added to :attr:`~.Base.repos`.

  .. method:: read_comps()

    Read comps data from all the enabled repositories and initialize the :attr:`comps` object.

  .. method:: reset(**kwargs)

    Reset the state of different :class:`.Base` attributes. Selecting attributes to reset is controlled by passing the method keyword arguments set to ``True``. When called with no arguments the method has no effect.

    =============== =================================================
    argument passed effect
    =============== =================================================
    `goal=True`     drop all the current :ref:`packaging requests <package_marking-label>`
    `repos=True`    drop the current repositries (see :attr:`.repos`). This won't
                    affect the package data already loaded into the :attr:`.sack`.
    `sack=True`     drop the current sack (see :attr:`.sack`)
    =============== =================================================

  .. method:: resolve(allow_erasing=True)

    Resolve the marked requirements and store the resulting :class:`dnf.transaction.Transaction` into :attr:`transaction`. Raise :exc:`dnf.exceptions.DepsolveError` on a depsolving error. Return ``True`` iff the resolved transaction is non-empty.

    Enabling `allow_erasing` lets to solver remove other packages while looking to fulfill the current packaging requests. For instance, this is used to allow the solver remove dependants of a package being removed.

    The exact operation of the solver further depends on the :attr:`dnf.conf.Conf.best` setting.

  .. method:: select_group(group, pkg_types=None)

    Mark packages in the group for installation. Return the number of packages that the operation has marked for installation. `pkg_types` is a sequence of strings determining the kinds of packages to be installed, where the respective groups can be selected by adding ``"mandatory"``, ``"default"`` or ``"optional"`` to it. If `pkg_types` is ``None``, it defaults to ``("mandatory", "default")``.

    .. warning::
      As of dnf-0.4.18 this method is deprecated and will be dropped as early as dnf-0.4.21 (also see :ref:`deprecating-label`). Use :meth:`.group_install`.

  .. _package_marking-label:

  The :class:`.Base` class provides a number of methods to make packaging requests that can later be resolved and turned into a transaction. The `pkg_spec` argument some of them take must be a package specification recognized by :class:`dnf.subject.Subject`. If these methods fail to find suitable packages for the operation they raise a :exc:`~dnf.exceptions.MarkingError`. Note that successful completion of these methods does not necessarily imply that the desired transaction can be carried out (e.g. for dependency reasons).

  .. method:: downgrade(pkg_spec)

    Mark packages matching `pkg_spec` for downgrade.

  .. method:: install(pkg_spec)

    Mark packages matching `pkg_spec` for installation.

  .. method:: package_downgrade(pkg)

    If `pkg` is a :class:`dnf.package.Package` in an available repository, mark the matching installed package for downgrade to `pkg`.

  .. method:: package_install(pkg)

    Mark `pkg` (a :class:`dnf.package.Package` instance) for installation.

  .. method:: package_upgrade(pkg)

    If `pkg` is a :class:`dnf.package.Package` in an available repository, mark the matching installed package for upgrade to `pkg`.

  .. method:: remove(pkg_spec)

    Mark packages matching `pkg_spec` for removal.

  .. method:: upgrade(pkg_spec)

    Mark packages matching `pkg_spec` for upgrade.

  .. method:: upgrade_all

    Mark all installed packages for an upgrade.
