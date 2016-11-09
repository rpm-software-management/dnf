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

####################################
 Changes in DNF CLI compared to Yum
####################################

.. only :: html

    .. contents::

======================
 No ``--skip-broken``
======================

The ``--skip-broken`` command line switch is not recognized by DNF.

For install command:

Instead of ``--skip-broken``, the new option ``--setopt=strict=0`` could be used
with DNF to skip all unavailable packages or packages with broken dependencies
given to DNF command without raising the error causing the whole operation to
fail. This behavior can be set as default in dnf.conf file. See :ref:`strict
conf option <strict-label>`.

For upgrade command:

The semantics this was supposed to trigger in Yum is now the default for plain
``dnf update``. There is no equivalent for ``yum --skip-broken update foo``, as
silently skipping ``foo`` in this case only amounts to masking an error
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
switch is on by default in DNF. It can thus be confusing to compare the "remove"
operation results between DNF and Yum as by default DNF is often going to remove
more packages.

===========================
 No ``resolvedep`` command
===========================

The Yum version of this command is maintained for legacy reasons only. The user
can just do ``dnf provides`` to find out what package gives a particular
provide.

===========================
 No ``deplist`` command
===========================

Alternative to Yum ``deplist`` command to find out dependencies of the package
is ``dnf repoquery --deplist`` using :ref:`repoquery command
<repoquery_command-label>`.

.. note::  Alternatively there is a YUM compatibility support where
           ``yum deplist`` is alias for ``dnf repoquery --deplist`` command

====================================================
 Excludes and repo excludes apply to all operations
====================================================

Yum only respects excludes during installs and upgrades. DNF extends this to all
operations, among others erasing and listing. If you e.g. want to see a list of
all installed ``python-f*`` packages but not any of the Flask packages, the
following will work::

    dnf -x '*flask*' list installed 'python-f*'

==========================================================
 Yum's conf directive ``includepkgs`` is just ``include``
==========================================================

``include`` directive name of [main] and Repo configuration is more logical and better named counterpart of ``exclude`` in DNF.

=============================================================
 ``dnf remove kernel`` deletes all packages called ``kernel``
=============================================================

In Yum, the running kernel is spared. There is no reason to keep this in DNF,
the user can always specify concrete versions on the command line, e.g.::

    dnf remove kernel-3.9.4

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
Yum immediately stops on a repo error, confusing and bothering the user.

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
packages to install per-group and not via a global setting::

    dnf group install with-optional Editors

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

.. _allowerasing_instead_of_shell:

============================================================
 Packages replacement without ``yum shell`` or ``yum swap``
============================================================

Time after time one needs to remove an installed package and replace it with a different one, providing the same capabilities while other packages depending on these capabilities stay installed. Without (transiently) breaking consistency of the package database this can be done by performing the remove and the install in one transaction. The common way to setup such transaction in Yum is to use ``yum shell``.

There is no shell in DNF but the case above is still valid. We provide the ``--allowerasing`` switch for this purpose, e.g. say you want to replace ``A`` (providing ``P``)  with B (also providing ``P``, conflicting with ``A``) without deleting ``C`` (which requires ``P``) in the process. Use::

  dnf --allowerasing install B

This command is equal to ``yum swap A B``.

========================================================
 Dependency processing details are not shown in the CLI
========================================================

During its depsolving phase, Yum outputs lines similar to::

  ---> Package rubygem-rhc.noarch 0:1.16.9-1.fc19 will be an update
  --> Processing Dependency: rubygem-net-ssh-multi >= 1.2.0 for package: rubygem-rhc-1.16.9-1.fc19.noarch

DNF does not output information like this. The technical reason is that depsolver below DNF always considers all dependencies for update candidates and the output would be very long. Secondly, even in Yum this output gets confusing very quickly especially for large transactions and so does more harm than good.

See the the related `Fedora bug 1044999
<https://bugzilla.redhat.com/show_bug.cgi?id=1044999>`_.

===================================================================
``dnf provides`` complies with the Yum documentation of the command
===================================================================

When one executes::

  yum provides sandbox

Yum applies extra heuristics to determine what the user meant by ``sandbox``, for instance it sequentially prepends entries from the ``PATH`` environment variable to it to see if it matches a file provided by some package. This is an undocumented behavior that DNF does not emulate. Just typically use::

  dnf provides /usr/bin/sandbox

or even::

  dnf provides '*/sandbox'

to obtain similar results.

=================================
``--enableplugin`` not recognized
=================================

This switch has been dropped. It is not documented for Yum and of a questionable use (all plugins are enabled by default).

==================
Bandwidth limiting
==================

DNF supports the ``throttle`` and ``bandwidth`` options familiar from Yum.
Contrary to Yum, when multiple downloads run simultaneously the total
downloading speed is throttled. This was not possible in Yum since
downloaders ran in different processes.

===================================
 ``installonlypkgs`` config option
===================================

Compared to Yum, DNF appends list values from the ``installonlypkgs`` config option to DNF defaults, where YUM overwrites the defaults by option values.

==============================
 The usage of Delta RPM files
==============================

The boolean ``deltarpm`` option controls whether delta RPM files are used. Compared to Yum, DNF does not support ``deltarpm_percentage`` and instead chooses some optimal value of DRPM/RPM ratio to decide whether using deltarpm makes sense in the given case.

================================================
 Handling .srpm files and non-existent packages
================================================

DNF will terminate early with an error if a command is executed requesting an installing operation on a local ``.srpm`` file::

  $ dnf install fdn-0.4.17-1.fc20.src.rpm tour-4-6.noarch.rpm
  Error: Will not install a source rpm package (fdn-0.4.17-1.fc20.src).

The same applies for package specifications that does not match any available package.

Yum will only issue warning in this case and continue installing the "tour" package. The rationale behind the result in DNF is that a program should terminate with an error if it can not fulfill the CLI command in its entirety.

=============================================================
 Promoting package to install to a package that obsoletes it
=============================================================

DNF will not magically replace a request for installing package ``X`` to installing package ``Y`` if ``Y`` obsoletes ``X``. Yum does this if its ``obsoletes`` config option is enabled but the behavior is not properly documented and can be harmful.

See the the related `Fedora bug 1096506
<https://bugzilla.redhat.com/show_bug.cgi?id=1096506>`_ and `guidelines for renaming and obsoleting packages in Fedora <http://fedoraproject.org/wiki/Upgrade_paths_%E2%80%94_renaming_or_splitting_packages>`_.

====================================
Behavior of ``--installroot`` option
====================================

DNF offer more predictable behavior of installroot. DNF differently handles path
from ``--config`` command-line option, where this path is always related to host
system (Yum combines this path with installroot). Reposdir is also slightly
differently handled, if one path of reposdirs exists inside of installroot, than
repos are strictly taken from installroot (Yum tests each path from reposdir
separately and use installroot path if existed). See detailed description for
\-\ :ref:`-installroot <installroot-label>` option.

###############################################
 Changes in DNF plugins compared to Yum plugins
###############################################

======================================  ================================================================  ===================================
Original Yum tool                       DNF command/option                                                Package
--------------------------------------  ----------------------------------------------------------------  -----------------------------------
``yum check``                           :ref:`dnf repoquery <repoquery_command-label>` ``--unsatisfied``  ``dnf``
``yum-langpacks``                                                                                         ``dnf-langpacks``
``yum-plugin-auto-update-debug-info``   option in ``debuginfo-install.conf``                              ``dnf-plugins-core``
``yum-plugin-copr``                     `dnf copr`_                                                       ``dnf-plugins-core``
``yum-plugin-fastestmirror``            ``fastestmirror`` option in `dnf.conf`_                           ``dnf``
``yum-plugin-fs-snapshot``                                                                                ``dnf-plugins-extras-snapper``
``yum-plugin-local``                                                                                      ``dnf-plugins-extras-local``
``yum-plugin-merge-conf``                                                                                 ``dnf-plugins-extras-rpmconf``
``yum-plugin-priorities``               ``priority`` option in `dnf.conf`_                                ``dnf``
``yum-plugin-remove-with-leaves``       ``dnf autoremove``                                                ``dnf``
``yum-plugin-show-leaves``                                                                                ``dnf-plugins-extras-show-leaves``
``yum-plugin-versionlock``                                                                                ``dnf-plugins-extras-versionlock``
======================================  ================================================================  ===================================

Plugins that have not been ported yet:

``yum-plugin-aliases``,
``yum-plugin-changelog``,
``yum-plugin-filter-data``,
``yum-plugin-keys``,
``yum-plugin-list-data``,
``yum-plugin-post-transaction-actions``,
``yum-plugin-protectbase``,
``yum-plugin-ps``,
``yum-plugin-puppetverify``,
``yum-plugin-refresh-updatesd``,
``yum-plugin-rpm-warm-cache``,
``yum-plugin-tmprepo``,
``yum-plugin-tsflags``,
``yum-plugin-upgrade-helper``,
``yum-plugin-verify``

Feel free to file a RFE_ for missing functionality if you need it.

#################################################
 Changes in DNF plugins compared to Yum utilities
#################################################

All ported yum tools are now implemented as DNF plugins.

=========================  ================================================ =================================
Original Yum tool          New DNF command                                  Package
-------------------------  ------------------------------------------------ ---------------------------------
``debuginfo-install``      `dnf debuginfo-install`_                         ``dnf-plugins-core``
``find-repos-of-install``  `dnf list installed`_                            ``dnf``
``needs-restarting``       `dnf tracer`_                                    ``dnf-plugins-extras-tracer``
``package-cleanup``        :ref:`dnf list <list_command-label>`,
                           :ref:`dnf repoquery <repoquery_command-label>`   ``dnf``, ``dnf-plugins-core``
``repoclosure``            `dnf repoclosure`_                               ``dnf-plugins-extras-repoclosure``
``repo-graph``             `dnf repograph`_                                 ``dnf-plugins-extras-repograph``
``repomanage``             `dnf repomanage`_                                ``dnf-plugins-extras-repomanage``
``repoquery``              :ref:`dnf repoquery <repoquery_command-label>`   ``dnf``
``reposync``               `dnf reposync`_                                  ``dnf-plugins-core``
``repotrack``              `dnf download`_                                  ``dnf-plugins-core``
``yum-builddep``           `dnf builddep`_                                  ``dnf-plugins-core``
``yum-config-manager``     `dnf config-manager`_                            ``dnf-plugins-core``
``yum-debug-dump``         `dnf debug-dump`_                                ``dnf-plugins-extras-debug``
``yum-debug-restore``      `dnf debug-restore`_                             ``dnf-plugins-extras-debug``
``yumdownloader``          `dnf download`_                                  ``dnf-plugins-core``
=========================  ================================================ =================================

Detailed table for ``package-cleanup`` replacement:

==================================       =====================================
``package-cleanup --dupes``              ``dnf repoquery --duplicates``
``package-cleanup --leaves``             ``dnf repoquery --unneeded``
``package-cleanup --orphans``            ``dnf repoquery --extras``
``package-cleanup --oldkernels``         ``dnf repoquery --installonly``
``package-cleanup --problems``           ``dnf repoquery --unsatisfied``
``package-cleanup --cleandupes``         ``dnf remove --duplicates``
``package-cleanup --oldkernels``         ``dnf remove --oldinstallonly``
==================================       =====================================

Utilities that have not been ported yet:

``repodiff``,
``repo-rss``,
``show-changed-rco``,
``show-installed``,
``verifytree``,
``yum-groups-manager``

Take a look at FAQ_ about yum to DNF migration. Feel free to file a RFE_ for missing functionality if you need it.

.. _dnf debuginfo-install: http://dnf-plugins-core.readthedocs.org/en/latest/debuginfo-install.html
.. _dnf list installed: http://dnf.readthedocs.org/en/latest/command_ref.html
.. _dnf tracer: http://dnf-plugins-extras.readthedocs.org/en/latest/tracer.html
.. _dnf repoclosure: http://dnf-plugins-extras.readthedocs.org/en/latest/repoclosure.html
.. _dnf repograph: http://dnf-plugins-extras.readthedocs.org/en/latest/repograph.html
.. _dnf repomanage: http://dnf-plugins-extras.readthedocs.org/en/latest/repomanage.html
.. _dnf reposync: http://dnf-plugins-core.readthedocs.org/en/latest/reposync.html
.. _dnf download: http://dnf-plugins-core.readthedocs.org/en/latest/download.html
.. _dnf builddep: http://dnf-plugins-core.readthedocs.org/en/latest/builddep.html
.. _dnf config-manager: http://dnf-plugins-core.readthedocs.org/en/latest/config_manager.html
.. _dnf debug-dump: http://dnf-plugins-extras.readthedocs.org/en/latest/debug.html
.. _dnf debug-restore: http://dnf-plugins-extras.readthedocs.org/en/latest/debug.html
.. _dnf copr: http://rpm-software-management.github.io/dnf-plugins-core/copr.html
.. _dnf.conf: http://dnf.readthedocs.org/en/latest/conf_ref.html
.. _RFE: https://github.com/rpm-software-management/dnf/wiki/Bug-Reporting#new-feature-request
.. _FAQ: http://dnf.readthedocs.io/en/latest/user_faq.html
