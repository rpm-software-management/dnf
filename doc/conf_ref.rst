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

.. _keepcache-label:

``keepcache``
    boolean

    Keep downloaded packages in the cache. The default is off.

.. _metadata_timer_sync-label:

``metadata_timer_sync``
    time in seconds

    The minimal period between two consecutive ``makecache timer`` runs. The
    command will stop immediately if it's less than this time period since its
    last run. Does not affect simple ``makecache`` run. Use ``0`` to completely
    disable automatic metadata synchronizing. The default corresponds to three
    hours.

``pluginpath``
    list

    List of directories that are searched for plugins to load. Plugins found in *any of the directories* in this configuration option are used. The default contains a Python version-specific path.

==============
 Repo Options
==============

.. _repo_cost-label:

``cost``
    integer

    The relative cost of accessing this repository, defaulting to 1000. If the
    same package can be downloaded from two or more repositories, the repository
    with the lowest cost is preferred.

.. _repo_gpgkey-label:

``gpgkey``
    list of strings

    URLs of a GPG key files that can be used for signing metadata and packages of this repository, empty by default. If a file can not be verified using the already imported keys, import of keys from this option is attempted and the keys are then used for verification.

.. _repo_priority-label:

``priority``
    integer

    The priority value of this repository, default is 99. If there is more than one candidate package for a particular operation, the one from a repo with *the lowest priority value* is picked, possibly despite being less convenient otherwise (e.g. by being a lower version).

``skip_if_unavailable``
    boolean

    If enabled, DNF will continue running and disable the repository that couldn't be contacted for any reason when downloading metadata. This option doesn't affect skipping of unavailable packages after dependency resolution. To check inaccessibility of repository use it in combination with :ref:`refresh command line option <refresh_command-label>`. The default is True.


==================================
 Options for both [main] and Repo
==================================

Some options can be applied in either the main section, per repository, or in a
combination. The value provided in the main section is used for all repositories
as the default value and concrete repositories can override it in their
configuration.

.. _bandwidth-label:

``bandwidth``
    storage size

    Total bandwidth available for downloading. Meaningful when used with the :ref:`throttle option <throttle-label>` option. Storage size is in bytes by default but can be specified with a unit of storage. Valid units are 'k', 'M', 'G'.

.. _deltarpm-label:

``deltarpm``
    boolean

    When enabled, DNF will save bandwidth by downloading much smaller delta RPM
    files, rebuilding them to RPM locally. However, this is quite CPU and I/O
    intensive. Default is on.

.. _exclude-label:

``exclude``
    list

    Exclude packages of this repository, specified by a name or a glob and
    separated by a comma, from all operations.
    Can be disabled using ``--disableexcludes`` command line switch.

``fastestmirror``
    boolean

    If enabled a metric is used to find the fastest available mirror. This overrides the order provided by the mirrorlist/metalink file itself. This file is often dynamically generated by the server to provide the best download speeds and enabling fastestmirror overrides this. The default is False.

.. _gpgcheck-label:

``gpgcheck``
    boolean

    Whether to perform GPG signature check on packages found in this repository. The default is False.

.. _include-label:

``include``
    list

    Include packages of this repository, specified by a name or a glob and separated by a comma, from all operations.
    Inverse of :ref:`exclude <exclude-label>`, DNF will exclude any package in the repo. that doesn't match this list. This works in conjunction with exclude and doesn't override it, so if you 'exclude=*.i386' and 'include=python*' then only packages starting with python that do not have an i386 arch. will be seen by DNF in this repo.
    Can be disabled using ``--disableexcludes`` command line switch.

.. _ip-resolve-label:

``ip_resolve``
    IP address type

    Determines how DNF resolves host names. Set this to '4'/'IPv4' or '6'/'IPv6' to resolve to IPv4 or IPv6 addresses only. By default, DNF resolves to either addresses.

.. _metadata_expire-label:

``metadata_expire``
    time in seconds

    The period after which the remote repository is checked for metadata update and in the positive case the local metadata cache is updated. The default corresponds to 48 hours. Set this to ``-1`` or ``never`` to make the repo never considered expired.

``proxy``
    string

    URL of a proxy server to connect through. If none is specified then direct connection is used (the default).

``proxy_username``
    string

    The username to use for connecting to the proxy server. Empty by default.

``proxy_password``
    string

    The password to use for connecting to the proxy server. Empty by default.

.. _repo_gpgcheck-label:

``repo_gpgcheck``
    boolean

    Whether to perform GPG signature check on this repository's metadata. The default is False.

.. _sslverify-label:

``sslverify``
    boolean

    When enabled, remote SSL connections are verified. If the client can not be authenticated connecting fails and the given repo is not used further. On False, SSL connections can be used but are not verified. Default is True.

.. _throttle-label:

``throttle``
    storage size

    Limits the downloading speed. It might be an absolute value or a percentage, relative to the value of the :ref:`bandwidth option <bandwidth-label>` option. ``0`` means no throttling (the default). The absolute value is in bytes by default but can be specified with a unit of storage. Valid units are 'k', 'M', 'G'.

==========
 See Also
==========

* :manpage:`dnf(8)`, :ref:`DNF Command Reference <command_ref-label>`
