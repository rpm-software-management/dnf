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
.. _clean_requirements_on_remove-label:

``clean_requirements_on_remove``
    Remove dependencies that are no longer used during ``dnf erase``. A package
    only qualifies for removal via ``clean_requirements_on_remove`` if it was
    installed through DNF but not on explicit user request, i.e. it was
    pulled in as a dependency. The default is on.

``debuglevel``
    Debug messages output level, in the range 0 to 10. Default is 2.

``errorlevel``
    Error messages output level, in the range 0 to 10. Default is 2. This is
    deprecated in DNF.

.. _metadata_expire-label:

``metadata_expire``
    The period after which the remote repository is checked for metadata update
    and in the positive case the local metadata cache is updated. The default is
    48 hours.

.. _metadata_timer_sync-label:

``metadata_timer_sync``
    The minimal period between two consecutive ``makecache timer`` runs. The
    command will stop immediately if it's less than this time period since its
    last run. Does not affect simple ``makecache`` run. Use ``0`` to completely
    disable automatic metadata synchronizing. The default is 3 hours.

==============
 Repo Options
==============

``skip_if_unavailable``
    If enabled, DNF will continue running if this repository cannot be contacted
    for any reason. The default is True.

==================================
 Options for both [main] and Repo
==================================

Some options can be applied in either the main section, per repository, or in a
combination. The value provided in the main section is used for all repositories
as the default value and concrete repositories can override it in their
configuration.

``exclude``
    Exclude packages of this repository, specified by a name or a glob and
    separated by a comma, from all operations.

==========
 See Also
==========

* :manpage:`dnf(8)`, :ref:`DNF Command Reference <command_ref-label>`
