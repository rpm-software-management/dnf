.. _conf_ref-label:

#############################
 DNF Configuration Reference
#############################

=============
 Description
=============

`DNF`_ by default uses the global configuration file at ``/etc/dnf/dnf.conf`` and
all \*.repo files found under ``/etc/yum.repos.d``. The latter is typically used
for repository configuration.

There are two types of sections in the configuration files: main and
repository. Main defines all global configuration options. There should be only
one main section. The repository sections define the configuration for each
(remote or local) repository.

================
 [main] Options
================

``best``
    boolean

    When upgrading a package, always try to install its highest version
    available, even only to find out some of its deps are not
    satisfiable. Enable this if you want to experience broken dependencies in
    the repositories firsthand. The default is off.

.. _clean_requirements_on_remove-label:

``clean_requirements_on_remove``
    boolean

    Remove dependencies that are no longer used during ``dnf erase``. A package
    only qualifies for removal via ``clean_requirements_on_remove`` if it was
    installed through DNF but not on explicit user request, i.e. it was
    pulled in as a dependency. The default is on.

``debuglevel``
    integer

    Debug messages output level, in the range 0 to 10. The higher the number the
    more debug output is put to stdout. Default is 2.

``errorlevel``
    integer

    Error messages output level, in the range 0 to 10. The higher the number the
    more error output is put to stderr. Default is 2. This is deprecated in DNF.

``installonlypkgs``
    list

    List of provide names of packages that should only ever be installed, never
    upgraded. Kernels in particular fall into this category.

.. _installonly-limit-label:

``installonly_limit``
    integer

    Number of installonly packages allowed to be installed
    concurrently. Defaults to 3.

.. _metadata_expire-label:

``metadata_expire``
    time in seconds

    The period after which the remote repository is checked for metadata update
    and in the positive case the local metadata cache is updated. The default
    corresponds to 48 hours.

.. _metadata_timer_sync-label:

``metadata_timer_sync``
    time in seconds

    The minimal period between two consecutive ``makecache timer`` runs. The
    command will stop immediately if it's less than this time period since its
    last run. Does not affect simple ``makecache`` run. Use ``0`` to completely
    disable automatic metadata synchronizing. The default corresponds to three
    hours.

==============
 Repo Options
==============

``skip_if_unavailable``
    boolean

    If enabled, DNF will continue running if this repository cannot be contacted
    for any reason. The default is True.

.. _repo_cost-label:

``cost``
    integer

    The relative cost of accessing this repository, defaulting to 1000. If the
    same package can be downloaded from two or more repositories, the repository
    with the lowest cost is preferred.

==================================
 Options for both [main] and Repo
==================================

Some options can be applied in either the main section, per repository, or in a
combination. The value provided in the main section is used for all repositories
as the default value and concrete repositories can override it in their
configuration.

``exclude``
    list

    Exclude packages of this repository, specified by a name or a glob and
    separated by a comma, from all operations.

``throttle, bandwidth``
    The 'throttle' option limits the downloading speed. It might be an absolute
    value (in bytes per second) or a percentage, relative to the value of the
    'bandwidth' option. '0' means no throttling (the default).

    The input to both options is a string containing a (possibly floating
    point) number followed by an optional unit. Valid units are 'k', 'M', 'G'.
    Case is ignored. The convention that 1k = 1024 bytes is used.

``proxy``
    string

    URL of a proxy server to connect through. If none is specified then direct connection is used (the default).

==========
 See Also
==========

* :manpage:`dnf(8)`, :ref:`DNF Command Reference <command_ref-label>`
