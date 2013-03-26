.. _conf_ref-label:

#############################
 DNF Configuration Reference
#############################

=============
 Description
=============

`DNF`_ uses by default the global configuration file at ``/etc/dnf/dnf.conf`` and
all \*.repo files found under ``/etc/yum.repos.d``. The latter is typically used
for repository configuration.

There are two types of sections in the configuration files: main and
repository. Main defines all global configuration options. There should be only
one main section. The repository sections define the configuration for each
(remote or local) repository.

================
 [main] Options
================

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

==========
 See Also
==========

* :manpage:`dnf(8)`, :ref:`DNF Command Reference <command_ref-label>`
