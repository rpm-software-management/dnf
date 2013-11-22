####################################
 Changes in DNF CLI compared to Yum
####################################

.. contents::

======================
 No ``--skip-broken``
======================

The ``--skip-broken`` command line switch is not recognized by DNF. The
semantics this was supposed to trigger in Yum is now the default for plain ``dnf
update``. There is no equivalent for ``yum --skip-broken update foo``, as
silentnly skipping ``foo`` in this case only amounts to masking an error
contradicting the user request. To try using the latest versions of packages in
transactions there is the ``--best`` command line switch.

========================================
Update and Upgrade Commands are the Same
========================================

Invoking ``dnf update`` or ``dnf upgrade``, in all their forms, has the same
effect in DNF, with the latter being preferred. In Yum ``yum upgrade`` was
exactly like ``yum --obsoletes update``.

================================================
 ``clean_requirements_on_remove`` on by default
================================================

The :ref:`clean_requirements_on_remove <clean_requirements_on_remove-label>`
switch is on by default in DNF. It can thus be confusing to compare the "erase"
operation results between DNF and Yum as by default DNF is often going to remove
more packages.

===========================
 No ``resolvedep`` command
===========================

The Yum version of this command is maintained for legacy reasons only. The user
can just do ``dnf provides`` to find out what package gives a particular
provide.

====================================================
 Excludes and repo excludes apply to all operations
====================================================

Yum only respects excludes during installs and upgrades. DNF extends this to all
operations, among others erasing and listing. If you e.g. want to see a list of
all installed ``python-f*`` packages but not any of the Flask packages, the
following will work::

    dnf -x '*flask*' list installed 'python-f*'

===================================
 ``protected_packages`` is ignored
===================================

DNF drops Yum's ``protected_packages`` configuration option. Generally, DNF lets
the user do what she specified, even have DNF itself removed. Similar functionality
can be implemented by a plugin.

=============================================================
 ``dnf erase kernel`` deletes all packages called ``kernel``
=============================================================

In Yum, the running kernel is spared. There is no reason to keep this in DNF,
the user can always specify concrete versions on the command line, e.g.::

    dnf erase kernel-3.9.4

=====================================================================
``dnf provides /bin/<file>`` does not find any packages on Fedora
=====================================================================

After `UsrMove <https://fedoraproject.org/wiki/Features/UsrMove>`_ there's no
directory ``/bin`` on Fedora systems and no files get installed there,
``/bin`` is only a symlink created by the ``filesystem`` package to point to
``/usr/bin``. Resolving the symlinks to their real path would only give the
user false sense that this works while in fact provides requests using globs
such as::

    dnf provides /b*/<file>

will fail still (as it does in Yum now). To find what provides a particular
binary use the actual path for binaries on Fedora::

    dnf provides /usr/bin/<file>

Also see related Fedora bugzillas `982947
<https://bugzilla.redhat.com/show_bug.cgi?id=982947>`_ and `982664
<https://bugzilla.redhat.com/show_bug.cgi?id=982664>`_.


.. _skip_if_unavailable_default:

============================================
 ``skip_if_unavailable`` enabled by default
============================================

The important system repos should never be down and we see the third party repos
down often enough to warrant this change. Note that without this setting and
without an explicit ``skip_if_unavailable=True`` in the relevant repo .ini file
DNF immediately stops on a repo error, confusing and bothering the user.

See the related `Fedora bug 984483 <https://bugzilla.redhat.com/show_bug.cgi?id=984483>`_.

============================================================================
 ``overwrite_groups`` dropped, comps functions acting as if always disabled
============================================================================

This config option has been dropped. When DNF sees several groups with the same
group id it merges the groups' contents together.

===============================
 ``mirrorlist_expire`` dropped
===============================

To simplify things for the user, DNF uses ``metadata_expire`` for both expiring
metadata and the mirrorlist file (which is a kind of metadata itself).

===========================================================
 metalink not recognized in the ``mirrorlist`` repo option
===========================================================

The following part of ``yum.conf(5)`` no longer applies for the ``mirrorlist``
option:

    As a special hack is the mirrorlist URL contains the word "metalink" then
    the value of mirrorlist is copied to metalink (if metalink is not set).

The relevant repository configuration files have been fixed to respect this, see
the related `Fedora bug 948788
<https://bugzilla.redhat.com/show_bug.cgi?id=948788>`_.

.. _group_package_types_dropped:

=================================
 ``group_package_types`` dropped
=================================

Done to simplify the configuration. User will typically want to decide what
packages to install per-group and not via a global setting.

.. _upgrade_requirements_on_install_dropped:

=============================================
 ``upgrade_requirements_on_install`` dropped
=============================================

Dropping this config option with blurry semantics simplifies the
configuration. DNF behaves as if this was disabled. If the user wanted to
upgrade everything to the latest version she'd simply use ``dnf upgrade``.

========================================
 ``dnf history rollback`` check dropped
========================================

DNF tolerates the use of other package managers. Then it is possible that not
all changes to RPMDB are stored in the history of transactions. Therefore, DNF
does not fail if such a situation is encountered and thus the ``force`` option
is not needed anymore.
