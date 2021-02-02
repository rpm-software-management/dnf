..
  Copyright (C) 2014-2018 Red Hat, Inc.

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
 Changes in DNF CLI compared to YUM
####################################

.. only :: html

    .. contents::

======================
 ``--skip-broken``
======================

For install command:

The ``--skip-broken`` option is an alias for ``--setopt=strict=0``. Both options could be used
with DNF to skip all unavailable packages or packages with broken dependencies given to DNF
without raising an error causing the whole operation to fail. This behavior can be set as default
in dnf.conf file. See :ref:`strict conf option <strict-label>`.

For upgrade command:

The semantics that were supposed to trigger in YUM with ``--skip-broken`` are now set for plain
``dnf update`` as a default. There is no need to use ``--skip-broken`` with the ``dnf upgrade``
command. To use only the latest versions of packages in transactions, there is the ``--best``
command line switch.

========================================
Update and Upgrade Commands are the Same
========================================

Invoking ``dnf update`` or ``dnf upgrade``, in all their forms, has the same
effect in DNF, with the latter being preferred. In YUM ``yum upgrade`` was
exactly like ``yum --obsoletes update``.

================================================
 ``clean_requirements_on_remove`` on by default
================================================

The :ref:`clean_requirements_on_remove <clean_requirements_on_remove-label>`
switch is on by default in DNF. It can thus be confusing to compare the "remove"
operation results between DNF and YUM as by default DNF is often going to remove
more packages.

===========================
 No ``resolvedep`` command
===========================

The YUM version of this command is maintained for legacy reasons only. The user
can just use ``dnf provides`` to find out what package provides a particular file.

===========================
 No ``deplist`` command
===========================

An alternative to the YUM ``deplist`` command to find out dependencies of a package
is ``dnf repoquery --deplist`` using :ref:`repoquery command
<repoquery_command-label>`.

.. note::  Alternatively there is a YUM compatibility support where
           ``yum deplist`` is alias for ``dnf repoquery --deplist`` command

====================================================
 Excludes and repo excludes apply to all operations
====================================================

YUM only respects excludes during installs and upgrades. DNF extends this to all
operations, among others erasing and listing. If you e.g. want to see a list of
all installed ``python-f*`` packages but not any of the Flask packages, the
following will work::

    dnf -x '*flask*' list installed 'python-f*'

=======================================
The ``include`` option has been removed
=======================================

Inclusion of other configuration files in the main configuration file is no longer supported.

====================================================
``dnf provides /bin/<file>`` is not fully supported
====================================================

After `UsrMove <https://fedoraproject.org/wiki/Features/UsrMove>`_ there's no
directory ``/bin`` on Fedora systems and no files get installed there,
``/bin`` is only a symlink created by the ``filesystem`` package to point to
``/usr/bin``. Resolving the symlinks to their real path would only give the
user a false sense that this works, while in fact provides requests using globs
such as::

    dnf provides /b*/<file>

will fail still (as they do in YUM now). To find what provides a particular
binary, use the actual path for binaries on Fedora::

    dnf provides /usr/bin/<file>

Also see related Fedora bugzillas `982947
<https://bugzilla.redhat.com/show_bug.cgi?id=982947>`_ and `982664
<https://bugzilla.redhat.com/show_bug.cgi?id=982664>`_.

.. _skip_if_unavailable_default:

====================================================
 ``skip_if_unavailable`` could be enabled by default
====================================================

In some distributions DNF is shipped with ``skip_if_unavailable=True`` in
the :ref:`DNF configuration file <conf_ref-label>`. The reason for the change
is that third-party repositories can often be unavailable. Without this setting
in the relevant repository configuration file YUM immediately stops on a
repository synchronization error, confusing and bothering the user.

See the related `Fedora bug 984483 <https://bugzilla.redhat.com/show_bug.cgi?id=984483>`_.

============================================================================
 ``overwrite_groups`` dropped, comps functions acting as if always disabled
============================================================================

This config option has been dropped. When DNF sees several groups with the same
group ID it merges the groups' contents together.

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

    As a special hack if the mirrorlist URL contains the word "metalink" then
    the value of mirrorlist is copied to metalink (if metalink is not set).

The relevant repository configuration files have been fixed to respect this, see
the related `Fedora bug 948788
<https://bugzilla.redhat.com/show_bug.cgi?id=948788>`_.

=================================
 ``alwaysprompt`` dropped
=================================

Unsupported to simplify the configuration.

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

Since DNF tolerates the use of other package managers, it is possible that not
all changes to the RPMDB are stored in the history of transactions. Therefore, DNF
does not fail if such a situation is encountered and thus the ``force`` option
is not needed anymore.

.. _allowerasing_instead_of_swap:

============================================================
 Packages replacement without ``yum swap``
============================================================

Time after time one needs to remove an installed package and replace it with a different one, providing the same capabilities while other packages depending on these capabilities stay installed. Without (transiently) breaking consistency of the package database this can be done by performing the remove and the install in one transaction. The common way to set up such a transaction in DNF is to use ``dnf shell`` or use the ``--allowerasing`` switch.

E.g. say you want to replace ``A`` (providing ``P``)  with B (also providing ``P``, conflicting with ``A``) without deleting ``C`` (which requires ``P``) in the process. Use::

  dnf --allowerasing install B

This command is equal to ``yum swap A B``.

DNF provides swap command but only ``dnf swap A B`` syntax is supported

========================================================
 Dependency processing details are not shown in the CLI
========================================================

During its depsolving phase, YUM outputs lines similar to::

  ---> Package rubygem-rhc.noarch 0:1.16.9-1.fc19 will be an update
  --> Processing Dependency: rubygem-net-ssh-multi >= 1.2.0 for package: rubygem-rhc-1.16.9-1.fc19.noarch

DNF does not output information like this. The technical reason is that depsolver below DNF always considers all dependencies for update candidates and the output would be very long. Secondly, even in YUM this output gets confusing very quickly especially for large transactions and so does more harm than good.

See the related `Fedora bug 1044999
<https://bugzilla.redhat.com/show_bug.cgi?id=1044999>`_.

===================================================================
``dnf provides`` complies with the YUM documentation of the command
===================================================================

When one executes::

  yum provides sandbox

YUM applies extra heuristics to determine what the user meant by ``sandbox``, for instance it sequentially prepends entries from the ``PATH`` environment variable to it to see if it matches a file provided by some package. This is an undocumented behavior that DNF does not emulate. Just typically use::

  dnf provides /usr/bin/sandbox

or even::

  dnf provides '*/sandbox'

to obtain similar results.

==================
Bandwidth limiting
==================

DNF supports the ``throttle`` and ``bandwidth`` options familiar from YUM.
Contrary to YUM, when multiple downloads run simultaneously the total
downloading speed is throttled. This was not possible in YUM since
downloaders ran in different processes.

===================================
 ``installonlypkgs`` config option
===================================

Compared to YUM, DNF appends list values from the ``installonlypkgs`` config option to DNF defaults, where YUM overwrites the defaults by option values.

==============================
 The usage of Delta RPM files
==============================

The boolean ``deltarpm`` option controls whether delta RPM files are used. Compared to YUM, DNF does not support ``deltarpm_percentage`` and instead chooses some optimal value of DRPM/RPM ratio to decide whether using deltarpm makes sense in the given case.

================================================
 Handling .srpm files and non-existent packages
================================================

DNF will terminate early with an error if a command is executed requesting an installing operation on a local ``.srpm`` file::

  $ dnf install fdn-0.4.17-1.fc20.src.rpm tour-4-6.noarch.rpm
  Error: Will not install a source rpm package (fdn-0.4.17-1.fc20.src).

The same applies for package specifications that do not match any available package.

YUM will only issue a warning in this case and continue installing the "tour" package. The rationale behind the result in DNF is that a program should terminate with an error if it can not fulfill the CLI command in its entirety.

=============================================================
 Promoting package to install to a package that obsoletes it
=============================================================

DNF will not magically replace a request for installing package ``X`` to installing package ``Y`` if ``Y`` obsoletes ``X``. YUM does this if its ``obsoletes`` config option is enabled but the behavior is not properly documented and can be harmful.

See the related `Fedora bug 1096506
<https://bugzilla.redhat.com/show_bug.cgi?id=1096506>`_ and `guidelines for renaming and obsoleting packages in Fedora <http://fedoraproject.org/wiki/Upgrade_paths_%E2%80%94_renaming_or_splitting_packages>`_.

====================================
Behavior of ``--installroot`` option
====================================

DNF offers more predictable behavior of installroot. DNF handles the path differently
from the ``--config`` command-line option, where this path is always related to the host
system (YUM combines this path with installroot). Reposdir is also handled slightly
differently, if one path of the reposdirs exists inside of installroot, then
repos are strictly taken from installroot (YUM tests each path from reposdir
separately and use installroot path if existed). See the detailed description for
\-\ :ref:`-installroot <installroot-label>` option.

========================================
Different prompt after transaction table
========================================

DNF doesn't provide download functionality after displaying transaction table. It only asks user whether to continue with transaction or not.
If one wants to download packages, they can use the 'download' command.

========================================
List command shows all repo alternatives
========================================

DNF lists all packages from all repos, which means there can be duplicates package names (with different repo name). This is due to providing users
possibility to choose preferred repo.


===============================================
``yum-langpacks`` subcommands have been removed
===============================================
Translations became part of core DNF and it is no longer
necessary to manage individual language packs.

Following sub-commands were removed:

* langavailable
* langinstall
* langremove
* langlist
* langinfo


###############################################
 Changes in DNF plugins compared to YUM plugins
###############################################

=======================================  ================================================================  ===================================
Original YUM tool                        DNF command/option                                                Package
---------------------------------------  ----------------------------------------------------------------  -----------------------------------
``yum check``                            :ref:`dnf repoquery <repoquery_command-label>` ``--unsatisfied``  ``dnf``
``yum-langpacks``                                                                                          ``dnf``
``yum-plugin-aliases``                   :ref:`dnf alias <alias_command-label>`                            ``dnf``
``yum-plugin-auto-update-debug-info``    option in ``debuginfo-install.conf``                              ``dnf-plugins-core``
``yum-plugin-changelog``                                                                                   ``dnf-plugins-core``
``yum-plugin-copr``                      `dnf copr`_                                                       ``dnf-plugins-core``
``yum-plugin-fastestmirror``             ``fastestmirror`` option in `dnf.conf`_                           ``dnf``
``yum-plugin-fs-snapshot``                                                                                 ``dnf-plugins-extras-snapper``
``yum-plugin-local``                                                                                       ``dnf-plugins-core``
``yum-plugin-merge-conf``                                                                                  ``dnf-plugins-extras-rpmconf``
``yum-plugin-post-transaction-actions``                                                                    ``dnf-plugins-core``
``yum-plugin-priorities``                ``priority`` option in `dnf.conf`_                                ``dnf``
``yum-plugin-remove-with-leaves``        :ref:`dnf autoremove <autoremove_command-label>`                  ``dnf``
``yum-plugin-show-leaves``                                                                                 ``dnf-plugins-core``
``yum-plugin-tmprepo``                   ``--repofrompath`` option                                         ``dnf``
``yum-plugin-tsflags``                   ``tsflags``  option in `dnf.conf`_                                ``dnf``
``yum-plugin-versionlock``                                                                                 ``python3-dnf-plugin-versionlock``
``yum-rhn-plugin``                                                                                         ``dnf-plugin-spacewalk``
=======================================  ================================================================  ===================================

Plugins that have not been ported yet:

``yum-plugin-filter-data``,
``yum-plugin-keys``,
``yum-plugin-list-data``,
``yum-plugin-protectbase``,
``yum-plugin-ps``,
``yum-plugin-puppetverify``,
``yum-plugin-refresh-updatesd``,
``yum-plugin-rpm-warm-cache``,
``yum-plugin-upgrade-helper``,
``yum-plugin-verify``

Feel free to file an RFE_ for missing functionality if you need it.

#################################################
 Changes in DNF plugins compared to YUM utilities
#################################################

All ported YUM tools are now implemented as DNF plugins.

=========================  ================================================ =================================
Original YUM tool          New DNF command                                  Package
-------------------------  ------------------------------------------------ ---------------------------------
``debuginfo-install``      `dnf debuginfo-install`_                         ``dnf-plugins-core``
``find-repos-of-install``  `dnf list installed`_                            ``dnf``
``needs-restarting``       `dnf tracer`_                                    ``dnf-plugins-extras-tracer``
``package-cleanup``        :ref:`dnf list <list_command-label>`,
                           :ref:`dnf repoquery <repoquery_command-label>`   ``dnf``, ``dnf-plugins-core``
``repoclosure``            `dnf repoclosure`_                               ``dnf-plugins-extras-repoclosure``
``repodiff``               `dnf repodiff`_                                  ``dnf-plugins-core``
``repo-graph``             `dnf repograph`_                                 ``dnf-plugins-extras-repograph``
``repomanage``             `dnf repomanage`_                                ``dnf-plugins-extras-repomanage``
``repoquery``              :ref:`dnf repoquery <repoquery_command-label>`   ``dnf``
``reposync``               `dnf reposync`_                                  ``dnf-plugins-core``
``repotrack``              `dnf download`_ --resolve --alldeps              ``dnf-plugins-core``
``yum-builddep``           `dnf builddep`_                                  ``dnf-plugins-core``
``yum-config-manager``     `dnf config-manager`_                            ``dnf-plugins-core``
``yum-debug-dump``         `dnf debug-dump`_                                ``dnf-plugins-extras-debug``
``yum-debug-restore``      `dnf debug-restore`_                             ``dnf-plugins-extras-debug``
``yumdownloader``          `dnf download`_                                  ``dnf-plugins-core``
=========================  ================================================ =================================

Detailed table for ``package-cleanup`` replacement:

==========================================       ===============================================================
``package-cleanup --dupes``                      ``dnf repoquery --duplicates``
``package-cleanup --leaves``                     ``dnf repoquery --unneeded``
``package-cleanup --orphans``                    ``dnf repoquery --extras``
``package-cleanup --problems``                   ``dnf repoquery --unsatisfied``
``package-cleanup --cleandupes``                 ``dnf remove --duplicates``
``package-cleanup --oldkernels``                 ``dnf remove --oldinstallonly``
``package-cleanup --oldkernels --keep=2``        ``dnf remove $(dnf repoquery --installonly --latest-limit=-2)``
==========================================       ===============================================================

=============================
yum-updateonboot and yum-cron
=============================

DNF does not have a direct replacement of yum-updateonboot and yum-cron commands.
However, the similar result can be achieved by ``dnf automatic`` command (see :doc:`automatic`).

You can either use the shortcut::

  $ systemctl enable --now dnf-automatic-install.timer

Or set ``apply_updates`` option of ``/etc/dnf/automatic.conf`` to True and use generic timer unit::

  $ systemctl enable --now dnf-automatic.timer

The timer in both cases is activated 1 hour after the system was booted up and then repetitively once every 24 hours. There is also a random delay on these timers set to 5 minutes. These values can be tweaked via ``dnf-automatic*.timer`` config files located in the ``/usr/lib/systemd/system/`` directory.


=======================================
Utilities that have not been ported yet
=======================================

``repo-rss``,
``show-changed-rco``,
``show-installed``,
``verifytree``,
``yum-groups-manager``

Take a look at the FAQ_ about YUM to DNF migration. Feel free to file an RFE_ for missing functionality if you need it.

.. _dnf debuginfo-install: http://dnf-plugins-core.readthedocs.org/en/latest/debuginfo-install.html
.. _dnf list installed: http://dnf.readthedocs.org/en/latest/command_ref.html
.. _dnf tracer: http://dnf-plugins-extras.readthedocs.org/en/latest/tracer.html
.. _dnf repoclosure: http://dnf-plugins-extras.readthedocs.org/en/latest/repoclosure.html
.. _dnf repodiff: http://dnf-plugins-core.readthedocs.org/en/latest/repodiff.html
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
