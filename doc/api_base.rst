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

===================================
 ``Base``---The centerpiece of DNF
===================================

.. class:: dnf.Base

  Instances of :class:`dnf.Base` are the central point of functionality supplied by DNF. An application will typically create a single instance of this class which it will keep for the runtime needed to accomplish its packaging tasks. Plugins are managed by DNF and get a reference to :class:`dnf.Base` object when they run.

  :class:`.Base` instances are stateful objects holding references to various data sources and data sinks. To properly finalize and close off any handles the object may hold, client code should either call :meth:`.Base.close` when it has finished operations with the instance, or use the instance as a context manager. After the object has left the context, or its :meth:`.Base.close` has been called explicitly, it must not be used. :meth:`.Base.close` will delete all downloaded packages upon successful transaction.

  .. attribute:: comps

    Is ``None`` by default. Explicit load via :meth:`read_comps`  initializes this attribute to a :class:`dnf.comps.Comps` instance.

  .. attribute:: conf

    An instance of :class:`dnf.conf.Conf`, concentrates all the different configuration options. :meth:`__init__` initializes this to usable defaults.

  .. attribute:: goal

    An instance of :class:`dnf.goal.Goal` that this :class:`Base<dnf.Base>` object is using.

  .. attribute:: repos

    A :class:`dnf.repodict.RepoDict` instance, this member object contains all the repositories available.

  .. attribute:: sack

    The :class:`Sack<dnf.sack.Sack>` that this :class:`Base<dnf.Base>` object is using. It needs to be explicitly initialized by :meth:`fill_sack`.

  .. attribute:: transaction

    A resolved transaction object, a :class:`dnf.transaction.Transaction` instance, or ``None`` if no transaction has been prepared yet.

  .. method:: __init__()

    Init an instance with a reasonable default configuration. The constructor takes no arguments.

  .. method:: add_remote_rpms(path_list, strict=True, progress=None)

    This function must be called before anything is added to the :attr:`goal`. Adds RPM files
    in path_list to the :attr:`sack` and return the list of respective :class:`dnf.package.Package`
    instances. Downloads the RPMs to a temporary file for each path if it is a remote URL.
    Raises :exc:`IOError` if there are `IO` problems with files and `strict=True`. Raises
    :exc:`dnf.exceptions.Error` if the :attr:`goal` is not empty. `progress`, if given, should be a
    :class:`.DownloadProgress` instance which can be used to monitor the progress of the download.

  .. method:: close()

    Close all external handles the object holds. This is called automatically via context manager mechanism if the instance is handled using the ``with`` statement.

  .. method:: init_plugins([disabled_glob=None, cli=None])

     Initialize plugins. If you want to disable some plugins pass the list of their name patterns to
     `disabled_glob`. When run from interactive script then also pass your :class:`dnf.cli.Cli` instance.

  .. method:: pre_configure_plugins()

     Configure plugins by running their pre_configure() method. It makes possible to change
     variables before repo files and rpmDB are loaded. It also makes possible to create internal
     repositories that will be affected by ``--disablerepo`` and ``--enablerepo``.

  .. method:: configure_plugins()

     Configure plugins by running their configure() method.

  .. method:: fill_sack([load_system_repo=True, load_available_repos=True])

    Setup the package sack. If `load_system_repo` is ``True``, load information about packages in the local RPMDB into the sack. Else no package is considered installed during dependency solving. If `load_available_repos` is ``True``, load information about packages from the available repositories into the sack.

    This operation will call :meth:`load() <dnf.repo.Repo.load>` for repos as necessary and can take a long time. Adding repositories or changing repositories' configuration does not affect the information within the sack until :meth:`fill_sack` has been called.

    Before this method is invoked, the client application should setup any explicit configuration relevant to the operation. This will often be at least :attr:`conf.cachedir <.Conf.cachedir>` and the substitutions used in repository URLs. See :attr:`.Conf.substitutions`.

    Throws `IOError` exception in case cached metadata could not be opened.

    Example::

        #!/usr/bin/python3
        import dnf

        base = dnf.Base()
        conf = base.conf
        conf.cachedir = '/tmp/my_cache_dir'
        conf.substitutions['releasever'] = '30'
        conf.substitutions['basearch'] = 'x86_64'

        base.repos.add_new_repo('my-repo', conf,
            baseurl=["http://download.fedoraproject.org/pub/fedora/linux/releases/$releasever/Everything/$basearch/os/"])
        base.fill_sack()

        print("Enabled repositories:")
        for repo in base.repos.iter_enabled():
            print("id: {}".format(repo.id))
            print("baseurl: {}".format(repo.baseurl))


  .. method:: do_transaction([display])

    Perform the resolved transaction. Use the optional `display` object(s) to report the progress. `display` can be either an instance of a subclass of :class:`dnf.callback.TransactionProgress` or a sequence of such instances. Raise :exc:`dnf.exceptions.Error` or dnf.exceptions.TransactionCheckError.

  .. method:: download_packages(pkglist, progress=None, callback_total=None)

    Download packages in `pkglist` from remote repositories. Packages from local repositories or from the command line are not downloaded. `progress`, if given, should be a :class:`.DownloadProgress` and can be used by the caller to monitor the progress of the download. `callback_total` is a function accepting two parameters: total size of the downloaded content in bytes and time when the download process started, in seconds since the epoch. Raises :exc:`.DownloadError` if some packages failed to download.

  .. method:: group_install(group_id, pkg_types, exclude=None, strict=True)

    Mark group with corresponding `group_id` installed and mark the packages in the group for installation. Return the number of packages that the operation has marked for installation. `pkg_types` is a sequence of strings determining the kinds of packages to be installed, where the respective groups can be selected by including ``"mandatory"``, ``"default"`` or ``"optional"`` in it. If `exclude` is given, it has to be an iterable of package name glob patterns: :meth:`.group_install` will then not mark the respective packages for installation whenever possible. Parameter `strict` is a boolean indicating whether group packages that exist but are non-installable due to e.g. dependency issues should be skipped (False) or cause transaction to fail to resolve (True).

  .. method:: group_remove(group_id)

    Mark group with corresponding `group_id` not installed. All the packages marked as belonging to this group will be marked for removal. Return the number of packages marked for removal in this call.

  .. method:: group_upgrade(group_id)

    Upgrade group with corresponding `group_id`. If there has been packages added to the group's comps information since installing on the system, they will be marked for installation. Similarly, removed packages get marked for removal. The remaining packages in the group are marked for an upgrade. The operation respects the package types from the original installation of the group.

  .. method:: environment_install(env_id, types, exclude=None, strict=True, exclude_groups=None)

    Similar to :meth:`.group_install` but operates on environmental groups. `exclude_groups` is an iterable of group IDs that will not be marked as installed.

  .. method:: environment_remove(env_id)

    Similar to :meth:`.group_remove` but operates on environmental groups.

  .. method:: environment_upgrade(env_id)

    Similar to :meth:`.group_upgrade` but operates on environmental groups.

  .. method:: read_all_repos()

    Read repository configuration from the main configuration file specified by :attr:`dnf.conf.Conf.config_file_path` and any ``.repo`` files under :attr:`dnf.conf.Conf.reposdir`. All the repositories found this way are added to :attr:`~.Base.repos`.

  .. method:: read_comps(arch_filter=False)

    Read comps data from all the enabled repositories and initialize the :attr:`comps` object. If `arch_filter` is set to ``True``, the result is limited to system basearch.

  .. method:: reset(\*\*kwargs)

    Reset the state of different :class:`.Base` attributes. Selecting attributes to reset is controlled by passing the method keyword arguments set to ``True``. When called with no arguments the method has no effect.

    =============== =================================================
    argument passed effect
    =============== =================================================
    `goal=True`     drop all the current :ref:`packaging requests <package_marking-label>`
    `repos=True`    drop the current repositories (see :attr:`.repos`). This won't
                    affect the package data already loaded into the :attr:`.sack`.
    `sack=True`     drop the current sack (see :attr:`.sack`)
    =============== =================================================

  .. method:: resolve(allow_erasing=False)

    Resolve the marked requirements and store the resulting :class:`dnf.transaction.Transaction` into :attr:`transaction`. Raise :exc:`dnf.exceptions.DepsolveError` on a depsolving error. Return ``True`` if the resolved transaction is non-empty.

    Enabling `allow_erasing` lets the solver remove other packages while looking to fulfill the current packaging requests. For instance, this is used to allow the solver to remove dependants of a package being removed.

    The exact operation of the solver further depends on the :attr:`dnf.conf.Conf.best` setting.

  .. method:: update_cache(timer=False)

    Downloads and caches in binary format metadata for all known repos. Tries to avoid downloading
    whenever possible (e.g. when the local metadata hasn’t expired yet or when the metadata
    timestamp hasn’t changed).

    If 'timer' equals 'True', DNF becomes more resource-aware, meaning DNF will not do anything if
    running on battery power and will terminate immediately if it’s too soon after the last
    successful update_cache operation.

    When the method is used after :meth:`fill_sack`, information about packages will not be updated.

  .. _package_marking-label:

  The :class:`.Base` class provides a number of methods to make packaging requests that can later be resolved and turned into a transaction. The `pkg_spec` argument some of them take must be a package specification recognized by :class:`dnf.subject.Subject`. If these methods fail to find suitable packages for the operation they raise a :exc:`~dnf.exceptions.MarkingError`. Note that successful completion of these methods does not necessarily imply that the desired transaction can be carried out (e.g. for dependency reasons).

  .. method:: downgrade(pkg_spec)

    Mark packages matching `pkg_spec` for downgrade.

  .. method:: install(pkg_spec, reponame=None, strict=True, forms=None)

    Mark packages matching `pkg_spec` for installation. 
    `reponame` can be a name of a repository or a list of repository names. If given, the selection of available packages is limited to packages from these repositories. If strict is set to False, the installation ignores packages with dependency solving problems. Parameter `forms` has the same meaning as in :meth:`dnf.subject.Subject.get_best_query`.

  .. method:: package_downgrade(pkg, strict=False)

    If `pkg` is a :class:`dnf.package.Package` in an available repository, mark the matching installed package for downgrade to `pkg`. If strict=False it ignores problems with dep-solving.

  .. method:: package_install(pkg, strict=True)

    Mark `pkg` (a :class:`dnf.package.Package` instance) for installation. Ignores package that is already installed. `strict` has the same meaning as in :meth:`install`.

  .. method:: package_upgrade(pkg)

    If `pkg` is a :class:`dnf.package.Package` in an available repository, mark the matching installed package for upgrade to `pkg`.

  .. method:: autoremove()

    Removes all 'leaf' packages from the system that were originally installed as dependencies of user-installed packages but which are no longer required by any such package.

  .. method:: remove(pkg_spec, reponame=None, forms=None)

    Mark packages matching `pkg_spec` for removal. `reponame` and `forms` have the same meaning as in :meth:`install`.

  .. method:: upgrade(pkg_spec, reponame=None)

    Mark packages matching `pkg_spec` for upgrade. `reponame` has the same meaning as in :meth:`install`.

  .. method:: upgrade_all(reponame=None)

    Mark all installed packages for an upgrade. `reponame` has the same meaning as in :meth:`install`.

  .. method:: urlopen(url, repo=None, mode='w+b', \*\*kwargs):

    Open the specified absolute `url` and return a file object which respects proxy setting even for non-repo downloads

  .. method:: install_specs(install, exclude=None, reponame=None, strict=True, forms=None)

    Provides unified way to mark packages, groups or modules for installation. The `install` and `exclude` arguments have to be iterables containing specifications of packages (e.g. 'dnf') or groups/modules (e.g. '\@core'). Specifications from the `exclude` list will not be marked for installation. The `reponame`, `strict` and `forms` parameters have the same meaning as in :meth:`install`. In case of errors the method raises :exc:`dnf.exceptions.MarkingErrors`.

    Example to install two groups and a package::

        #!/usr/bin/python3
        import dnf
        import dnf.cli.progress

        base = dnf.Base()
        base.read_all_repos()
        base.fill_sack()

        base.install_specs(['acpi', '@Web Server', '@core'])
        print("Resolving transaction...",)
        base.resolve()
        print("Downloading packages...")
        progress = dnf.cli.progress.MultiFileProgressMeter()
        base.download_packages(base.transaction.install_set, progress)
        print("Installing...")
        base.do_transaction()
