#######################
 DNF Command Reference
#######################

========
Synopsis
========

``dnf [options] <command> <[args]>``

===========
Description
===========

`DNF`_ is an experimental replacent for `Yum`_, a package manager for RPM Linux
distributions. It aims to maintain CLI compatibility with Yum while improving on
speed and defining strict API and plugin interface.

Available commands are:

* downgrade
* erase
* help
* history
* info
* install
* list
* makecache
* provides
* repolist
* update

See the reference for each command below.

=======
Options
=======

``-h, --help``
    Shows the help.

``-C, --cacheonly``
    Run entirely from system cache, don't update cache

``-c [config file], --config=[config file]``
    config file location

``-R [minutes], --randomwait=[minutes]``
    maximum command wait time

``-d [debug level], --debuglevel=[debug level]``
    debugging output level

``--showduplicates``
    show duplicates, in repos, in list/search commands

``-e [error level], --errorlevel=[error level]``
    error output level

``--rpmverbosity=[debug level name]``
    debugging output level for rpm

``-q, --quiet``
    quiet operation

``-v, --verbose``
    verbose operation

``-y, --assumeyes``
    answer yes for all questions

``--assumeno``
    answer no for all questions

``--version``
    show Yum version and exit

``--installroot=[path]``
    set install root

========
Commands
========

For an explanation of ``<package-spec>`` see :ref:`\specifying_packages-label`.

For an explanation of ``<provide-spec>`` see :ref:`\specifying_provides-label`.

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
    is enabled also removes any dependencies that are no longer needed.

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
    during the latest transacton.

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

``dnf [options] list [all] [<package-specs>...]``
    Lists all packages known to us, present in the RPMDB, in a repo or in both.

``dnf [options] list installed [<package-specs>...]``
    Lists installed packages.

``dnf [options] list available [<package-specs>...]``
    Lists available packages.

``dnf [options] list extras [<package-specs>...]``
    Lists extras, that is packages installed on the system that are not
    available in any known repository.

``dnf [options] list obsoletes [<package-specs>...]``
    List the packages installed on the system that are obsoleted by packages in
    any known repository.

-----------------
Makecache Command
-----------------
``dnf [options] makecache``
    Downloads and caches in binary format metadata for all known repos. Tries to
    avoid downloading whenever possible (typically when the metadata timestamp
    hasn't changed).

----------------
Provides Command
----------------
``dnf [options] provides <provide-spec>``
    Finds the packages providing the given ``<provide-spec>``.

----------------
Repolist Command
----------------
``dnf [options] repolist [enabled|disabled|all]``
    Depending on the exact command, lists enabled, disabled or all known
    repositories. Lists all enabled repositories by default. Provides more
    detailed information when ``-v`` option is used.

--------------
Update Command
--------------
``dnf [options] update [<package-specs>...]``
    Updates the specified packages and their dependencies as necessary. If no
    ``<package-specs>`` are given, updates all packages a newer version and
    relevant dependencies available.


.. _specifying_packages-label:

===================
Specifying Packages
===================

(how to spec a package)

.. _specifying_provides-label:

===================
Specifying Provides
===================

(how to spec a provide)


========
See Also
========

* `DNF`_ project homepage (https://github.com/akozumpl/dnf/)
* `Yum`_ project homepage (http://yum.baseurl.org/)
