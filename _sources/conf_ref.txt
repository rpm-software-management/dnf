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
    for any reason. The default is False.

==========
 See Also
==========

* :manpage:`dnf(8)`, :ref:`DNF Command Reference <command_ref-label>`
