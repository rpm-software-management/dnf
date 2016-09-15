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

===============
 Configuration
===============

Configurable settings of the :class:`dnf.Base` object are stored into a :class:`dnf.conf.Conf` instance. The various options are described here.

.. class:: dnf.conf.Conf

  .. attribute:: assumeyes

    Boolean option, if set to ``True`` on any user input asking for confirmation
    (e.g. after transaction summary) the answer is implicitly ``yes``. Default is ``False``.
  
  .. attribute:: best

    Boolean option, ``True`` instructs the solver to either use a package with the highest available version or fail. On ``False``, do not fail if the latest version can not be installed. Default is ``False``.

  .. attribute:: cachedir

    Path to a directory used by various DNF subsystems for storing cache data. Has a reasonable root-writable default depending on the distribution. It is up to the client to set this to a location where files and directories can be created under the running user. The directory can be safely deleted after the :class:`dnf.Base` object is destroyed

  .. attribute:: check_config_file_age

    Boolean option. Specifies whether dnf should automatically expire metadata of repos, which are older than
    their corresponding configuration file (usually the dnf.conf file and the foo.repo file).
    Default is ``True`` (perform the check).

  .. attribute:: clean_requirements_on_remove

    Boolean option. ``True`` removes dependencies that are no longer used during ``dnf remove``. A package only qualifies for removal via ``clean_requirements_on_remove`` if it was installed through DNF but not on explicit user request, i.e. it was pulled in as a dependency. The default is ``True``. (:ref:`installonlypkgs <installonlypkgs-label>` are never automatically removed.)

  .. attribute:: config_file_path

    Path to the default main configuration file. Default is ``"/etc/dnf/dnf.conf"``.

  .. attribute:: debuglevel

    Debug messages output level, in the range 0 to 10. Default is 2.

  .. attribute:: deltarpm_percentage

    Integer option. When the relative size of delta vs pkg is larger than this, delta is not used. Default value is 75 (%).
    Use `0' to turn off delta rpm processing. Local repositories (with file:// baseurl) have delta rpms always turned off.

  .. attribute:: exit_on_lock

    Boolean option, if set to ``True`` dnf client exits immediately when something else has the lock. Default is ``False``.

  .. attribute:: get_reposdir

    Returns the value of the first valid reposdir or if unavailable the value of created reposdir (string)

  .. attribute:: group_package_types

    List of the following: optional, default, mandatory. Tells dnf which type of packages in groups will
    be installed when 'groupinstall' is called. Default is: default, mandatory

  .. attribute:: installonlypkgs

    List of provide names of packages that should only ever be installed, never
    upgraded. Kernels in particular fall into this category.
    These packages are never removed by ``dnf autoremove`` even if they were
    installed as dependencies (see
    :ref:`clean_requirements_on_remove <clean_requirements_on_remove-label>`
    for auto removal details).
    This option overrides the default installonlypkgs list used by DNF.
    The number of kept package versions is regulated by
    :ref:`installonly_limit <installonly-limit-label>`.

  .. attribute:: installonly_limit

    An integer to limit the number of installed installonly packages (packages that do not upgrade, instead few versions are installed in parallel). Defaults to ``0``, that is the limiting is disabled.

  .. attribute:: install_weak_deps

    When this boolean option is set to True and a new package is about to be
    installed, all packages linked by weak dependency relation (Recommends or Supplements flags) with this package will pulled into the transaction.
    Default is True.

  .. attribute:: installroot

    The root of the filesystem for all packaging operations.

  .. attribute:: keepcache

    Keeps downloaded packages in the cache when this boolean option is set to
    True. Even if it is set to False and packages have not been installed they
    will still persist until next successful transaction. The default is False.

  .. attribute:: logdir

    Directory where the log files will be stored. Default is ``"/var/log"``.

  .. attribute:: multilib_policy

    Controls how multilib packages are treated during install operations. Can either be ``"best"`` (the default) for the depsolver to prefer packages which best match the system's architecture, or ``"all"`` to install all available packages with compatible architectures.

  .. attribute:: persistdir

    Directory where the data that DNF keeps track of between different runs is stored. Default is ``"/var/lib/dnf"``.

  .. attribute:: pluginconfpath

    List of directories that are searched for plugin configuration to load. All configuration files found in these directories, that are named same as a plugin, are parsed. The default contains ``/etc/dnf/plugins`` path.

  .. attribute:: pluginpath

    List of directories where DNF searches for :doc:`plugins <api_plugins>`. The default contains a Python version-specific path.

  .. attribute:: proxy

    URL of of a proxy server to use for network connections. Defaults to ``None``, i.e. no proxy used. The expected format of this option is::

      <scheme>://<ip-or-hostname>[:port]

  .. attribute:: protected_packages

    List of packages that DNF should never completely remove. They are protected via Obsoletes as well as user/plugin removals.

  .. attribute:: proxy_username

    The username to use for connecting to the proxy server. Defaults to ``None``.

  .. attribute:: proxy_password

    The password to use for connecting to the proxy server. Defaults to ``None``.

  .. attribute:: releasever

    Used for substitution of ``$releasever`` in the repository configuration.

  .. attribute:: reposdir

    List of directories to search for repo configuration files. Has a reasonable default commonly used on the given distribution.

  .. attribute:: retries

    Number of times any attempt to retrieve a file should retry before returning an error. Setting this to `0' makes it try forever. Defaults to `10'.

  .. attribute:: sslcacert

    Path to the directory or file containing the certificate authorities to verify SSL certificates.
    Defaults to None - uses system default.

  .. attribute:: sslverify

    Whether SSL certificate checking should be performed at all. Defaults to ``True``.

  .. attribute:: sslclientcert

    Path to the SSL client certificate used to connect to remote sites.
    Defaults to None.

  .. attribute:: sslclientkey

    Path to the SSL client key used to connect to remote sites.
    Defaults to None.

  .. attribute:: substitutions

    A mapping of substitutions used in repositories' remote URL configuration. The commonly used ones are:

    ==========     ============================================== ============
    key            meaning                                        default
    ==========     ============================================== ============
    arch           architecture of the machine                    autodetected
    basearch       the architecture family of the current "arch"  autodetected
    releasever     release name of the system distribution        ``None``
    ==========     ============================================== ============

    :func:`dnf.rpm.detect_releasever` can be used to detect the ``releasever`` value.

    Following example shows recommended method how to override autodetected architectures::

        import dnf
        import dnf.arch

        base = dnf.Base()
        base.conf.substitutions['arch'] = arch
        base.conf.substitutions['basearch'] = dnf.rpm.basearch(arch)
        base.fill_sack()
        ...


  .. attribute:: tsflags

    List of strings adding extra flags for the RPM transaction.

    ==========              ===========================
    tsflag                  RPM Transaction Flag
    ==========              ===========================
    noscripts               RPMTRANS_FLAG_NOSCRIPTS
    test                    RPMTRANS_FLAG_TEST
    notriggers              RPMTRANS_FLAG_NOTRIGGERS
    nodocs                  RPMTRANS_FLAG_NODOCS
    justdb                  RPMTRANS_FLAG_JUSTDB
    nocontexts              RPMTRANS_FLAG_NOCONTEXTS
    nocrypto                RPMTRANS_FLAG_NOFILEDIGEST
    ==========              ===========================

    The ``"nocrypto"`` option will also set the ``_RPMVSF_NOSIGNATURES`` and ``_RPMVSF_NODIGESTS`` VS flags.

  .. attribute:: username

    The username to use for connecting to repo with basic HTTP authentication. Defaults to ``None``.

  .. attribute:: upgrade_group_objects_upgrade

    Set this to False to disable the automatic running of ``group upgrade`` when running the ``upgrade`` command. Default is ``True`` (perform the operation).

  .. attribute:: password

    The password to use for connecting to repo with basic HTTP authentication. Defaults to ``None``.

  .. method:: prepend_installroot(option)

    Prefix config option named `option` with :attr:`installroot`.

  .. method:: read(filename=None)

    Read configuration options from the ``main`` section in `filename`. Option values not present there are left at their current values. If `filename` is ``None``, :attr:`config_file_path` is used. Conversely, the configuration path used to load the configuration file that was used is stored into :attr:`config_file_path` before the function returns.

  .. method:: dump()

    Print configuration values, including inherited values.

  .. method:: write_raw_configfile(filename, section_id, substitutions, modify)

    Update or create config file. Where `filename` represents name of config file (.conf or .repo); `section_id`
    represents id of modified section (e.g. main, fedora, updates); `substitutions` represents an instance of
    base.conf.substitutions; `modify` represents dict of modified options.
