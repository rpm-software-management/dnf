..
  Copyright (C) 2014-2016 Red Hat, Inc.

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

.. _command_ref-label:

#######################
 DNF Command Reference
#######################

========
Synopsis
========

``dnf [options] <command> [<args>...]``

===========
Description
===========

.. _command_provides-label:

`DNF`_ is the next upcoming major version of `Yum`_, a package manager for RPM-based Linux distributions. It roughly
maintains CLI compatibility with Yum and defines strict API for extensions and plugins. Plugins can modify or extend
features of DNF or provide additional CLI commands on top of those mentioned below. If you know the name of such a
command (including commands mentioned below), you may find/install the package which provides it using the appropriate
virtual provide in the form of ``dnf-command(<alias>)`` where ``<alias>`` is the name of the command; e.g.
``dnf install 'dnf-command(repoquery)'`` to install a ``repoquery`` plugin (the same applies to specifying
dependencies of packages that require a particular DNF command).

Available commands:

* :ref:`autoremove <autoremove_command-label>`
* :ref:`check <check_command-label>`
* :ref:`check-update <check_update_command-label>`
* :ref:`clean <clean_command-label>`
* :ref:`distro-sync <distro_sync_command-label>`
* :ref:`downgrade <downgrade_command-label>`
* :ref:`group <group_command-label>`
* :ref:`help <help_command-label>`
* :ref:`history <history_command-label>`
* :ref:`info <info_command-label>`
* :ref:`install <install_command-label>`
* :ref:`list <list_command-label>`
* :ref:`makecache <makecache_command-label>`
* :ref:`mark <mark_command-label>`
* :ref:`provides <provides_command-label>`
* :ref:`reinstall <reinstall_command-label>`
* :ref:`remove <remove_command-label>`
* :ref:`repoinfo <repoinfo_command-label>`
* :ref:`repolist <repolist_command-label>`
* :ref:`repoquery <repoquery_command-label>`
* :ref:`repository-packages <repository-packages_command-label>`
* :ref:`search <search_command-label>`
* :ref:`updateinfo <updateinfo_command-label>`
* :ref:`upgrade <upgrade_command-label>`
* :ref:`upgrade-minimal <upgrade_minimal_command-label>`
* :ref:`upgrade-to <upgrade_to_command-label>`

Additional informations:

* :ref:`Options <options-label>`
* :ref:`Specifying Packages <specifying_packages-label>`
* :ref:`Specifying Exact Versions of Packages <specifying_packages_versions-label>`
* :ref:`Specifying Provides <specifying_provides-label>`
* :ref:`Specifying Groups <specifying_groups-label>`
* :ref:`Specifying Transactions <specifying_transactions-label>`
* :ref:`Metadata Synchronization <metadata_synchronization-label>`
* :ref:`Configuration Files Replacement Policy <configuration_files_replacement_policy-label>`
* :ref:`Files <files-label>`
* :ref:`See Also <see_also-label>`

.. _options-label:

=======
Options
=======

``-4``
    Resolve to IPv4 addresses only.

``-6``
    Resolve to IPv6 addresses only.

``--advisory=<advisory>, --advisories=<advisory>``
    Includes packages corresponding to the advisory ID, Eg. FEDORA-2201-123.
    Applicable for upgrade command.

``--allowerasing``
    Allow erasing of installed packages to resolve dependencies. This option could be used as an alternative to ``yum swap`` command where packages to remove are not explicitly defined.

``--assumeno``
    Automatically answer no for all questions

``-b, --best``
    Try the best available package versions in transactions. Specifically during :ref:`dnf upgrade <upgrade_command-label>`, which by default skips over updates that can not be installed for dependency reasons, the switch forces DNF to only consider the latest packages. When running into packages with broken dependencies, DNF will fail giving a reason why the latest version can not be installed.

``--bugfix``
    Includes packages that fix a bugfix issue. Applicable for upgrade command.

``--bz=<bugzilla>``
    Includes packages that fix a Bugzilla ID, Eg. 123123. Applicable for upgrade
    command.

``-C, --cacheonly``
    Run entirely from system cache, don't update the cache and use it even in case it is expired.

    DNF uses a separate cache for each user under which it executes. The cache for the root user is called the system cache. This switch allows a regular user read-only access to the system cache which usually is more fresh than the user's and thus he does not have to wait for metadata sync.

``-c <config file>, --config=<config file>``
    config file location

``--cve=<cves>``
    Includes packages that fix a CVE (Common Vulnerabilities and Exposures) ID
    (http://cve.mitre.org/about/), Eg. CVE-2201-0123. Applicable for upgrade
    command.

``-d <debug level>, --debuglevel=<debug level>``
    Debugging output level. This is an integer value between 0 (no additional information strings) and 10 (shows all debugging information, even that not understandable to the user), default is 2. Deprecated, use ``-v`` instead.

``--debugsolver``
    Dump data aiding in dependency solver debugging into ``./debugdata``.

.. _disableexcludes-label:

``--disableexcludes=[all|main|<repoid>]``

    Disable the config file excludes. Takes one of three options:

    * ``all``, disables all config file excludes
    * ``main``, disables excludes defined in the ``[main]`` section
    * ``repoid``, disables excludes defined for the given repo

``--disableplugin=<plugin names>``
    Disable the listed plugins specified by names or globs.

``--disablerepo=<repoid>``
    Disable specific repositories by an id or a glob. This option is mutually exclusive with ``--repo``.

.. _downloadonly-label:

``--downloadonly``
    Download resolved package set without performing any rpm transaction (install/upgrade/erase).

``-e <error level>, --errorlevel=<error level>``
    Error output level. This is an integer value between 0 (no error output) and
    10 (shows all error messages), default is 2. Deprecated, use ``-v`` instead.

``--enablerepo=<repoid>``
    Enable additional repositories by an id or a glob.

``--enhancement``
    Include enhancement relevant packages. Applicable for upgrade command.

``-x <package-spec>, --exclude=<package-spec>``
    Exclude packages specified by ``<package-spec>`` from the operation.

``-h, --help``
    Show the help.

.. _installroot-label:

``--installroot=<path>``
    Specifies an alternative installroot, relative to where all packages will be
    installed. Think of this like doing ``chroot <root> dnf`` except using
    ``--installroot`` allows dnf to work before the chroot is created.

- *cachedir*, *log files*, *releasever*, and *gpgkey* are taken from or
  stored in installroot. *Gpgkeys* are imported into installroot from
  path, related to the host, described in .repo file.

- *config file* and :ref:`reposdir <reposdir-label>` are searched inside the installroot first. If
  they are not present, they are taken from host system.
  Note:  When a path is specified within command line argument
  (``--config=<config file>`` in case of *config file* and
  ``--setopt=reposdir=<reposdir>`` for *reposdir*) then this path is always
  related to the host with no exceptions.

- The *pluginpath* and *pluginconfpath* are not related to installroot.

 Note: You may also want to use the command-line option
 ``--releasever=<release>`` when creating the installroot otherwise the
 *$releasever* value is taken from the rpmdb within the installroot (and thus
 it is empty at time of creation, the transaction will fail).
 The new installroot path at time of creation do not contain *repository*,
 *releasever*, and *dnf.conf* file.

 Installroot examples:

 ``dnf --installroot=<installroot> --releasever=<release> install system-release``
     Sets permanently the ``releasever`` of the system within
     ``<installroot>`` directory from given ``<release>``.

 ``dnf --installroot=<installroot> --setopt=reposdir=<path> --config /path/dnf.conf upgrade``
     Upgrade packages inside of installroot from repository described by
     ``--setopt`` using configuration from ``/path/dnf.conf``

``--newpackage``
    Include newpackage relevant packages. Applicable for upgrade command.

``--nogpgcheck``
    skip checking GPG signatures on packages

``--noplugins``
    Disable all plugins.

``-q, --quiet``
    In combination with a non-interactive command it shows just the relevant content. It suppresses messages notifying about current state or actions of DNF.

``-R <minutes>, --randomwait=<minutes>``
    maximum command wait time

.. _refresh_command-label:

``--refresh``
    set metadata as expired before running the command

``--releasever=<release>``
    configure DNF as if the distribution release was ``<release>``. This can
    affect cache paths, values in configuration files and mirrorlist URLs.

.. _repofrompath_options-label:


``--repofrompath <repo>,<path/url>``
    Specify a path or url to a repository (same path as in a baseurl) to add to
    the repositories for this query. This option can be used multiple times. The
    repo label for the repository is specified by <repo>. If you want to view
    only the packages from this repository, combine this with
    with ``--repo=<repo>`` or ``--disablerepo="*"`` switches.
    The repo label for the repository is specified by <repo>.

``--repo=<repoid>``
    Enable just specific repositories by an id or a glob. Can be used multiple
    times with accumulative effect. It is basically shortcut for
    ``--disablerepo="*" --enablerepo=<repoid>`` and is mutually exclusive with
    ``--disablerepo`` option.

``--rpmverbosity=<name>``
    RPM debug scriptlet output level. Sets the debug level to ``<name>`` for RPM scriptlets.
    For available levels, see ``rpmverbosity`` configuration option.

``--sec-severity=<severity>, --secseverity=<severity>``
    Includes packages that provides a fix for issue of the specified severity.
    Applicable for upgrade command.

``--security``
    Includes packages that provides a fix for security issue. Applicable for
    upgrade command.

``--setopt=<option>=<value>``
    override a config option from the config file. To override config options from repo files, use ``repoid.option`` for the ``<option>``.

``--showduplicates``
    show duplicates, in repos, in list/search commands

.. _verbose_options-label:

``-v, --verbose``
    verbose operation, show debug messages.

``--version``
    show DNF version and exit

``-y, --assumeyes``
    Automatically answer yes for all questions

List options are comma separated. Command-line options override respective settings from configuration files.

========
Commands
========

For an explanation of ``<package-spec>`` and ``<package-name-spec>`` see
:ref:`\specifying_packages-label`.

For an explanation of ``<package-nevr-spec>`` see
:ref:`\specifying_packages_versions-label`.

For an explanation of ``<provide-spec>`` see :ref:`\specifying_provides-label`.

For an explanation of ``<group-spec>`` see :ref:`\specifying_groups-label`.

For an explanation of ``<transaction-spec>`` see :ref:`\specifying_transactions-label`.

.. _autoremove_command-label:

-------------------
Auto Remove Command
-------------------

``dnf [options] autoremove``

    Removes all "leaf" packages from the system that were originally installed as dependencies of user-installed packages but which are no longer required by any such package.

Packages listed in :ref:`installonlypkgs <installonlypkgs-label>` are never automatically removed by
this command.

This command by default does not force a sync of expired metadata. See also :ref:`\metadata_synchronization-label`.

.. _check_command-label:

--------------------
Check Command
--------------------

``dnf [options] check [--dependencies] [--duplicates] [--obsoleted] [--provides]``

    Checks the local packagedb and produces information on any problems it
    finds. You can pass the check command the options "--dependencies",
    "--duplicates", "--obsoleted" or "--provides", to limit the checking that is
    performed (the default is "all" which does all).

.. _check_update_command-label:

--------------------
Check Update Command
--------------------

``dnf [options] check-update [<package-specs>...]``

    Non-interactively checks if updates of the specified packages are available. If no ``<package-specs>`` are given checks whether any updates at all are available for your system. DNF exit code will be 100 when there are updates available and a list of the updates will be printed, 0 if not and 1 if an error occurs.

    Please note that having a specific newer version available for an installed package (and reported by ``check-update``) does not imply that subsequent ``dnf upgrade`` will install it. The difference is that ``dnf upgrade`` must also ensure the satisfiability of all dependencies and other restrictions.

.. _clean_command-label:

-------------
Clean Command
-------------
Performs cleanup of temporary files kept for repositories. This includes any
such data left behind from disabled or removed repositories as well as for
different distribution release versions.

``dnf clean dbcache``
    Removes cache files generated from the repository metadata. This forces DNF
    to regenerate the cache files the next time it is run.

``dnf clean expire-cache``
    Marks the repository metadata expired. DNF will re-validate the cache for
    each repo the next time it is used.

``dnf clean metadata``
    Removes repository metadata. Those are the files which DNF uses to determine
    the remote availability of packages. Using this option will make DNF
    download all the metadata the next time it is run.

``dnf clean packages``
    Removes any cached packages from the system.

``dnf clean all``
    Does all of the above.

.. _distro_sync_command-label:

-------------------
Distro-sync command
-------------------

``dnf distro-sync [<package-spec>...]``
    As necessary upgrades, downgrades or keeps selected installed packages to match
    the latest version available from any enabled repository. If no package is given, all installed packages are considered.

    See also :ref:`\configuration_files_replacement_policy-label`.

------------------------------------
Distribution-synchronization command
------------------------------------

``dnf distribution-synchronization``
    Deprecated alias for the :ref:`\distro_sync_command-label`.

.. _downgrade_command-label:

-----------------
Downgrade Command
-----------------

``dnf [options] downgrade <package-installed-specs>...``
    Downgrades the specified packages to the highest of all known lower versions if possible. When version is given and is lower than version of installed package then it downgrades to target version.

.. _erase_command-label:

-------------
Erase Command
-------------

``dnf [options] erase <spec>...``
    Deprecated alias for the :ref:`\remove_command-label`.

.. _group_command-label:

-------------
Group Command
-------------

Groups are virtual collections of packages. DNF keeps track of groups that the user selected ("marked") installed and can manipulate the comprising packages with simple commands.

``dnf [options] group [summary] <group-spec>``
    Display overview of how many groups are installed and available. With a
    spec, limit the output to the matching groups. ``summary`` is the default
    groups subcommand.

``dnf [options] group info <group-spec>``
    Display package lists of a group. Shows which packages are installed or
    available from a repo when ``-v`` is used.

``dnf [options] group install [--with-optional] <group-spec>...``
    Mark the specified group installed and install packages it contains. Also include `optional` packages of the group if ``--with-optional`` is specified. All `mandatory` packages are going to be installed otherwise the transaction fails. `Default` packages will be installed whenever possible. `Optional` and `default` packages that are in conflict with other packages or have missing dependencies does not terminate the transaction and will be skipped.

.. _grouplist_command-label:

``dnf [options] group list <group-spec>...``
    List all matching groups, either among installed or available groups. If
    nothing is specified list all known groups. Options ``installed`` and ``available`` narrows down the requested list.
    Records are ordered by `display_order` tag defined in comps.xml file.
    Provides more detailed information when ``-v`` option is used.

``dnf [options] group remove <group-spec>...``
    Mark the group removed and remove those packages in the group from the system which are neither comprising another installed group and were not installed explicitly by the user.

``dnf [options] group upgrade <group-spec>...``
    Upgrades the packages from the group and upgrades the group itself. The latter comprises of installing pacakges that were added to the group by the distribution and removing packages that got removed from the group as far as they were not installed explicitly by the user.

Groups can also be marked installed or removed without physically manipulating any packages:

``dnf [options] group mark install <group-spec>...``
    Mark the specified group installed. No packages will be installed by this command but the group is then considered installed.

``dnf [options] group mark remove <group-spec>...``
    Mark the specified group removed. No packages will be removed by this command.

See also :ref:`\configuration_files_replacement_policy-label`.

.. _help_command-label:

------------
Help Command
------------

``dnf help [<command>]``
    Displays the help text for all commands. If given a command name then only
    displays the help for that particular command.

.. _history_command-label:

---------------
History Command
---------------

The history command allows the user to view what has happened in past
transactions and act according to this information (assuming the
``history_record`` configuration option is set).

.. _history_list_command-label:

``dnf history [list] [<spec>...]``
    The default history action is listing information about given transactions
    in a table. Each ``<spec>`` can be either a ``<transaction-spec>``, which
    specifies a transaction directly, or a ``<transaction-spec>..<transaction-spec>``,
    which specifies a range of transactions, or a ``<package-name-spec>``,
    which specifies a transaction by a package which it manipulated. When no
    transaction is specified, list all known transactions.

``dnf history info [<spec>...]``
    Describe the given transactions. The meaning of ``<spec>`` is the same as
    in the :ref:`History List Command <history_list_command-label>`. When no
    transaction is specified, describe what happened during the latest
    transaction.

.. _history_redo_command-label:

``dnf history redo <transaction-spec>``
    Repeat the specified transaction. If it is not possible to redo any
    operation due to the current state of RPMDB, do not redo any operation.

``dnf history rollback <transaction-spec>``
    Undo all transactions performed after the specified transaction. If it is
    not possible to undo any transaction due to the current state of RPMDB,
    do not undo any transaction.

``dnf history undo <transaction-spec>``
    Perform the opposite operation to all operations performed in the
    specified transaction. If it is not possible to undo any operation due to
    the current state of RPMDB, do not undo any operation.

``dnf history userinstalled``
    List names of all packages installed by a user. The output can be used as
    the %packages section in a `kickstart <http://fedoraproject.org/wiki/
    Anaconda/Kickstart>`_ file. It will show all installonly packages, packages installed outside of DNF and packages not installed as dependency. I.e. it lists packages that will stay on the system when :ref:`\autoremove_command-label` or :ref:`\remove_command-label` along with `clean_requirements_on_remove` configuration option set to True is executed.

This command by default does not force a sync of expired metadata.
See also :ref:`\metadata_synchronization-label`
and :ref:`\configuration_files_replacement_policy-label`.

.. _info_command-label:

------------
Info Command
------------

``dnf [options] info [<package-spec>...]``
    Is used to list description and summary information about installed and available packages.

This command by default does not force a sync of expired metadata. See also :ref:`\metadata_synchronization-label`.

.. _install_command-label:

---------------
Install Command
---------------

``dnf [options] install <spec>...``
    DNF makes sure that the given packages and their dependencies are installed
    on the system. Each ``<spec>`` can be either a :ref:`<package-spec>
    <specifying_packages-label>`, or a \@\ :ref:`\<group-spec>\ <specifying_groups-label>`. See :ref:`\Install Examples\ <install_examples-label>`.
    If a given package or provide cannot be (and is not already) installed,
    the exit code will be non-zero.

    When :ref:`<package-spec> <specifying_packages-label>` that specify exact version
    of the package is given, DNF will install the desired version, no matter which
    version of the package is already installed. The former version of the package
    will be removed in the case of non-installonly package.

    See also :ref:`\configuration_files_replacement_policy-label`.

.. _install_examples-label:

Install Examples
----------------

``dnf install tito``
    Install package tito (tito is package name).

``dnf install ~/Downloads/tito-0.6.2-1.fc22.noarch.rpm``
    Install local rpm file tito-0.6.2-1.fc22.noarch.rpm from ~/Downloads/
    directory.

``dnf install tito-0.5.6-1.fc22``
    Install package with specific version. If the package is already installed it
    will automatically try to downgrade or upgrade to specific version.

``dnf --best install tito``
    Install the latest available version of package. If the package is already installed it
    will automatically try to upgrade to the latest version. If the latest version
    of package cannot be installed, the installation fail.

``dnf install vim``
    DNF will automatically recognize that vim is not a package name, but
    provide, and install a package that provides vim with all required
    dependencies. Note: Package name match has precedence over package provides
    match.

``dnf install https://kojipkgs.fedoraproject.org//packages/tito/0.6.0/1.fc22/noarch/tito-0.6.0-1.fc22.noarch.rpm``
    Install package directly from URL.

``dnf install '@Web Server'``
    Install environmental group 'Web Server'

``dnf install /usr/bin/rpmsign``
    Install a package that provides /usr/bin/rpmsign file.

.. _list_command-label:

------------
List Command
------------

Dumps lists of packages depending on the packages' relation to the
system. A package is ``installed`` if it is present in the RPMDB, and it is ``available``
if it is not installed but it is present in a repository that DNF knows about.
The list command can also limit the displayed packages according to other criteria,
e.g. to only those that update an installed package. The :ref:`exclude
<exclude-label>` option in configuration file (.conf) might influence the
result, but if the command line option \-\ :ref:`-disableexcludes
<disableexcludes-label>` is used, it ensure that all installed packages will be
listed.

All the forms take a ``[<package-specs>...]`` parameter to further limit the
result to only those packages matching it.

``dnf [options] list [--all] [<package-name-specs>...]``
    Lists all packages known to us, present in the RPMDB, in a repo or in both.

``dnf [options] list --installed [<package-name-specs>...]``
    Lists installed packages.

``dnf [options] list --available [<package-name-specs>...]``
    Lists available packages.

``dnf [options] list --extras [<package-name-specs>...]``
    Lists extras, that is packages installed on the system that are not
    available in any known repository.

``dnf [options] list --obsoletes [<package-name-specs>...]``
    List the packages installed on the system that are obsoleted by packages in
    any known repository.

``dnf [options] list --recent [<package-name-specs>...]``
    List packages recently added into the repositories.

``dnf [options] list --upgrades [<package-name-specs>...]``
    List upgrades available for the installed packages.

``dnf [options] list --autoremove``
    List packages which will be removed by ``dnf autoremove`` command.

This command by default does not force a sync of expired metadata. See also :ref:`\metadata_synchronization-label`.

.. _makecache_command-label:

-----------------
Makecache Command
-----------------

``dnf [options] makecache``
    Downloads and caches in binary format metadata for all known repos. Tries to
    avoid downloading whenever possible (e.g. when the local metadata hasn't
    expired yet or when the metadata timestamp hasn't changed).

``dnf [options] makecache --timer``
    Like plain ``makecache`` but instructs DNF to be more resource-aware,
    meaning will not do anything if running on battery power and will terminate
    immediately if it's too soon after the last successful ``makecache`` run
    (see :manpage:`dnf.conf(5)`, :ref:`metadata_timer_sync
    <metadata_timer_sync-label>`).

.. _mark_command-label:

-------------
Mark Command
-------------

``dnf mark install <package-specs>...``
    Marks the specified packages as installed by user. This can be useful if any package was installed as a dependency and is desired to stay on the system when :ref:`\autoremove_command-label` or :ref:`\remove_command-label` along with `clean_requirements_on_remove` configuration option set to True is executed.

``dnf mark remove <package-specs>...``
    Unmarks the specified packages as installed by user. Whenever you as a user don't need a specific package you can mark it for removal. The package stays installed on the system but will be removed when :ref:`\autoremove_command-label` or :ref:`\remove_command-label` along with `clean_requirements_on_remove` configuration option set to True is executed. You should use this operation instead of :ref:`\remove_command-label` if you're not sure whether the package is a requirement of other user installed packages on the system.

.. _provides_command-label:

----------------
Provides Command
----------------

``dnf [options] provides <provide-spec>``
    Finds the packages providing the given ``<provide-spec>``. This is useful
    when one knows a filename and wants to find what package (installed or not)
    provides this file.

This command by default does not force a sync of expired metadata. See also :ref:`\metadata_synchronization-label`.

.. _reinstall_command-label:

-----------------
Reinstall Command
-----------------

``dnf [options] reinstall <package-specs>...``
    Installs the specified packages, fails if some of the packages are either
    not installed or not available (i.e. there is no repository where to
    download the same RPM).

.. _remove_command-label:

--------------
Remove Command
--------------

``dnf [options] remove <package-specs>...``
    Removes the specified packages from the system along with any packages depending on the packages being removed. Each ``<spec>`` can be either a ``<package-spec>``, which specifies a package directly, or a ``@<group-spec>``, which specifies an (environment) group which contains it. If ``clean_requirements_on_remove`` is enabled (the default) also removes any dependencies that are no longer needed.

``dnf [options] remove --duplicates``
    Removes older version of duplicated packages.

``dnf [options] remove --oldinstallonly``
    Removes old installonly packages keeping only ``installonly_limit`` latest versions.

.. _repoinfo_command-label:

----------------
Repoinfo Command
----------------

    This command is alias for :ref:`repolist <repolist_command-label>` command
    that provides more detailed information like ``dnf repolist -v``.

.. _repolist_command-label:

----------------
Repolist Command
----------------

``dnf [options] repolist [--enabled|--disabled|--all]``
    Depending on the exact command, lists enabled, disabled or all known
    repositories. Lists all enabled repositories by default. Provides more
    detailed information when ``-v`` option is used.

This command by default does not force a sync of expired metadata. See also :ref:`\metadata_synchronization-label`.

.. _repoquery_command-label:

-----------------
Repoquery Command
-----------------

``dnf [options] repoquery [<select-options>] [<query-options>] [<pkg-spec>]``
    Searches the available DNF repositories for selected packages and displays the requested information about them. It
    is an equivalent of ``rpm -q`` for remote repositories.

``dnf [options] repoquery --querytags``
    Provides list of recognized tags by repoquery option \-\ :ref:`-queryformat <queryformat_repoquery-label>`

Select Options
--------------

Together with ``<pkg-spec>``, control what packages are displayed in the output. If ``<pkg-spec>`` is given, the set of
resulting packages matching the specification. All packages are considered if no ``<pkg-spec>`` is specified.

``<pkg-spec>``
    Package specification like: name[-[epoch:]version[-release]][.arch]. See :ref:`Specifying Packages
    <specifying_packages-label>`

``--arch <arch>[,<arch>...]``
    Limit the resulting set only to packages of selected architectures.

``--duplicates``
    Limit the resulting set to installed duplicated packages (i.e. more package versions
    for the same name and architecture). Installonly packages are excluded from this set.

``--unneeded``
    Limit the resulting set to leaves packages that were installed as dependencies so they are no longer needed. This
    switch lists packages that are going to be removed after executing ``dnf autoremove`` command.

``--available``
    Limit the resulting set to available packages only (set by default).

``--extras``
    Limit the resulting set to packages that are not present in any of available repositories.

``-f <file>``, ``--file <file>``
    Limit the resulting set only to package that owns ``<file>``.

``--installed``
    Limit the resulting set to installed packages. The :ref:`exclude <exclude-label>` option in configuration file
    (.conf) might influence the result, but if the command line option  \-\
    :ref:`-disableexcludes <disableexcludes-label>` is used, it ensures that all installed packages will be listed.

``--installonly``
    Limit the resulting set to installed installonly packages.

``--latest-limit <number>``
    Limit the resulting set to <number> of latest packages for every package name and architecture.
    If <number> is negative skip <number> of latest packages.

``--recent``
    Limit the resulting set to packages that were recently edited.

``--repo <repoid>``
    Limit the resulting set only to packages from repo identified by ``<repoid>``.
    Can be used multiple times with accumulative effect.

``--unsatisfied``
    Report unsatisfied dependencies among installed packages (i.e. missing requires and
    and existing conflicts).

``--upgrades``
    Limit the resulting set to packages that provide an upgrade for some already installed package.

``--whatenhances <capability>``
    Limit the resulting set only to packages that enhance ``<capability>``.

``--whatprovides <capability>``
    Limit the resulting set only to packages that provide ``<capability>``.

``--whatrecommends <capability>``
    Limit the resulting set only to packages that recommend ``<capability>``.

``--whatrequires <capability>``
    Limit the resulting set only to packages that require ``<capability>``.

``--whatsuggests <capability>``
    Limit the resulting set only to packages that suggest ``<capability>``.

``--whatsupplements <capability>``
    Limit the resulting set only to packages that supplement ``<capability>``.

``--alldeps``
    This option is stackable with ``--whatrequires`` only. Additionally it adds to the result set all packages requiring
    the package features (used as default).

``--exactdeps``
    This option is stackable with ``--whatrequires`` only. Limit the resulting set only to packages that require
    ``<capability>`` specified by --whatrequires.

``--srpm``
    Operate on corresponding source RPM.

Query Options
-------------

Set what information is displayed about each package.

The following are mutually exclusive, i.e. at most one can be specified. If no query option is given, matching packages
are displayed in the standard NEVRA notation.

.. _info_repoquery-label:

``-i, --info``
    Show detailed information about the package.

``-l, --list``
    Show list of files in the package.

``-s, --source``
    Show package source RPM name.

``--conflicts``
    Display capabilities that the package conflicts with. Same as ``--qf "%{conflicts}``.

``--enhances``
    Display capabilities enhanced by the package. Same as ``--qf "%{enhances}""``.

``--obsoletes``
    Display capabilities that the package obsoletes. Same as ``--qf "%{obsoletes}"``.

``--provides``
    Display capabilities provided by the package. Same as ``--qf "%{provides}"``.

``--recommends``
    Display capabilities recommended by the package. Same as ``--qf "%{recommends}"``.

``--requires``
    Display capabilities that the package depends on. Same as ``--qf "%{requires}"``.

``--requires-pre``
    Display capabilities that the package depends on for running a ``%pre`` script.
    Same as ``--qf "%{requires-pre}"``.

``--suggests``
    Display capabilities suggested by the package. Same as ``--qf "%{suggests}"``.

``--supplements``
    Display capabilities supplemented by the package. Same as ``--qf "%{supplements}"``.

``--tree``
    Display a recursive tree of packages with capabilities specified by one of the following supplementary options:
    ``--whatrequires``, ``--requires``, ``--conflicts``, ``--enhances``, ``--suggests``, ``--provides``,
    ``--suplements``, ``--recommends``.

``--deplist``
    Produces a list of all dependencies and what packages provide those
    dependencies for the given packages. The results only shows the newest
    providers (which can be changed by using --verbose)

.. _queryformat_repoquery-label:

``--qf <format>``, ``--queryformat <format>``
    Custom display format. ``<format>`` is a string to output for each matched package. Every occurrence of
    ``%{<tag>}`` within is replaced by corresponding attribute of the package. List of recognized tags can be displayed
    by running ``dnf repoquery --querytags``.


``--resolve``
    resolve capabilities to originating package(s).


Examples
--------

Display NEVRAS of all available packages matching ``light*``::

    dnf repoquery 'light*'

Display requires of all ligttpd packages::

    dnf repoquery --requires lighttpd

Display packages providing the requires of python packages::

    dnf repoquery --requires python --resolve

Display source rpm of ligttpd package::

    dnf repoquery --source lighttpd

Display package name that owns the given file::

    dnf repoquery --file /etc/lighttpd/lighttpd.conf

Display name, architecture and the containing repository of all lighttpd packages::

    dnf repoquery --queryformat '%{name}.%{arch} : %{reponame}' lighttpd

Display all available packages providing "webserver"::

    dnf repoquery --whatprovides webserver

Display all available packages providing "webserver" but only for "i686" architecture::

    dnf repoquery --whatprovides webserver --arch i686

Display duplicated packages::

    dnf repoquery --duplicates

Remove older versions of duplicated packages (an equivalent of yum's `package-cleanup --cleandups`)::

    dnf remove $(dnf repoquery --duplicates --latest-limit -1 -q)


.. _repository-packages_command-label:

---------------------------
Repository-Packages Command
---------------------------

The repository-packages command allows the user to run commands on top of all packages in the repository named ``<repoid>``. However, any dependency resolution takes into account packages from all enabled repositories. Specifications ``<package-name-spec>`` and ``<package-spec>`` further limit the candidates to only those packages matching at least one of them.

``info`` subcommand lists description and summary information about packages depending on the packages' relation to the repository. ``list`` subcommand just dumps lists of that packages.

``dnf [options] repository-packages <repoid> check-update [<package-name-spec>...]``
    Non-interactively checks if updates of the specified packages in the repository are available. DNF exit code will be 100 when there are updates available and a list of the updates will be printed.

``dnf [options] repository-packages <repoid> info [--all] [<package-name-spec>...]``
    List all related packages.

``dnf [options] repository-packages <repoid> info --installed [<package-name-spec>...]``
    List packages installed from the repository.

``dnf [options] repository-packages <repoid> info --available [<package-name-spec>...]``
    List packages available in the repository but not currently installed on the system.

``dnf [options] repository-packages <repoid> info --extras [<package-name-specs>...]``
    List packages installed from the repository that are not available in any repository.

``dnf [options] repository-packages <repoid> info --obsoletes [<package-name-spec>...]``
    List packages in the repository that obsolete packages installed on the system.

``dnf [options] repository-packages <repoid> info --recent [<package-name-spec>...]``
    List packages recently added into the repository.

``dnf [options] repository-packages <repoid> info --upgrades [<package-name-spec>...]``
    List packages in the repository that upgrade packages installed on the system.

``dnf [options] repository-packages <repoid> install [<package-spec>...]``
    Install all packages in the repository.

``dnf [options] repository-packages <repoid> list [--all] [<package-name-spec>...]``
    List all related packages.

``dnf [options] repository-packages <repoid> list --installed [<package-name-spec>...]``
    List packages installed from the repository.

``dnf [options] repository-packages <repoid> list --available [<package-name-spec>...]``
    List packages available in the repository but not currently installed on the system.

``dnf [options] repository-packages <repoid> list --extras [<package-name-specs>...]``
    List packages installed from the repository that are not available in any repository.

``dnf [options] repository-packages <repoid> list --obsoletes [<package-name-spec>...]``
    List packages in the repository that obsolete packages installed on the system.

``dnf [options] repository-packages <repoid> list --recent [<package-name-spec>...]``
    List packages recently added into the repository.

``dnf [options] repository-packages <repoid> list --upgrades [<package-name-spec>...]``
    List packages in the repository that upgrade packages installed on the system.

``dnf [options] repository-packages <repoid> move-to [<package-name-spec>...]``
    Reinstall all those packages that are available in the repository.

``dnf [options] repository-packages <repoid> reinstall [<package-name-spec>...]``
    Run ``reinstall-old`` subcommand. If it fails, run ``move-to`` subcommand.

``dnf [options] repository-packages <repoid> reinstall-old [<package-name-spec>...]``
    Reinstall all those packages that were installed from the repository and simultaneously are available in the repository.

``dnf [options] repository-packages <repoid> remove [<package-name-spec>...]``
    Remove all packages installed from the repository along with any packages depending on the packages being removed. If ``clean_requirements_on_remove`` is enabled (the default) also removes any dependencies that are no longer needed.

``dnf [options] repository-packages <repoid> remove-or-distro-sync [<package-name-spec>...]``
    Select all packages installed from the repository. Upgrade, downgrade or keep those of them that are available in another repository to match the latest version available there and remove the others along with any packages depending on the packages being removed. If ``clean_requirements_on_remove`` is enabled (the default) also removes any dependencies that are no longer needed.

``dnf [options] repository-packages <repoid> remove-or-reinstall [<package-name-spec>...]``
    Select all packages installed from the repository. Reinstall those of them that are available in another repository and remove the others along with any packages depending on the packages being removed. If ``clean_requirements_on_remove`` is enabled (the default) also removes any dependencies that are no longer needed.

``dnf [options] repository-packages <repoid> upgrade [<package-name-spec>...]``
    Update all packages to the highest resolvable version available in the repository.

``dnf [options] repository-packages <repoid> upgrade-to <package-nevr-specs>...``
    Update packages to the specified versions that are available in the repository.

.. _search_command-label:

--------------
Search Command
--------------

``dnf [options] search [--all] <keywords>...``
    Search package metadata for the keywords. Keywords are matched as case-insensitive substrings, globbing is supported. By default the command will only look at package names and summaries, failing that (or whenever ``all`` was given as an argument) it will match against package descriptions and URLs. The result is sorted from the most relevant results to the least.

This command by default does not force a sync of expired metadata. See also :ref:`\metadata_synchronization-label`.

.. _update_command-label:

--------------
Update Command
--------------

``dnf [options] update``
    Deprecated alias for the :ref:`\upgrade_command-label`.

.. _updateinfo_command-label:

------------------
Updateinfo Command
------------------

``dnf [options] updateinfo [--summary|--list|--info] [<availability>] [<spec>...]``
    Display information about update advisories.

    Depending on output type, DNF displays just counts of advisory types
    (omitted or ``--summary``), list of advisories (``--list``) or detailed
    information (``--info``). When ``--info`` with ``-v`` option is used, the
    information is even more detailed.

    ``<availability>`` specifies whether advisories about newer versions of
    installed packages (omitted or ``available``), advisories about equal and
    older versions of installed packages (``installed``), advisories about
    newer versions of those installed packages for which a newer version is
    available (``updates``) or advisories about any versions of installed
    packages (``all``) are taken into account. Most of the time, ``available``
    and ``updates`` displays the same output. The outputs differ only in the
    cases when an advisory refers to a newer version but there is no enabled
    repository which contains any newer version.

    If given and if neither ID, type (``bugfix``, ``enhancement``,
    ``security``/``sec``) nor a package name of an advisory does match
    ``<spec>``, the advisory is not taken into account. The matching is
    case-sensitive and in the case of advisory IDs and package names, globbing
    is supported.

.. _upgrade_command-label:

---------------
Upgrade Command
---------------

``dnf [options] upgrade``
    Updates each package to the latest version that is both available and
    resolvable.

``dnf [options] upgrade <package-installed-specs>...``
    Updates each specified package to the latest available version. Updates
    dependencies as necessary.

See also :ref:`\configuration_files_replacement_policy-label`.

.. _upgrade_minimal_command-label:

-----------------------
Upgrade-minimal Command
-----------------------

``dnf [options] upgrade-minimal``
    Updates each package to the latest version that provides bugfix, enhancement
    or fix for security issue (security)

``dnf [options] upgrade-minimal <package-installed-specs>...``
    Updates each specified package to the latest available version that provides
    bugfix, enhancement or fix for security issue (security). Updates
    dependencies as necessary.

-----------------
Update-To Command
-----------------

``dnf [options] update-to <package-nevr-specs>...``
    Deprecated alias for the :ref:`\upgrade_to_command-label`.

.. _upgrade_to_command-label:

------------------
Upgrade-To Command
------------------

``dnf [options] upgrade-to <package-nevr-specs>...``
    Upgrades packages to the specified versions.

.. _specifying_packages-label:

===================
Specifying Packages
===================

Many commands take a ``<package-spec>`` parameter that selects a package for the
operation. DNF looks for interpretations of the parameter from the most commonly
used meanings to the least, that is it tries to see if the given spec fits one
of the following patterns (in decreasing order of priority):

* ``name.arch``
* ``name``
* ``name-[epoch:]version-release.arch``
* ``name-[epoch:]version-release``
* ``name-[epoch:]version``

Note that ``name`` can in general contain dashes (e.g. ``package-subpackage``).

Failing to match the input argument to an existing package name based on the
patterns above, DNF tries to see if the argument matches an existing provide.

By default, if multiple versions of the selected package exist in the repo, the
most recent version suitable for the given operation is used. If the selected
package exists for multiple architectures, the packages which best match the
system's architecture will be preferred. The name specification is
case-sensitive, globbing characters "``?``, ``*`` and ``[`` are allowed and
trigger shell-like glob matching. If globbing character is present in ``name``,
DNF expands given ``name`` first and consequently selects all packages matching
expanded ``<package-spec>``.

``<package-name-spec>`` is similar to ``<package-spec>`` except the provides
matching is never attempted there.

``<package-installed-specs>`` is similar to ``<package-specs>`` except it
considers only installed packages.

.. _specifying_packages_versions-label:

=====================================
Specifying Exact Versions of Packages
=====================================

Commands accepting the ``<package-nevr-spec>`` parameter need not only the name
of the package, but also its version, release and optionally the
architecture. Further, the version part can be preceded by an epoch when it is
relevant (i.e. the epoch is non-zero).

.. _specifying_provides-label:

===================
Specifying Provides
===================

``<provide-spec>`` in command descriptions means the command operates on
packages providing the given spec. This can either be an explicit provide, an
implicit provide (i.e. name of the package) or a file provide. The selection is
case-sensitive and globbing is supported.

.. _specifying_groups-label:

=================
Specifying Groups
=================

``<group-spec>`` allows one to select (environment) groups a particular operation should work
on. It is a case insensitive string (supporting globbing characters) that is
matched against a group's ID, canonical name and name translated into the
current LC_MESSAGES locale (if possible).

.. _specifying_transactions-label:

=======================
Specifying Transactions
=======================

``<transaction-spec>`` can be in one of several forms. If it is an integer, it
specifies a transaction ID. Specifying ``last`` is the same as specifying the ID
of the most recent transaction. The last form is ``last-<offset>``, where
``<offset>`` is a positive integer. It specifies offset-th transaction preceding
the most recent transaction.

.. _metadata_synchronization-label:

========================
Metadata Synchronization
========================

Correct operation of DNF depends on having access to up-to-date data from all enabled repositories but contacting remote mirrors on every operation considerably slows it down and costs bandwidth for both the client and the repository provider. The :ref:`metadata_expire <metadata_expire-label>` (see :manpage:`dnf.conf(5)`) repo config option is used by DNF to determine whether particular local copy of repository data is due to be re-synced. It is crucial that the repository providers set the option well, namely to a value where it is guaranteed that if particular metadata was available in time ``T`` on the server, then all packages it references will still be available for download from the server in time ``T + metadata_expire``.

To further reduce the bandwidth load, some of the commands where having up-to-date metadata is not critical (e.g. the ``list`` command) do not look at whether a repository is expired and whenever any version of it is locally available, it will be used. Note that in all situations the user can force synchronization of all enabled repositories with the ``--refresh`` switch.

.. _configuration_files_replacement_policy-label:

======================================
Configuration Files Replacement Policy
======================================

The updated packages could replace the old modified configuration files
with the new ones or keep the older files. Neither of the files are actually replaced.
To the conflicting ones RPM gives additional suffix to the origin name. Which file
should maintain the true name after transaction is not controlled by package manager
but is specified by each package itself, following packaging guideline.

.. _files-label:

========
Files
========

``Cache Files``
    /var/cache/dnf

``Main Configuration``
    /etc/dnf/dnf.conf

``Repository``
    /etc/yum.repos.d/

.. _see_also-label:

========
See Also
========

* :manpage:`dnf.conf(5)`, :ref:`DNF Configuration Reference <conf_ref-label>`
* :manpage:`dnf.plugin.*(8)`, assorted DNF plugins that might be installed on the system.
* `DNF`_ project homepage (https://github.com/rpm-software-management/dnf/)
* How to report a bug (https://github.com/rpm-software-management/dnf/wiki/Bug-Reporting)
* `Yum`_ project homepage (http://yum.baseurl.org/)

.. _dnf config-manager: https://dnf-plugins-core.readthedocs.org/en/latest/config_manager.html
