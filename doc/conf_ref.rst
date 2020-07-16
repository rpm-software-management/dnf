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

.. _conf_distribution_specific-label:

=====================================
 Distribution-Specific Configuration
=====================================

Configuration options, namely :ref:`best <best-label>` and
:ref:`skip_if_unavailable <skip_if_unavailable-label>`, can be set in the DNF
configuration file by your distribution to override the DNF defaults.


.. _conf_main_options-label:

================
 [main] Options
================

.. _arch-label:

``arch``
    :ref:`string <string-label>`

    The architecture used for installing packages. By default this is auto-detected. Often used
    together with :ref:`ignorearch <ignorearch-label>` option.

.. _assumeno-label:

``assumeno``
    :ref:`boolean <boolean-label>`

    If enabled dnf will assume ``No`` where it would normally prompt for
    confirmation from user input. Default is ``False``.

.. _assumeyes-label:

``assumeyes``
    :ref:`boolean <boolean-label>`

    If enabled dnf will assume ``Yes`` where it would normally prompt for
    confirmation from user input (see also :ref:`defaultyes <defaultyes-label>`). Default is ``False``.

.. _autocheck_running_kernel-label:

``autocheck_running_kernel``
    :ref:`boolean <boolean-label>`

    Automatic check whether there is installed newer kernel module with security update than currently running kernel. Default is ``True``.

``basearch``
    :ref:`string <string-label>`

    The base architecture used for installing packages. By default this is auto-detected.

.. _best-label:

``best``
    :ref:`boolean <boolean-label>`

    ``True`` instructs the solver to either use a package with the highest available
    version or fail. On ``False``, do not fail if the latest version cannot be
    installed and go with the lower version. The default is ``False``.  Note
    this option in particular :ref:`can be set in your configuration file by
    your distribution <conf_distribution_specific-label>`.

``cachedir``
    :ref:`string <string-label>`

    Path to a directory used by various DNF subsystems for storing cache data.
    Has a reasonable root-writable default depending on the distribution. DNF
    needs to be able to create files and directories at this location.

``cacheonly``
    :ref:`boolean <boolean-label>`

    If set to ``True`` DNF will run entirely from system cache, will not update
    the cache and will use it even in case it is expired. Default is ``False``.

.. _check_config_file_age-label:

``check_config_file_age``
    :ref:`boolean <boolean-label>`

    Specifies whether dnf should automatically expire metadata of repos, which are older than
    their corresponding configuration file (usually the dnf.conf file and the foo.repo file).
    Default is ``True`` (perform the check). Expire of metadata is also affected by metadata age.
    See also :ref:`metadata_expire <metadata_expire-label>`.

.. _clean_requirements_on_remove-label:

``clean_requirements_on_remove``
    :ref:`boolean <boolean-label>`

    Remove dependencies that are no longer used during ``dnf remove``. A package
    only qualifies for removal via ``clean_requirements_on_remove`` if it was
    installed through DNF but not on explicit user request, i.e. it was
    pulled in as a dependency. The default is True.
    (:ref:`installonlypkgs <installonlypkgs-label>` are never automatically removed.)

``config_file_path``
    :ref:`string <string-label>`

    Path to the default main configuration file. Default is ``/etc/dnf/dnf.conf``.

``debuglevel``
    :ref:`integer <integer-label>`

    Debug messages output level, in the range 0 to 10. The higher the number the
    more debug output is put to stdout. Default is 2.

``debug_solver``
    :ref:`boolean <boolean-label>`

    Controls whether the libsolv debug files should be created when solving the
    transaction. The debug files are created in the `./debugdata` directory.
    Default is ``False``.

.. _defaultyes-label:

``defaultyes``
    :ref:`boolean <boolean-label>`

    If enabled the default answer to user confirmation prompts will be ``Yes``. Not
    to be confused with :ref:`assumeyes <assumeyes-label>` which will not prompt at all. Default is ``False``.

``diskspacecheck``
    :ref:`boolean <boolean-label>`

    Controls wheather rpm shoud check available disk space during the transaction.
    Default is ``True``.

``errorlevel``
    :ref:`integer <integer-label>`

    Error messages output level, in the range 0 to 10. The higher the number the
    more error output is put to stderr. Default is 3. This is deprecated in DNF
    and overwritten by \-\ :ref:`-verbose <verbose_options-label>` commandline
    option.

``exit_on_lock``
    :ref:`boolean <boolean-label>`

    Should the dnf client exit immediately when something else has the lock. Default is ``False``.

``gpgkey_dns_verification``
    :ref:`boolean <boolean-label>`

    Should the dnf attempt to automatically verify GPG verification keys using the DNS
    system. This option requires libunbound to be installed on the client system. This
    system has two main features. The first one is to check if any of the already
    installed keys have been revoked. Automatic removal of the key is not yet available,
    so it is up to the user, to remove revoked keys from the system. The second feature is
    automatic verification of new keys when a repository is added to the system. In
    interactive mode, the result is written to the output as a suggestion to the user. In
    non-interactive mode (i.e. when -y is used), this system will automatically accept
    keys that are available in the DNS and are correctly signed using DNSSEC. It will also
    accept keys that do not exist in the DNS system and their NON-existence is
    cryptographically proven using DNSSEC. This is mainly to preserve backward
    compatibility.
    Default is ``False``.


``group_package_types``
    :ref:`list <list-label>`

    List of the following: optional, default, mandatory. Tells dnf which type of packages in groups will
    be installed when 'groupinstall' is called. Default is: ``default, mandatory``.

.. _ignorearch-label:

``ignorearch``
    :ref:`boolean <boolean-label>`

    If set to ``True``, RPM will allow attempts to install packages incompatible with the CPU's
    architecture. Defaults to ``False``. Often used together with
    :ref:`arch <arch-label>` option.

.. _installonlypkgs-label:

``installonlypkgs``
    :ref:`list <list-label>`

    List of provide names of packages that should only ever be installed, never
    upgraded. Kernels in particular fall into this category.
    These packages are never removed by ``dnf autoremove`` even if they were
    installed as dependencies (see
    :ref:`clean_requirements_on_remove <clean_requirements_on_remove-label>`
    for auto removal details).
    This option append the list values to the default installonlypkgs list used
    by DNF. The number of kept package versions is regulated
    by :ref:`installonly_limit <installonly-limit-label>`.

.. _installonly-limit-label:

``installonly_limit``
    :ref:`integer <integer-label>`

    Number of :ref:`installonly packages <installonlypkgs-label>` allowed to be installed
    concurrently. Defaults to 3. The minimal number of installonly packages is 2. Value 0 or 1 means
    unlimited number of installonly packages.

``installroot``
    :ref:`string <string-label>`

    The root of the filesystem for all packaging operations. It requires an absolute path. See also :ref:`--installroot commandline option <installroot-label>`.

``install_weak_deps``
    :ref:`boolean <boolean-label>`

    When this option is set to True and a new package is about to be
    installed, all packages linked by weak dependency relation (Recommends or Supplements flags) with this package will be pulled into the transaction.
    Default is ``True``.

.. _keepcache-label:

``keepcache``
    :ref:`boolean <boolean-label>`

    Keeps downloaded packages in the cache when set to True. Even if it is set to False and packages have not been
    installed they will still persist until next successful transaction. The default
    is ``False``.

``logdir``
    :ref:`string <string-label>`

    Directory where the log files will be stored. Default is ``/var/log``.

``logfilelevel``
    :ref:`integer <integer-label>`

    Log file messages output level, in the range 0 to 10. The higher the number the
    more debug output is put to logs. Default is 9.

    This option controls dnf.log, dnf.librepo.log and hawkey.log. Although dnf.librepo.log
    and hawkey.log are affected only by setting the logfilelevel to 10.

``log_compress``
	:ref:`boolean <boolean-label>`

	When set to ``True``, log files are compressed when they are rotated. Default is ``False``.

.. _log_rotate-label:

``log_rotate``
    :ref:`integer <integer-label>`

    Log files are rotated ``log_rotate`` times before being removed. If ``log_rotate``
    is ``0``, the rotation is not performed.
    Default is ``4``.

.. _log_size-label:

``log_size``
    storage size

    Log  files are rotated when they grow bigger than log_size bytes. If
    log_size is 0, the rotation is not performed. The default is 1 MB. Valid
    units are 'k', 'M', 'G'.

    The size applies for individual log files, not the sum of all log files.
    See also :ref:`log_rotate <log_rotate-label>`.

.. _metadata_timer_sync-label:

``metadata_timer_sync``
    time in seconds

    The minimal period between two consecutive ``makecache timer`` runs. The
    command will stop immediately if it's less than this time period since its
    last run. Does not affect simple ``makecache`` run. Use ``0`` to completely
    disable automatic metadata synchronizing. The default corresponds to three
    hours. The value is rounded to the next commenced hour.

.. _module_platform_id-label:

``module_platform_id``
    :ref:`string <string-label>`

    Set this to $name:$stream to override PLATFORM_ID detected from ``/etc/os-release``.
    It is necessary to perform a system upgrade and switch to a new platform.

``multilib_policy``
    :ref:`string <string-label>`

    Controls how multilib packages are treated during install operations. Can either be ``"best"`` (the default) for the depsolver to prefer packages which best match the system's architecture, or ``"all"`` to install all available packages with compatible architectures.

.. _obsoletes_conf_option-label:

``obsoletes``
    :ref:`boolean <boolean-label>`

    This option only has affect during an install/update. It enables
    dnf's obsoletes processing logic, which means it makes dnf check whether
    any dependencies of given package are no longer required and removes them.
    Useful when doing distribution level upgrades.
    Default is 'true'.

    Command-line option: :ref:`--obsoletes <obsoletes_option-label>`

``persistdir``
    :ref:`string <string-label>`

    Directory where DNF stores its persistent data between runs. Default is ``"/var/lib/dnf"``.

``pluginconfpath``
    :ref:`list <list-label>`

    List of directories that are searched for plugin configurations to load. All
    configuration files found in these directories, that are named same as a
    plugin, are parsed. The default path is ``/etc/dnf/plugins``.

.. _pluginpath-label:

``pluginpath``
    :ref:`list <list-label>`

    List of directories that are searched for plugins to load. Plugins found in *any of the directories* in this configuration option are used. The default contains a Python version-specific path.

``plugins``
    :ref:`boolean <boolean-label>`

    Controls whether the plugins are enabled. Default is ``True``.

``protected_packages``
    :ref:`list <list-label>`

    List of packages that DNF should never completely remove. They are protected via Obsoletes as well as user/plugin removals.

    The default is: ``dnf``, ``glob:/etc/yum/protected.d/*.conf`` and ``glob:/etc/dnf/protected.d/*.conf``. So any packages which should be protected can do so by including a file in ``/etc/dnf/protected.d`` with their package name in it.

    DNF will protect also the package corresponding to the running version of the kernel. See also :ref:`protect_running_kernel <protect_running_kernel-label>` option.

.. _protect_running_kernel-label:

``protect_running_kernel``
	:ref:`boolean <boolean-label>`

	Controls whether the package corresponding to the running version of kernel is protected from removal. Default is ``True``.

``releasever``
    :ref:`string <string-label>`

    Used for substitution of ``$releasever`` in the repository configuration.
    See also :ref:`repo variables <repo-variables-label>`.

.. _reposdir-label:

``reposdir``
    :ref:`list <list-label>`

    DNF searches for repository configuration files in the paths specified by
    ``reposdir``. The behavior of ``reposdir`` could differ when it is used
    along with \-\ :ref:`-installroot <installroot-label>` option.

``rpmverbosity``
    :ref:`string <string-label>`

    RPM debug scriptlet output level. One of: ``critical``, ``emergency``,
    ``error``, ``warn``, ``info`` or ``debug``. Default is ``info``.

.. _strict-label:

``strict``
    :ref:`boolean <boolean-label>`

    If disabled, all unavailable packages or packages with broken dependencies given to DNF command will be skipped without raising the error causing the whole operation to fail. Currently works for install command only. The default is True.

``tsflags``
    :ref:`list <list-label>`

    List of strings adding extra flags for the RPM transaction.

    ============  ===========================
    tsflag value  RPM Transaction Flag
    ============  ===========================
    noscripts     RPMTRANS_FLAG_NOSCRIPTS
    test          RPMTRANS_FLAG_TEST
    notriggers    RPMTRANS_FLAG_NOTRIGGERS
    nodocs        RPMTRANS_FLAG_NODOCS
    justdb        RPMTRANS_FLAG_JUSTDB
    nocontexts    RPMTRANS_FLAG_NOCONTEXTS
    nocaps        RPMTRANS_FLAG_NOCAPS
    nocrypto      RPMTRANS_FLAG_NOFILEDIGEST
    ============  ===========================

    The ``nocrypto`` option will also set the ``_RPMVSF_NOSIGNATURES`` and
    ``_RPMVSF_NODIGESTS`` VS flags. The ``test`` option provides a transaction check
    without performing the transaction. It includes downloading of packages, gpg keys check
    (including permanent import of additional keys if necessary), and rpm check to prevent
    file conflicts.
    The ``nocaps`` is supported with rpm-4.14 or later. When ``nocaps`` is used but rpm
    doesn't support it, DNF only reports it as an invalid tsflag.

``upgrade_group_objects_upgrade``
    :ref:`boolean <boolean-label>`

    Set this to False to disable the automatic running of ``group upgrade`` when running the ``upgrade`` command. Default is ``True`` (perform the operation).

.. _varsdir_options-label:

``varsdir``
    :ref:`list <list-label>`

    List of directories where variables definition files are looked for. Defaults to
    ``"/etc/dnf/vars", "/etc/yum/vars"``. See :ref:`variable files <varfiles-label>`
    in Configuration reference.

.. _conf_repo_options-label:

``zchunk``
    :ref:`boolean <boolean-label>`

    Enables or disables the use of repository metadata compressed using the zchunk format (if available). Default is ``True``.


.. _conf_main_options-colors-label:

=========================
 [main] Options - Colors
=========================

``color``
    :ref:`string <string-label>`

    Controls if DNF uses colored output on the command line.
    Possible values: "auto", "never", "always". Default is "auto".

``color_list_available_downgrade``
    :ref:`color <color-label>`

    Color of available packages that are older than installed packages.
    The option is used during list operations.

``color_list_available_install``
    :ref:`color <color-label>`

    Color of packages that are available for installation and none of their versions in installed.
    The option is used during list operations.

``color_list_available_reinstall``
    :ref:`color <color-label>`

    Color of available packages that are identical to installed versions and are available for reinstalls.
    The option is used during list operations.

``color_list_available_upgrade``
    :ref:`color <color-label>`

    Color of available packages that are newer than installed packages.
    The option is used during list operations.

``color_list_installed_extra``
    :ref:`color <color-label>`

    Color of installed packages that do not have any version among available packages.
    The option is used during list operations.

``color_list_installed_newer``
    :ref:`color <color-label>`

    Color of installed packages that are newer than any version among available packages.
    The option is used during list operations.

``color_list_installed_older``
    :ref:`color <color-label>`

    Color of installed packages that are older than any version among available packages.
    The option is used during list operations.

``color_list_installed_reinstall``
    :ref:`color <color-label>`

    Color of installed packages that are among available packages and can be reinstalled.
    The option is used during list operations.

``color_search_match``
    :ref:`color <color-label>`

    Color of patterns matched in search output.

``color_update_installed``
    :ref:`color <color-label>`

    Color of removed packages.
    This option is used during displaying transactions.

``color_update_local``
    :ref:`color <color-label>`

    Color of local packages that are installed from the @commandline repository.
    This option is used during displaying transactions.

``color_update_remote``
    :ref:`color <color-label>`

    Color of packages that are installed/upgraded/downgraded from remote repositories.
    This option is used during displaying transactions.


==============
 Repo Options
==============

.. _baseurl-label:

``baseurl``
    :ref:`list <list-label>`

    List of URLs for the repository. Defaults to ``[]``.

.. _repo_cost-label:

``cost``
    :ref:`integer <integer-label>`

    The relative cost of accessing this repository, defaulting to 1000. This
    value is compared when the priorities of two repositories are the same. The
    repository with *the lowest cost* is picked. It is useful to make the
    library prefer on-disk repositories to remote ones.

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

    URL of a metalink for the repository. Defaults to ``None``.

.. _mirrorlist-label:

``mirrorlist``
    :ref:`string <string-label>`

    URL of a mirrorlist for the repository. Defaults to ``None``.

.. _module_hotfixes-label:

``module_hotfixes``
    :ref:`boolean <boolean-label>`

    Set this to True to disable module RPM filtering and make all RPMs from the repository available. The default is False.
    This allows user to create a repository with cherry-picked hotfixes that are included in a package set on a modular system.

.. _repo_name-label:

``name``
    :ref:`string <string-label>`

    A human-readable name of the repository. Defaults to the ID of the repository.

.. _repo_priority-label:

``priority``
    :ref:`integer <integer-label>`

    The priority value of this repository, default is 99. If there is more than one candidate package for a particular operation, the one from a repo with *the lowest priority value* is picked, possibly despite being less convenient otherwise (e.g. by being a lower version).

``type``
    :ref:`string <string-label>`

    Type of repository metadata. Supported values are: ``rpm-md``.
    Aliases for ``rpm-md``: ``rpm``, ``repomd``, ``rpmmd``, ``yum``, ``YUM``.

.. _repo-variables-label:

================
 Repo Variables
================

Right side of every repo option can be enriched by the following variables:

``$arch``

    Refers to the system’s CPU architecture e.g, aarch64, i586, i686 and x86_64.

``$basearch``

    Refers to the base architecture of the system. For example, i686 and i586 machines
    both have a base architecture of i386, and AMD64 and Intel64 machines have a base architecture of x86_64.

``$releasever``

    Refers to the release version of operating system which DNF derives from information available in RPMDB.


In addition to these hard coded variables, user-defined ones can also be used. They can be defined either via :ref:`variable files <varfiles-label>`, or by using special environmental variables. The names of these variables must be prefixed with DNF_VAR\_ and they can only consist of alphanumeric characters and underscores::

    $ DNF_VAR_MY_VARIABLE=value

To use such variable in your repository configuration remove the prefix. E.g.::

    [myrepo]
    baseurl=https://example.site/pub/fedora/$MY_VARIABLE/releases/$releasever

Note that it is not possible to override the ``arch`` and ``basearch`` variables using either variable files or environmental variables.

Although users are encouraged to use named variables, the numbered environmental variables ``DNF0`` - ``DNF9`` are still supported::

    $ DNF1=value

    [myrepo]
    baseurl=https://example.site/pub/fedora/$DNF1/releases/$releasever


.. _conf_main_and_repo_options-label:

==================================
 Options for both [main] and Repo
==================================

Some options can be applied in either the main section, per repository, or in a
combination. The value provided in the main section is used for all repositories
as the default value, which repositories can then override in their
configuration.

.. _bandwidth-label:

``bandwidth``
    storage size

    Total bandwidth available for downloading. Meaningful when used with the :ref:`throttle option <throttle-label>`. Storage size is in bytes by default but can be specified with a unit of storage. Valid units are 'k', 'M', 'G'.

``countme``
    :ref:`boolean <boolean-label>`

    Determines whether a special flag should be added to a single, randomly
    chosen metalink/mirrorlist query each week.
    This allows the repository owner to estimate the number of systems
    consuming it, by counting such queries over a week's time, which is much
    more accurate than just counting unique IP addresses (which is subject to
    both overcounting and undercounting due to short DHCP leases and NAT,
    respectively).

    The flag is a simple "countme=N" parameter appended to the metalink and
    mirrorlist URL, where N is an integer representing the "longevity" bucket
    this system belongs to.
    The following 4 buckets are defined, based on how many full weeks have
    passed since the beginning of the week when this system was installed: 1 =
    first week, 2 = first month (2-4 weeks), 3 = six months (5-24 weeks) and 4
    = more than six months (> 24 weeks).
    This information is meant to help distinguish short-lived installs from
    long-term ones, and to gather other statistics about system lifecycle.

    Default is False.

.. _deltarpm-label:

``deltarpm``
    :ref:`boolean <boolean-label>`

    When enabled, DNF will save bandwidth by downloading much smaller delta RPM
    files, rebuilding them to RPM locally. However, this is quite CPU and I/O
    intensive. Default is True.

``deltarpm_percentage``
    :ref:`integer <integer-label>`

    When the relative size of delta vs pkg is larger than this, delta is not used.  Default value is 75
    (Deltas must be at least 25% smaller than the pkg).  Use `0` to turn off delta rpm processing. Local repositories (with
    file:// baseurl) have delta rpms turned off by default.

``enablegroups``
    :ref:`boolean <boolean-label>`

    Determines whether DNF will allow the use of package groups for this repository. Default is True (package groups are allowed).

.. _exclude-label:

``excludepkgs``
    :ref:`list <list-label>`

    Exclude packages of this repository, specified by a name or a glob and
    separated by a comma, from all operations.
    Can be disabled using ``--disableexcludes`` command line switch.
    Defaults to ``[]``.

``fastestmirror``
    :ref:`boolean <boolean-label>`

    If enabled a metric is used to find the fastest available mirror. This overrides the order provided by the mirrorlist/metalink file itself. This file is often dynamically generated by the server to provide the best download speeds and enabling fastestmirror overrides this. The default is False.

.. _gpgcheck-label:

``gpgcheck``
    :ref:`boolean <boolean-label>`

    Whether to perform GPG signature check on packages found in this repository.
    The default is False.

    This option can only be used to strengthen the active RPM security policy set with the ``%_pkgverify_level`` macro (see the ``/usr/lib/rpm/macros`` file for details).
    That means, if the macro is set to 'signature' or 'all' and this option is False, it will be overridden to True during DNF runtime, and a warning will be printed.
    To squelch the warning, make sure this option is True for every enabled repository, and also enable :ref:`localpkg_gpgcheck <localpkg_gpgcheck-label>`.

.. _include-label:

``includepkgs``
    :ref:`list <list-label>`

    Include packages of this repository, specified by a name or a glob and separated by a comma, in all operations.
    Inverse of :ref:`excludepkgs <exclude-label>`, DNF will exclude any package in the repository that doesn't match this list. This works in conjunction with ``excludepkgs`` and doesn't override it, so if you 'excludepkgs=*.i386' and 'includepkgs=python*' then only packages starting with python that do not have an i386 arch will be seen by DNF in this repo.
    Can be disabled using ``--disableexcludes`` command line switch.
    Defaults to ``[]``.

.. _ip-resolve-label:

``ip_resolve``
    IP address type

    Determines how DNF resolves host names. Set this to '4'/'IPv4' or '6'/'IPv6' to resolve to IPv4 or IPv6 addresses only. By default, DNF resolves to either addresses.

.. _localpkg_gpgcheck-label:

``localpkg_gpgcheck``
    :ref:`boolean <boolean-label>`

    Whether to perform a GPG signature check on local packages (packages in a file, not in a repository).
    The default is False.
    This option is subject to the active RPM security policy (see :ref:`gpgcheck <gpgcheck-label>` for more details).

``max_parallel_downloads``
    :ref:`integer <integer-label>`

    Maximum number of simultaneous package downloads. Defaults to 3.

.. _metadata_expire-label:

``metadata_expire``
    time in seconds

    The period after which the remote repository is checked for metadata update and in the positive
    case the local metadata cache is updated. The default corresponds to 48 hours. Set this to
    ``-1`` or ``never`` to make the repo never considered expired. Expire of metadata can bee also
    triggered by change of timestamp of configuration files (``dnf.conf``, ``<repo>.repo``). See
    also :ref:`check_config_file_age <check_config_file_age-label>`.

.. _minrate-label:

``minrate``
    storage size

    This sets the low speed threshold in bytes per second. If the server is sending data at the same or slower speed than this value for at least :ref:`timeout option <timeout-label>` seconds, DNF aborts the connection. The default is 1000. Valid units are 'k', 'M', 'G'.

``password``
    :ref:`string <string-label>`

    The password to use for connecting to a repository with basic HTTP authentication. Empty by default.

``proxy``
    :ref:`string <string-label>`

    URL of a proxy server to connect through. Set to an empty string to disable the proxy setting inherited from the main section and use direct connection instead. The expected format of this option is ``<scheme>://<ip-or-hostname>[:port]``.
    (For backward compatibility, '_none_' can be used instead of the empty string.)

    Note: The curl environment variables (such as ``http_proxy``) are effective if this option is unset. See the ``curl`` man page for details.

``proxy_username``
    :ref:`string <string-label>`

    The username to use for connecting to the proxy server. Empty by default.

``proxy_password``
    :ref:`string <string-label>`

    The password to use for connecting to the proxy server. Empty by default.

``proxy_auth_method``
    :ref:`string <string-label>`

    The authentication method used by the proxy server. Valid values are

    ==========     ==========================================================
    method         meaning
    ==========     ==========================================================
    basic          HTTP Basic authentication
    digest         HTTP Digest authentication
    negotiate      HTTP Negotiate (SPNEGO) authentication
    ntlm           HTTP NTLM authentication
    digest_ie      HTTP Digest authentication with an IE flavor
    ntlm_wb        NTLM delegating to winbind helper
    none           None auth method
    any            All suitable methods
    ==========     ==========================================================

    Defaults to ``any``


.. _repo_gpgcheck-label:

``repo_gpgcheck``
    :ref:`boolean <boolean-label>`

    Whether to perform GPG signature check on this repository's metadata. The default is False.

``retries``
    :ref:`integer <integer-label>`

    Set the number of total retries for downloading packages. The number is
    accumulative, so e.g. for `retries=10`, dnf will fail after any package
    download fails for eleventh time. Setting this to `0` makes dnf try
    forever. Default is `10`.

.. _skip_if_unavailable-label:

``skip_if_unavailable``
    :ref:`boolean <boolean-label>`

    If enabled, DNF will continue running and disable the repository that couldn't be synchronized
    for any reason. This option doesn't affect skipping of unavailable packages after dependency
    resolution. To check inaccessibility of repository use it in combination with
    :ref:`refresh command line option <refresh_command-label>`. The default is ``False``.
    Note this option in particular :ref:`can be set in your configuration file
    by your distribution <conf_distribution_specific-label>`.

.. _sslcacert-label:

``sslcacert``
    :ref:`string <string-label>`

    Path to the directory or file containing the certificate authorities to verify SSL certificates.
    Empty by default - uses system default.

.. _sslverify-label:

``sslverify``
    :ref:`boolean <boolean-label>`

    When enabled, remote SSL certificates are verified. If the client can not be authenticated, connecting fails and the repository is not used any further. If ``False``, SSL connections can be used, but certificates are not verified. Default is ``True``.

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

    Number of seconds to wait for a connection before timing out. Used in combination with :ref:`minrate option <minrate-label>` option. Defaults to 30 seconds.

``username``
    :ref:`string <string-label>`

    The username to use for connecting to repo with basic HTTP authentication. Empty by default.

``user_agent``
    :ref:`string <string-label>`

    The User-Agent string to include in HTTP requests sent by DNF.
    Defaults to ::

        libdnf (NAME VERSION_ID; VARIANT_ID; OS.BASEARCH)

    where NAME, VERSION_ID and VARIANT_ID are OS identifiers read from the
    :manpage:`os-release(5)` file, and OS and BASEARCH are the canonical OS
    name and base architecture, respectively.
    Example: ::

        libdnf (Fedora 31; server; Linux.x86_64)

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

.. _color-label:

``color``
    A string describing color and modifiers separated with a comma, for example "red,bold".

    * Colors: black, blue, cyan, green, magenta, red, white, yellow
    * Modifiers: bold, blink, dim, normal, reverse, underline


==========
Files
==========

``Cache Files``
    /var/cache/dnf

``Main Configuration File``
    /etc/dnf/dnf.conf

``Repository``
    /etc/yum.repos.d/

.. _varfiles-label:

``Variables``
    Any properly named file in /etc/dnf/vars is turned into a variable named after the filename (or
    overrides any of the above variables but those set from commandline). Filenames may contain only
    alphanumeric characters and underscores and be in lowercase.
    Variables are also read from /etc/yum/vars for YUM compatibility reasons.

==========
 See Also
==========

* :manpage:`dnf(8)`, :ref:`DNF Command Reference <command_ref-label>`
