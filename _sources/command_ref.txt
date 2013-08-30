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

`DNF`_ is an experimental replacement for `Yum`_, a package manager for RPM Linux
distributions. It aims to maintain CLI compatibility with Yum while improving on
speed and defining strict API and plugin interface.

Available commands are:

* check-update
* clean
* dist-sync
* distribution-sync
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
* search
* update
* update-to
* upgrade
* upgrade-to

See the reference for each command below.

=======
Options
=======

``--assumeno``
    answer no for all questions

``--best``
    Try the best available package versions in transactions.

``-C, --cacheonly``
    Run entirely from system cache, don't update cache

``-c <config file>, --config=<config file>``
    config file location

``-d <debug level>, --debuglevel=<debug level>``
    Debugging output level. This is an integer value between 0 (no additional
    information strings) and 10 (shows all debugging information, even that not
    understandable to the user), default is 2. Deprecated, use ``-v`` instead.

``--disableexcludes=[all|main|<repoid>]``

    Disable the config file excludes. Takes one of three options:

    * ``all``, disables all config file excludes
    * ``main``, disables excludes defined in the ``[main]`` section
    * ``repoid``, disables excludes defined for the given repo

``-e <error level>, --errorlevel=<error level>``
    Error output level. This is an integer value between 0 (no error output) and
    10 (shows all error messages), default is 2. Deprecated, use ``-v`` instead.

``-x <package-spec>, --exclude=<package-spec>``
    Exclude packages specified by a name or a glob from the operation.

``-h, --help``
    Shows the help.

``--installroot=<path>``
    set install root

``--nogpgcheck``
    skip checking GPG signatures on packages

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

``--showduplicates``
    show duplicates, in repos, in list/search commands

``-v, --verbose``
    verbose operation, show debug messages.

``--version``
    show Yum version and exit

``-y, --assumeyes``
    answer yes for all questions

========
Commands
========

For an explanation of ``<package-spec>`` and ``<package-name-spec>`` see
:ref:`\specifying_packages-label`.

For an explanation of ``<package-nevr-spec>`` see
:ref:`\specifying_packages_versions-label`.

For an explanation of ``<provide-spec>`` see :ref:`\specifying_provides-label`.

For an explanation of ``<group-spec>`` see :ref:`\specifying_groups-label`.

--------------------
Check Update Command
--------------------

``dnf [options] check-update [<package-specs>...]``

    Non-interactively checks if updates of the specified packages are
    available. If no ``<package-specs>`` are given checks whether any updates at
    all are available for your system. DNF exit code will be 100 when there are
    updates available and a list of the updates will be printed, 0 if not and 1
    if an error occurs.

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
    Removes any cached packages from the system.  Note that packages are not
    automatically deleted after they are downloaded.

``dnf clean plugins``
    Tells all enabled plugins to eliminate their cached data.

``dnf clean all``
    Does all of the above.

.. _distro_sync_command-label:

-------------------
Distro-sync command
-------------------

``dnf distro-sync``
    As necessary upgrades, downgrades or keeps all installed packages to match
    the latest version available from any enabled repository.

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

-------------
Erase Command
-------------

``dnf [options] erase <package-specs>...``
    Removes the specified packages from the system along with any packages
    depending on the packages being removed. If ``clean_requirements_on_remove``
    is enabled (the default) also removes any dependencies that are no longer
    needed.

-------------
Group Command
-------------

``dnf [options] group list [<group-spec>]``
    List all matching groups, either among installed or available groups. If
    nothing is specified list all known groups.

``dnf [options] group install <group-spec>``
    Install packages in the specified group that are not currently installed.

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
transactions (assuming the ``history_record`` configuration option is set).

``dnf history [list]``
    The default history action is listing all known transaction information in a
    table.

``dnf history info [<transaction_id>]``
    Describe the given transaction. When no ID is given describes what happened
    during the latest transaction.

------------
Info Command
------------

``dnf [options] info <package-specs>...``
    Is used to list a description and summary information about available packages.

---------------
Install Command
---------------

``dnf [options] install <package-specs>...``
    Installs the specified packages and their dependencies. After the
    transaction is finished all the specified packages are installed on the
    system.

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

-----------------
Reinstall Command
-----------------

``dnf [options] reinstall <package-specs>...``
    Installs the specified packages, fails if some of the packages are either
    not installed or not available (i.e. there is no repository where to
    download the same RPM).

----------------
Repolist Command
----------------

``dnf [options] repolist [enabled|disabled|all]``
    Depending on the exact command, lists enabled, disabled or all known
    repositories. Lists all enabled repositories by default. Provides more
    detailed information when ``-v`` option is used.

--------------
Search Command
--------------

``dnf [options] search [all] <keywords>...``
    Search package metadata for the keywords. Keywords are matched as
    case-insensitive substrings, globbing is supported. By default the command
    will only look at package names and summaries, failing that (or whenever
    ``all`` was given as an argument) it will match against package descriptions
    and URLs. The result is sorted from the most relevant results to the least.

--------------
Update Command
--------------

``dnf [options] update``
    Deprecated alias for the :ref:`\upgrade_command-label`.

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

``<group-spec>`` allows one to select groups a particular operation should work
on. It is a case insensitive string (supporting globbing characters) that is
matched against a group's ID, canonical name and name translated into the
current LC_MESSAGES locale (if possible).

========
See Also
========

* :manpage:`dnf.conf(8)`, :ref:`DNF Configuration Reference <conf_ref-label>`
* `DNF`_ project homepage (https://github.com/akozumpl/dnf/)
* `Yum`_ project homepage (http://yum.baseurl.org/)
