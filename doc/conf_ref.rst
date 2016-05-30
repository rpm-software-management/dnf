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

.. _conf_ref-label:

#############################
 DNF Configuration Reference
#############################

=============
 Description
=============

`DNF`_ by default uses the global configuration file at ``/etc/dnf/dnf.conf`` and
all \*.repo files found under ``/etc/yum.repos.d``. The latter is typically used
for repository configuration and takes precedence over global configuration.

The configuration file has INI format consisting of section declaration and
``name=value`` options below each on separate line. There are two types of sections
in the configuration files: main and repository. Main section defines all global
configuration options and should be only one.

The repository sections define the configuration for each (remote or local)
repository. The section name of the repository in brackets serve as repo ID reference
and should be unique across configuration files. The allowed characters of repo ID
string are lower and upper case alphabetic letters, digits, ``-``, ``_``, ``.``
and ``:``. The minimal repository configuration file should aside from repo ID
consists of :ref:`baseurl <baseurl-label>`, :ref:`metalink <metalink-label>`
or :ref:`mirrorlist <mirrorlist-label>` option definition.

================
 [main] Options
================

.. _assumeyes-label:

``assumeyes``
    :ref:`boolean <boolean-label>`

    If enabled dnf will assume ``Yes`` where it would normally prompt for
    confirmation from user input (see also :ref:`defaultyes <defaultyes-label>`). Default is False.

``best``
    :ref:`boolean <boolean-label>`

    When upgrading a package, always try to install its highest version
    available, even only to find out some of its deps are not
    satisfiable. Enable this if you want to experience broken dependencies in
    the repositories firsthand. The default is False.

.. _clean_requirements_on_remove-label:

``clean_requirements_on_remove``
    :ref:`boolean <boolean-label>`

    Remove dependencies that are no longer used during ``dnf remove``. A package
    only qualifies for removal via ``clean_requirements_on_remove`` if it was
    installed through DNF but not on explicit user request, i.e. it was
    pulled in as a dependency. The default is True.
    (:ref:`installonlypkgs <installonlypkgs-label>` are never automatically removed.)

``debuglevel``
    :ref:`integer <integer-label>`

    Debug messages output level, in the range 0 to 10. The higher the number the
    more debug output is put to stdout. Default is 2.

.. _defaultyes-label:

``defaultyes``
    :ref:`boolean <boolean-label>`

    If enabled the default answer to user confirmation prompts will be ``Yes``. Not
    to be confused with :ref:`assumeyes <assumeyes-label>` which will not prompt at all. Default is False.

``errorlevel``
    :ref:`integer <integer-label>`

    Error messages output level, in the range 0 to 10. The higher the number the
    more error output is put to stderr. Default is 2. This is deprecated in DNF.

``install_weak_deps``
    :ref:`boolean <boolean-label>`

    When this option is set to True and a new package is about to be
    installed, all packages linked by weak dependency relation (Recommends or Supplements flags) with this package will pulled into the transaction.
    Default is True.

.. _installonlypkgs-label:

``installonlypkgs``
    :ref:`list <list-label>`

    List of provide names of packages that should only ever be installed, never
    upgraded. Kernels in particular fall into this category.
    These packages are never removed by ``dnf autoremove`` even if they were
    installed as dependencies (see
    :ref:`clean_requirements_on_remove <clean_requirements_on_remove-label>`
    for auto removal details).
    This option overrides the default installonlypkgs list used by DNF.
    The number of kept package versions is regulated by :ref:`installonly_limit <installonly-limit-label>`.

.. _installonly-limit-label:

``installonly_limit``
    :ref:`integer <integer-label>`

    Number of :ref:`installonly packages <installonlypkgs-label>` allowed to be installed
    concurrently. Defaults to 3.

.. _keepcache-label:

``keepcache``
    :ref:`boolean <boolean-label>`

    Keeps downloaded packages in the cache when set to True. Even if it is set to False and packages have not been
    installed they will still persist until next successful transaction. The default
    is False.

.. _metadata_timer_sync-label:

``metadata_timer_sync``
    time in seconds

    The minimal period between two consecutive ``makecache timer`` runs. The
    command will stop immediately if it's less than this time period since its
    last run. Does not affect simple ``makecache`` run. Use ``0`` to completely
    disable automatic metadata synchronizing. The default corresponds to three
    hours. The value is rounded to the next commenced hour.

``pluginconfpath``
    :ref:`list <list-label>`

    List of directories that are searched for plugin configurations to load. All
    configuration files found in these directories, that are named same as a
    plugin, are parsed. The default path is ``/etc/dnf/plugins``.

``pluginpath``
    :ref:`list <list-label>`

    List of directories that are searched for plugins to load. Plugins found in *any of the directories* in this configuration option are used. The default contains a Python version-specific path.

.. _reposdir-label:

``reposdir``
    :ref:`list <list-label>`

    DNF searches for repository configuration files in the paths specified by
    ``reposdir``. The behavior of ``reposdir`` could differ when it is used
    along with \-\ :ref:`-installroot <installroot-label>` option.

``protected_packages``
    :ref:`list <list-label>`

    List of packages that DNF should never completely remove. They are protected via Obsoletes as well as user/plugin removals.

    The default is: ``dnf``, ``glob:/etc/yum/protected.d/*.conf`` and ``glob:/etc/dnf/protected.d/*.conf``. So any packages which should be protected can do so by including a file in ``/etc/dnf/protected.d`` with their package name in it.

    DNF will protect also the package corresponding to the running version of the kernel.

==============
 Repo Options
==============

.. _repo_cost-label:

``cost``
    :ref:`integer <integer-label>`

    The relative cost of accessing this repository, defaulting to 1000. This
    value is compared when the priorities of two repositories are the same. The
    repository with *the lowest cost* is picked. It is useful to make the
    library prefer on-disk repositories to remote ones.

.. _baseurl-label:

``baseurl``
    :ref:`list <list-label>`

    URLs for the repository.

``enabled``
    :ref:`boolean <boolean-label>`

    Include this repository as a package source. The default is True.

.. _repo_gpgkey-label:

``gpgkey``
    :ref:`list <list-label>` of strings

    URLs of a GPG key files that can be used for signing metadata and packages of this repository, empty by default. If a file can not be verified using the already imported keys, import of keys from this option is attempted and the keys are then used for verification.

.. _metalink-label:

``metalink``
    :ref:`string <string-label>`

    URL of a metalink for the repository.

.. _mirrorlist-label:

``mirrorlist``
    :ref:`string <string-label>`

    URL of a mirrorlist for the repository.

``name``
    :ref:`string <string-label>`

    A human-readable name of the repository. Defaults to the ID of the repository.

.. _repo_priority-label:

``priority``
    :ref:`integer <integer-label>`

    The priority value of this repository, default is 99. If there is more than one candidate package for a particular operation, the one from a repo with *the lowest priority value* is picked, possibly despite being less convenient otherwise (e.g. by being a lower version).

.. _skip_if_unavailable-label:

``skip_if_unavailable``
    :ref:`boolean <boolean-label>`

    If enabled, DNF will continue running and disable the repository that couldn't be contacted for any reason when downloading metadata. This option doesn't affect skipping of unavailable packages after dependency resolution. To check inaccessibility of repository use it in combination with :ref:`refresh command line option <refresh_command-label>`. The default is True.

.. _strict-label:

``strict``
    :ref:`boolean <boolean-label>`

    If disabled, all unavailable packages or packages with broken dependencies given to DNF command will be skipped without raising the error causing the whole operation to fail. Currently works for install command only. The default is True.

================
 Repo Variables
================

Right side of every repo option can be enriched by the following variables:

``$releasever``

    Refers to the release version of operating system which DNF derives from information available in RPMDB.

``$arch``

    Refers to the system’s CPU architecture e.g, aarch64, i586, i686 and x86_64.

``$basearch``

    Refers to the base architecture of the system. For example, i686 and i586 machines
    both have a base architecture of i386, and AMD64 and Intel64 machines have a base architecture of x86_64.

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

    Total bandwidth available for downloading. Meaningful when used with the :ref:`throttle option <throttle-label>`. Storage size is in bytes by default but can be specified with a unit of storage. Valid units are 'k', 'M', 'G'.

.. _deltarpm-label:

``deltarpm``
    :ref:`boolean <boolean-label>`

    When enabled, DNF will save bandwidth by downloading much smaller delta RPM
    files, rebuilding them to RPM locally. However, this is quite CPU and I/O
    intensive. Default is True.

``enablegroups``
    :ref:`boolean <boolean-label>`

    Determines whether DNF will allow the use of package groups for this repository. Default is True (package groups are allowed).

.. _exclude-label:

``exclude``
    :ref:`list <list-label>`

    Exclude packages of this repository, specified by a name or a glob and
    separated by a comma, from all operations.
    Can be disabled using ``--disableexcludes`` command line switch.

``fastestmirror``
    :ref:`boolean <boolean-label>`

    If enabled a metric is used to find the fastest available mirror. This overrides the order provided by the mirrorlist/metalink file itself. This file is often dynamically generated by the server to provide the best download speeds and enabling fastestmirror overrides this. The default is False.

.. _gpgcheck-label:

``gpgcheck``
    :ref:`boolean <boolean-label>`

    Whether to perform GPG signature check on packages found in this repository. The default is False.

.. _include-label:

``include``
    :ref:`list <list-label>`

    Include packages of this repository, specified by a name or a glob and separated by a comma, in all operations.
    Inverse of :ref:`exclude <exclude-label>`, DNF will exclude any package in the repository that doesn't match this list. This works in conjunction with exclude and doesn't override it, so if you 'exclude=*.i386' and 'include=python*' then only packages starting with python that do not have an i386 arch will be seen by DNF in this repo.
    Can be disabled using ``--disableexcludes`` command line switch.

.. _ip-resolve-label:

``ip_resolve``
    IP address type

    Determines how DNF resolves host names. Set this to '4'/'IPv4' or '6'/'IPv6' to resolve to IPv4 or IPv6 addresses only. By default, DNF resolves to either addresses.

``max_parallel_downloads``
    :ref:`integer <integer-label>`

    Maximum number of simultaneous package downloads. Defaults to 3.

.. _metadata_expire-label:

``metadata_expire``
    time in seconds

    The period after which the remote repository is checked for metadata update and in the positive case the local metadata cache is updated. The default corresponds to 48 hours. Set this to ``-1`` or ``never`` to make the repo never considered expired.

.. _minrate-label:

``minrate``
    storage size

    This sets the low speed threshold in bytes per second. If the server is sending data at the same or slower speed than this value for at least :ref:`timeout option <timeout-label>` seconds, DNF aborts the connection. The default is 1000. Valid units are 'k', 'M', 'G'.

``proxy``
    :ref:`string <string-label>`

    URL of a proxy server to connect through. If none is specified then direct connection is used (the default).

``proxy_username``
    :ref:`string <string-label>`

    The username to use for connecting to the proxy server. Empty by default.

``proxy_password``
    :ref:`string <string-label>`

    The password to use for connecting to the proxy server. Empty by default.

.. _repo_gpgcheck-label:

``repo_gpgcheck``
    :ref:`boolean <boolean-label>`

    Whether to perform GPG signature check on this repository's metadata. The default is False.

.. _sslcacert-label:

``sslcacert``
    :ref:`string <string-label>`

    Path to the directory or file containing the certificate authorities to verify SSL certificates.
    Empty by default - uses system default.

.. _sslverify-label:

``sslverify``
    :ref:`boolean <boolean-label>`

    When enabled, remote SSL connections are verified. If the client can not be authenticated connecting fails and the given repo is not used further. On False, SSL connections can be used but are not verified. Default is True.

.. _sslclientcert-label:

``sslclientcert``
    :ref:`string <string-label>`

    Path to the SSL client certificate used to connect to remote sites.
    Empty by default.

.. _sslclientkey-label:

``sslclientkey``
    :ref:`string <string-label>`

    Path to the SSL client key used to connect to remote sites.
    Empty by default.

.. _throttle-label:

``throttle``
    storage size

    Limits the downloading speed. It might be an absolute value or a percentage, relative to the value of the :ref:`bandwidth option <bandwidth-label>` option. ``0`` means no throttling (the default). The absolute value is in bytes by default but can be specified with a unit of storage. Valid units are 'k', 'M', 'G'.

.. _timeout-label:

``timeout``
    time in seconds

    Number of seconds to wait for a connection before timing out. Used in combination with :ref:`minrate option <minrate-label>` option. Defaults to 120 seconds.

``username``
    :ref:`string <string-label>`

    The username to use for connecting to repo with basic HTTP authentication. Empty by default.

``password``
    :ref:`string <string-label>`

    The password to use for connecting to repo with basic HTTP authentication. Empty by default.

=================
Types of Options
=================

.. _boolean-label:

``boolean``
    This is a data type with only two possible values.

    One of following options can be used: 1, 0, True, False, yes, no

.. _integer-label:

``integer``
    It is a whole number that can be written without a fractional component.

.. _list-label:

``list``
    It is an option that could represent one or more strings separated by space or comma characters.

.. _string-label:

``string``
    It is a sequence of symbols or digits without any whitespace character.

==========
Files
==========

``Cache Files``
    /var/cache/dnf

``Main Configuration File``
    /etc/dnf/dnf.conf

``Repository``
    /etc/yum.repos.d/

==========
 See Also
==========

* :manpage:`dnf(8)`, :ref:`DNF Command Reference <command_ref-label>`
