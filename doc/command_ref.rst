..
  Copyright (C) 2014  Red Hat, Inc.

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

`DNF`_ is the next upcoming major version of `Yum`_, a package manager for RPM-based Linux distributions. It roughly maintains CLI compatibility with Yum and defines strict API for extensions and plugins. Plugins can modify or extend features of DNF or provide additional CLI commands on top of those mentioned below.

Available commands are:

* autoerase
* check-update
* clean
* distro-sync
* downgrade
* erase
* group
* help
* history
* info
* install
* list
* makecache
* provides
* reinstall
* repolist
* repository-packages
* search
* updateinfo
* upgrade
* upgrade-to

See the reference for each command below.

=======
Options
=======

``-4``
    Resolve to IPv4 addresses only.

``-6``
    Resolve to IPv6 addresses only.

``--allowerasing``
    Allow erasing of installed packages to resolve dependencies. This option could be used as an alternative to ``yum swap`` command where packages to remove are not explicitly defined.

``--assumeno``
    answer no for all questions

``--best``
    Try the best available package versions in transactions. Specifically during ``dnf upgrade``, which by default skips over updates that can not be installed for dependency reasons, the switch forces DNF to only consider the latest packages and possibly fail giving a reason why the latest version can not be installed.

``-C, --cacheonly``
    Run entirely from system cache, don't update the cache and use it even in case it is expired.

    DNF uses a separate cache for each user under which it executes. The cache for the root user is called the system cache. This switch allows a regular user read-only access to the system cache which usually is more fresh then the user's and thus he does not have to wait for metadata sync.

``-c <config file>, --config=<config file>``
    config file location

``-d <debug level>, --debuglevel=<debug level>``
    Debugging output level. This is an integer value between 0 (no additional information strings) and 10 (shows all debugging information, even that not understandable to the user), default is 2. Deprecated, use ``-v`` instead.

``--debugsolver``
    Dump data aiding in dependency solver debugging into ``./debugdata``.

``--disableexcludes=[all|main|<repoid>]``

    Disable the config file excludes. Takes one of three options:

    * ``all``, disables all config file excludes
    * ``main``, disables excludes defined in the ``[main]`` section
    * ``repoid``, disables excludes defined for the given repo

``--disableplugin=<plugin names>``
    Disable the listed plugins specified by names or globs.

``--disablerepo=<repoid>``
    Disable specific repositories by an id or a glob.

``-e <error level>, --errorlevel=<error level>``
    Error output level. This is an integer value between 0 (no error output) and
    10 (shows all error messages), default is 2. Deprecated, use ``-v`` instead.

``--enablerepo=<repoid>``
    Enable specific repositories by an id or a glob.

``-x <package-spec>, --exclude=<package-spec>``
    Exclude packages specified by ``<package-spec>`` from the operation.

``-h, --help``
    Show the help.

``--installroot=<path>``
    set install root

``--refresh``
    set metadata as expired before running the command

``--nogpgcheck``
    skip checking GPG signatures on packages

``--noplugins``
    Disable all plugins.

``-q, --quiet``
    quiet operation

``-R <minutes>, --randomwait=<minutes>``
    maximum command wait time

``--releasever=<release>``
    configure DNF as if the distribution release was ``<release>``. This can
    affect cache paths, values in configuration files and mirrorlist URLs. Using
    '/' for this value makes DNF detect the release number from the running
    system.

``--rpmverbosity=<debug level name>``
    debugging output level for rpm

``--setopt=<option>=<value>``
    override a config option from the config file. To override config options from repo files, use ``repoid.option`` for the ``<option>``.

``--showduplicates``
    show duplicates, in repos, in list/search commands

``-v, --verbose``
    verbose operation, show debug messages.

``--version``
    show DNF version and exit

``-y, --assumeyes``
    answer yes for all questions

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

-------------------
Auto Erase Command
-------------------

``dnf [options] autoerase``

    Removes all "leaf" packages from the system that were originally installed as dependencies of user-installed packages but which are no longer required by any such package.

This command by default does not force a sync of expired metadata. See also :ref:`\metadata_synchronization-label`.


--------------------
Check Update Command
--------------------

``dnf [options] check-update [<package-specs>...]``

    Non-interactively checks if updates of the specified packages are available. If no ``<package-specs>`` are given checks whether any updates at all are available for your system. DNF exit code will be 100 when there are updates available and a list of the updates will be printed, 0 if not and 1 if an error occurs.

    Please note that having a specific newer version available for an installed package (and reported by ``check-update``) does not imply that subsequent ``dnf upgrade`` will install it. The difference is that ``dnf upgrade`` must also ensure the satisfiability of all dependencies and other restrictions.

-------------
Clean Command
-------------
Performs cleanup of temporary files for the currently enabled repositories.

``dnf clean dbcache``
    Removes cache files generated from the repository metadata. This forces DNF
    to regenerate the cache files the next time it is run.

``dnf clean expire-cache``
    Removes local cookie files saying when the metadata and mirrorlists were
    downloaded for each repo. DNF will re-validate the cache for each repo the
    next time it is used.

``dnf clean metadata``
    Removes repository metadata. Those are the files which DNF uses to determine
    the remote availability of packages. Using this option will make DNF
    download all the metadata the next time it is run.

``dnf clean packages``
    Removes any cached packages from the system.

``dnf clean plugins``
    Tells all enabled plugins to eliminate their cached data.

``dnf clean all``
    Does all of the above.

.. _distro_sync_command-label:

-------------------
Distro-sync command
-------------------

``dnf distro-sync [<package-spec>...]``
    As necessary upgrades, downgrades or keeps selected installed packages to match
    the latest version available from any enabled repository. If no package is given, all installed packages are considered.

------------------------------------
Distribution-synchronization command
------------------------------------

``dnf distribution-synchronization``
    Deprecated alias for the :ref:`\distro_sync_command-label`.

-----------------
Downgrade Command
-----------------

``dnf [options] downgrade <package-specs>...``
    Downgrades the specified packages to the highest of all known lower versions.

.. _erase_command-label:

-------------
Erase Command
-------------

``dnf [options] erase <spec>...``
     Removes the specified packages from the system along with any packages depending on the packages being removed. Each ``<spec>`` can be either a ``<package-spec>``, which specifies a package directly, or a ``@<group-spec>``, which specifies an (environment) group which contains it. If ``clean_requirements_on_remove`` is enabled (the default) also removes any dependencies that are no longer needed.

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

``dnf [options] group install [with-optional] <group-spec>...``
    Mark the specified group installed and install packages it contains. Also include optional packages of the group if ``with-optional`` is specified.

``dnf [options] group list <group-spec>...``
    List all matching groups, either among installed or available groups. If
    nothing is specified list all known groups.

``dnf [options] group remove <group-spec>...``
    Mark the group removed and remove those packages in the group from the system which are neither comprising another installed group and were not installed explicitly by the user.

``dnf [options] group upgrade <group-spec>...``
    Upgrades the packages from the group and upgrades the group itself. The latter comprises of installing pacakges that were added to the group by the distribution and removing packages that got removed from the group as far as they were not installed explicitly by the user.

Groups can be also be marked installed or removed without physically manipualting any packages:

``dnf [options] group mark install <group-spec>...``
    Mark the specified group installed. No packages will be installed by this command but the group is then considered installed.

``dnf [options] group mark remove <group-spec>...``
    Mark the specified group removed. No packages will be removed by this command.

------------
Help Command
------------

``dnf help [<command>]``
    Displays the help text for all commands. If given a command name then only
    displays the help for that particular command.

---------------
History Command
---------------

The history command allows the user to view what has happened in past
transactions and act according to this information (assuming the
``history_record`` configuration option is set).

``dnf history [list]``
    The default history action is listing all known transaction information in a
    table.

``dnf history info [<spec>...]``
    Describe the given transactions. Each ``<spec>`` can be either a
    ``<transaction-spec>``, which specifies a transaction directly, or a
    ``<package-name-spec>``, which specifies a transaction by a package which
    it manipulated. When no transaction is specified describe what happened
    during the latest transaction.

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
    Anaconda/Kickstart>`_ file.

This command by default does not force a sync of expired metadata. See also :ref:`\metadata_synchronization-label`.

------------
Info Command
------------

``dnf [options] info [<package-spec>...]``
    Is used to list description and summary information about available packages.

This command by default does not force a sync of expired metadata. See also :ref:`\metadata_synchronization-label`.

---------------
Install Command
---------------

``dnf [options] install <spec>...``
    Installs the given packages and their dependencies. Each ``<spec>`` can be
    either a ``<package-spec>``, which specifies a package directly, or a path to the local rpm package, or a ``@<group-spec>``, which specifies an (environment) group which contains it. After the transaction is finished all not yet installed specified packages are installed
    on the system.

------------
List Command
------------

Dumps lists of packages depending on the packages' relation to the
system. Generally packages are available (it is present in a repository we know
about) or installed (present in the RPMDB). The list command can also limit the
displayed packages according to other criteria, e.g. to only those that update
an installed package.

All the forms take a ``[<package-specs>...]`` parameter to further limit the
result to only those packages matching it.

``dnf [options] list [all] [<package-name-specs>...]``
    Lists all packages known to us, present in the RPMDB, in a repo or in both.

``dnf [options] list installed [<package-name-specs>...]``
    Lists installed packages.

``dnf [options] list available [<package-name-specs>...]``
    Lists available packages.

``dnf [options] list extras [<package-name-specs>...]``
    Lists extras, that is packages installed on the system that are not
    available in any known repository.

``dnf [options] list obsoletes [<package-name-specs>...]``
    List the packages installed on the system that are obsoleted by packages in
    any known repository.

``dnf [options] list recent [<package-name-specs>...]``
    List packages recently added into the repositories.

``dnf [options] list upgrades [<package-name-specs>...]``
    List upgrades available for the installed packages.

This command by default does not force a sync of expired metadata. See also :ref:`\metadata_synchronization-label`.

-----------------
Makecache Command
-----------------

``dnf [options] makecache``
    Downloads and caches in binary format metadata for all known repos. Tries to
    avoid downloading whenever possible (e.g. when the local metadata hasn't
    expired yet or when the metadata timestamp hasn't changed).

``dnf [options] makecache timer``
    Like plain ``makecache`` but instructs DNF to be more resource-aware,
    meaning will not do anything if running on battery power and will terminate
    immediately if it's too soon after the last successful ``makecache`` run
    (see :manpage:`dnf.conf(8)`, :ref:`metadata_timer_sync
    <metadata_timer_sync-label>`).

----------------
Provides Command
----------------

``dnf [options] provides <provide-spec>``
    Finds the packages providing the given ``<provide-spec>``. This is useful
    when one knows a filename and wants to find what package (installed or not)
    provides this file.

This command by default does not force a sync of expired metadata. See also :ref:`\metadata_synchronization-label`.

-----------------
Reinstall Command
-----------------

``dnf [options] reinstall <package-specs>...``
    Installs the specified packages, fails if some of the packages are either
    not installed or not available (i.e. there is no repository where to
    download the same RPM).

--------------
Remove Command
--------------

``dnf [options] remove <package-specs>...``
    Deprecated alias for the :ref:`\erase_command-label`.

----------------
Repolist Command
----------------

``dnf [options] repolist [enabled|disabled|all]``
    Depending on the exact command, lists enabled, disabled or all known
    repositories. Lists all enabled repositories by default. Provides more
    detailed information when ``-v`` option is used.

This command by default does not force a sync of expired metadata. See also :ref:`\metadata_synchronization-label`.

---------------------------
Repository-Packages Command
---------------------------

The repository-packages command allows the user to run commands on top of all packages in the repository named ``<repoid>``. However, any dependency resolution takes into account packages from all enabled repositories. Specifications ``<package-name-spec>`` and ``<package-spec>`` further limit the candidates to only those packages matching at least one of them.

``info`` subcommand lists description and summary information about packages depending on the packages' relation to the repository. ``list`` subcommand just dumps lists of that packages.

``dnf [options] repository-packages <repoid> check-update [<package-name-spec>...]``
    Non-interactively checks if updates of the specified packages in the repository are available. DNF exit code will be 100 when there are updates available and a list of the updates will be printed.

``dnf [options] repository-packages <repoid> info [all] [<package-name-spec>...]``
    List all related packages.

``dnf [options] repository-packages <repoid> info installed [<package-name-spec>...]``
    List packages installed from the repository.

``dnf [options] repository-packages <repoid> info available [<package-name-spec>...]``
    List packages available in the repository.

``dnf [options] repository-packages <repoid> info extras [<package-name-specs>...]``
    List packages installed from the repository that are not available in any repository.

``dnf [options] repository-packages <repoid> info obsoletes [<package-name-spec>...]``
    List packages in the repository that obsolete packages installed on the system.

``dnf [options] repository-packages <repoid> info recent [<package-name-spec>...]``
    List packages recently added into the repository.

``dnf [options] repository-packages <repoid> info upgrades [<package-name-spec>...]``
    List packages in the repository that upgrade packages installed on the system.

``dnf [options] repository-packages <repoid> install [<package-spec>...]``
    Install all packages in the repository.

``dnf [options] repository-packages <repoid> list [all] [<package-name-spec>...]``
    List all related packages.

``dnf [options] repository-packages <repoid> list installed [<package-name-spec>...]``
    List packages installed from the repository.

``dnf [options] repository-packages <repoid> list available [<package-name-spec>...]``
    List packages available in the repository.

``dnf [options] repository-packages <repoid> list extras [<package-name-specs>...]``
    List packages installed from the repository that are not available in any repository.

``dnf [options] repository-packages <repoid> list obsoletes [<package-name-spec>...]``
    List packages in the repository that obsolete packages installed on the system.

``dnf [options] repository-packages <repoid> list recent [<package-name-spec>...]``
    List packages recently added into the repository.

``dnf [options] repository-packages <repoid> list upgrades [<package-name-spec>...]``
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
    Select all packages installed from the repository. Upgrade, downgrade or keep those of them that are available in another repositories to match the latest version available there and remove the others along with any packages depending on the packages being removed. If ``clean_requirements_on_remove`` is enabled (the default) also removes any dependencies that are no longer needed.

``dnf [options] repository-packages <repoid> remove-or-reinstall [<package-name-spec>...]``
    Select all packages installed from the repository. Reinstall those of them that are available in another repositories and remove the others along with any packages depending on the packages being removed. If ``clean_requirements_on_remove`` is enabled (the default) also removes any dependencies that are no longer needed.

``dnf [options] repository-packages <repoid> upgrade [<package-name-spec>...]``
    Update all packages to the highest resolvable version available in the repository.

``dnf [options] repository-packages <repoid> upgrade-to <package-nevr-specs>...``
    Update packages to the specified versions that are available in the repository.


--------------
Search Command
--------------

``dnf [options] search [all] <keywords>...``
    Search package metadata for the keywords. Keywords are matched as case-insensitive substrings, globbing is supported. By default the command will only look at package names and summaries, failing that (or whenever ``all`` was given as an argument) it will match against package descriptions and URLs. The result is sorted from the most relevant results to the least.

This command by default does not force a sync of expired metadata. See also :ref:`\metadata_synchronization-label`.

--------------
Update Command
--------------

``dnf [options] update``
    Deprecated alias for the :ref:`\upgrade_command-label`.

.. _updateinfo_command-label:

------------------
Updateinfo Command
------------------

``dnf [options] updateinfo [<output>] [<availability>] [<spec>...]``
    Display information about update advisories.

    Depending on ``<output>``, DNF displays just counts of advisory types
    (omitted or ``summary``), list of advisories (``list``) or detailed
    information (``info``). When ``info`` with ``-v`` option is used, the
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
    Updates each package to a highest version that is both available and
    resolvable.

``dnf [options] upgrade <package-specs>...``
    Updates each specified package to the latest available version. Updates
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

If multiple versions of the selected package exist in the repo, the most recent
version suitable for the given operation is used.  The name specification is
case-sensitive, globbing characters "``?``, ``*`` and ``[`` are allowed and
trigger shell-like glob matching.

``<package-name-spec>`` is similar to ``<package-spec>`` except the provides
matching is never attempted there.

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

Correct operation of DNF depends on having access to up-to-date data from all enabled repositories but contacting remote mirrors on every operation considerably slows it down and costs bandwidth for both the client and the repository provider. The :ref:`metadata_expire <metadata_expire-label>` (see :manpage:`dnf.conf(8)`) repo config option is used by DNF to determine whether particular local copy of repository data is due to be re-synced. It is crucial that the repository providers set the option well, namely to a value where it is guaranteed that if particular metadata was available in time ``T`` on the server, then all packages it references will still be available for download from the server in time ``T + metadata_expire``.

To further reduce the bandwidth load, some of the commands where having up-to-date metadata is not critical (e.g. the ``list`` command) do not look at whether a repository is expired and whenever any version of it is locally available, it will be used. Note that in all situations the user can force synchronization of all enabled repositories with the ``--refresh`` switch.

========
See Also
========

* :manpage:`dnf.conf(8)`, :ref:`DNF Configuration Reference <conf_ref-label>`
* :manpage:`dnf.plugin.*(8)`, assorted DNF plugins that might be installed on the system.
* `DNF`_ project homepage (https://github.com/rpm-software-management/dnf/)
* `Yum`_ project homepage (http://yum.baseurl.org/)
